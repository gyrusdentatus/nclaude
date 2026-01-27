"""Bridge to aqua - all nclaude coordination flows through here.

nclaude is a thin wrapper around aqua. This module provides convenience
functions that handle:
- Session ID management (NCLAUDE_ID env var)
- Project vs global database selection
- Error handling for uninitialized aqua projects

Example usage:
    from nclaude.aqua_bridge import send_message, read_messages, acquire_lock

    send_message("Starting work on auth module")
    messages = read_messages(unread_only=True)
    acquire_lock("src/api.py")
"""

import os
from pathlib import Path
from typing import Optional, List, Dict, Any

# Import aqua library
from aqua import (
    # Database
    Database, get_db, init_db,
    # Managers
    AgentManager, TaskManager, MessageManager, LockManager, SessionManager,
    # Models
    Agent, Task, Message, AgentStatus, TaskStatus,
    # Results
    ClaimResult, AskResult, FileLock,
    # Errors
    AgentError, TaskError, MessageError, LockError, LockConflictError,
    NoCurrentTaskError,
)
# GlobalDatabase is not exported from aqua main module, import from db directly
from aqua.db import GlobalDatabase, get_global_db


# =============================================================================
# Session Identity
# =============================================================================

def get_session_id() -> str:
    """Get current session ID from environment.

    Returns NCLAUDE_ID env var, or generates a fallback from git context.
    """
    if "NCLAUDE_ID" in os.environ:
        return os.environ["NCLAUDE_ID"]

    # Fallback: generate from git context
    import subprocess
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            repo_name = Path(result.stdout.strip()).name
            branch_result = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True, text=True, timeout=5
            )
            branch = branch_result.stdout.strip() if branch_result.returncode == 0 else "main"
            branch_safe = branch.replace("/", "-").replace(" ", "-")
            return f"{repo_name}/{branch_safe}-1"
    except Exception:
        pass

    return "unknown/main-1"


def get_project_path() -> Optional[Path]:
    """Get current project root (git toplevel)."""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return Path(result.stdout.strip())
    except Exception:
        pass
    return None


# =============================================================================
# Database Access
# =============================================================================

def get_project_db() -> Optional[Database]:
    """Get aqua database for current project (.aqua/aqua.db).

    Returns None if aqua is not initialized for this project.
    Run `aqua init` to initialize.
    """
    project_path = get_project_path()
    if project_path is None:
        return None

    aqua_dir = project_path / ".aqua"
    if not aqua_dir.exists():
        return None

    return get_db(project_path)


def get_messaging_db() -> GlobalDatabase:
    """Get global database for cross-project messaging (~/.aqua/global.db).

    This is used for nclaude's cross-project messaging functionality.
    Always available (creates ~/.aqua/ if needed).
    """
    return get_global_db()


def ensure_project_db() -> Database:
    """Get project database, raising error if not initialized."""
    db = get_project_db()
    if db is None:
        raise RuntimeError(
            "Aqua not initialized for this project. "
            "Run 'aqua init' to enable coordination features."
        )
    return db


# =============================================================================
# Agent Management
# =============================================================================

def join_project(name: Optional[str] = None) -> tuple[Agent, bool]:
    """Join the project as an agent.

    Returns (agent, is_leader) tuple.
    """
    db = ensure_project_db()
    agent_name = name or get_session_id()
    manager = AgentManager(db)
    return manager.join(name=agent_name)


def leave_project() -> bool:
    """Leave the project gracefully."""
    db = get_project_db()
    if db is None:
        return False
    manager = AgentManager(db)
    try:
        manager.leave()
        return True
    except AgentError:
        return False


def heartbeat() -> None:
    """Send heartbeat to indicate agent is still alive."""
    db = get_project_db()
    if db is None:
        return
    manager = AgentManager(db)
    try:
        manager.heartbeat()
    except AgentError:
        pass


def get_agent_status() -> Optional[Dict[str, Any]]:
    """Get current agent status."""
    db = get_project_db()
    if db is None:
        return None
    manager = AgentManager(db)
    try:
        state = manager.refresh()
        return {
            "id": state.agent.id,
            "name": state.agent.name,
            "is_leader": state.is_leader,
            "current_task": state.current_task.id if state.current_task else None,
        }
    except AgentError:
        return None


# =============================================================================
# Messaging
# =============================================================================

def send_message(
    content: str,
    to: Optional[str] = None,
    message_type: str = "chat",
    global_: bool = False,
) -> Dict[str, Any]:
    """Send a message.

    Args:
        content: Message content
        to: Recipient (@mention or agent ID). None = broadcast
        message_type: Type of message (chat, task, status, etc.)
        global_: If True, use global messaging (cross-project)

    Returns:
        Dict with message details
    """
    agent_id = get_session_id()

    if global_:
        db = get_messaging_db()
        msg_id = db.send_message(
            from_agent=agent_id,
            content=content,
            to_agent=to.lstrip("@") if to else None,
            message_type=message_type,
        )
        return {"id": msg_id, "from": agent_id, "to": to, "global": True}

    db = get_project_db()
    if db is None:
        # Fallback to global messaging if no project db
        db = get_messaging_db()
        msg_id = db.send_message(
            from_agent=agent_id,
            content=content,
            to_agent=to.lstrip("@") if to else None,
            message_type=message_type,
        )
        return {"id": msg_id, "from": agent_id, "to": to, "global": True}

    manager = MessageManager(db, agent_id)
    msg = manager.send(content, to=to.lstrip("@") if to else None, message_type=message_type)
    return {"id": msg.id, "from": agent_id, "to": to, "global": False}


def read_messages(
    unread_only: bool = True,
    limit: int = 50,
    global_: bool = False,
) -> List[Dict[str, Any]]:
    """Read messages.

    Args:
        unread_only: If True, only return unread messages
        limit: Maximum number of messages to return
        global_: If True, read from global messaging

    Returns:
        List of message dicts
    """
    agent_id = get_session_id()

    if global_:
        db = get_messaging_db()
        messages = db.get_messages(to_agent=agent_id, unread_only=unread_only, limit=limit)
        return messages

    db = get_project_db()
    if db is None:
        # Fallback to global
        db = get_messaging_db()
        messages = db.get_messages(to_agent=agent_id, unread_only=unread_only, limit=limit)
        return messages

    manager = MessageManager(db, agent_id)
    messages = manager.inbox(unread_only=unread_only, limit=limit)
    return [
        {
            "id": m.id,
            "from": m.from_agent,
            "to": m.to_agent,
            "content": m.content,
            "type": m.message_type,
            "created_at": m.created_at.isoformat() if m.created_at else None,
            "read_at": m.read_at.isoformat() if m.read_at else None,
        }
        for m in messages
    ]


def mark_read(message_ids: List[int]) -> int:
    """Mark messages as read. Returns count marked."""
    agent_id = get_session_id()
    db = get_project_db()
    if db is None:
        return 0
    return db.mark_messages_read(agent_id, message_ids)


def ask(
    question: str,
    to: str,
    timeout: int = 60,
) -> Optional[Dict[str, Any]]:
    """Send a blocking question and wait for reply.

    Args:
        question: The question to ask
        to: Recipient agent (@mention or ID)
        timeout: Seconds to wait for reply

    Returns:
        Reply message dict, or None if timeout
    """
    db = ensure_project_db()
    agent_id = get_session_id()
    manager = MessageManager(db, agent_id)

    result = manager.ask(question, to=to.lstrip("@"), timeout=timeout)
    if result.reply:
        return {
            "id": result.reply.id,
            "from": result.reply.from_agent,
            "content": result.reply.content,
            "question_id": result.question_id,
        }
    return None


def reply_to(message_id: int, content: str) -> Dict[str, Any]:
    """Reply to a specific message.

    Args:
        message_id: ID of message to reply to
        content: Reply content

    Returns:
        Reply message dict
    """
    db = ensure_project_db()
    agent_id = get_session_id()
    manager = MessageManager(db, agent_id)

    msg = manager.reply(message_id, content)
    return {"id": msg.id, "from": agent_id, "reply_to": message_id}


# =============================================================================
# File Locking
# =============================================================================

def acquire_lock(file_path: str) -> Dict[str, Any]:
    """Acquire a file lock.

    Args:
        file_path: Path to file to lock (relative to project root)

    Returns:
        Lock info dict

    Raises:
        LockConflictError: If file is already locked by another agent
    """
    db = ensure_project_db()
    agent_id = get_session_id()
    manager = LockManager(db, agent_id)

    lock = manager.acquire(file_path)
    return {
        "file": lock.file_path,
        "agent": lock.agent_id,
        "locked_at": lock.locked_at.isoformat() if lock.locked_at else None,
    }


def release_lock(file_path: str) -> bool:
    """Release a file lock.

    Returns True if released, False if lock didn't exist or wasn't ours.
    """
    db = get_project_db()
    if db is None:
        return False

    agent_id = get_session_id()
    manager = LockManager(db, agent_id)
    return manager.release(file_path)


def get_locks() -> List[Dict[str, Any]]:
    """Get all current file locks."""
    db = get_project_db()
    if db is None:
        return []

    locks = db.get_all_locks()
    return locks


def get_my_locks() -> List[Dict[str, Any]]:
    """Get locks held by current agent."""
    db = get_project_db()
    if db is None:
        return []

    agent_id = get_session_id()
    return db.get_agent_locks(agent_id)


# =============================================================================
# Task Queue
# =============================================================================

def add_task(
    title: str,
    description: Optional[str] = None,
    priority: int = 5,
    tags: Optional[List[str]] = None,
    depends_on: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Add a task to the queue.

    Args:
        title: Task title
        description: Optional detailed description
        priority: 1-10, higher = more urgent
        tags: Optional tags for filtering
        depends_on: Optional list of task IDs this depends on

    Returns:
        Task info dict
    """
    db = ensure_project_db()
    agent_id = get_session_id()
    manager = TaskManager(db, agent_id)

    task = manager.add(
        title=title,
        description=description,
        priority=priority,
        tags=tags,
        depends_on=depends_on,
    )
    return {
        "id": task.id,
        "title": task.title,
        "priority": task.priority,
        "status": task.status.value,
    }


def claim_task() -> Optional[Dict[str, Any]]:
    """Claim the next available task.

    Returns:
        Task info dict, or None if no tasks available
    """
    db = ensure_project_db()
    agent_id = get_session_id()
    manager = TaskManager(db, agent_id)

    result = manager.claim()
    if result.task:
        return {
            "id": result.task.id,
            "title": result.task.title,
            "description": result.task.description,
            "priority": result.task.priority,
            "status": result.task.status.value,
            "role_match": result.role_match,
        }
    return None


def complete_task(summary: Optional[str] = None) -> bool:
    """Mark current task as complete.

    Args:
        summary: Optional completion summary

    Returns:
        True if successful
    """
    db = ensure_project_db()
    agent_id = get_session_id()
    manager = TaskManager(db, agent_id)

    return manager.done(summary=summary)


def fail_task(error: str) -> bool:
    """Mark current task as failed.

    Args:
        error: Error description

    Returns:
        True if successful
    """
    db = ensure_project_db()
    agent_id = get_session_id()
    manager = TaskManager(db, agent_id)

    return manager.fail(error=error)


def report_progress(message: str) -> None:
    """Report progress on current task.

    Also sends a heartbeat.
    """
    db = get_project_db()
    if db is None:
        return

    agent_id = get_session_id()
    manager = TaskManager(db, agent_id)

    try:
        manager.progress(message)
    except NoCurrentTaskError:
        # No task claimed, just send heartbeat
        heartbeat()


def get_task_queue() -> List[Dict[str, Any]]:
    """Get all tasks in the queue."""
    db = get_project_db()
    if db is None:
        return []

    tasks = db.get_all_tasks()
    return [
        {
            "id": t.id,
            "title": t.title,
            "status": t.status.value,
            "priority": t.priority,
            "claimed_by": t.claimed_by,
        }
        for t in tasks
    ]


# =============================================================================
# Aliases
# =============================================================================

def create_alias(alias_name: str, agent_id: Optional[str] = None) -> None:
    """Create an alias for an agent.

    Args:
        alias_name: Alias name (without @)
        agent_id: Agent ID to alias. Defaults to current session.
    """
    agent_id = agent_id or get_session_id()

    # Use global database for cross-project aliases
    db = get_messaging_db()
    project_path = get_project_path()
    db.create_alias(
        alias_name.lstrip("@"),
        agent_id,
        project_path=str(project_path) if project_path else None,
    )


def delete_alias(alias_name: str) -> bool:
    """Delete an alias. Returns True if deleted."""
    db = get_messaging_db()
    return db.delete_alias(alias_name.lstrip("@"))


def get_aliases() -> Dict[str, str]:
    """Get all aliases as {alias: agent_id} dict."""
    db = get_messaging_db()
    aliases = db.get_all_aliases()
    return {a["alias_name"]: a["agent_id"] for a in aliases}


def resolve_alias(name_or_alias: str) -> str:
    """Resolve @mention to agent ID.

    Checks global aliases first, then project aliases.
    Returns the original name if not found.
    """
    clean_name = name_or_alias.lstrip("@")

    # Try global aliases
    db = get_messaging_db()
    alias_info = db.get_alias(clean_name)
    if alias_info:
        return alias_info["agent_id"]

    # Try project database
    pdb = get_project_db()
    if pdb:
        agent = pdb.resolve_agent(clean_name)
        if agent:
            return agent.id

    return clean_name


# =============================================================================
# Status / Info
# =============================================================================

def get_status() -> Dict[str, Any]:
    """Get comprehensive status info."""
    agent_id = get_session_id()
    project_path = get_project_path()

    status = {
        "session_id": agent_id,
        "project": str(project_path) if project_path else None,
        "aqua_initialized": get_project_db() is not None,
    }

    # Add aqua status if initialized
    db = get_project_db()
    if db:
        agents = db.get_all_agents(status=AgentStatus.ACTIVE)
        tasks = db.get_task_counts()
        locks = db.get_all_locks()

        status["agents"] = [
            {"id": a.id, "name": a.name, "task": a.current_task_id}
            for a in agents
        ]
        status["tasks"] = tasks
        status["locks"] = len(locks)

    return status
