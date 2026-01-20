"""Interactive chat command implementation."""

from typing import Any, Dict, Optional

from ..rooms.base import Room


def cmd_chat(room: Room) -> Optional[Dict[str, Any]]:
    """Interactive human chat mode.

    Args:
        room: Room to chat in

    Returns:
        None (handles its own output)
    """
    room.storage.init()

    print("\n" + "=" * 60)
    print("  ★★★ HUMAN CHAT MODE ★★★")
    print("  Messages will be marked [HUMAN] [BROADCAST]")
    print("  Type 'quit' or Ctrl+C to exit")
    print("=" * 60 + "\n")

    try:
        while True:
            try:
                msg = input("HUMAN> ")
                if msg.lower() in ("quit", "exit", "q"):
                    print("Goodbye!")
                    break
                if msg.strip():
                    room.send("HUMAN", msg, "BROADCAST")
                    print(f"  → Sent to all Claudes")
            except EOFError:
                break
    except KeyboardInterrupt:
        print("\nGoodbye!")

    return None  # Don't print JSON at end
