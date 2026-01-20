"""Clear command implementation."""

from typing import Any, Dict

from ..rooms.base import Room


def cmd_clear(room: Room) -> Dict[str, Any]:
    """Clear all messages and session data.

    Args:
        room: Room to clear

    Returns:
        Dict with status
    """
    return room.clear()
