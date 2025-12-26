#!/usr/bin/env python3
"""nclaude - headless Claude-to-Claude chat

A simple file-based message queue for communication between Claude Code sessions.
No sockets, no pipes, no bullshit.
"""
import fcntl
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(os.environ.get("NCLAUDE_DIR", "/tmp/nclaude"))
LOG = BASE / "messages.log"
LOCK = BASE / ".lock"
SESSIONS = BASE / "sessions"


def init():
    """Initialize workspace"""
    SESSIONS.mkdir(parents=True, exist_ok=True)
    LOG.touch()
    LOCK.touch()
    return {"status": "ok", "path": str(BASE)}


def send(session_id: str, message: str):
    """Send a message (atomic append with flock)"""
    init()
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    line = f"[{ts}] [{session_id}] {message}\n"

    with open(LOCK, "r") as lock_fd:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        with open(LOG, "a") as f:
            f.write(line)
    return {"sent": message, "session": session_id, "timestamp": ts}


def read(session_id: str, all_messages: bool = False):
    """Read new messages since last read"""
    init()
    pointer_file = SESSIONS / session_id

    # Get last read position
    last_line = 0
    if pointer_file.exists() and not all_messages:
        try:
            last_line = int(pointer_file.read_text().strip() or "0")
        except ValueError:
            last_line = 0

    # Read log
    if not LOG.exists():
        return {"messages": [], "new_count": 0, "total": 0}

    lines = LOG.read_text().splitlines()
    new_lines = lines[last_line:]

    # Update pointer
    pointer_file.write_text(str(len(lines)))

    return {
        "messages": new_lines,
        "new_count": len(new_lines),
        "total": len(lines)
    }


def status():
    """Get chat status"""
    if not BASE.exists() or not LOG.exists():
        return {"active": False, "message_count": 0, "sessions": [], "log_path": str(LOG)}

    lines = LOG.read_text().splitlines()
    sessions = []
    if SESSIONS.exists():
        sessions = [f.name for f in SESSIONS.iterdir() if f.is_file()]

    return {
        "active": True,
        "message_count": len(lines),
        "sessions": sessions,
        "log_path": str(LOG)
    }


def clear():
    """Clear all messages and session data"""
    if BASE.exists():
        shutil.rmtree(BASE)
    return {"status": "cleared"}


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: nclaude.py <init|send|read|status|clear> [args]"}))
        sys.exit(1)

    cmd = sys.argv[1]

    try:
        if cmd == "init":
            result = init()
        elif cmd == "send":
            session_id = sys.argv[2] if len(sys.argv) > 2 else "anon"
            message = " ".join(sys.argv[3:]) if len(sys.argv) > 3 else ""
            if not message:
                result = {"error": "No message provided"}
            else:
                result = send(session_id, message)
        elif cmd == "read":
            session_id = sys.argv[2] if len(sys.argv) > 2 else "anon"
            all_msgs = "--all" in sys.argv
            result = read(session_id, all_msgs)
        elif cmd == "status":
            result = status()
        elif cmd == "clear":
            result = clear()
        else:
            result = {"error": f"Unknown command: {cmd}"}
    except Exception as e:
        result = {"error": str(e)}

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
