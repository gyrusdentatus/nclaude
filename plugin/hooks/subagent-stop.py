#!/usr/bin/env python3
"""
SubagentStop hook: Announce subagent completion to nclaude room.

When a Task subagent completes, sends STATUS message with:
- Completion reason
- Modified files (from git diff)
"""
import json
import os
import subprocess
import sys
from pathlib import Path


def get_session_id(hook_input: dict) -> str:
    cc_session = hook_input.get("session_id", "")
    if cc_session:
        return f"cc-{cc_session[:12]}"
    return os.environ.get("NCLAUDE_ID", "default")


def get_modified_files() -> list[str]:
    """Get files modified in last commit via git diff."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD~1"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            files = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
            return files[:10]  # Limit to 10 files
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # Fallback: check staged files
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "--cached"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            files = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
            return files[:10]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return []


def send_status_message(message: str) -> bool:
    """Send STATUS message via nclaude."""
    try:
        result = subprocess.run(
            ["nclaude", "send", message, "--type", "STATUS"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def main():
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    session_id = get_session_id(hook_input)
    reason = hook_input.get("reason", "completed")
    subagent_type = hook_input.get("subagent_type", "unknown")

    # Get modified files
    files = get_modified_files()

    # Build status message
    msg_parts = [f"SUBAGENT [{subagent_type}] {reason}"]

    if files:
        files_str = ", ".join(files[:5])
        if len(files) > 5:
            files_str += f" (+{len(files) - 5} more)"
        msg_parts.append(f"Modified: {files_str}")

    message = " | ".join(msg_parts)

    # Send notification
    send_status_message(message)

    sys.exit(0)


if __name__ == "__main__":
    main()
