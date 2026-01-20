"""Status command implementation."""

from typing import Any, Dict, List

from ..rooms.base import Room
from ..config import PEERS_FILE


def load_peers() -> Dict[str, List[str]]:
    """Load peers from global peers file."""
    import json

    if not PEERS_FILE.exists():
        return {}
    try:
        return json.loads(PEERS_FILE.read_text())
    except (json.JSONDecodeError, IOError):
        return {}


def cmd_status(room: Room) -> Dict[str, Any]:
    """Get room status with peer info.

    Args:
        room: Room to get status for

    Returns:
        Dict with status info including peers
    """
    status = room.status()

    # Add peer info
    peers = load_peers()
    project_name = room.name
    status["peers"] = peers.get(project_name, [])

    return status
