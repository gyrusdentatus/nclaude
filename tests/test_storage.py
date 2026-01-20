"""Tests for storage backends."""

from pathlib import Path

import pytest

from nclaude.storage.base import Message
from nclaude.storage.file import FileStorage
from nclaude.storage.sqlite import SQLiteStorage


class TestFileStorage:
    """Tests for FileStorage backend."""

    @pytest.fixture
    def storage(self, tmp_path):
        """Create a temporary file storage with unique path per test."""
        import uuid
        unique_dir = tmp_path / f"test-project-{uuid.uuid4().hex[:8]}"
        return FileStorage(base_dir=unique_dir)

    def test_init(self, storage):
        """Test storage initialization."""
        storage.init()
        assert storage.sessions_dir.exists()
        assert storage.log_path.exists()

    def test_append_and_read(self, storage):
        """Test appending and reading messages."""
        msg = Message.create("test", "session-1", "Hello World", "MSG")
        result = storage.append_message(msg)

        assert result.id > 0
        messages = storage.read_messages("test")
        assert len(messages) == 1
        assert messages[0].content == "Hello World"
        assert messages[0].session_id == "session-1"

    def test_multiline_message(self, storage):
        """Test multi-line message handling."""
        content = "Line 1\nLine 2\nLine 3"
        msg = Message.create("test", "session-1", content, "TASK")
        storage.append_message(msg)

        messages = storage.read_messages("test")
        assert len(messages) == 1
        assert messages[0].content == content
        assert messages[0].msg_type == "TASK"

    def test_read_pointer(self, storage):
        """Test read pointer tracking."""
        storage.init()
        storage.set_read_pointer("session-1", "test", 10)
        ptr = storage.get_read_pointer("session-1", "test")
        assert ptr == 10

    def test_message_count(self, storage):
        """Test message count."""
        storage.init()
        assert storage.get_message_count("test") == 0

        msg = Message.create("test", "session-1", "Test", "MSG")
        storage.append_message(msg)
        assert storage.get_message_count("test") == 1

    def test_type_filter(self, storage):
        """Test filtering by message type."""
        storage.append_message(Message.create("test", "s1", "msg1", "MSG"))
        storage.append_message(Message.create("test", "s1", "task1", "TASK"))
        storage.append_message(Message.create("test", "s1", "msg2", "MSG"))
        storage.append_message(Message.create("test", "s1", "urgent1", "URGENT"))

        tasks = storage.read_messages("test", msg_type="TASK")
        assert len(tasks) == 1
        assert tasks[0].content == "task1"

        urgent = storage.read_messages("test", msg_type="URGENT")
        assert len(urgent) == 1
        assert urgent[0].content == "urgent1"

    def test_limit(self, storage):
        """Test message limit."""
        for i in range(10):
            storage.append_message(Message.create("test", "s1", f"msg{i}", "MSG"))

        messages = storage.read_messages("test", limit=3)
        assert len(messages) == 3

    def test_clear(self, storage):
        """Test clearing storage."""
        storage.append_message(Message.create("test", "s1", "test", "MSG"))
        assert storage.get_message_count("test") == 1

        storage.clear("test")
        assert not storage.base_dir.exists()


class TestSQLiteStorage:
    """Tests for SQLiteStorage backend."""

    @pytest.fixture
    def storage(self, tmp_path):
        """Create a temporary SQLite storage with unique path per test."""
        import uuid
        unique_dir = tmp_path / f"test-project-{uuid.uuid4().hex[:8]}"
        return SQLiteStorage(base_dir=unique_dir)

    def test_init(self, storage):
        """Test storage initialization."""
        storage.init()
        assert storage.db_path.exists()

    def test_append_and_read(self, storage):
        """Test appending and reading messages."""
        msg = Message.create("test", "session-1", "Hello SQLite", "MSG")
        result = storage.append_message(msg)

        # ID should be positive (global DB means IDs accumulate across tests)
        assert result.id > 0
        messages = storage.read_messages("test")
        assert len(messages) >= 1
        assert messages[-1].content == "Hello SQLite"

    def test_multiline_message(self, storage):
        """Test multi-line message handling."""
        content = "Line 1\nLine 2\nLine 3"
        msg = Message.create("test", "session-1", content, "TASK")
        storage.append_message(msg)

        messages = storage.read_messages("test")
        assert len(messages) == 1
        assert messages[0].content == content

    def test_type_filter(self, storage):
        """Test filtering by message type."""
        storage.append_message(Message.create("test", "s1", "msg1", "MSG"))
        storage.append_message(Message.create("test", "s1", "task1", "TASK"))
        storage.append_message(Message.create("test", "s1", "urgent1", "URGENT"))

        tasks = storage.read_messages("test", msg_type="TASK")
        assert len(tasks) == 1
        assert tasks[0].content == "task1"

    def test_limit(self, storage):
        """Test message limit."""
        for i in range(10):
            storage.append_message(Message.create("test", "s1", f"msg{i}", "MSG"))

        messages = storage.read_messages("test", limit=3)
        assert len(messages) == 3

    def test_since_id(self, storage):
        """Test reading since ID."""
        # Store the first message to get its ID
        first_msg = storage.append_message(Message.create("test", "s1", "msg0", "MSG"))
        first_id = first_msg.id

        # Add more messages
        for i in range(1, 5):
            storage.append_message(Message.create("test", "s1", f"msg{i}", "MSG"))

        # Read since the third message (first_id + 2)
        messages = storage.read_messages("test", since_id=first_id + 2)
        assert len(messages) == 2
        assert messages[0].content == "msg3"
        assert messages[1].content == "msg4"

    def test_sessions_list(self, storage):
        """Test listing sessions."""
        storage.init()
        storage.set_read_pointer("session-1", "test", 1)
        storage.set_read_pointer("session-2", "test", 2)

        sessions = storage.get_sessions("test")
        assert "session-1" in sessions
        assert "session-2" in sessions

    def test_raw_lines_compatibility(self, storage):
        """Test raw lines output for backwards compatibility."""
        storage.append_message(Message.create("test", "s1", "Hello", "MSG"))
        storage.append_message(Message.create("test", "s1", "Task!", "TASK"))

        lines = storage.get_raw_lines("test")
        assert len(lines) == 2
        assert "[s1]" in lines[0]
        assert "[TASK]" in lines[1]
