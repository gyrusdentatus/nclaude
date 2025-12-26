#!/usr/bin/env python3
"""
nclaude hub - Unix socket server for real-time Claude-to-Claude chat

Handles:
- Client connections/disconnections
- @mention parsing and routing
- Broadcast for non-mentioned messages
- Message persistence to log file (fallback compatibility)
"""

import socket
import select
import json
import os
import re
import sys
import signal
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Set, Optional
import uuid

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


BASE = get_base_dir()
SOCKET_PATH = BASE / "hub.sock"
LOG_PATH = BASE / "messages.log"
PID_FILE = BASE / "hub.pid"


class NClaudeHub:
    """Unix socket server for nclaude message routing."""

    def __init__(self):
        self.clients: Dict[str, socket.socket] = {}  # session_id -> socket
        self.sockets: Dict[socket.socket, str] = {}  # socket -> session_id
        self.server: Optional[socket.socket] = None
        self.running = False
        self.lock = threading.Lock()

    def start(self):
        """Start the hub server."""
        # Ensure base directory exists
        BASE.mkdir(parents=True, exist_ok=True)

        # Remove stale socket
        if SOCKET_PATH.exists():
            SOCKET_PATH.unlink()

        # Create Unix socket
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind(str(SOCKET_PATH))
        self.server.listen(50)  # Support up to 50 concurrent clients
        self.server.setblocking(False)

        # Write PID file
        PID_FILE.write_text(str(os.getpid()))

        self.running = True
        print(f"[HUB] Started on {SOCKET_PATH}", file=sys.stderr)
        print(f"[HUB] PID: {os.getpid()}", file=sys.stderr)

        self._run_loop()

    def stop(self):
        """Stop the hub server."""
        self.running = False

        # Close all client connections
        with self.lock:
            for sock in list(self.sockets.keys()):
                try:
                    sock.close()
                except:
                    pass
            self.clients.clear()
            self.sockets.clear()

        # Close server socket
        if self.server:
            self.server.close()

        # Cleanup files
        if SOCKET_PATH.exists():
            SOCKET_PATH.unlink()
        if PID_FILE.exists():
            PID_FILE.unlink()

        print("[HUB] Stopped", file=sys.stderr)

    def _run_loop(self):
        """Main event loop using select."""
        while self.running:
            try:
                # Build list of sockets to monitor
                read_sockets = [self.server] + list(self.sockets.keys())

                readable, _, _ = select.select(read_sockets, [], [], 1.0)

                for sock in readable:
                    if sock is self.server:
                        self._handle_new_connection()
                    else:
                        self._handle_client_data(sock)

            except Exception as e:
                if self.running:
                    print(f"[HUB] Loop error: {e}", file=sys.stderr)

    def _handle_new_connection(self):
        """Accept new client connection."""
        try:
            client_sock, _ = self.server.accept()
            client_sock.setblocking(False)

            # Client must send REGISTER message first
            # For now, add to pending (no session_id yet)
            with self.lock:
                self.sockets[client_sock] = None  # Pending registration

            print(f"[HUB] New connection (pending registration)", file=sys.stderr)

        except Exception as e:
            print(f"[HUB] Connection error: {e}", file=sys.stderr)

    def _handle_client_data(self, sock: socket.socket):
        """Handle data from a client."""
        try:
            data = sock.recv(65536)

            if not data:
                # Client disconnected
                self._disconnect_client(sock)
                return

            # Parse message (newline-delimited JSON)
            for line in data.decode('utf-8').strip().split('\n'):
                if not line:
                    continue

                try:
                    msg = json.loads(line)
                    self._process_message(sock, msg)
                except json.JSONDecodeError as e:
                    print(f"[HUB] Invalid JSON: {e}", file=sys.stderr)

        except ConnectionResetError:
            self._disconnect_client(sock)
        except Exception as e:
            print(f"[HUB] Client data error: {e}", file=sys.stderr)
            self._disconnect_client(sock)

    def _disconnect_client(self, sock: socket.socket):
        """Handle client disconnection."""
        with self.lock:
            session_id = self.sockets.pop(sock, None)
            if session_id:
                self.clients.pop(session_id, None)
                print(f"[HUB] Client disconnected: {session_id}", file=sys.stderr)

            try:
                sock.close()
            except:
                pass

    def _process_message(self, sock: socket.socket, msg: dict):
        """Process a message from a client."""
        msg_type = msg.get("type", "MSG")

        if msg_type == "REGISTER":
            # Client registering their session ID
            session_id = msg.get("session_id")
            if session_id:
                with self.lock:
                    self.sockets[sock] = session_id
                    self.clients[session_id] = sock

                print(f"[HUB] Registered: {session_id}", file=sys.stderr)

                # Send confirmation
                self._send_to_socket(sock, {
                    "type": "REGISTERED",
                    "session_id": session_id,
                    "clients": list(self.clients.keys())
                })

        elif msg_type in ("MSG", "TASK", "REPLY", "STATUS", "ERROR", "URGENT"):
            # Regular message - route based on @mentions
            self._route_message(sock, msg)

        elif msg_type == "LIST":
            # List connected clients
            with self.lock:
                clients = list(self.clients.keys())
            self._send_to_socket(sock, {
                "type": "CLIENT_LIST",
                "clients": clients
            })

    def _route_message(self, sender_sock: socket.socket, msg: dict):
        """Route message to recipients based on @mentions."""
        body = msg.get("body", "")
        sender_id = self.sockets.get(sender_sock, "unknown")

        # Parse @mentions
        mentions = set(re.findall(r'@([\w-]+)', body))

        # Build message with metadata
        full_msg = {
            "id": str(uuid.uuid4())[:8],
            "from": sender_id,
            "type": msg.get("type", "MSG"),
            "body": body,
            "mentions": list(mentions),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        # Log to file (for fallback/history)
        self._log_message(full_msg)

        # Route to recipients
        with self.lock:
            if mentions:
                # Send only to mentioned clients
                for mention in mentions:
                    if mention in self.clients:
                        self._send_to_socket(self.clients[mention], full_msg)

                # Also send to sender (confirmation)
                self._send_to_socket(sender_sock, {
                    "type": "SENT",
                    "id": full_msg["id"],
                    "routed_to": [m for m in mentions if m in self.clients]
                })
            else:
                # Broadcast to all (except sender)
                for session_id, client_sock in self.clients.items():
                    if client_sock != sender_sock:
                        self._send_to_socket(client_sock, full_msg)

                # Confirm to sender
                self._send_to_socket(sender_sock, {
                    "type": "SENT",
                    "id": full_msg["id"],
                    "broadcast": True
                })

    def _send_to_socket(self, sock: socket.socket, msg: dict):
        """Send JSON message to a socket."""
        try:
            data = json.dumps(msg) + '\n'
            sock.sendall(data.encode('utf-8'))
        except Exception as e:
            print(f"[HUB] Send error: {e}", file=sys.stderr)
            self._disconnect_client(sock)

    def _log_message(self, msg: dict):
        """Log message to file for persistence/fallback."""
        ts = msg.get("timestamp", datetime.now(timezone.utc).isoformat())
        sender = msg.get("from", "unknown")
        msg_type = msg.get("type", "MSG")
        body = msg.get("body", "")

        # Use same format as nclaude.py for compatibility
        if "\n" in body:
            line = f"<<<[{ts}][{sender}][{msg_type}]>>>\n{body}\n<<<END>>>\n"
        else:
            if msg_type != "MSG":
                line = f"[{ts}] [{sender}] [{msg_type}] {body}\n"
            else:
                line = f"[{ts}] [{sender}] {body}\n"

        # Append to log (atomic-ish)
        with open(LOG_PATH, "a") as f:
            f.write(line)


def main():
    if len(sys.argv) < 2:
        print("Usage: hub.py <start|stop|status>")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "start":
        # Check if already running
        if PID_FILE.exists():
            pid = int(PID_FILE.read_text().strip())
            try:
                os.kill(pid, 0)  # Check if process exists
                print(f"[HUB] Already running (PID: {pid})")
                sys.exit(1)
            except OSError:
                # Stale PID file
                PID_FILE.unlink()

        hub = NClaudeHub()

        # Handle signals
        def signal_handler(sig, frame):
            hub.stop()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        hub.start()

    elif cmd == "stop":
        if PID_FILE.exists():
            pid = int(PID_FILE.read_text().strip())
            try:
                os.kill(pid, signal.SIGTERM)
                print(f"[HUB] Stopped (PID: {pid})")
            except OSError:
                print("[HUB] Not running (stale PID file)")
                PID_FILE.unlink()
        else:
            print("[HUB] Not running")

    elif cmd == "status":
        if PID_FILE.exists():
            pid = int(PID_FILE.read_text().strip())
            try:
                os.kill(pid, 0)
                print(f"[HUB] Running (PID: {pid})")
                print(f"[HUB] Socket: {SOCKET_PATH}")
            except OSError:
                print("[HUB] Not running (stale PID file)")
        else:
            print("[HUB] Not running")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
