#!/usr/bin/env python3
"""
swarm.py - Spawn multiple Claude Code sessions to divide work

Usage:
    python3 scripts/swarm.py "Refactor the auth module" --agents 4
    python3 scripts/swarm.py "Fix all type errors in src/" --agents 3
    python3 scripts/swarm.py status  # Check swarm status
"""

import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

CLAUDE_BIN = os.path.expanduser("~/.claude/local/node_modules/.bin/claude")
NCLAUDE_SCRIPT = Path(__file__).parent / "nclaude.py"
SESSION_FILE = Path("/tmp/nclaude/swarm_sessions.json")


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


def spawn_agent(agent_id: str, task: str, timeout: int = 120) -> dict:
    """Spawn a single Claude agent with a task"""
    print(f"[{agent_id}] Starting...")

    cmd = [
        CLAUDE_BIN,
        "-p", task,
        "--output-format", "stream-json",
        "--dangerously-skip-permissions"
    ]

    env = os.environ.copy()
    env["NCLAUDE_ID"] = agent_id

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(Path(__file__).parent.parent),
            env=env
        )

        # Parse output for session_id and response
        session_id = None
        response_text = []

        for line in result.stdout.splitlines():
            try:
                data = json.loads(line)
                if "session_id" in data:
                    session_id = data["session_id"]
                if data.get("type") == "assistant" and "message" in data:
                    # Extract text content
                    msg = data["message"]
                    if isinstance(msg, dict) and "content" in msg:
                        for block in msg["content"]:
                            if block.get("type") == "text":
                                response_text.append(block.get("text", ""))
            except:
                continue

        print(f"[{agent_id}] Completed. Session: {session_id[:8] if session_id else 'N/A'}...")

        return {
            "agent_id": agent_id,
            "session_id": session_id,
            "response": "\n".join(response_text),
            "returncode": result.returncode,
            "success": result.returncode == 0
        }

    except subprocess.TimeoutExpired:
        print(f"[{agent_id}] Timed out after {timeout}s")
        return {"agent_id": agent_id, "error": "timeout", "success": False}
    except Exception as e:
        print(f"[{agent_id}] Error: {e}")
        return {"agent_id": agent_id, "error": str(e), "success": False}


def divide_work(main_task: str, num_agents: int) -> list:
    """Generate task prompts that divide work among agents"""

    # Each agent gets context about the overall task and their role
    prompts = []

    for i in range(num_agents):
        agent_id = f"swarm-{chr(ord('a') + i)}"

        prompt = f"""You are {agent_id}, part of a {num_agents}-agent swarm working on:

MAIN TASK: {main_task}

You are agent {i+1} of {num_agents}. Coordinate via nclaude messages:
- Read messages: python3 scripts/nclaude.py read {agent_id}
- Send messages: python3 scripts/nclaude.py send {agent_id} "your message"

IMPORTANT:
1. First check for existing messages from other agents
2. Claim specific files/areas before working on them
3. Report your progress and findings
4. If you finish early, help others or review their work

Focus on your portion of the work. Be efficient and coordinate."""

        prompts.append((agent_id, prompt))

    return prompts


def spawn_swarm(main_task: str, num_agents: int = 4, timeout: int = 120):
    """Spawn multiple agents to work on a task"""

    print("=" * 60)
    print(f"SPAWNING SWARM: {num_agents} agents")
    print(f"TASK: {main_task}")
    print("=" * 60)

    # Broadcast the task to nclaude log
    run_nclaude("send", "HUMAN", f"SWARM TASK: {main_task} ({num_agents} agents)", "--type", "BROADCAST")

    # Generate prompts for each agent
    prompts = divide_work(main_task, num_agents)

    # Spawn all agents in parallel
    results = []
    with ThreadPoolExecutor(max_workers=num_agents) as executor:
        futures = {
            executor.submit(spawn_agent, agent_id, prompt, timeout): agent_id
            for agent_id, prompt in prompts
        }

        for future in as_completed(futures):
            agent_id = futures[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                results.append({"agent_id": agent_id, "error": str(e), "success": False})

    # Save session info for later resume
    sessions = {r["agent_id"]: r.get("session_id") for r in results if r.get("session_id")}
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    SESSION_FILE.write_text(json.dumps(sessions, indent=2))

    # Print summary
    print("\n" + "=" * 60)
    print("SWARM RESULTS")
    print("=" * 60)

    for r in results:
        status = "✓" if r.get("success") else "✗"
        agent = r.get("agent_id", "unknown")
        session = r.get("session_id", "N/A")[:8] if r.get("session_id") else "N/A"
        print(f"  {status} {agent}: session {session}")

        if r.get("response"):
            # Show first 200 chars of response
            resp = r["response"][:200].replace("\n", " ")
            print(f"      Response: {resp}...")

    print(f"\nSessions saved to: {SESSION_FILE}")

    return results


def resume_agent(agent_id: str, session_id: str, prompt: str, timeout: int = 60):
    """Resume an agent with a new prompt"""
    print(f"[{agent_id}] Resuming session {session_id[:8]}...")

    cmd = [
        CLAUDE_BIN,
        "--resume", session_id,
        "-p", prompt,
        "--output-format", "stream-json",
        "--dangerously-skip-permissions"
    ]

    env = os.environ.copy()
    env["NCLAUDE_ID"] = agent_id

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(Path(__file__).parent.parent),
            env=env
        )
        print(f"[{agent_id}] Resume completed")
        return {"agent_id": agent_id, "success": result.returncode == 0}
    except Exception as e:
        return {"agent_id": agent_id, "error": str(e), "success": False}


def check_status():
    """Check status of swarm sessions"""
    print("=" * 60)
    print("SWARM STATUS")
    print("=" * 60)

    # Load saved sessions
    if SESSION_FILE.exists():
        sessions = json.loads(SESSION_FILE.read_text())
        print(f"\nSaved sessions ({len(sessions)}):")
        for agent_id, session_id in sessions.items():
            print(f"  {agent_id}: {session_id}")
    else:
        print("\nNo saved sessions found.")

    # Check nclaude messages
    print("\nRecent messages:")
    messages = run_nclaude("read", "--all")
    if "messages" in messages:
        for msg in messages["messages"][-10:]:
            print(f"  {msg[:80]}...")


def resume_all(prompt: str):
    """Resume all saved sessions with a new prompt"""
    if not SESSION_FILE.exists():
        print("No saved sessions to resume")
        return

    sessions = json.loads(SESSION_FILE.read_text())

    print(f"Resuming {len(sessions)} agents with: {prompt[:50]}...")

    with ThreadPoolExecutor(max_workers=len(sessions)) as executor:
        futures = [
            executor.submit(resume_agent, agent_id, session_id, prompt)
            for agent_id, session_id in sessions.items()
        ]

        for future in as_completed(futures):
            result = future.result()
            status = "✓" if result.get("success") else "✗"
            print(f"  {status} {result.get('agent_id')}")


def main():
    parser = argparse.ArgumentParser(description="Spawn Claude swarm to divide work")
    parser.add_argument("task", nargs="?", help="Task for the swarm to work on")
    parser.add_argument("--agents", "-n", type=int, default=4, help="Number of agents (default: 4)")
    parser.add_argument("--timeout", "-t", type=int, default=120, help="Timeout per agent in seconds")
    parser.add_argument("--resume", "-r", help="Resume all agents with this prompt")

    args = parser.parse_args()

    if args.task == "status":
        check_status()
    elif args.resume:
        resume_all(args.resume)
    elif args.task:
        spawn_swarm(args.task, args.agents, args.timeout)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
