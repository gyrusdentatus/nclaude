#!/usr/bin/env python3
"""
Swarm Proof of Concept - Spawn multiple Claudes with --resume

This demonstrates that we can:
1. Spawn Claude with -p to start a session
2. Get the session ID from output
3. Later spawn claude --resume <id> -p "check messages"
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

NCLAUDE_SCRIPT = Path(__file__).parent / "nclaude.py"


def run_nclaude(cmd, *args):
    """Run nclaude command"""
    result = subprocess.run(
        ["python3", str(NCLAUDE_SCRIPT), cmd] + list(args),
        capture_output=True, text=True, timeout=30,
        env={**os.environ, "NCLAUDE_DIR": "/tmp/nclaude"}
    )
    if result.stdout:
        try:
            return json.loads(result.stdout)
        except:
            return {"raw": result.stdout}
    return {"error": result.stderr}


CLAUDE_BINARY = os.path.expanduser("~/.claude/local/node_modules/.bin/claude")


def spawn_claude_oneshot(session_name: str, prompt: str, timeout: int = 60):
    """
    Spawn Claude with -p for a one-shot task.
    Returns session info from the output.
    """
    print(f"\n[{session_name}] Spawning with prompt: {prompt[:50]}...")

    cmd = [
        CLAUDE_BINARY,
        "-p", prompt,
        "--output-format", "stream-json",
        "--dangerously-skip-permissions",
        "--verbose"
    ]

    env = os.environ.copy()
    env["NCLAUDE_ID"] = session_name

    try:
        # Run with timeout, capture output
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(Path(__file__).parent.parent),
            env=env
        )

        # Parse JSONL output to find session ID
        session_id = None
        for line in result.stdout.splitlines():
            try:
                data = json.loads(line)
                if "session_id" in data:
                    session_id = data["session_id"]
                    break
            except:
                continue

        print(f"[{session_name}] Completed. Session ID: {session_id}")
        return {
            "session_name": session_name,
            "session_id": session_id,
            "stdout_lines": len(result.stdout.splitlines()),
            "returncode": result.returncode
        }

    except subprocess.TimeoutExpired:
        print(f"[{session_name}] Timed out after {timeout}s")
        return {"session_name": session_name, "error": "timeout"}
    except Exception as e:
        print(f"[{session_name}] Error: {e}")
        return {"session_name": session_name, "error": str(e)}


def resume_claude(session_name: str, session_id: str, prompt: str, timeout: int = 60):
    """
    Resume an existing Claude session with --resume
    """
    print(f"\n[{session_name}] Resuming session {session_id} with: {prompt[:50]}...")

    cmd = [
        CLAUDE_BINARY,
        "--resume", session_id,
        "-p", prompt,
        "--output-format", "stream-json",
        "--dangerously-skip-permissions"
    ]

    env = os.environ.copy()
    env["NCLAUDE_ID"] = session_name

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(Path(__file__).parent.parent),
            env=env
        )

        print(f"[{session_name}] Resume completed. Output lines: {len(result.stdout.splitlines())}")
        return {
            "session_name": session_name,
            "session_id": session_id,
            "stdout_lines": len(result.stdout.splitlines()),
            "returncode": result.returncode
        }

    except subprocess.TimeoutExpired:
        print(f"[{session_name}] Resume timed out")
        return {"error": "timeout"}
    except Exception as e:
        print(f"[{session_name}] Resume error: {e}")
        return {"error": str(e)}


def demo_two_claudes():
    """
    Demo: Two Claudes communicating via nclaude messages
    """
    print("=" * 60)
    print("SWARM POC: Two Claudes Communicating")
    print("=" * 60)

    # Step 1: Claude-A sends a message and creates session
    print("\n--- Step 1: Claude-A sends initial message ---")
    run_nclaude("send", "poc-claude-a", "POC: Claude-A is online and starting work", "--type", "STATUS")

    result_a = spawn_claude_oneshot(
        "poc-claude-a",
        "You are poc-claude-a. Send a message via nclaude: python3 scripts/nclaude.py send poc-claude-a 'Hello from Claude-A! What should we work on?' --type MSG. Then say DONE.",
        timeout=30
    )

    # Step 2: Claude-B reads and responds
    print("\n--- Step 2: Claude-B reads and responds ---")
    run_nclaude("send", "poc-claude-b", "POC: Claude-B checking messages", "--type", "STATUS")

    result_b = spawn_claude_oneshot(
        "poc-claude-b",
        "You are poc-claude-b. First read nclaude messages: python3 scripts/nclaude.py read poc-claude-b --all. Then send a reply: python3 scripts/nclaude.py send poc-claude-b 'Claude-B here! I see your message. Lets coordinate.' --type REPLY. Say DONE when finished.",
        timeout=30
    )

    # Step 3: Check the message log
    print("\n--- Step 3: Verify message exchange ---")
    messages = run_nclaude("read", "--all")

    print("\n" + "=" * 60)
    print("MESSAGE LOG:")
    print("=" * 60)
    if "messages" in messages:
        for msg in messages["messages"][-10:]:
            print(f"  {msg}")

    print("\n" + "=" * 60)
    print("RESULTS:")
    print("=" * 60)
    print(f"Claude-A: {json.dumps(result_a, indent=2)}")
    print(f"Claude-B: {json.dumps(result_b, indent=2)}")

    return result_a, result_b


def demo_resume():
    """
    Demo: Resume a session to check messages
    """
    print("\n" + "=" * 60)
    print("RESUME DEMO: Continue existing session")
    print("=" * 60)

    # First spawn to create a session
    print("\n--- Creating initial session ---")
    result = spawn_claude_oneshot(
        "poc-resume",
        "You are poc-resume. Just say 'Session started' and nothing else.",
        timeout=20
    )

    if result.get("session_id"):
        print(f"\n--- Resuming session {result['session_id']} ---")

        # Add a message for it to find
        run_nclaude("send", "HUMAN", "POC-RESUME: Please acknowledge this message!", "--type", "BROADCAST")

        resume_result = resume_claude(
            "poc-resume",
            result["session_id"],
            "Check for new nclaude messages with: python3 scripts/nclaude.py read poc-resume. Report what you find.",
            timeout=30
        )

        print(f"\nResume result: {json.dumps(resume_result, indent=2)}")
    else:
        print("Could not get session ID from initial spawn")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "resume":
        demo_resume()
    else:
        demo_two_claudes()
