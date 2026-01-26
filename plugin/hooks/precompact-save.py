#!/usr/bin/env python3
"""
PreCompact hook: Save session state before context compaction.

Extracts from transcript:
- Current working directory
- Task summary (what user is working on)
- Claimed files (from CLAIMING: protocol without RELEASED:)
- Last activity timestamp

This enables session resume and peer handoff.
"""
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path.home() / ".nclaude" / "messages.db"


def get_session_id(hook_input: dict) -> str:
    cc_session = hook_input.get("session_id", "")
    if cc_session:
        return f"cc-{cc_session[:12]}"
    return os.environ.get("NCLAUDE_ID", "default")


def extract_task_summary(transcript: str) -> str:
    """Extract what user is working on from transcript."""
    patterns = [
        r"(?:working on|implementing|fixing|building|creating|adding)[:\s]+([^\n]{10,100})",
        r"(?:task|goal|objective)[:\s]+([^\n]{10,100})",
        r"(?:let me|I'll|I will)[:\s]+([^\n]{10,100})",
    ]

    for pattern in patterns:
        match = re.search(pattern, transcript, re.IGNORECASE)
        if match:
            return match.group(1).strip()[:200]

    return ""


def extract_claimed_files(transcript: str) -> list[str]:
    """Extract files that were claimed but not released."""
    claims = set(re.findall(r"CLAIMING:\s*(\S+)", transcript, re.IGNORECASE))
    releases = set(re.findall(r"RELEASED:\s*(\S+)", transcript, re.IGNORECASE))
    return list(claims - releases)


def extract_pending_work(transcript: str) -> list[str]:
    """Extract TODO items or pending work from transcript."""
    pending = []

    # Look for TODO comments
    todos = re.findall(r"TODO[:\s]+([^\n]{5,100})", transcript, re.IGNORECASE)
    pending.extend(todos[:5])

    # Look for "need to" or "should" patterns
    needs = re.findall(r"(?:need to|should|must)[:\s]+([^\n]{5,100})", transcript, re.IGNORECASE)
    pending.extend(needs[:3])

    return pending[:5]  # Limit to 5 items


def save_metadata(session_id: str, metadata: dict) -> bool:
    """Save session metadata to database."""
    if not DB_PATH.exists():
        return False

    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=2.0)
        conn.execute(
            """
            INSERT OR REPLACE INTO session_metadata
            (session_id, project_dir, last_activity, task_summary, claimed_files, pending_work, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                metadata.get("project_dir", ""),
                metadata.get("last_activity", ""),
                metadata.get("task_summary", ""),
                json.dumps(metadata.get("claimed_files", [])),
                json.dumps(metadata.get("pending_work", [])),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.Error:
        return False


def main():
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    session_id = get_session_id(hook_input)
    transcript = hook_input.get("transcript_summary", "") or hook_input.get("transcript", "")

    # Get working directory from hook input or environment
    project_dir = hook_input.get("cwd", "") or os.getcwd()

    metadata = {
        "project_dir": project_dir,
        "last_activity": datetime.now(timezone.utc).isoformat(),
        "task_summary": extract_task_summary(transcript),
        "claimed_files": extract_claimed_files(transcript),
        "pending_work": extract_pending_work(transcript),
    }

    if save_metadata(session_id, metadata):
        # Output success message for logging
        output = {
            "systemMessage": f"Session state saved for {session_id}"
        }
        print(json.dumps(output))

    sys.exit(0)


if __name__ == "__main__":
    main()
