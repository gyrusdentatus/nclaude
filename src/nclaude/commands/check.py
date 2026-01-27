"""Check command implementation - delegates to aqua_bridge."""

from typing import Any, Dict

from ..aqua_bridge import read_messages, get_session_id


def cmd_check(
    for_me: bool = False,
    global_: bool = False,
) -> Dict[str, Any]:
    """Get all unread messages - "catch me up" command.

    Args:
        for_me: If True, only show messages addressed to me (or broadcast)
        global_: If True, check global room

    Returns:
        Dict with message list and counts
    """
    messages = read_messages(unread_only=True, global_=global_)

    # Filter for_me if requested
    if for_me:
        session_id = get_session_id()
        messages = [
            m for m in messages
            if m.get("to") is None or m.get("to") == session_id
        ]

    # Format for display
    formatted = []
    for m in messages:
        # Format: [timestamp] [from] content
        created = m.get("created_at", "")
        if created:
            # Just show time part
            created = created.split("T")[-1][:8] if "T" in created else created

        formatted.append(f"[{created}] [{m.get('from', 'unknown')}] {m.get('content', '')}")

    return {
        "messages": formatted,
        "pending_messages": [],  # Legacy field for compatibility
        "new_messages": formatted,
        "pending_count": 0,
        "new_count": len(messages),
        "total": len(messages),
    }
