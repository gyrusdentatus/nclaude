"""Broadcast command implementation for human-to-Claude messaging."""

import re
from typing import Any, Dict, List, Optional, Tuple

from ..config import resolve_recipient
from ..rooms.base import Room
from .pair import load_peers


def parse_broadcast_targets(
    message: str, all_peers: bool = False, room: Optional[Room] = None
) -> Tuple[str, List[str]]:
    """Parse broadcast targets from message or flags.

    Supports:
    - `--all-peers` flag: sends to all registered peers for current room
    - `@peer1 @peer2 msg`: sends to specific peers (multiple @mentions)
    - `@all msg` or `@* msg`: true broadcast (recipient=None, visible to all)

    Args:
        message: Raw message content potentially starting with @mentions
        all_peers: If True, load and use all registered peers
        room: Current room (needed for --all-peers)

    Returns:
        Tuple of (cleaned_message, list_of_recipients)
        Empty list = broadcast to all (@all)
    """
    # Handle --all-peers flag
    if all_peers:
        if room is None:
            return message, []
        peers = load_peers()
        peer_list = peers.get(room.name, [])
        return message, peer_list

    # Parse multiple @mentions from start of message
    targets = []
    remaining = message
    while remaining.startswith("@"):
        match = re.match(r'^@([\w/.-]+)\s*', remaining)
        if match:
            target = match.group(1)
            # @all or @* = true broadcast (no filtering)
            if target in ("all", "*"):
                return remaining[match.end():].strip(), []
            targets.append(resolve_recipient(target))
            remaining = remaining[match.end():]
        else:
            break

    return remaining.strip(), targets


def cmd_broadcast(
    room: Room, message: str, all_peers: bool = False
) -> Dict[str, Any]:
    """Send a BROADCAST message from HUMAN to specified targets.

    Supports three modes:
    1. `--all-peers`: Send to all registered peers for this room
    2. `@peer1 @peer2 msg`: Send to specific peers
    3. `@all msg`: True broadcast (no recipient filtering)

    Args:
        room: Room to broadcast to
        message: Message content (may contain @mentions)
        all_peers: If True, send to all registered peers

    Returns:
        Dict with sent message details
    """
    if not message:
        return {"error": "No message provided"}

    cleaned_msg, targets = parse_broadcast_targets(message, all_peers, room)

    if not cleaned_msg:
        return {"error": "No message content after parsing targets"}

    if not targets:
        # True broadcast to all (recipient=None)
        result = room.send(
            "HUMAN",
            f"[BROADCAST TO: @all] {cleaned_msg}",
            "BROADCAST",
            recipient=None,
        )
        return {**result, "broadcast_to": "all", "targets": []}

    # Send to each specific target
    results = []
    for target in targets:
        r = room.send(
            "HUMAN",
            f"[BROADCAST TO: @{target}] {cleaned_msg}",
            "BROADCAST",
            recipient=target,
        )
        results.append({"to": target, "timestamp": r["timestamp"]})

    return {
        "sent": cleaned_msg,
        "session": "HUMAN",
        "type": "BROADCAST",
        "targets": targets,
        "messages_sent": len(results),
        "details": results,
    }
