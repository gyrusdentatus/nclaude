"""Status command implementation - delegates to aqua_bridge."""

from pathlib import Path
from typing import Any, Dict, List
import json

from ..aqua_bridge import get_status, get_session_id, get_project_path


# Legacy peers file for backwards compatibility
PEERS_FILE = Path("/tmp/nclaude/.peers")


def load_peers() -> Dict[str, List[str]]:
    """Load peers from global peers file."""
    if not PEERS_FILE.exists():
        return {}
    try:
        return json.loads(PEERS_FILE.read_text())
    except (json.JSONDecodeError, IOError):
        return {}


def cmd_status() -> Dict[str, Any]:
    """Get comprehensive status info.

    Returns:
        Dict with session, aqua, and peer status
    """
    # Get aqua status
    status = get_status()

    # Add peer info for backwards compatibility
    project_path = get_project_path()
    project_name = project_path.name if project_path else "unknown"
    peers = load_peers()
    status["peers"] = peers.get(project_name, [])

    # Add legacy fields for compatibility
    status["room_name"] = project_name
    status["message_count"] = 0  # Deprecated, use aqua messaging

    return status
