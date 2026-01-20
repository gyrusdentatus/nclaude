"""Broadcast command implementation."""

from typing import Any, Dict, List, Optional

from ..config import PEERS_FILE, get_base_dir
from ..storage.file import FileStorage
from ..storage.base import Message


def load_peers() -> Dict[str, List[str]]:
    """Load peers from global peers file."""
    import json
    if not PEERS_FILE.exists():
        return {}
    try:
        return json.loads(PEERS_FILE.read_text())
    except (json.JSONDecodeError, IOError):
        return {}


def cmd_broadcast(
    room,  # Room - but we may not use it for multi-peer
    message: str,
    targets: Optional[List[str]] = None,
    all_peers: bool = False,
) -> Dict[str, Any]:
    """Broadcast message to multiple rooms.

    Args:
        room: Current room (used if no targets specified)
        message: Message content
        targets: List of @peer targets (e.g., ["speaktojade", "tf-gitlab"])
        all_peers: If True, broadcast to all registered peers

    Returns:
        Dict with broadcast results
    """
    if not message:
        return {"error": "No message provided"}

    # Determine target rooms
    if all_peers:
        peers = load_peers()
        current = room.name
        target_rooms = peers.get(current, [])
        if not target_rooms:
            return {"error": "No peers registered. Use 'nclaude pair <project>' first."}
    elif targets:
        # Parse @mentions - strip @ prefix if present
        target_rooms = [t.lstrip("@") for t in targets]
    else:
        # Just current room
        return room.send("HUMAN", message, "BROADCAST")

    # Broadcast to each target
    results = []
    for target in target_rooms:
        try:
            target_base = get_base_dir(override=target)
            storage = FileStorage(base_dir=target_base)
            storage.init()

            msg = Message.create(
                room=target,
                session_id="HUMAN",
                content=message,
                msg_type="BROADCAST",
            )
            storage.append_message(msg)
            results.append({"target": target, "status": "sent", "timestamp": msg.timestamp})
        except Exception as e:
            results.append({"target": target, "status": "error", "error": str(e)})

    return {
        "broadcast": True,
        "message": message,
        "targets": target_rooms,
        "results": results,
        "sent_count": len([r for r in results if r["status"] == "sent"]),
    }
