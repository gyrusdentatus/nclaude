"""Read command implementation - delegates to aqua_bridge."""

from typing import Any, Dict, Optional

from ..aqua_bridge import read_messages, get_session_id


def cmd_read(
    all_messages: bool = False,
    quiet: bool = False,
    limit: Optional[int] = None,
    msg_type: Optional[str] = None,
    for_me: bool = True,
    global_: bool = False,
) -> Optional[Dict[str, Any]]:
    """Read messages.

    Args:
        all_messages: If True, read all messages (not just unread)
        quiet: If True, return None when no new messages
        limit: Maximum messages to return
        msg_type: Filter by message type (TASK, URGENT, etc.)
        for_me: If True, only show messages addressed to me (or broadcast)
        global_: If True, read from global room

    Returns:
        Dict with messages, or None in quiet mode with no messages
    """
    messages = read_messages(
        unread_only=not all_messages,
        limit=limit or 50,
        global_=global_,
    )

    # Filter by type if requested
    if msg_type:
        type_lower = msg_type.lower()
        messages = [m for m in messages if m.get("type", "").lower() == type_lower]

    # Filter for_me if requested
    if for_me:
        session_id = get_session_id()
        messages = [
            m for m in messages
            if m.get("to") is None or m.get("to") == session_id
        ]

    if quiet and not messages:
        return None

    # Format for display
    formatted = []
    for m in messages:
        created = m.get("created_at", "")
        if created:
            created = created.split("T")[-1][:8] if "T" in created else created

        formatted.append(f"[{created}] [{m.get('from', 'unknown')}] {m.get('content', '')}")

    return {
        "messages": formatted,
        "count": len(messages),
        "raw": messages,  # Include raw data for programmatic access
    }
