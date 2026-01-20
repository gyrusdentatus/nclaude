"""Tests for command implementations."""

import tempfile
from pathlib import Path

import pytest

from nclaude.storage.file import FileStorage
from nclaude.rooms.project import ProjectRoom
from nclaude.commands.send import cmd_send
from nclaude.commands.read import cmd_read
from nclaude.commands.check import cmd_check
from nclaude.commands.status import cmd_status
from nclaude.commands.clear import cmd_clear
from nclaude.commands.whoami import cmd_whoami
from nclaude.commands.pending import cmd_pending


class MockRoom:
    """Mock room for testing commands."""

    def __init__(self, tmpdir):
        self._base_dir = Path(tmpdir) / "test-project"
        self._storage = FileStorage(base_dir=self._base_dir)

    @property
    def name(self):
        return "test-project"

    @property
    def path(self):
        return self._base_dir

    @property
    def storage(self):
        return self._storage

    def send(self, session_id, content, msg_type="MSG", recipient=None):
        from nclaude.storage.base import Message
        msg = Message.create(self.name, session_id, content, msg_type, recipient=recipient)
        self._storage.append_message(msg)
        result = {
            "sent": content,
            "session": session_id,
            "timestamp": msg.timestamp,
            "type": msg_type,
        }
        if recipient:
            result["to"] = recipient
        return result

    def read(self, session_id, all_messages=False, quiet=False, limit=None, msg_type=None):
        self._storage.init()
        last_line = 0
        if not all_messages:
            last_line = self._storage.get_read_pointer(session_id, self.name)

        lines = self._storage.get_raw_lines(self.name)
        new_lines = lines[last_line:]

        if limit:
            new_lines = new_lines[:limit]

        self._storage.set_read_pointer(session_id, self.name, len(lines))

        if quiet and len(new_lines) == 0:
            return None

        return {
            "messages": new_lines,
            "new_count": len(new_lines),
            "total": len(lines),
        }

    def status(self):
        self._storage.init()
        return {
            "active": True,
            "project": self.name,
            "message_count": self._storage.get_message_count(self.name),
            "sessions": self._storage.get_sessions(self.name),
            "log_path": str(self._storage.log_path),
        }

    def clear(self):
        self._storage.clear(self.name)
        return {"status": "cleared"}

    def pending(self, session_id):
        return {"pending": False, "messages": [], "count": 0}

    def check(self, session_id, for_me=False):
        pending_result = self.pending(session_id)
        read_result = self.read(session_id)
        return {
            "pending_messages": pending_result.get("messages", []),
            "new_messages": read_result.get("messages", []),
            "pending_count": pending_result.get("count", 0),
            "new_count": read_result.get("new_count", 0),
            "total": pending_result.get("count", 0) + read_result.get("new_count", 0),
        }


class TestCommands:
    """Tests for command functions."""

    @pytest.fixture
    def room(self):
        """Create a mock room for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield MockRoom(tmpdir)

    def test_cmd_send(self, room):
        """Test send command."""
        result = cmd_send(room, "test-session", "Hello!", "MSG")
        assert result["sent"] == "Hello!"
        assert result["session"] == "test-session"
        assert result["type"] == "MSG"

    def test_cmd_send_empty_message(self, room):
        """Test send command with empty message."""
        result = cmd_send(room, "test-session", "", "MSG")
        assert "error" in result

    def test_cmd_read(self, room):
        """Test read command."""
        room.send("s1", "Message 1")
        room.send("s1", "Message 2")

        result = cmd_read(room, "reader-1")
        assert result["new_count"] == 2
        assert len(result["messages"]) == 2

    def test_cmd_read_quiet_no_messages(self, room):
        """Test read command in quiet mode with no messages."""
        result = cmd_read(room, "reader-1", quiet=True)
        assert result is None

    def test_cmd_read_with_limit(self, room):
        """Test read command with limit."""
        for i in range(10):
            room.send("s1", f"Message {i}")

        result = cmd_read(room, "reader-1", limit=3)
        assert len(result["messages"]) == 3

    def test_cmd_status(self, room):
        """Test status command."""
        room.send("s1", "Test message")

        result = cmd_status(room)
        assert result["active"] is True
        assert result["project"] == "test-project"
        assert result["message_count"] == 1

    def test_cmd_clear(self, room):
        """Test clear command."""
        room.send("s1", "Test message")
        result = cmd_clear(room)
        assert result["status"] == "cleared"

    def test_cmd_whoami(self, room):
        """Test whoami command."""
        result = cmd_whoami(room, "my-session")
        assert result["session_id"] == "my-session"
        assert "base_dir" in result
        assert "log_path" in result

    def test_cmd_check(self, room):
        """Test check command."""
        room.send("s1", "Message 1")

        result = cmd_check(room, "reader-1")
        assert result["new_count"] == 1
        assert result["pending_count"] == 0
        assert result["total"] == 1

    def test_cmd_pending_no_pending(self, room):
        """Test pending command with no pending messages."""
        result = cmd_pending(room, "session-1")
        assert result["pending"] is False
        assert result["count"] == 0
