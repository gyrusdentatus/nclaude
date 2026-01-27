"""Whoami command implementation - delegates to aqua_bridge."""

from typing import Any, Dict

from ..aqua_bridge import get_session_id, get_project_path


def cmd_whoami() -> Dict[str, Any]:
    """Show current session info.

    Returns:
        Dict with session info
    """
    session_id = get_session_id()
    project_path = get_project_path()

    return {
        "session_id": session_id,
        "project": str(project_path) if project_path else None,
        "base_dir": str(project_path) if project_path else None,
        "log_path": "~/.aqua/global.db",  # Global messaging location
    }
