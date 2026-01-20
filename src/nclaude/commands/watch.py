"""Watch command implementation."""

import signal
import sys
import time
from typing import Any, Dict

from ..rooms.base import Room
from ..utils.formatting import format_message_line


def cmd_watch(
    room: Room,
    session_id: str,
    timeout: int = 60,
    interval: float = 1.0,
    history: int = 0,
) -> Dict[str, Any]:
    """Watch messages live (like tail -f but formatted).

    Args:
        room: Room to watch
        session_id: Viewer's session ID
        timeout: Max seconds to watch (0 = forever)
        interval: Polling interval in seconds
        history: Number of recent messages to show first

    Returns:
        Dict with status
    """
    storage = room.storage
    storage.init()

    # Handle graceful shutdown
    running = True

    def handle_signal(signum, frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    # Get current line count to start from
    last_line = 0
    lines = storage.get_raw_lines(room.name)
    total_lines = len(lines)

    if history > 0 and total_lines > 0:
        # Show last N lines as history
        last_line = max(0, total_lines - history)
    else:
        last_line = total_lines

    print(f"\n{'='*60}")
    print(f"  ★ WATCHING: {room.name} (as {session_id})")
    print(f"  Timeout: {'forever' if timeout == 0 else f'{timeout}s'} | Interval: {interval}s")
    print(f"  Press Ctrl+C to stop")
    print(f"{'='*60}\n")

    start_time = time.time()

    while running:
        try:
            # Check timeout
            if timeout > 0 and (time.time() - start_time) >= timeout:
                print(f"\n[timeout reached after {timeout}s]")
                break

            # Read new lines
            lines = storage.get_raw_lines(room.name)
            new_lines = lines[last_line:]

            if new_lines:
                for line in new_lines:
                    print(format_message_line(line))

                last_line = len(lines)
                # Terminal bell on new messages
                print("\a", end="", flush=True)

            time.sleep(interval)
        except Exception as e:
            print(f"\033[1;31m[error: {e}]\033[0m", file=sys.stderr)
            time.sleep(interval)

    print(f"\n[stopped watching {room.name}]")
    return {"status": "stopped", "lines_seen": last_line}
