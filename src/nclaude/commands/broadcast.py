"""Broadcast command implementation."""

from typing import Any, Dict

from ..rooms.base import Room


def cmd_broadcast(room: Room, message: str) -> Dict[str, Any]:
    """Send a BROADCAST message from HUMAN.

    Args:
        room: Room to broadcast to
        message: Message content

    Returns:
        Dict with sent message details
    """
    if not message:
        return {"error": "No message provided"}

    return room.send("HUMAN", message, "BROADCAST")
