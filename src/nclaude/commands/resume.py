"""Wake/resume command implementation."""

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from ..aqua_bridge import resolve_alias, get_project_db


def cmd_wake(
    target: str,
    method: str = "auto",
    message: Optional[str] = None,
) -> Dict[str, Any]:
    """Wake a peer session with their saved context.

    Args:
        target: Session alias or ID (e.g., "@k8s" or "nclaude/main-1")
        method: Wake method - "auto", "tmux", "terminal", "iterm", or "info"
        message: Optional message to include in wake

    Returns:
        Dict with wake result or session info
    """
    # Resolve alias
    session_id = target.lstrip("@")
    resolved = resolve_alias(session_id)
    if resolved and resolved != session_id:
        session_id = resolved

    # Try to get agent info from aqua
    db = get_project_db()
    agent = None
    if db:
        agent = db.get_agent_by_name(session_id) or db.get_agent(session_id)

    if not agent:
        return {
            "error": f"No saved state for {target}",
            "hint": "Agent must be registered with aqua to have state"
        }

    project_dir = str(Path.cwd())  # Use current project
    task_summary = agent.metadata.get("last_task", "") if agent.metadata else ""

    # Build resume command
    resume_cmd = f"cd {project_dir} && claude --resume"

    # Info-only mode
    if method == "info":
        return {
            "session_id": session_id,
            "agent_name": agent.name,
            "status": agent.status.value,
            "current_task": agent.current_task_id,
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
    """List all registered agents in the project.

    Returns:
        Dict with list of agents
    """
    db = get_project_db()
    if not db:
        return {
            "sessions": [],
            "message": "Aqua not initialized. Run 'aqua init' to enable agent tracking."
        }

    agents = db.get_all_agents()
    sessions = [
        {
            "id": a.id,
            "name": a.name,
            "status": a.status.value,
            "current_task": a.current_task_id,
            "last_heartbeat": a.last_heartbeat_at.isoformat() if a.last_heartbeat_at else None,
        }
        for a in agents
    ]

    if not sessions:
        return {
            "sessions": [],
            "message": "No agents registered. Run 'aqua join' to register."
        }

    return {"sessions": sessions}
