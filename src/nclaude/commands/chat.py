"""Interactive chat command implementation."""

from typing import Any, Dict, Optional

from ..aqua_bridge import send_message


def cmd_chat() -> Optional[Dict[str, Any]]:
    """Interactive human chat mode.

    Returns:
        None (handles its own output)
    """
    print("\n" + "=" * 60)
    print("  HUMAN CHAT MODE")
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
                    # Send via aqua global messaging with HUMAN as sender
                    send_message(
                        content=msg,
                        to=None,  # Broadcast
                        message_type="broadcast",
                    )
                    print(f"  -> Sent to all Claudes")
            except EOFError:
                break
    except KeyboardInterrupt:
        print("\nGoodbye!")

    return None  # Don't print JSON at end
