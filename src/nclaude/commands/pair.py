"""Pair/unpair/peers command implementations - using aqua global messaging."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..aqua_bridge import get_project_path, send_message


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


def save_peers(peers: Dict[str, List[str]]) -> None:
    """Save peers to global peers file."""
    PEERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PEERS_FILE.write_text(json.dumps(peers, indent=2))


def cmd_pair(target_project: str) -> Dict[str, Any]:
    """Register a peer relationship.

    Note: With aqua's global messaging, explicit pairing is less necessary.
    Messages can be sent to any agent via @mention.

    Args:
        target_project: Project to pair with

    Returns:
        Dict with pairing status
    """
    project_path = get_project_path()
    current = project_path.name if project_path else "unknown"
    peers = load_peers()

    # Add bidirectional pairing
    if current not in peers:
        peers[current] = []
    if target_project not in peers[current]:
        peers[current].append(target_project)

    if target_project not in peers:
        peers[target_project] = []
    if current not in peers[target_project]:
        peers[target_project].append(current)

    save_peers(peers)

    # Send a notification via global messaging
    send_message(
        content=f"PAIRED: {current} is now paired with {target_project}",
        message_type="status",
        global_=True,
    )

    return {
        "status": "paired",
        "project": current,
        "peer": target_project,
        "all_peers": peers[current],
        "hint": "With aqua, you can message any agent directly via @mention without explicit pairing.",
    }


def cmd_unpair(target_project: Optional[str] = None) -> Dict[str, Any]:
    """Remove a peer relationship (or all if target is None).

    Args:
        target_project: Specific peer to remove, or None for all

    Returns:
        Dict with unpairing status
    """
    project_path = get_project_path()
    current = project_path.name if project_path else "unknown"
    peers = load_peers()

    if target_project:
        # Remove specific peer
        if current in peers and target_project in peers[current]:
            peers[current].remove(target_project)
        if target_project in peers and current in peers[target_project]:
            peers[target_project].remove(current)
        save_peers(peers)
        return {"status": "unpaired", "project": current, "removed": target_project}
    else:
        # Remove all peers for current project
        removed = peers.pop(current, [])
        # Also remove current from other projects' peer lists
        for proj in peers:
            if current in peers[proj]:
                peers[proj].remove(current)
        save_peers(peers)
        return {"status": "unpaired_all", "project": current, "removed": removed}


def cmd_peers() -> Dict[str, Any]:
    """List all peers for current project.

    Returns:
        Dict with peer info
    """
    project_path = get_project_path()
    current = project_path.name if project_path else "unknown"
    peers = load_peers()
    my_peers = peers.get(current, [])

    return {
        "project": current,
        "peers": my_peers,
        "all_pairings": peers,
        "hint": "With aqua, you can message any agent directly via @mention.",
    }
