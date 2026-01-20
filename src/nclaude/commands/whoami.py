"""Whoami command implementation."""

from typing import Any, Dict

from ..rooms.base import Room


def cmd_whoami(room: Room, session_id: str) -> Dict[str, Any]:
    """Show current session info.

    Args:
        room: Current room
        session_id: Current session ID

    Returns:
        Dict with session info
    """
    return {
        "session_id": session_id,
        "base_dir": str(room.path),
        "log_path": str(room.storage.log_path),
    }
