"""SQLite storage backend for nclaude messages."""

import json
import sqlite3
import threading
from pathlib import Path
from typing import List, Optional, Dict, Any

from .base import Message


class SQLiteStorage:
    """SQLite-based storage with WAL mode for concurrent access.

    Schema:
        messages: id, room, session_id, msg_type, content, timestamp, metadata
        read_pointers: session_id, room, last_read_id

    Uses thread-local connections for safety.
    """

    _local = threading.local()

    def __init__(self, base_dir: Path):
        """Initialize SQLite storage.

        Args:
            base_dir: Base directory for database file
        """
        self.base_dir = Path(base_dir)
        self.db_path = self.base_dir / "messages.db"
        self.log_path = self.db_path  # For compatibility with Room

    @property
    def _conn(self) -> sqlite3.Connection:
        """Get thread-local connection."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = self._create_connection()
        return self._local.conn

    def _create_connection(self) -> sqlite3.Connection:
        """Create a new database connection."""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        # Enable WAL mode for concurrent reads
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    @property
    def room(self) -> str:
        """Room name is the base directory name."""
        return self.base_dir.name

    def init(self) -> None:
        """Initialize database schema."""
        self.base_dir.mkdir(parents=True, exist_ok=True)

        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room TEXT NOT NULL,
                session_id TEXT NOT NULL,
                msg_type TEXT NOT NULL DEFAULT 'MSG',
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                metadata TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_messages_room
                ON messages(room);

            CREATE INDEX IF NOT EXISTS idx_messages_timestamp
                ON messages(timestamp);

            CREATE INDEX IF NOT EXISTS idx_messages_room_id
                ON messages(room, id);

            CREATE TABLE IF NOT EXISTS read_pointers (
                session_id TEXT NOT NULL,
                room TEXT NOT NULL,
                last_read_id INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (session_id, room)
            );

            CREATE TABLE IF NOT EXISTS pending (
                session_id TEXT PRIMARY KEY,
                start_id INTEGER NOT NULL,
                end_id INTEGER NOT NULL
            );
        """)
        self._conn.commit()

    def append_message(self, message: Message) -> Message:
        """Append a message to storage.

        Args:
            message: Message to store

        Returns:
            Message with assigned ID
        """
        self.init()

        metadata_json = json.dumps(message.metadata) if message.metadata else None

        cursor = self._conn.execute(
            """
            INSERT INTO messages (room, session_id, msg_type, content, timestamp, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                self.room,
                message.session_id,
                message.msg_type,
                message.content,
                message.timestamp,
                metadata_json,
            ),
        )
        self._conn.commit()

        message.id = cursor.lastrowid
        return message

    def read_messages(
        self,
        room: str,
        since_id: int = 0,
        limit: Optional[int] = None,
    ) -> List[Message]:
        """Read messages from storage.

        Args:
            room: Room to read from (uses self.room)
            since_id: Only return messages after this ID
            limit: Maximum number of messages

        Returns:
            List of messages
        """
        self.init()

        query = """
            SELECT id, room, session_id, msg_type, content, timestamp, metadata
            FROM messages
            WHERE room = ? AND id > ?
            ORDER BY id ASC
        """
        params: List[Any] = [self.room, since_id]

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        cursor = self._conn.execute(query, params)
        messages = []

        for row in cursor:
            metadata = json.loads(row["metadata"]) if row["metadata"] else None
            messages.append(
                Message(
                    id=row["id"],
                    room=row["room"],
                    session_id=row["session_id"],
                    msg_type=row["msg_type"],
                    content=row["content"],
                    timestamp=row["timestamp"],
                    metadata=metadata,
                )
            )

        return messages

    def get_read_pointer(self, session_id: str, room: str) -> int:
        """Get last read message ID for a session.

        Args:
            session_id: Session identifier
            room: Room name (uses self.room)

        Returns:
            Last read message ID (0 if never read)
        """
        self.init()

        cursor = self._conn.execute(
            "SELECT last_read_id FROM read_pointers WHERE session_id = ? AND room = ?",
            (session_id, self.room),
        )
        row = cursor.fetchone()
        return row["last_read_id"] if row else 0

    def set_read_pointer(self, session_id: str, room: str, message_id: int) -> None:
        """Set last read message ID for a session.

        Args:
            session_id: Session identifier
            room: Room name (uses self.room)
            message_id: Last read message ID
        """
        self.init()

        self._conn.execute(
            """
            INSERT OR REPLACE INTO read_pointers (session_id, room, last_read_id)
            VALUES (?, ?, ?)
            """,
            (session_id, self.room, message_id),
        )
        self._conn.commit()

    def get_message_count(self, room: str) -> int:
        """Get total message count for a room.

        Args:
            room: Room name (uses self.room)

        Returns:
            Number of messages
        """
        self.init()

        cursor = self._conn.execute(
            "SELECT COUNT(*) as count FROM messages WHERE room = ?",
            (self.room,),
        )
        row = cursor.fetchone()
        return row["count"] if row else 0

    def get_sessions(self, room: str) -> List[str]:
        """Get list of sessions that have read from this room.

        Args:
            room: Room name (uses self.room)

        Returns:
            List of session IDs
        """
        self.init()

        cursor = self._conn.execute(
            "SELECT session_id FROM read_pointers WHERE room = ?",
            (self.room,),
        )
        return [row["session_id"] for row in cursor]

    def clear(self, room: str) -> None:
        """Clear all messages and session data for a room.

        Args:
            room: Room name (uses self.room)
        """
        self.init()

        self._conn.execute("DELETE FROM messages WHERE room = ?", (self.room,))
        self._conn.execute("DELETE FROM read_pointers WHERE room = ?", (self.room,))
        self._conn.execute("DELETE FROM pending")
        self._conn.commit()

    def get_raw_lines(self, room: str) -> List[str]:
        """Get messages as raw log lines (for backwards compatibility).

        Converts SQLite messages to the same format as file backend.

        Args:
            room: Room name (uses self.room)

        Returns:
            List of log-formatted lines
        """
        messages = self.read_messages(room)
        lines = []

        for msg in messages:
            lines.append(msg.to_log_line())
            # Multi-line messages add extra lines
            if "\n" in msg.content:
                # Header line is already added, now add content lines
                for line in msg.content.split("\n"):
                    lines.append(line)
                lines.append("<<<END>>>")

        return lines

    def get_pending_range(self, session_id: str) -> Optional[tuple]:
        """Get pending message range from daemon.

        Returns:
            Tuple of (start_id, end_id), or None if no pending.
        """
        self.init()

        cursor = self._conn.execute(
            "SELECT start_id, end_id FROM pending WHERE session_id = ?",
            (session_id,),
        )
        row = cursor.fetchone()
        if row:
            return (row["start_id"], row["end_id"])
        return None

    def clear_pending(self, session_id: str) -> None:
        """Clear pending notification for a session."""
        self._conn.execute("DELETE FROM pending WHERE session_id = ?", (session_id,))
        self._conn.commit()

    def set_pending_range(self, session_id: str, start: int, end: int) -> None:
        """Set pending message range (used by listen daemon)."""
        self.init()

        self._conn.execute(
            """
            INSERT OR REPLACE INTO pending (session_id, start_id, end_id)
            VALUES (?, ?, ?)
            """,
            (session_id, start, end),
        )
        self._conn.commit()
