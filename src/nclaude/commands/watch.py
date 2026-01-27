"""Watch command implementation - delegates to aqua_bridge."""

import signal
import sys
import time
from typing import Any, Dict

from ..aqua_bridge import read_messages, get_session_id, get_project_path


def format_message(msg: Dict[str, Any]) -> str:
    """Format a message for display."""
    created = msg.get("created_at", "")
    if created:
        # Show just time part
        created = created.split("T")[-1][:8] if "T" in created else created

    from_agent = msg.get("from", "unknown")
    content = msg.get("content", "")
    msg_type = msg.get("type", "chat")

    # Color based on type
    colors = {
        "task": "\033[1;33m",    # Yellow
        "urgent": "\033[1;31m",  # Red
        "error": "\033[1;31m",   # Red
        "status": "\033[1;36m",  # Cyan
        "reply": "\033[1;32m",   # Green
    }
    color = colors.get(msg_type, "\033[0m")
    reset = "\033[0m"

    return f"{color}[{created}] [{from_agent}]{reset} {content}"


def cmd_watch(
    timeout: int = 60,
    interval: float = 1.0,
    history: int = 0,
    global_: bool = False,
) -> Dict[str, Any]:
    """Watch messages live (like tail -f but formatted).

    Args:
        timeout: Max seconds to watch (0 = forever)
        interval: Polling interval in seconds
        history: Number of recent messages to show first
        global_: If True, watch global room

    Returns:
        Dict with status
    """
    session_id = get_session_id()
    project_path = get_project_path()
    room_name = project_path.name if project_path else "global"

    # Handle graceful shutdown
    running = True

    def handle_signal(signum, frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    # Track seen messages by ID
    seen_ids = set()

    # Show history if requested
    if history > 0:
        messages = read_messages(unread_only=False, limit=history, global_=global_)
        for msg in reversed(messages):  # Oldest first
            print(format_message(msg))
            seen_ids.add(msg.get("id"))

    print(f"\n{'='*60}")
    print(f"  WATCHING: {room_name} (as {session_id})")
    print(f"  Timeout: {'forever' if timeout == 0 else f'{timeout}s'} | Interval: {interval}s")
    print(f"  Press Ctrl+C to stop")
    print(f"{'='*60}\n")

    start_time = time.time()
    messages_seen = 0

    while running:
        try:
            # Check timeout
            if timeout > 0 and (time.time() - start_time) >= timeout:
                print(f"\n[timeout reached after {timeout}s]")
                break

            # Read new messages
            messages = read_messages(unread_only=True, global_=global_)

            for msg in messages:
                msg_id = msg.get("id")
                if msg_id not in seen_ids:
                    print(format_message(msg))
                    seen_ids.add(msg_id)
                    messages_seen += 1
                    # Terminal bell on new messages
                    print("\a", end="", flush=True)

            time.sleep(interval)
        except Exception as e:
            print(f"\033[1;31m[error: {e}]\033[0m", file=sys.stderr)
            time.sleep(interval)

    print(f"\n[stopped watching {room_name}]")
    return {"status": "stopped", "messages_seen": messages_seen}
