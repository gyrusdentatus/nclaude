"""SQLite storage backend for nclaude messages."""

import json
import sqlite3
import threading
from pathlib import Path
from typing import List, Optional, Dict, Any

from .base import Message

# Single global database for all projects
GLOBAL_DB_PATH = Path.home() / ".nclaude" / "messages.db"


class SQLiteStorage:
    """SQLite-based storage with WAL mode for concurrent access.

    Uses a single global database at ~/.nclaude/messages.db with room column
    for project separation. This enables cross-project coordination.

    Schema:
        messages: id, room, session_id, msg_type, content, timestamp, metadata, recipient
        read_pointers: session_id, room, last_read_id

    Uses thread-local connections for safety.
    """

    _local = threading.local()

    def __init__(self, base_dir: Path):
        """Initialize SQLite storage.

        Args:
            base_dir: Base directory - used for room name only, DB is global
        """
        self.base_dir = Path(base_dir)
        # Always use global DB path - room column separates projects
        self.db_path = GLOBAL_DB_PATH
        self.log_path = self.db_path  # For compatibility with Room

    @property
    def _conn(self) -> sqlite3.Connection:
        """Get thread-local connection."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = self._create_connection()
        return self._local.conn

    def _create_connection(self) -> sqlite3.Connection:
        """Create a new database connection."""
        # Ensure global DB directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
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
        # Ensure global DB directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room TEXT NOT NULL,
                session_id TEXT NOT NULL,
                msg_type TEXT NOT NULL DEFAULT 'MSG',
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                metadata TEXT,
                recipient TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_messages_room
                ON messages(room);

            CREATE INDEX IF NOT EXISTS idx_messages_timestamp
                ON messages(timestamp);

            CREATE INDEX IF NOT EXISTS idx_messages_room_id
                ON messages(room, id);

            CREATE INDEX IF NOT EXISTS idx_messages_recipient
                ON messages(recipient);

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

            CREATE TABLE IF NOT EXISTS session_metadata (
                session_id TEXT PRIMARY KEY,
                project_dir TEXT,
                last_activity TEXT,
                task_summary TEXT,
                claimed_files TEXT,
                pending_work TEXT,
                updated_at TEXT
            );
        """)
        self._conn.commit()

        # Add recipient column if it doesn't exist (migration for existing DBs)
        try:
            self._conn.execute("ALTER TABLE messages ADD COLUMN recipient TEXT")
            self._conn.commit()
        except sqlite3.OperationalError:
            pass  # Column already exists

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
            INSERT INTO messages (room, session_id, msg_type, content, timestamp, metadata, recipient)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                self.room,
                message.session_id,
                message.msg_type,
                message.content,
                message.timestamp,
                metadata_json,
                message.recipient,
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
        msg_type: Optional[str] = None,
        recipient: Optional[str] = None,
    ) -> List[Message]:
        """Read messages from storage.

        Args:
            room: Room to read from (uses self.room)
            since_id: Only return messages after this ID
            limit: Maximum number of messages
            msg_type: Filter by message type (TASK, URGENT, etc.)
            recipient: Filter by recipient (None = all, session_id = for me)

        Returns:
            List of messages
        """
        self.init()

        query = """
            SELECT id, room, session_id, msg_type, content, timestamp, metadata, recipient
            FROM messages
            WHERE room = ? AND id > ?
        """
        params: List[Any] = [self.room, since_id]

        if msg_type:
            query += " AND msg_type = ?"
            params.append(msg_type.upper())

        if recipient:
            # Filter: broadcast, directly to me, or I'm in comma-separated list
            query += """ AND (
                recipient IS NULL
                OR recipient = '*'
                OR recipient = ?
                OR (',' || recipient || ',') LIKE ?
            )"""
            params.append(recipient)
            params.append(f"%,{recipient},%")

        query += " ORDER BY id ASC"

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
                    recipient=row["recipient"],
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

    def save_session_metadata(self, session_id: str, metadata: Dict[str, Any]) -> None:
        """Save session metadata (used by PreCompact hook).

        Args:
            session_id: Session identifier
            metadata: Dict with keys: project_dir, task_summary, claimed_files, pending_work
        """
        self.init()

        from datetime import datetime, timezone

        self._conn.execute(
            """
            INSERT OR REPLACE INTO session_metadata
            (session_id, project_dir, last_activity, task_summary, claimed_files, pending_work, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                metadata.get("project_dir", ""),
                metadata.get("last_activity", ""),
                metadata.get("task_summary", ""),
                json.dumps(metadata.get("claimed_files", [])),
                json.dumps(metadata.get("pending_work", [])),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        self._conn.commit()

    def get_session_metadata(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session metadata.

        Args:
            session_id: Session identifier

        Returns:
            Dict with session metadata, or None if not found
        """
        self.init()

        cursor = self._conn.execute(
            """
            SELECT project_dir, last_activity, task_summary, claimed_files, pending_work, updated_at
            FROM session_metadata
            WHERE session_id = ?
            """,
            (session_id,),
        )
        row = cursor.fetchone()

        if not row:
            return None

        return {
            "session_id": session_id,
            "project_dir": row["project_dir"],
            "last_activity": row["last_activity"],
            "task_summary": row["task_summary"],
            "claimed_files": json.loads(row["claimed_files"]) if row["claimed_files"] else [],
            "pending_work": json.loads(row["pending_work"]) if row["pending_work"] else [],
            "updated_at": row["updated_at"],
        }

    def list_session_metadata(self) -> List[Dict[str, Any]]:
        """List all session metadata.

        Returns:
            List of session metadata dicts
        """
        self.init()

        cursor = self._conn.execute(
            """
            SELECT session_id, project_dir, last_activity, task_summary, claimed_files, pending_work, updated_at
            FROM session_metadata
            ORDER BY updated_at DESC
            """
        )

        sessions = []
        for row in cursor:
            sessions.append({
                "session_id": row["session_id"],
                "project_dir": row["project_dir"],
                "last_activity": row["last_activity"],
                "task_summary": row["task_summary"],
                "claimed_files": json.loads(row["claimed_files"]) if row["claimed_files"] else [],
                "pending_work": json.loads(row["pending_work"]) if row["pending_work"] else [],
                "updated_at": row["updated_at"],
            })

        return sessions
