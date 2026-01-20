"""Check command implementation."""

from typing import Any, Dict

from ..rooms.base import Room


def cmd_check(room: Room, session_id: str, for_me: bool = False) -> Dict[str, Any]:
    """Combined pending + read - one-stop "catch me up" command.

    Args:
        room: Room to check
        session_id: Session to check for
        for_me: If True, only show messages addressed to me (or broadcast)

    Returns:
        Dict with pending and new messages
    """
    return room.check(session_id, for_me=for_me)
