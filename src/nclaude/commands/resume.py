"""Wake/resume command implementation."""

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from ..config import resolve_alias
from ..storage.sqlite import SQLiteStorage, GLOBAL_DB_PATH


def cmd_wake(
    target: str,
    method: str = "auto",
    message: Optional[str] = None,
) -> Dict[str, Any]:
    """Wake a peer session with their saved context.

    Args:
        target: Session alias or ID (e.g., "@k8s" or "cc-abc123")
        method: Wake method - "auto", "tmux", "terminal", "iterm", or "info"
        message: Optional message to include in wake

    Returns:
        Dict with wake result or session info
    """
    # Resolve alias
    session_id = target.lstrip("@")
    resolved = resolve_alias(session_id)
    if resolved:
        session_id = resolved

    # Get session metadata
    storage = SQLiteStorage(Path.cwd())
    metadata = storage.get_session_metadata(session_id)

    if not metadata:
        return {
            "error": f"No saved state for {target}",
            "hint": "Session must have been active with PreCompact hook to have saved state"
        }

    project_dir = metadata.get("project_dir", "")
    task_summary = metadata.get("task_summary", "")
    claimed_files = metadata.get("claimed_files", [])
    updated_at = metadata.get("updated_at", "")

    # Build resume command
    resume_cmd = f"cd {project_dir} && claude --resume"

    # Info-only mode
    if method == "info":
        return {
            "session_id": session_id,
            "metadata": metadata,
            "resume_command": resume_cmd,
        }

    # Try to wake the session
    wake_result = _try_wake(
        session_id=session_id,
        project_dir=project_dir,
        resume_cmd=resume_cmd,
        method=method,
        message=message,
        task_summary=task_summary,
    )

    return wake_result


def _try_wake(
    session_id: str,
    project_dir: str,
    resume_cmd: str,
    method: str,
    message: Optional[str],
    task_summary: str,
) -> Dict[str, Any]:
    """Attempt to wake session using specified method."""

    # Try tmux first (if available and method allows)
    if method in ("auto", "tmux") and shutil.which("tmux"):
        # Check if tmux server is running
        check = subprocess.run(
            ["tmux", "list-sessions"],
            capture_output=True,
            text=True,
        )
        if check.returncode == 0:
            # tmux is running, create new window
            window_name = f"claude-{session_id[:8]}"
            result = subprocess.run(
                ["tmux", "new-window", "-n", window_name, resume_cmd],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return {
                    "woke": True,
                    "method": "tmux",
                    "session": session_id,
                    "window": window_name,
                    "task_summary": task_summary,
                }

    # macOS Terminal.app
    if method in ("auto", "terminal") and sys.platform == "darwin":
        script = f'''
        tell application "Terminal"
            do script "{resume_cmd}"
            activate
        end tell
        '''
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return {
                "woke": True,
                "method": "terminal",
                "session": session_id,
                "task_summary": task_summary,
            }

    # macOS iTerm
    if method == "iterm" and sys.platform == "darwin":
        script = f'''
        tell application "iTerm"
            create window with default profile
            tell current session of current window
                write text "{resume_cmd}"
            end tell
        end tell
        '''
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return {
                "woke": True,
                "method": "iterm",
                "session": session_id,
                "task_summary": task_summary,
            }

    # No method worked
    return {
        "error": "No wake method available",
        "session": session_id,
        "resume_command": resume_cmd,
        "hint": "Copy the resume_command and run manually",
    }


def cmd_sessions() -> Dict[str, Any]:
    """List all saved session metadata.

    Returns:
        Dict with list of sessions
    """
    storage = SQLiteStorage(Path.cwd())
    sessions = storage.list_session_metadata()

    if not sessions:
        return {
            "sessions": [],
            "message": "No saved sessions. Sessions are saved by PreCompact hook."
        }

    return {"sessions": sessions}
