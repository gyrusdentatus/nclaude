#!/usr/bin/env python3
"""
nclaude client - Unix socket client for connecting to nclaude hub

Handles:
- Connection to hub
- Session registration
- Sending messages with @mentions
- Receiving messages in background
- Queueing received messages for Claude to read
"""

import socket
import json
import os
import sys
import threading
import queue
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Callable
import time

# Get base directory (git-aware)
def get_base_dir() -> Path:
    """Get nclaude base directory, git-aware."""
    if custom := os.environ.get("NCLAUDE_DIR"):
        return Path(custom)

    try:
        import subprocess
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True
        )
        repo_name = Path(result.stdout.strip()).name
    except:
        repo_name = "default"

    return Path(f"/tmp/nclaude/{repo_name}")


def get_auto_session_id() -> str:
    """Auto-detect session ID from git context."""
    if custom := os.environ.get("NCLAUDE_ID"):
        return custom

    try:
        import subprocess
        # Get repo name
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True
        )
        repo_name = Path(result.stdout.strip()).name

        # Get branch name
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, check=True
        )
        branch = result.stdout.strip()

        return f"{repo_name}-{branch}"
    except:
        return "claude-default"


BASE = get_base_dir()
SOCKET_PATH = BASE / "hub.sock"
INBOX_PATH = BASE / "inbox"  # Per-session inbox for queued messages


class NClaudeClient:
    """Client for connecting to nclaude hub."""

    def __init__(self, session_id: Optional[str] = None):
        self.session_id = session_id or get_auto_session_id()
        self.sock: Optional[socket.socket] = None
        self.connected = False
        self.receive_thread: Optional[threading.Thread] = None
        self.message_queue: queue.Queue = queue.Queue()
        self.callbacks: list[Callable[[dict], None]] = []
        self._stop_event = threading.Event()

    def connect(self) -> bool:
        """Connect to the hub."""
        if not SOCKET_PATH.exists():
            print(f"[CLIENT] Hub not running (no socket at {SOCKET_PATH})", file=sys.stderr)
            return False

        try:
            self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.sock.connect(str(SOCKET_PATH))
            self.connected = True

            # Register with hub
            self._send({
                "type": "REGISTER",
                "session_id": self.session_id
            })

            # Start receive thread
            self._stop_event.clear()
            self.receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
            self.receive_thread.start()

            # Wait for registration confirmation
            time.sleep(0.1)

            print(f"[CLIENT] Connected as {self.session_id}", file=sys.stderr)
            return True

        except Exception as e:
            print(f"[CLIENT] Connection failed: {e}", file=sys.stderr)
            self.connected = False
            return False

    def disconnect(self):
        """Disconnect from hub."""
        self._stop_event.set()
        self.connected = False

        if self.sock:
            try:
                self.sock.close()
            except:
                pass
            self.sock = None

        if self.receive_thread:
            self.receive_thread.join(timeout=1.0)

        print(f"[CLIENT] Disconnected", file=sys.stderr)

    def send(self, body: str, msg_type: str = "MSG") -> Optional[dict]:
        """Send a message through the hub."""
        if not self.connected:
            print("[CLIENT] Not connected", file=sys.stderr)
            return None

        msg = {
            "type": msg_type,
            "body": body
        }

        self._send(msg)

        # Wait for confirmation (with timeout)
        try:
            for _ in range(10):  # 1 second timeout
                while not self.message_queue.empty():
                    response = self.message_queue.get_nowait()
                    if response.get("type") == "SENT":
                        return response
                time.sleep(0.1)
        except:
            pass

        return {"sent": True, "body": body}

    def receive(self, block: bool = False, timeout: float = None) -> Optional[dict]:
        """Receive a message from the queue."""
        try:
            return self.message_queue.get(block=block, timeout=timeout)
        except queue.Empty:
            return None

    def get_pending(self) -> list[dict]:
        """Get all pending messages."""
        messages = []
        while not self.message_queue.empty():
            try:
                messages.append(self.message_queue.get_nowait())
            except queue.Empty:
                break
        return messages

    def on_message(self, callback: Callable[[dict], None]):
        """Register a callback for incoming messages."""
        self.callbacks.append(callback)

    def list_clients(self) -> list[str]:
        """Get list of connected clients."""
        if not self.connected:
            return []

        self._send({"type": "LIST"})

        # Wait for response
        try:
            for _ in range(10):
                while not self.message_queue.empty():
                    response = self.message_queue.get_nowait()
                    if response.get("type") == "CLIENT_LIST":
                        return response.get("clients", [])
                time.sleep(0.1)
        except:
            pass

        return []

    def _send(self, msg: dict):
        """Send raw message to hub."""
        if not self.sock:
            return

        try:
            data = json.dumps(msg) + '\n'
            self.sock.sendall(data.encode('utf-8'))
        except Exception as e:
            print(f"[CLIENT] Send error: {e}", file=sys.stderr)
            self.connected = False

    def _receive_loop(self):
        """Background thread for receiving messages."""
        buffer = ""

        while not self._stop_event.is_set() and self.connected:
            try:
                self.sock.settimeout(0.5)
                data = self.sock.recv(65536)

                if not data:
                    self.connected = False
                    break

                buffer += data.decode('utf-8')

                # Process complete messages (newline-delimited)
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if line.strip():
                        try:
                            msg = json.loads(line)
                            self._handle_message(msg)
                        except json.JSONDecodeError:
                            pass

            except socket.timeout:
                continue
            except Exception as e:
                if not self._stop_event.is_set():
                    print(f"[CLIENT] Receive error: {e}", file=sys.stderr)
                break

    def _handle_message(self, msg: dict):
        """Handle incoming message."""
        msg_type = msg.get("type", "")

        # Queue for retrieval
        self.message_queue.put(msg)

        # Save to inbox file for persistence
        self._save_to_inbox(msg)

        # Trigger callbacks
        for callback in self.callbacks:
            try:
                callback(msg)
            except Exception as e:
                print(f"[CLIENT] Callback error: {e}", file=sys.stderr)

        # Print notification for non-system messages
        if msg_type not in ("REGISTERED", "SENT", "CLIENT_LIST"):
            sender = msg.get("from", "unknown")
            body = msg.get("body", "")[:50]
            print(f"[CLIENT] Message from {sender}: {body}...", file=sys.stderr)

    def _save_to_inbox(self, msg: dict):
        """Save message to inbox file."""
        inbox_file = INBOX_PATH / f"{self.session_id}.jsonl"
        INBOX_PATH.mkdir(parents=True, exist_ok=True)

        with open(inbox_file, "a") as f:
            f.write(json.dumps(msg) + '\n')


# Singleton client for easy access
_client: Optional[NClaudeClient] = None


def get_client() -> NClaudeClient:
    """Get or create the singleton client."""
    global _client
    if _client is None:
        _client = NClaudeClient()
    return _client


def connect(session_id: Optional[str] = None) -> bool:
    """Connect to hub with optional session ID."""
    global _client
    _client = NClaudeClient(session_id)
    return _client.connect()


def send(body: str, msg_type: str = "MSG") -> Optional[dict]:
    """Send a message."""
    client = get_client()
    if not client.connected:
        if not client.connect():
            return None
    return client.send(body, msg_type)


def receive(block: bool = False) -> Optional[dict]:
    """Receive a message."""
    return get_client().receive(block=block)


def pending() -> list[dict]:
    """Get all pending messages."""
    return get_client().get_pending()


def main():
    """CLI interface for client."""
    if len(sys.argv) < 2:
        print("Usage: client.py <connect|send|receive|list|status>")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "connect":
        session_id = sys.argv[2] if len(sys.argv) > 2 else None
        client = NClaudeClient(session_id)
        if client.connect():
            print(json.dumps({"connected": True, "session_id": client.session_id}))
            # Keep running to receive messages
            try:
                while client.connected:
                    time.sleep(1)
            except KeyboardInterrupt:
                client.disconnect()
        else:
            print(json.dumps({"connected": False, "error": "Failed to connect"}))
            sys.exit(1)

    elif cmd == "send":
        if len(sys.argv) < 3:
            print("Usage: client.py send <message> [--type TYPE]")
            sys.exit(1)

        # Parse args
        msg_type = "MSG"
        body_parts = []
        i = 2
        while i < len(sys.argv):
            if sys.argv[i] == "--type" and i + 1 < len(sys.argv):
                msg_type = sys.argv[i + 1].upper()
                i += 2
            else:
                body_parts.append(sys.argv[i])
                i += 1

        body = " ".join(body_parts)

        result = send(body, msg_type)
        print(json.dumps(result or {"error": "Failed to send"}))

    elif cmd == "receive":
        client = get_client()
        if not client.connected:
            client.connect()

        messages = client.get_pending()
        print(json.dumps({"messages": messages, "count": len(messages)}))

    elif cmd == "list":
        client = get_client()
        if not client.connected:
            client.connect()

        clients = client.list_clients()
        print(json.dumps({"clients": clients}))

    elif cmd == "status":
        if SOCKET_PATH.exists():
            client = NClaudeClient()
            if client.connect():
                clients = client.list_clients()
                print(json.dumps({
                    "hub": "running",
                    "socket": str(SOCKET_PATH),
                    "clients": clients
                }))
                client.disconnect()
            else:
                print(json.dumps({"hub": "error", "socket": str(SOCKET_PATH)}))
        else:
            print(json.dumps({"hub": "not_running"}))

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
