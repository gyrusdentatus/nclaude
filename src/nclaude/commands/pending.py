"""Pending command implementation - deprecated with aqua backend."""

from typing import Any, Dict

from ..aqua_bridge import read_messages


def cmd_pending() -> Dict[str, Any]:
    """Check for pending messages.

    Note: The listen daemon feature is deprecated with aqua backend.
    This now just returns unread messages.

    Returns:
        Dict with pending messages
    """
    messages = read_messages(unread_only=True)

    if not messages:
        return {
            "pending_count": 0,
            "messages": [],
            "hint": "No pending messages. The listen daemon is deprecated - use aqua messaging.",
        }

    formatted = []
    for m in messages:
        created = m.get("created_at", "")
        if created:
            created = created.split("T")[-1][:8] if "T" in created else created
        formatted.append(f"[{created}] [{m.get('from', 'unknown')}] {m.get('content', '')}")

    return {
        "pending_count": len(messages),
        "messages": formatted,
    }
