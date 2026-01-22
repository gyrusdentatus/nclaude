"""Send command implementation."""

import re
from typing import Any, Dict, Optional, Tuple

from ..config import resolve_recipient
from ..rooms.base import Room


def parse_recipient(
    message: str,
    explicit_to: Optional[str] = None,
    room_name: Optional[str] = None,
) -> Tuple[str, Optional[str]]:
    """Extract @mention from message start or use explicit --to flag.

    Args:
        message: Raw message content
        explicit_to: Explicit recipient from --to flag
        room_name: Room name for @room/@peers resolution

    Returns:
        Tuple of (cleaned_message, resolved_recipient)
    """
    # Explicit --to flag takes precedence
    if explicit_to:
        # Strip leading @ if present
        target = explicit_to.lstrip("@")
        return message, resolve_recipient(target, room_name)

    # Parse @mention from message start
    # Matches: @name, @nclaude/branch, @some-session-id, @a,@b (multi)
    match = re.match(r'^@([\w/.,@-]+)\s+', message)
    if match:
        target = match.group(1)
        cleaned_message = message[match.end():]
        return cleaned_message, resolve_recipient(target, room_name)

    return message, None


def cmd_send(
    room: Room,
    session_id: str,
    message: str,
    msg_type: str = "MSG",
    to: Optional[str] = None,
) -> Dict[str, Any]:
    """Send a message to the room.

    Args:
        room: Room to send to
        session_id: Sender's session ID
        message: Message content
        msg_type: Message type (MSG, TASK, REPLY, STATUS, URGENT, ERROR)
        to: Optional explicit recipient (--to flag)

    Returns:
        Dict with sent message details
    """
    if not message:
        return {"error": "No message provided"}

    # Parse @mention and resolve recipient (pass room name for @room/@peers)
    cleaned_message, recipient = parse_recipient(message, to, room_name=room.name)

    return room.send(session_id, cleaned_message, msg_type, recipient=recipient)
