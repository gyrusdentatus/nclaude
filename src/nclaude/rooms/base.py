"""Base Room abstraction."""

import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional, Dict, Any

from ..storage.base import Message, StorageBackend


class Room(ABC):
    """Abstract base class for rooms.

    A room is a message namespace - all messages in a room are visible
    to all participants in that room.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Room name/identifier."""
        ...

    @property
    @abstractmethod
    def path(self) -> Path:
        """Path to room's storage directory."""
        ...

    @property
    @abstractmethod
    def storage(self) -> StorageBackend:
        """Storage backend for this room."""
        ...

    def send(
        self,
        session_id: str,
        content: str,
        msg_type: str = "MSG",
        recipient: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send a message to the room.

        Args:
            session_id: Sender's session ID
            content: Message content
            msg_type: Message type
            recipient: Optional @mention target (None = broadcast)

        Returns:
            Dict with sent message details
        """
        message = Message.create(
            room=self.name,
            session_id=session_id,
            content=content,
            msg_type=msg_type,
            recipient=recipient,
        )
        self.storage.append_message(message)

        result = {
            "sent": content,
            "session": session_id,
            "timestamp": message.timestamp,
            "type": msg_type,
        }
        if recipient:
            result["to"] = recipient
        return result

    def read(
        self,
        session_id: str,
        all_messages: bool = False,
        quiet: bool = False,
        limit: Optional[int] = None,
        msg_type: Optional[str] = None,
        for_me: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Read messages from the room.

        Args:
            session_id: Reader's session ID
            all_messages: If True, read all messages
            quiet: If True, return None when no new messages
            limit: Maximum messages to return
            msg_type: Filter by message type (TASK, URGENT, etc.)
            for_me: If True, only show messages addressed to me (or broadcast)

        Returns:
            Dict with messages, or None in quiet mode with no messages
        """
        self.storage.init()

        # Get last read position
        last_line = 0
        if not all_messages:
            last_line = self.storage.get_read_pointer(session_id, self.name)

        # Get raw lines for backwards compatibility
        lines = self.storage.get_raw_lines(self.name)
        new_lines = lines[last_line:]

        # Apply type filter if specified (for raw lines)
        if msg_type:
            type_upper = msg_type.upper()
            filtered = []
            i = 0
            while i < len(new_lines):
                line = new_lines[i]
                # Check single-line format: [ts] [session] [TYPE] msg
                if f"[{type_upper}]" in line:
                    filtered.append(line)
                # Check multi-line header: <<<[ts][session][TYPE]>>>
                elif line.startswith("<<<[") and f"][{type_upper}]>>>" in line:
                    # Include header and content until <<<END>>>
                    filtered.append(line)
                    i += 1
                    while i < len(new_lines) and new_lines[i] != "<<<END>>>":
                        filtered.append(new_lines[i])
                        i += 1
                    if i < len(new_lines):
                        filtered.append(new_lines[i])  # <<<END>>>
                i += 1
            new_lines = filtered

        # Apply for_me filter (messages to me or broadcast)
        if for_me:
            filtered = []
            for line in new_lines:
                # Check for @mention at start of content
                # Format: [ts] [session] [TYPE] @recipient msg
                # or: [ts] [session] @recipient msg
                match = re.search(r'\] @([\w/.-]+)\s', line)
                if match:
                    recipient = match.group(1)
                    if recipient == session_id or recipient == "*":
                        filtered.append(line)
                else:
                    # No @mention = broadcast, include it
                    filtered.append(line)
            new_lines = filtered

        # Apply limit
        if limit and len(new_lines) > limit:
            new_lines = new_lines[:limit]

        # Update pointer (always update to latest, regardless of filters)
        self.storage.set_read_pointer(session_id, self.name, len(lines))

        if quiet and len(new_lines) == 0:
            return None

        return {
            "messages": new_lines,
            "new_count": len(new_lines),
            "total": len(lines),
        }

    def status(self) -> Dict[str, Any]:
        """Get room status.

        Returns:
            Dict with room status info
        """
        self.storage.init()

        message_count = self.storage.get_message_count(self.name)
        sessions = self.storage.get_sessions(self.name)

        return {
            "active": message_count > 0 or len(sessions) > 0,
            "project": self.name,
            "message_count": message_count,
            "sessions": sessions,
            "log_path": str(self.storage.log_path),
        }

    def clear(self) -> Dict[str, str]:
        """Clear all messages and session data.

        Returns:
            Dict with status
        """
        self.storage.clear(self.name)
        return {"status": "cleared"}

    def pending(self, session_id: str) -> Dict[str, Any]:
        """Check for pending messages from listen daemon.

        Args:
            session_id: Session to check pending for

        Returns:
            Dict with pending messages info
        """
        pending_range = self.storage.get_pending_range(session_id)

        if not pending_range:
            return {"pending": False, "messages": [], "count": 0}

        start, end = pending_range
        lines = self.storage.get_raw_lines(self.name)
        pending_msgs = lines[start:end]

        # Clear pending and update pointer
        self.storage.clear_pending(session_id)
        self.storage.set_read_pointer(session_id, self.name, end)

        return {
            "pending": True,
            "messages": pending_msgs,
            "count": len(pending_msgs),
            "range": f"{start}:{end}",
        }

    def check(self, session_id: str, for_me: bool = False) -> Dict[str, Any]:
        """Combined pending + read - one-stop "catch me up" command.

        Args:
            session_id: Session to check for
            for_me: If True, only show messages addressed to me (or broadcast)

        Returns:
            Dict with pending and new messages
        """
        pending_result = self.pending(session_id)
        read_result = self.read(session_id, for_me=for_me)

        # Filter pending messages if for_me is set
        pending_msgs = pending_result.get("messages", [])
        if for_me and pending_msgs:
            # Filter for messages to me or broadcast
            filtered = []
            for msg in pending_msgs:
                # Check if it's a string (raw log line) or dict
                if isinstance(msg, str):
                    # For raw lines, check if @session_id appears or no @mention
                    if f"@{session_id}" in msg or not msg.startswith("@"):
                        filtered.append(msg)
                elif isinstance(msg, dict):
                    recipient = msg.get("recipient")
                    if recipient is None or recipient == session_id or recipient == "*":
                        filtered.append(msg)
            pending_msgs = filtered

        return {
            "pending_messages": pending_msgs,
            "new_messages": read_result.get("messages", []),
            "pending_count": len(pending_msgs),
            "new_count": read_result.get("new_count", 0),
            "total": len(pending_msgs) + read_result.get("new_count", 0),
        }
