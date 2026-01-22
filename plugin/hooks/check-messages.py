#!/usr/bin/env python3
"""
PostToolUse hook: Check for new messages and notify (OS notification).
Uses same state tracking as pretool-check.py for consistency.
Does NOT mark as read - just notifies.
"""
import json
import os
import sqlite3
import subprocess
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


def count_new_messages(session_id: str) -> int:
    if not DB_PATH.exists():
        return 0

    last_seen = get_last_seen(session_id)

    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=1.0)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM messages WHERE id > ? AND room = 'nclaude'",
            (last_seen,)
        )
        count = cursor.fetchone()[0] or 0
        conn.close()
        return count
    except sqlite3.Error:
        return 0


def notify(count: int):
    """Send OS notification."""
    if sys.platform == "darwin":
        try:
            subprocess.run([
                "osascript", "-e",
                f'display notification "{count} new message(s) - run /ncheck" with title "nclaude" sound name "Glass"'
            ], capture_output=True, timeout=2)
        except:
            pass


def main():
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    session_id = get_session_id(hook_input)
    count = count_new_messages(session_id)

    if count > 0:
        notify(count)
        print(f"📨 {count} new message(s) - run /ncheck to read")

    sys.exit(0)


if __name__ == "__main__":
    main()
