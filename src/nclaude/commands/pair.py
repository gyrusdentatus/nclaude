"""Pair/unpair/peers command implementations."""

import json
from typing import Any, Dict, List, Optional

from ..config import PEERS_FILE, get_base_dir
from ..rooms.base import Room
from ..storage.file import FileStorage


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


def cmd_pair(room: Room, session_id: str, target_project: str) -> Dict[str, Any]:
    """Register a peer relationship.

    Args:
        room: Current room
        session_id: Current session ID
        target_project: Project to pair with

    Returns:
        Dict with pairing status
    """
    current = room.name
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

    # Also send a PAIRED message to the target
    target_base = get_base_dir(override=target_project)
    target_storage = FileStorage(base_dir=target_base)
    target_storage.init()

    from ..storage.base import Message

    message = Message.create(
        room=target_project,
        session_id=session_id,
        content=f"PAIRED: {current} is now paired with you",
        msg_type="STATUS",
    )
    target_storage.append_message(message)

    return {
        "status": "paired",
        "project": current,
        "peer": target_project,
        "all_peers": peers[current],
    }


def cmd_unpair(
    room: Room, target_project: Optional[str] = None
) -> Dict[str, Any]:
    """Remove a peer relationship (or all if target is None).

    Args:
        room: Current room
        target_project: Specific peer to remove, or None for all

    Returns:
        Dict with unpairing status
    """
    current = room.name
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


def cmd_peers(room: Room) -> Dict[str, Any]:
    """List all peers for current project.

    Args:
        room: Current room

    Returns:
        Dict with peer info
    """
    current = room.name
    peers = load_peers()
    my_peers = peers.get(current, [])

    return {
        "project": current,
        "peers": my_peers,
        "all_pairings": peers,
    }
