"""Listen command implementation."""

import json
import signal
import sys
import time
from typing import Any, Dict

from ..rooms.base import Room
from ..storage.file import FileStorage


def cmd_listen(
    room: Room,
    session_id: str,
    interval: int = 5,
) -> None:
    """Run daemon that monitors for new messages.

    Runs in foreground - use & or nohup for background.
    Writes line range to pending/<session_id> when new messages arrive.

    Args:
        room: Room to monitor
        session_id: Session to monitor for
        interval: Polling interval in seconds
    """
    storage = room.storage
    if not isinstance(storage, FileStorage):
        print(json.dumps({"error": "Listen only works with file storage"}), flush=True)
        return

    storage.init()
    storage.pending_dir.mkdir(parents=True, exist_ok=True)
    pending_file = storage.pending_dir / session_id

    # Handle graceful shutdown
    running = True

    def handle_signal(signum, frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    print(
        json.dumps(
            {
                "status": "listening",
                "session": session_id,
                "interval": interval,
                "pending_file": str(pending_file),
            }
        ),
        flush=True,
    )

    while running:
        try:
            # Get current pointer (last read position)
            last_read = storage.get_read_pointer(session_id, room.name)

            # Get total line count
            total_lines = storage.get_message_count(room.name)

            # Check for new messages
            if total_lines > last_read:
                # Write pending range
                storage.set_pending_range(session_id, last_read, total_lines)
                new_count = total_lines - last_read

                print(
                    json.dumps(
                        {
                            "event": "new_messages",
                            "count": new_count,
                            "range": f"{last_read}:{total_lines}",
                            "session": session_id,
                        }
                    ),
                    flush=True,
                )

                # Terminal bell for human awareness
                print("\a", end="", flush=True)

            time.sleep(interval)
        except Exception as e:
            print(json.dumps({"error": str(e)}), file=sys.stderr, flush=True)
            time.sleep(interval)

    # Cleanup
    if pending_file.exists():
        pending_file.unlink()

    print(json.dumps({"status": "stopped", "session": session_id}), flush=True)
