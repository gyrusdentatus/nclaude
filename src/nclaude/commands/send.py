"""Send command implementation - delegates to aqua_bridge."""

import re
from typing import Any, Dict, Optional, Tuple

from ..aqua_bridge import send_message, resolve_alias


def parse_recipient(
    message: str,
    explicit_to: Optional[str] = None,
) -> Tuple[str, Optional[str]]:
    """Extract @mention from message start or use explicit --to flag.

    Args:
        message: Raw message content
        explicit_to: Explicit recipient from --to flag

    Returns:
        Tuple of (cleaned_message, resolved_recipient)
    """
    # Explicit --to flag takes precedence
    if explicit_to:
        target = explicit_to.lstrip("@")
        return message, resolve_alias(target)

    # Parse @mention from message start
    # Matches: @name, @nclaude/branch, @some-session-id, @a,@b (multi)
    match = re.match(r'^@([\w/.,@-]+)\s+', message)
    if match:
        target = match.group(1)
        cleaned_message = message[match.end():]
        return cleaned_message, resolve_alias(target)

    return message, None


def cmd_send(
    message: str,
    msg_type: str = "MSG",
    to: Optional[str] = None,
    global_: bool = False,
) -> Dict[str, Any]:
    """Send a message.

    Args:
        message: Message content
        msg_type: Message type (MSG, TASK, REPLY, STATUS, URGENT, ERROR)
        to: Optional explicit recipient (--to flag)
        global_: If True, send to global room

    Returns:
        Dict with sent message details
    """
    if not message:
        return {"error": "No message provided"}

    # Parse @mention and resolve recipient
    cleaned_message, recipient = parse_recipient(message, to)

    # Map MSG type to aqua message_type
    type_map = {
        "MSG": "chat",
        "TASK": "task",
        "REPLY": "reply",
        "STATUS": "status",
        "URGENT": "urgent",
        "ERROR": "error",
        "BROADCAST": "broadcast",
    }
    message_type = type_map.get(msg_type.upper(), "chat")

    return send_message(
        content=cleaned_message,
        to=recipient,
        message_type=message_type,
        global_=global_,
    )
