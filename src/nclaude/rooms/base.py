"""Base Room abstraction."""

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
        since_id = 0
        if not all_messages:
            since_id = self.storage.get_read_pointer(session_id, self.name)

        # Use storage-level filtering for efficiency
        recipient_filter = session_id if for_me else None
        messages = self.storage.read_messages(
            room=self.name,
            since_id=since_id,
            msg_type=msg_type,
            recipient=recipient_filter,
        )

        # Apply limit
        if limit and len(messages) > limit:
            if all_messages:
                # For --all, show the LAST N messages (most recent)
                messages = messages[-limit:]
            else:
                # For new messages, show the FIRST N (oldest unread first)
                messages = messages[:limit]

        # Convert to log lines for backwards compatibility
        new_lines = [msg.to_log_line() for msg in messages]

        # Get total count for pointer update
        total = self.storage.get_message_count(self.name)

        # Update pointer to latest (always update, regardless of filters)
        self.storage.set_read_pointer(session_id, self.name, total)

        if quiet and len(new_lines) == 0:
            return None

        return {
            "messages": new_lines,
            "new_count": len(new_lines),
            "total": total,
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
            filtered = []
            for msg in pending_msgs:
                if isinstance(msg, str):
                    # For raw lines, check @mention patterns
                    # No @mention = broadcast (include)
                    # @session_id = for me (include)
                    # @* = broadcast (include)
                    # @other = not for me (exclude)
                    import re
                    match = re.search(r'\] @([\w/.,@-]+)\s', msg)
                    if match:
                        recipient = match.group(1)
                        if self._recipient_for_me(recipient, session_id):
                            filtered.append(msg)
                    else:
                        # No @mention = broadcast
                        filtered.append(msg)
                elif isinstance(msg, dict):
                    recipient = msg.get("recipient")
                    if self._recipient_for_me(recipient, session_id):
                        filtered.append(msg)
            pending_msgs = filtered

        return {
            "pending_messages": pending_msgs,
            "new_messages": read_result.get("messages", []),
            "pending_count": len(pending_msgs),
            "new_count": read_result.get("new_count", 0),
            "total": len(pending_msgs) + read_result.get("new_count", 0),
        }

    def _recipient_for_me(self, recipient: Optional[str], session_id: str) -> bool:
        """Check if a recipient field includes the given session.

        Args:
            recipient: Recipient field (None, "*", session_id, or comma-list)
            session_id: Session to check for

        Returns:
            True if message is for this session
        """
        if recipient is None:
            return True
        if recipient == "*":
            return True
        if recipient == session_id:
            return True
        if "," in recipient:
            parts = [p.strip() for p in recipient.split(",")]
            return session_id in parts
        return False
