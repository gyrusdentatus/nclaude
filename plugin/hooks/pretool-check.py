#!/usr/bin/env python3
"""
Fast PreToolUse hook for nclaude message checking.
Queries SQLite directly for speed - no subprocess spawning.
"""
import json
import os
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path.home() / ".nclaude" / "messages.db"
STATE_DIR = Path("/tmp/nclaude-state")


def get_session_id(hook_input: dict) -> str:
    """Extract session ID from hook input or environment."""
    # Try Claude Code's session_id first
    cc_session = hook_input.get("session_id", "")
    if cc_session:
        return f"cc-{cc_session[:12]}"

    # Fall back to env var
    return os.environ.get("NCLAUDE_ID", "default")


def get_last_seen(session_id: str) -> int:
    """Get last seen message ID for this session."""
    STATE_DIR.mkdir(exist_ok=True)
    state_file = STATE_DIR / f"{session_id}.seen"
    try:
        return int(state_file.read_text().strip())
    except (FileNotFoundError, ValueError):
        return 0


def set_last_seen(session_id: str, msg_id: int):
    """Update last seen message ID."""
    STATE_DIR.mkdir(exist_ok=True)
    state_file = STATE_DIR / f"{session_id}.seen"
    state_file.write_text(str(msg_id))


def check_new_messages(session_id: str) -> tuple[int, int, list[str]]:
    """
    Fast check for new messages.
    Returns: (new_count, max_id, messages)
    """
    if not DB_PATH.exists():
        return 0, 0, []

    last_seen = get_last_seen(session_id)

    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=1.0)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Fast count check first (exclude self-sent messages)
        cursor.execute(
            "SELECT COUNT(*), MAX(id) FROM messages WHERE id > ? AND room = 'nclaude' AND session_id != ?",
            (last_seen, session_id)
        )
        row = cursor.fetchone()
        count = row[0] or 0
        max_id = row[1] or last_seen

        if count == 0:
            conn.close()
            return 0, max_id, []

        # Only fetch the 2 most recent new messages (save tokens, exclude self-sent)
        cursor.execute(
            """SELECT id, timestamp, session_id, msg_type, content, recipient
               FROM messages
               WHERE id > ? AND room = 'nclaude' AND session_id != ?
               ORDER BY id DESC LIMIT 2""",
            (last_seen, session_id)
        )

        messages = []
        for row in cursor.fetchall():
            sender = row["session_id"]
            msg_type = row["msg_type"]
            content = row["content"]
            recipient = row["recipient"]

            # Format message
            prefix = f"[{sender}]"
            if msg_type != "MSG":
                prefix += f" [{msg_type}]"
            if recipient:
                prefix += f" @{recipient}"

            messages.append(f"{prefix} {content[:100]}")

        conn.close()
        return count, max_id, messages

    except sqlite3.Error:
        return 0, 0, []


def main():
    # Read hook input
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)  # Invalid input, allow tool to proceed

    session_id = get_session_id(hook_input)

    # Fast check
    count, max_id, messages = check_new_messages(session_id)

    if count == 0:
        # No new messages - exit fast, allow tool
        sys.exit(0)

    # Update last seen (mark as read)
    set_last_seen(session_id, max_id)

    # Inject messages as context (short format)
    if count > 2:
        context = f"📨 nclaude: {count} new ({len(messages)} shown):\n" + "\n".join(messages)
    else:
        context = f"📨 nclaude:\n" + "\n".join(messages)

    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": context
        }
    }

    print(json.dumps(output))
    sys.exit(0)


if __name__ == "__main__":
    main()
