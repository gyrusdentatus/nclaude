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
    ) -> Dict[str, Any]:
        """Send a message to the room.

        Args:
            session_id: Sender's session ID
            content: Message content
            msg_type: Message type

        Returns:
            Dict with sent message details
        """
        message = Message.create(
            room=self.name,
            session_id=session_id,
            content=content,
            msg_type=msg_type,
        )
        self.storage.append_message(message)

        return {
            "sent": content,
            "session": session_id,
            "timestamp": message.timestamp,
            "type": msg_type,
        }

    def read(
        self,
        session_id: str,
        all_messages: bool = False,
        quiet: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Read messages from the room.

        Args:
            session_id: Reader's session ID
            all_messages: If True, read all messages
            quiet: If True, return None when no new messages

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

        # Update pointer
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

    def check(self, session_id: str) -> Dict[str, Any]:
        """Combined pending + read - one-stop "catch me up" command.

        Args:
            session_id: Session to check for

        Returns:
            Dict with pending and new messages
        """
        pending_result = self.pending(session_id)
        read_result = self.read(session_id)

        return {
            "pending_messages": pending_result.get("messages", []),
            "new_messages": read_result.get("messages", []),
            "pending_count": pending_result.get("count", 0),
            "new_count": read_result.get("new_count", 0),
            "total": pending_result.get("count", 0) + read_result.get("new_count", 0),
        }
