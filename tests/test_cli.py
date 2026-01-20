"""Tests for CLI functionality."""

import json
import subprocess
import sys
from pathlib import Path

import pytest


# Get the src directory for PYTHONPATH
SRC_DIR = Path(__file__).parent.parent / "src"


def run_nclaude(*args, env=None):
    """Run nclaude CLI and return result."""
    import os
    test_env = os.environ.copy()
    test_env["PYTHONPATH"] = str(SRC_DIR)
    if env:
        test_env.update(env)

    result = subprocess.run(
        [sys.executable, "-m", "nclaude"] + list(args),
        capture_output=True,
        text=True,
        env=test_env,
    )
    return result


class TestCLI:
    """Tests for CLI commands."""

    def test_version(self):
        """Test --version flag."""
        result = run_nclaude("--version")
        assert result.returncode == 0
        assert "2.0.0" in result.stdout

    def test_help(self):
        """Test --help flag."""
        result = run_nclaude("--help")
        assert result.returncode == 0
        assert "nclaude" in result.stdout
        assert "send" in result.stdout

    def test_whoami(self):
        """Test whoami command."""
        result = run_nclaude("whoami")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "session_id" in data
        assert "base_dir" in data

    def test_status(self):
        """Test status command."""
        result = run_nclaude("status")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "project" in data
        assert "message_count" in data

    def test_send_and_read(self, tmp_path):
        """Test send and read commands."""
        # Use a unique project dir for isolation
        test_dir = str(tmp_path / "test-cli")

        # Send a message
        result = run_nclaude(
            "send", "CLI test message",
            "--dir", test_dir
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["sent"] == "CLI test message"

        # Read messages
        result = run_nclaude("read", "--all", "--dir", test_dir)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["new_count"] >= 1

    def test_send_with_type(self, tmp_path):
        """Test send with --type flag."""
        test_dir = str(tmp_path / "test-cli-type")

        result = run_nclaude(
            "send", "Task message",
            "--type", "TASK",
            "--dir", test_dir
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["type"] == "TASK"

    def test_read_with_limit(self, tmp_path):
        """Test read with --limit flag."""
        test_dir = str(tmp_path / "test-cli-limit")

        # Send multiple messages
        for i in range(5):
            run_nclaude("send", f"Message {i}", "--dir", test_dir)

        # Read with limit
        result = run_nclaude("read", "--all", "--limit", "2", "--dir", test_dir)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert len(data["messages"]) == 2

    def test_read_with_filter(self, tmp_path):
        """Test read with --filter flag."""
        test_dir = str(tmp_path / "test-cli-filter")

        # Send different types
        run_nclaude("send", "Regular message", "--dir", test_dir)
        run_nclaude("send", "Task message", "--type", "TASK", "--dir", test_dir)
        run_nclaude("send", "Another regular", "--dir", test_dir)

        # Filter for TASK only
        result = run_nclaude(
            "read", "--all", "--filter", "TASK", "--dir", test_dir
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        # Should only have TASK messages
        for msg in data["messages"]:
            if msg.startswith("["):  # Skip multi-line headers
                assert "[TASK]" in msg

    def test_global_room(self, tmp_path):
        """Test --global flag."""
        result = run_nclaude("status", "--global")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["project"] == "global"
        assert ".nclaude" in data["log_path"]

    def test_quiet_mode_no_output(self, tmp_path):
        """Test --quiet flag with no messages."""
        test_dir = str(tmp_path / "test-quiet")

        # Read from empty room in quiet mode
        result = run_nclaude("read", "--quiet", "--dir", test_dir)
        assert result.returncode == 0
        # Should have no output
        assert result.stdout.strip() == ""

    def test_check_command(self, tmp_path):
        """Test check command."""
        test_dir = str(tmp_path / "test-check")

        run_nclaude("send", "Test message", "--dir", test_dir)

        result = run_nclaude("check", "--dir", test_dir)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "pending_messages" in data
        assert "new_messages" in data
        assert "total" in data

    def test_unknown_command(self):
        """Test unknown command error."""
        result = run_nclaude("nonexistent")
        assert result.returncode == 0  # Still returns 0 but with error in JSON
        data = json.loads(result.stdout)
        assert "error" in data
