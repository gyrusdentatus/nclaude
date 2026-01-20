"""Send command implementation."""

from typing import Any, Dict

from ..rooms.base import Room


def cmd_send(
    room: Room,
    session_id: str,
    message: str,
    msg_type: str = "MSG",
) -> Dict[str, Any]:
    """Send a message to the room.

    Args:
        room: Room to send to
        session_id: Sender's session ID
        message: Message content
        msg_type: Message type (MSG, TASK, REPLY, STATUS, URGENT, ERROR)

    Returns:
        Dict with sent message details
    """
    if not message:
        return {"error": "No message provided"}

    return room.send(session_id, message, msg_type)
