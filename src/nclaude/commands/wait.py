"""Wait command - blocking poll for new messages."""

import time
from typing import Any, Dict

from ..rooms.base import Room


def cmd_wait(
    room: Room,
    session_id: str,
    timeout: int = 30,
    interval: float = 1.0,
) -> Dict[str, Any]:
    """Block until new messages arrive or timeout.

    Args:
        room: Room to monitor
        session_id: Session ID waiting for messages
        timeout: Maximum seconds to wait (0 = wait forever, but that's dangerous)
        interval: Seconds between checks

    Returns:
        Dict with messages if found, or timeout status
    """
    start = time.time()
    initial_count = room.storage.get_message_count(room.name)

    # Cap timeout at 5 minutes to prevent infinite waits
    if timeout <= 0 or timeout > 300:
        timeout = 300

    while time.time() - start < timeout:
        current_count = room.storage.get_message_count(room.name)

        if current_count > initial_count:
            # New messages arrived - return them
            result = room.read(session_id)
            result["waited"] = round(time.time() - start, 1)
            return result

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
