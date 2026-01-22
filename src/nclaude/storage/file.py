"""File-based storage backend (current behavior)."""

import fcntl
import re
import shutil
from pathlib import Path
from typing import List, Optional

from .base import Message, StorageBackend


class FileStorage:
    """File-based storage using append-only log with flock.

    This maintains exact compatibility with the original nclaude.py behavior.

    Log format:
        Single-line: [timestamp] [session_id] [TYPE] message
        Multi-line:  <<<[timestamp][session_id][TYPE]>>>
                     content
                     <<<END>>>
    """

    def __init__(self, base_dir: Path):
        """Initialize file storage.

        Args:
            base_dir: Base directory for storage files
        """
        self.base_dir = Path(base_dir)
        self.log_path = self.base_dir / "messages.log"
        self.lock_path = self.base_dir / ".lock"
        self.sessions_dir = self.base_dir / "sessions"
        self.pending_dir = self.base_dir / "pending"

    @property
    def room(self) -> str:
        """Room name is the base directory name."""
        return self.base_dir.name

    def init(self) -> None:
        """Initialize storage directories and files."""
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.log_path.touch()
        self.lock_path.touch()

    def append_message(self, message: Message) -> Message:
        """Append message atomically using flock."""
        self.init()

        line = message.to_log_line() + "\n"

        with open(self.lock_path, "r") as lock_fd:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            try:
                with open(self.log_path, "a") as f:
                    f.write(line)
                # Get the message ID (line number)
                message.id = len(self.log_path.read_text().splitlines())
            finally:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)

        return message

    def read_messages(
        self,
        room: str,
        since_id: int = 0,
        limit: Optional[int] = None,
        msg_type: Optional[str] = None,
        recipient: Optional[str] = None,
    ) -> List[Message]:
        """Read messages from log file.

        Note: room parameter is ignored - we use self.room

        Args:
            room: Room name (ignored, uses self.room)
            since_id: Start reading after this line number
            limit: Maximum messages to return
            msg_type: Filter by message type (TASK, URGENT, etc.)
            recipient: Filter for session (None=all, session_id=for me only)
        """
        if not self.log_path.exists():
            return []

        lines = self.log_path.read_text().splitlines()
        messages = []
        type_filter = msg_type.upper() if msg_type else None

        i = since_id  # Start from the line after last read
        while i < len(lines):
            line = lines[i]
            msg = self._parse_line(line, i + 1, lines, i)

            if msg:
                # Apply type filter
                if type_filter is not None and msg.msg_type != type_filter:
                    pass  # Skip this message
                # Apply recipient filter
                elif recipient is not None and not self._recipient_matches(msg.recipient, recipient):
                    pass  # Skip this message
                else:
                    messages.append(msg)

                # Skip multi-line content
                if msg.content and "\n" in msg.content:
                    # Count lines in the multi-line message
                    i += msg.content.count("\n") + 2  # header + content lines + END
                else:
                    i += 1
            else:
                i += 1

            if limit and len(messages) >= limit:
                break

        return messages

    def _recipient_matches(self, msg_recipient: Optional[str], session_id: str) -> bool:
        """Check if a message is for the given session.

        Args:
            msg_recipient: Message's recipient field (None=broadcast, "*"=broadcast, or session ID(s))
            session_id: Session ID to check for

        Returns:
            True if message should be visible to this session
        """
        # No recipient = broadcast to all
        if msg_recipient is None:
            return True
        # Explicit broadcast
        if msg_recipient == "*":
            return True
        # Direct match
        if msg_recipient == session_id:
            return True
        # Check comma-separated list
        if "," in msg_recipient:
            recipients = [r.strip() for r in msg_recipient.split(",")]
            return session_id in recipients
        return False

    def _parse_line(
        self, line: str, line_num: int, all_lines: List[str], line_idx: int
    ) -> Optional[Message]:
        """Parse a single log line into a Message.

        Args:
            line: The line to parse
            line_num: 1-based line number (for message ID)
            all_lines: All lines in the file (for multi-line messages)
            line_idx: 0-based index into all_lines
        """
        # Multi-line message header: <<<[timestamp][session_id][TYPE]>>>
        if line.startswith("<<<["):
            match = re.match(r"<<<\[([^\]]+)\]\[([^\]]+)\]\[([^\]]+)\]>>>", line)
            if match:
                timestamp, session_id, msg_type = match.groups()
                # Collect content until <<<END>>>
                content_lines = []
                j = line_idx + 1
                while j < len(all_lines) and all_lines[j] != "<<<END>>>":
                    content_lines.append(all_lines[j])
                    j += 1
                content = "\n".join(content_lines)
                # Extract recipient from @mention prefix
                content, recipient = self._extract_recipient(content)
                return Message(
                    id=line_num,
                    room=self.room,
                    session_id=session_id,
                    msg_type=msg_type,
                    content=content,
                    timestamp=timestamp,
                    recipient=recipient,
                )

        # Single-line message: [timestamp] [session_id] [TYPE] content
        # or: [timestamp] [session_id] content (TYPE=MSG)
        if line.startswith("["):
            # Try with type first
            match = re.match(
                r"\[([^\]]+)\] \[([^\]]+)\] \[([^\]]+)\] (.+)", line
            )
            if match:
                timestamp, session_id, msg_type, content = match.groups()
                content, recipient = self._extract_recipient(content)
                return Message(
                    id=line_num,
                    room=self.room,
                    session_id=session_id,
                    msg_type=msg_type,
                    content=content,
                    timestamp=timestamp,
                    recipient=recipient,
                )

            # Try without type (defaults to MSG)
            match = re.match(r"\[([^\]]+)\] \[([^\]]+)\] (.+)", line)
            if match:
                timestamp, session_id, content = match.groups()
                content, recipient = self._extract_recipient(content)
                return Message(
                    id=line_num,
                    room=self.room,
                    session_id=session_id,
                    msg_type="MSG",
                    content=content,
                    timestamp=timestamp,
                    recipient=recipient,
                )

        return None

    def _extract_recipient(self, content: str) -> tuple:
        """Extract @recipient from content start.

        Args:
            content: Message content that may start with @recipient

        Returns:
            Tuple of (cleaned_content, recipient or None)
        """
        # Match @mention at start: @name, @a,@b (multi), @nclaude/branch
        match = re.match(r'^@([\w/.,@-]+)\s+', content)
        if match:
            recipient = match.group(1)
            cleaned = content[match.end():]
            return cleaned, recipient
        return content, None

    def get_read_pointer(self, session_id: str, room: str) -> int:
        """Get last read line number for a session."""
        pointer_file = self.sessions_dir / session_id
        if not pointer_file.exists():
            return 0
        try:
            return int(pointer_file.read_text().strip() or "0")
        except ValueError:
            return 0

    def set_read_pointer(self, session_id: str, room: str, message_id: int) -> None:
        """Set last read line number for a session."""
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        pointer_file = self.sessions_dir / session_id
        pointer_file.write_text(str(message_id))

    def get_message_count(self, room: str) -> int:
        """Get total line count (approximate message count)."""
        if not self.log_path.exists():
            return 0
        return len(self.log_path.read_text().splitlines())

    def get_sessions(self, room: str) -> List[str]:
        """Get list of sessions that have read pointers."""
        if not self.sessions_dir.exists():
            return []
        return [f.name for f in self.sessions_dir.iterdir() if f.is_file()]

    def clear(self, room: str) -> None:
        """Clear all storage for this room."""
        if self.base_dir.exists():
            shutil.rmtree(self.base_dir)

    def get_raw_lines(self, room: str) -> List[str]:
        """Get raw log lines for backwards compatibility."""
        if not self.log_path.exists():
            return []
        return self.log_path.read_text().splitlines()

    def get_pending_range(self, session_id: str) -> Optional[tuple]:
        """Get pending message range from daemon.

        Returns:
            Tuple of (start, end) line numbers, or None if no pending.
        """
        pending_file = self.pending_dir / session_id
        if not pending_file.exists():
            return None

        try:
            content = pending_file.read_text().strip()
            if not content:
                pending_file.unlink()
                return None
            start, end = map(int, content.split(":"))
            return (start, end)
        except (ValueError, FileNotFoundError):
            return None

    def clear_pending(self, session_id: str) -> None:
        """Clear pending notification for a session."""
        pending_file = self.pending_dir / session_id
        if pending_file.exists():
            pending_file.unlink()

    def set_pending_range(self, session_id: str, start: int, end: int) -> None:
        """Set pending message range (used by listen daemon)."""
        self.pending_dir.mkdir(parents=True, exist_ok=True)
        pending_file = self.pending_dir / session_id
        pending_file.write_text(f"{start}:{end}")
