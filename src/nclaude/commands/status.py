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


def cmd_status(room: Room, session_id: str = None) -> Dict[str, Any]:
    """Get room status with peer info and session identity.

    Args:
        room: Room to get status for
        session_id: Current session ID (for whoami info)

    Returns:
        Dict with status info including peers and session identity
    """
    status = room.status()

    # Add peer info
    peers = load_peers()
    project_name = room.name
    status["peers"] = peers.get(project_name, [])

    # Add session identity (whoami)
    if session_id:
        status["session_id"] = session_id

    return status
