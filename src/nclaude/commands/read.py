"""Read command implementation."""

from typing import Any, Dict, Optional

from ..rooms.base import Room


def cmd_read(
    room: Room,
    session_id: str,
    all_messages: bool = False,
    quiet: bool = False,
    limit: Optional[int] = None,
    msg_type: Optional[str] = None,
    for_me: bool = True,
) -> Optional[Dict[str, Any]]:
    """Read messages from the room.

    Args:
        room: Room to read from
        session_id: Reader's session ID
        all_messages: If True, read all messages
        quiet: If True, return None when no new messages
        limit: Maximum messages to return
        msg_type: Filter by message type (TASK, URGENT, etc.)
        for_me: If True, only show messages addressed to me (or broadcast)

    Returns:
        Dict with messages, or None in quiet mode with no messages
    """
    return room.read(session_id, all_messages, quiet, limit, msg_type, for_me=for_me)
