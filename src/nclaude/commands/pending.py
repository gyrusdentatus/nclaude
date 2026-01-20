"""Pending command implementation."""

from typing import Any, Dict

from ..rooms.base import Room


def cmd_pending(room: Room, session_id: str) -> Dict[str, Any]:
    """Check for pending messages from listen daemon.

    Args:
        room: Room to check
        session_id: Session to check pending for

    Returns:
        Dict with pending messages info
    """
    return room.pending(session_id)
