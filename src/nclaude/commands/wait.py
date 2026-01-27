"""Wait command - blocking poll for new messages."""

import time
from typing import Any, Dict

from ..aqua_bridge import read_messages


def cmd_wait(
    timeout: int = 30,
    interval: float = 1.0,
    global_: bool = False,
) -> Dict[str, Any]:
    """Block until new messages arrive or timeout.

    Args:
        timeout: Maximum seconds to wait (0 = wait forever, capped at 300s)
        interval: Seconds between checks
        global_: If True, wait on global room

    Returns:
        Dict with messages if found, or timeout status
    """
    start = time.time()

    # Get initial message count (by tracking IDs)
    initial_msgs = read_messages(unread_only=True, global_=global_)
    initial_ids = {m.get("id") for m in initial_msgs}

    # Cap timeout at 5 minutes to prevent infinite waits
    if timeout <= 0 or timeout > 300:
        timeout = 300

    while time.time() - start < timeout:
        current_msgs = read_messages(unread_only=True, global_=global_)
        current_ids = {m.get("id") for m in current_msgs}

        # Check for new messages
        new_ids = current_ids - initial_ids
        if new_ids:
            # New messages arrived - return them
            new_msgs = [m for m in current_msgs if m.get("id") in new_ids]
            return {
                "messages": new_msgs,
                "new_count": len(new_msgs),
                "waited": round(time.time() - start, 1),
            }

        time.sleep(interval)

    # Timeout reached
    elapsed = round(time.time() - start, 1)
    return {
        "timeout": True,
        "waited": elapsed,
        "messages": [],
        "new_count": 0,
        "hint": "No messages arrived. Try /nclaude:check again later or ask user to ping sender.",
    }
