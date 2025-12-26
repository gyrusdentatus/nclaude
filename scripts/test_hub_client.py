#!/usr/bin/env python3
"""
Tests for nclaude hub and client

Run: pytest scripts/test_hub_client.py -v
"""

import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent))

from client import HubClient, parse_mentions
from hub import MessageHub, get_hub_status, stop_hub


class TestParseMentions:
    """Test @mention parsing"""

    def test_single_mention(self):
        body, mentions = parse_mentions("@claude-a do the tests")
        assert mentions == ["claude-a"]
        assert body == "do the tests"

    def test_multiple_mentions(self):
        body, mentions = parse_mentions("@claude-a @claude-b both review this")
        assert mentions == ["claude-a", "claude-b"]
        assert body == "both review this"

    def test_no_mentions(self):
        body, mentions = parse_mentions("everyone do the thing")
        assert mentions == []
        assert body == "everyone do the thing"

    def test_mention_at_end(self):
        body, mentions = parse_mentions("hey @claude-c")
        assert mentions == ["claude-c"]
        assert body == "hey"

    def test_mention_with_numbers(self):
        body, mentions = parse_mentions("@agent-1 @agent-2 sync")
        assert mentions == ["agent-1", "agent-2"]
        assert body == "sync"

    def test_empty_string(self):
        body, mentions = parse_mentions("")
        assert mentions == []
        assert body == ""


class TestHubClient:
    """Test HubClient class"""

    def test_client_init(self):
        client = HubClient("test-session")
        assert client.session_id == "test-session"
        assert client.connected is False
        assert client.sock is None

    def test_client_custom_socket(self):
        custom_path = Path("/tmp/custom.sock")
        client = HubClient("test", socket_path=custom_path)
        assert client.socket_path == custom_path

    def test_connect_no_hub(self):
        """Connect fails when hub not running"""
        with tempfile.TemporaryDirectory() as tmpdir:
            sock_path = Path(tmpdir) / "test.sock"
            client = HubClient("test", socket_path=sock_path)
            result = client.connect()
            assert "error" in result
            assert "not running" in result["error"].lower()


class TestMessageHub:
    """Test MessageHub class"""

    def test_hub_init(self):
        hub = MessageHub()
        assert hub.socket_path == Path("/tmp/nclaude/hub.sock")
        assert hub.running is False
        assert len(hub.clients) == 0

    def test_hub_custom_socket(self):
        custom_path = Path("/tmp/custom.sock")
        hub = MessageHub(socket_path=custom_path)
        assert hub.socket_path == custom_path


class TestHubStatusFunctions:
    """Test hub status helper functions"""

    def test_get_hub_status_not_running(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sock_path = Path(tmpdir) / "test.sock"
            result = get_hub_status(sock_path)
            assert result["running"] is False

    def test_get_hub_status_no_pid_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sock_path = Path(tmpdir) / "test.sock"
            sock_path.touch()  # Socket exists but no PID file
            result = get_hub_status(sock_path)
            assert result["running"] is False
            assert "PID" in result["reason"]

    def test_stop_hub_not_running(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sock_path = Path(tmpdir) / "test.sock"
            result = stop_hub(sock_path)
            assert "error" in result


class TestHubClientIntegration:
    """Integration tests for hub + client"""

    @pytest.fixture
    def hub_socket(self):
        """Create a temporary socket path for testing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "test.sock"

    @pytest.fixture
    def running_hub(self, hub_socket):
        """Start a hub in a thread for testing"""
        hub = MessageHub(socket_path=hub_socket)

        def run_hub():
            try:
                hub.start()
            except:
                pass

        thread = threading.Thread(target=run_hub, daemon=True)
        thread.start()

        # Wait for hub to start
        for _ in range(50):
            if hub_socket.exists():
                break
            time.sleep(0.1)

        yield hub

        hub.stop()

    def test_client_connect_to_hub(self, running_hub, hub_socket):
        """Client can connect and register"""
        client = HubClient("test-client", socket_path=hub_socket)
        result = client.connect()

        assert result.get("connected") is True
        assert result.get("session_id") == "test-client"
        assert "online" in result

        client.disconnect()

    def test_two_clients_see_each_other(self, running_hub, hub_socket):
        """Two clients can see each other online"""
        client_a = HubClient("client-a", socket_path=hub_socket)
        client_b = HubClient("client-b", socket_path=hub_socket)

        result_a = client_a.connect()
        assert result_a.get("connected") is True

        result_b = client_b.connect()
        assert result_b.get("connected") is True
        assert "client-a" in result_b.get("online", [])

        client_a.disconnect()
        client_b.disconnect()

    def test_send_message_broadcast(self, running_hub, hub_socket):
        """Client can send broadcast message"""
        client_a = HubClient("sender", socket_path=hub_socket)
        client_b = HubClient("receiver", socket_path=hub_socket)

        client_a.connect()
        client_b.connect()

        # Drain any JOIN messages first
        time.sleep(0.3)
        client_b.recv_all()

        # Send broadcast
        result = client_a.send("Hello everyone!")
        assert result.get("sent") is True

        # Receiver should get it
        time.sleep(0.3)
        messages = client_b.recv_all()

        # Filter out JOIN/LEAVE/SENT messages
        content_msgs = [m for m in messages if m.get("type") not in ["JOIN", "LEAVE", "SENT"]]
        assert len(content_msgs) >= 1
        assert content_msgs[0].get("body") == "Hello everyone!"
        assert content_msgs[0].get("from") == "sender"

        client_a.disconnect()
        client_b.disconnect()

    def test_send_message_targeted(self, running_hub, hub_socket):
        """Client can send targeted message"""
        client_a = HubClient("sender", socket_path=hub_socket)
        client_b = HubClient("target", socket_path=hub_socket)
        client_c = HubClient("other", socket_path=hub_socket)

        client_a.connect()
        client_b.connect()
        client_c.connect()

        # Drain any JOIN messages first
        time.sleep(0.3)
        client_b.recv_all()
        client_c.recv_all()

        # Send to specific target
        result = client_a.send("Just for you", to=["target"])
        assert result.get("sent") is True

        time.sleep(0.3)

        # Target should get it - skip JOIN/LEAVE messages
        messages_b = client_b.recv_all()
        targeted_msgs = [m for m in messages_b if m.get("type") not in ["JOIN", "LEAVE", "SENT"]]
        assert len(targeted_msgs) >= 1
        assert targeted_msgs[0].get("body") == "Just for you"

        # Other should NOT get it (only JOIN messages possible)
        messages_c = client_c.recv_all()
        content_msgs = [m for m in messages_c if m.get("type") not in ["JOIN", "LEAVE", "SENT"]]
        assert len(content_msgs) == 0

        client_a.disconnect()
        client_b.disconnect()
        client_c.disconnect()

    def test_recv_timeout(self, running_hub, hub_socket):
        """Recv returns None on timeout"""
        client = HubClient("solo", socket_path=hub_socket)
        client.connect()

        start = time.time()
        msg = client.recv(timeout=0.5)
        elapsed = time.time() - start

        # Should have waited ~0.5 seconds
        assert 0.4 < elapsed < 1.0
        # No message
        assert msg is None

        client.disconnect()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
