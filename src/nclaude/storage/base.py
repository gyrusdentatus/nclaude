"""Storage backend protocol and Message dataclass."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Protocol, Any


@dataclass
class Message:
    """A single nclaude message.

    Attributes:
        id: Unique message identifier (line number for file, auto-increment for sqlite)
        room: Room/project name
        session_id: Sender's session identifier
        msg_type: Message type (MSG, TASK, REPLY, STATUS, URGENT, ERROR, BROADCAST)
        content: Message content (can be multi-line)
        timestamp: UTC timestamp string
        metadata: Optional JSON metadata for extensibility
        recipient: Optional @mention target (None = broadcast to all)
    """
    id: int
    room: str
    session_id: str
    msg_type: str
    content: str
    timestamp: str
    metadata: Optional[Dict[str, Any]] = None
    recipient: Optional[str] = None

    @classmethod
    def create(
        cls,
        room: str,
        session_id: str,
        content: str,
        msg_type: str = "MSG",
        metadata: Optional[Dict[str, Any]] = None,
        recipient: Optional[str] = None,
    ) -> "Message":
        """Create a new message with auto-generated timestamp."""
        return cls(
            id=0,  # Will be set by storage backend
            room=room,
            session_id=session_id,
            msg_type=msg_type,
            content=content,
            timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
            metadata=metadata,
            recipient=recipient,
        )

    def to_log_line(self) -> str:
        """Convert to log file format (for file backend compatibility)."""
        # Include @recipient prefix if targeted message
        content = self.content
        if self.recipient:
            content = f"@{self.recipient} {content}"

        if "\n" in content:
            # Multi-line format
            return f"<<<[{self.timestamp}][{self.session_id}][{self.msg_type}]>>>\n{content}\n<<<END>>>"
        else:
            # Single-line format
            if self.msg_type != "MSG":
                return f"[{self.timestamp}] [{self.session_id}] [{self.msg_type}] {content}"
            else:
                return f"[{self.timestamp}] [{self.session_id}] {content}"


class StorageBackend(Protocol):
    """Protocol defining storage backend interface.

    All storage backends must implement these methods.
    """

    def init(self) -> None:
        """Initialize storage (create directories, tables, etc.)."""
        ...

    def append_message(self, message: Message) -> Message:
        """Append a message to storage.

        Args:
            message: Message to store

        Returns:
            Message with assigned ID
        """
        ...

    def read_messages(
        self,
        room: str,
        since_id: int = 0,
        limit: Optional[int] = None,
        msg_type: Optional[str] = None,
        recipient: Optional[str] = None,
    ) -> List[Message]:
        """Read messages from storage.

        Args:
            room: Room to read from
            since_id: Only return messages after this ID (0 for all)
            limit: Maximum number of messages to return
            msg_type: Filter by message type (TASK, URGENT, etc.)
            recipient: Filter for session (None=all, session_id=for me only)

        Returns:
            List of messages
        """
        ...

    def get_read_pointer(self, session_id: str, room: str) -> int:
        """Get last read message ID for a session.

        Args:
            session_id: Session identifier
            room: Room name

        Returns:
            Last read message ID (0 if never read)
        """
        ...

    def set_read_pointer(self, session_id: str, room: str, message_id: int) -> None:
        """Set last read message ID for a session.

        Args:
            session_id: Session identifier
            room: Room name
            message_id: Last read message ID
        """
        ...

    def get_message_count(self, room: str) -> int:
        """Get total message count for a room.

        Args:
            room: Room name

        Returns:
            Number of messages
        """
        ...

    def get_sessions(self, room: str) -> List[str]:
        """Get list of sessions that have read from this room.

        Args:
            room: Room name

        Returns:
            List of session IDs
        """
        ...

    def clear(self, room: str) -> None:
        """Clear all messages and session data for a room.

        Args:
            room: Room name
        """
        ...

    def get_raw_lines(self, room: str) -> List[str]:
        """Get raw log lines (for backwards compatibility).

        Only implemented by FileStorage.

        Args:
            room: Room name

        Returns:
            List of raw log lines
        """
        ...
