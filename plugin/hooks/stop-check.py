#!/usr/bin/env python3
"""
Stop hook: Block Claude from stopping if unread nclaude messages exist.
Uses same state tracking as pretool-check.py for consistency.
"""
import json
import os
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path.home() / ".nclaude" / "messages.db"
STATE_DIR = Path("/tmp/nclaude-state")


def get_session_id(hook_input: dict) -> str:
    cc_session = hook_input.get("session_id", "")
    if cc_session:
        return f"cc-{cc_session[:12]}"
    return os.environ.get("NCLAUDE_ID", "default")


def get_last_seen(session_id: str) -> int:
    STATE_DIR.mkdir(exist_ok=True)
    state_file = STATE_DIR / f"{session_id}.seen"
    try:
        return int(state_file.read_text().strip())
    except (FileNotFoundError, ValueError):
        return 0


def check_new_messages(session_id: str) -> tuple[int, list[str]]:
    if not DB_PATH.exists():
        return 0, []

    last_seen = get_last_seen(session_id)

    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=1.0)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Count new messages (exclude self-sent)
        cursor.execute(
            "SELECT COUNT(*) FROM messages WHERE id > ? AND room = 'nclaude' AND session_id != ?",
            (last_seen, session_id)
        )
        count = cursor.fetchone()[0] or 0

        if count == 0:
            conn.close()
            return 0, []

        # Fetch recent messages for display (exclude self-sent)
        cursor.execute(
            """SELECT session_id, msg_type, content, recipient
               FROM messages
               WHERE id > ? AND room = 'nclaude' AND session_id != ?
               ORDER BY id DESC LIMIT 5""",
            (last_seen, session_id)
        )

        messages = []
        for row in cursor.fetchall():
            sender = row["session_id"]
            msg_type = row["msg_type"]
            content = row["content"][:150]
            prefix = f"[{sender}]"
            if msg_type != "MSG":
                prefix += f" [{msg_type}]"
            messages.append(f"{prefix} {content}")

        conn.close()
        return count, messages

    except sqlite3.Error:
        return 0, []


def main():
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    session_id = get_session_id(hook_input)
    count, messages = check_new_messages(session_id)

    if count == 0:
        # No messages - allow stop (output nothing)
        sys.exit(0)

    # Block the stop
    msg_preview = "\n".join(messages)
    output = {
        "decision": "block",
        "reason": f"STOP BLOCKED: {count} unread nclaude message(s). Run /ncheck to read:\n{msg_preview}"
    }
    print(json.dumps(output))
    sys.exit(0)


if __name__ == "__main__":
    main()
