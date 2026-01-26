#!/usr/bin/env python3
"""
Stop hook: Block Claude from stopping if unread nclaude messages exist.
Also suggests peers based on conversation patterns and rules.

Enhanced features (v3.0):
- Stuck pattern detection (repeated errors)
- Topic-based peer suggestions
- Hookify-compatible rules from ~/.claude/nclaude-rules.yaml
"""
import json
import os
import re
import sqlite3
import sys
from pathlib import Path
from typing import Optional

DB_PATH = Path.home() / ".nclaude" / "messages.db"
STATE_DIR = Path("/tmp/nclaude-state")
RULES_PATH = Path.home() / ".claude" / "nclaude-rules.yaml"


def get_session_id(hook_input: dict) -> str:
    cc_session = hook_input.get("session_id", "")
    if cc_session:
        return f"cc-{cc_session[:12]}"
    return os.environ.get("NCLAUDE_ID", "default")


def get_last_seen(session_id: str) -> int:
    STATE_DIR.mkdir(exist_ok=True)
    state_file = STATE_DIR / f"{session_id}.seen"
    try:
        return int(state_file.read_text().strip())
    except (FileNotFoundError, ValueError):
        return 0


def check_new_messages(session_id: str) -> tuple[int, list[str]]:
    if not DB_PATH.exists():
        return 0, []

    last_seen = get_last_seen(session_id)

    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=1.0)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Count new messages (exclude self-sent)
        cursor.execute(
            "SELECT COUNT(*) FROM messages WHERE id > ? AND room = 'nclaude' AND session_id != ?",
            (last_seen, session_id)
        )
        count = cursor.fetchone()[0] or 0

        if count == 0:
            conn.close()
            return 0, []

        # Fetch recent messages for display (exclude self-sent)
        cursor.execute(
            """SELECT session_id, msg_type, content, recipient
               FROM messages
               WHERE id > ? AND room = 'nclaude' AND session_id != ?
               ORDER BY id DESC LIMIT 5""",
            (last_seen, session_id)
        )

        messages = []
        for row in cursor.fetchall():
            sender = row["session_id"]
            msg_type = row["msg_type"]
            content = row["content"][:150]
            prefix = f"[{sender}]"
            if msg_type != "MSG":
                prefix += f" [{msg_type}]"
            messages.append(f"{prefix} {content}")

        conn.close()
        return count, messages

    except sqlite3.Error:
        return 0, []


# Built-in stuck patterns
STUCK_PATTERNS = [
    (r"(error|failed).{0,200}\1.{0,200}\1", "Same error 3+ times"),
    (r"(AttributeError|TypeError|ImportError).{0,300}\1", "Repeated Python exception"),
    (r"(command not found).{0,200}\1", "Command not found loop"),
    (r"(permission denied).{0,200}\1", "Permission issues"),
]

# Built-in topic -> peer mappings
TOPIC_PEERS = {
    r"kubectl|kubernetes|helm|k8s|pod|deployment": "@k8s",
    r"docker|container|dockerfile|compose|image": "@docker",
    r"security|auth|jwt|oauth|credentials|token": "@security",
    r"postgres|mysql|redis|database|sql|migration": "@data",
    r"terraform|ansible|pulumi|infrastructure": "@infra",
    r"react|vue|angular|frontend|css|html": "@frontend",
}


def load_rules() -> list[dict]:
    """Load rules from YAML config file."""
    if not RULES_PATH.exists():
        return []

    try:
        import yaml
        with open(RULES_PATH) as f:
            data = yaml.safe_load(f)
        return data.get("rules", []) if data else []
    except ImportError:
        # No PyYAML, try simple parsing
        return _parse_rules_simple(RULES_PATH)
    except Exception:
        return []


def _parse_rules_simple(path: Path) -> list[dict]:
    """Simple rule parser without PyYAML dependency."""
    rules = []
    try:
        content = path.read_text()
        # Very basic YAML parsing for our format
        current_rule = {}
        current_match = {}

        for line in content.split("\n"):
            line = line.rstrip()
            if not line or line.startswith("#"):
                continue

            # Rule start
            if line.strip() == "- name:":
                continue
            if line.strip().startswith("- name:"):
                if current_rule and current_rule.get("enabled", True):
                    if current_match:
                        current_rule["match"] = current_match
                    rules.append(current_rule)
                current_rule = {"name": line.split(":", 1)[1].strip()}
                current_match = {}
            elif ":" in line:
                key, value = line.strip().split(":", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")

                if key == "enabled":
                    current_rule["enabled"] = value.lower() == "true"
                elif key == "event":
                    current_rule["event"] = value
                elif key == "peer":
                    current_rule["peer"] = value
                elif key == "message":
                    current_rule["message"] = value
                elif key == "field":
                    current_match["field"] = value
                elif key == "pattern":
                    current_match["pattern"] = value
                elif key == "type":
                    current_match["type"] = value

        # Don't forget last rule
        if current_rule and current_rule.get("enabled", True):
            if current_match:
                current_rule["match"] = current_match
            rules.append(current_rule)

    except Exception:
        pass

    return rules


def evaluate_rules(transcript: str) -> list[dict]:
    """Evaluate rules against transcript, return matched rules."""
    matched = []
    rules = load_rules()

    for rule in rules:
        if not rule.get("enabled", True):
            continue
        if rule.get("event") not in ("stop", None):
            continue

        match_spec = rule.get("match", {})
        if match_spec.get("field") != "transcript":
            continue

        pattern = match_spec.get("pattern", "")
        if not pattern:
            continue

        flags = re.IGNORECASE
        try:
            if re.search(pattern, transcript, flags):
                matched.append(rule)
        except re.error:
            continue

    return matched


def check_stuck_patterns(transcript: str) -> Optional[str]:
    """Check if transcript shows stuck patterns."""
    transcript_lower = transcript.lower()

    for pattern, description in STUCK_PATTERNS:
        try:
            if re.search(pattern, transcript_lower, re.IGNORECASE | re.DOTALL):
                return description
        except re.error:
            continue

    return None


def check_topic_peers(transcript: str) -> list[str]:
    """Check if transcript suggests topic-specific peers."""
    transcript_lower = transcript.lower()
    suggestions = []

    for pattern, peer in TOPIC_PEERS.items():
        try:
            if re.search(pattern, transcript_lower, re.IGNORECASE):
                suggestions.append(peer)
        except re.error:
            continue

    return suggestions


def main():
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    session_id = get_session_id(hook_input)
    count, messages = check_new_messages(session_id)

    # Phase 1: Check unread messages (blocker)
    if count > 0:
        msg_preview = "\n".join(messages)
        output = {
            "decision": "block",
            "reason": f"STOP BLOCKED: {count} unread nclaude message(s). Run /nclaude:check to read:\n{msg_preview}"
        }
        print(json.dumps(output))
        sys.exit(0)

    # Phase 2: Check transcript for stuck patterns and topic suggestions
    transcript = hook_input.get("transcript_summary", "") or hook_input.get("transcript", "")

    if not transcript:
        # No transcript data - allow stop
        sys.exit(0)

    suggestions = []

    # Check stuck patterns
    stuck_reason = check_stuck_patterns(transcript)
    if stuck_reason:
        suggestions.append(f"You appear stuck: {stuck_reason}. Consider asking a peer: /nclaude:send \"Need help with...\"")

    # Check topic-based peers
    topic_peers = check_topic_peers(transcript)
    if topic_peers:
        peers_str = ", ".join(topic_peers[:3])  # Limit to 3
        suggestions.append(f"Topic experts available: {peers_str}")

    # Check user-defined rules
    matched_rules = evaluate_rules(transcript)
    for rule in matched_rules[:2]:  # Limit to 2 rule matches
        msg = rule.get("message", "")
        peer = rule.get("peer", "")
        if peer and peer not in msg:
            msg = f"{peer}: {msg}" if msg else f"Consider consulting {peer}"
        if msg:
            suggestions.append(msg)

    # If we have suggestions, output them as systemMessage (not blocking)
    if suggestions:
        suggestion_text = "\n".join(suggestions)
        output = {
            "systemMessage": f"Before stopping, consider:\n{suggestion_text}"
        }
        print(json.dumps(output))

    sys.exit(0)


if __name__ == "__main__":
    main()
