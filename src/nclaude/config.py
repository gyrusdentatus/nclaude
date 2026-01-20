"""Configuration management for nclaude.

Environment-first configuration with git-aware defaults.
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

from .utils.git import get_git_info, get_auto_session_id

# Global paths
NCLAUDE_HOME = Path.home() / ".nclaude"
ALIASES_PATH = NCLAUDE_HOME / "aliases.json"


def load_aliases() -> Dict[str, str]:
    """Load alias mappings from ~/.nclaude/aliases.json.

    Aliases allow using short names like @main to address nclaude-main.

    Returns:
        Dict mapping alias -> full session ID
    """
    if not ALIASES_PATH.exists():
        return {}
    try:
        return json.loads(ALIASES_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def save_aliases(aliases: Dict[str, str]) -> None:
    """Save alias mappings to ~/.nclaude/aliases.json.

    Args:
        aliases: Dict mapping alias -> full session ID
    """
    NCLAUDE_HOME.mkdir(parents=True, exist_ok=True)
    ALIASES_PATH.write_text(json.dumps(aliases, indent=2))


def resolve_recipient(target: str) -> str:
    """Resolve @mention target to actual session ID.

    Handles:
        - nclaude/branch -> nclaude-branch
        - aliases from ~/.nclaude/aliases.json
        - passthrough for already-resolved names

    Args:
        target: Raw @mention target (without @)

    Returns:
        Resolved session ID
    """
    # Handle nclaude/branch syntax -> nclaude-branch
    if target.startswith("nclaude/"):
        return f"nclaude-{target[8:]}"

    # Check aliases
    aliases = load_aliases()
    if target in aliases:
        return aliases[target]

    # Passthrough
    return target


@dataclass
class Config:
    """nclaude configuration with computed paths.

    Attributes:
        base_dir: Base directory for nclaude data
        session_id: Current session identifier
        is_global: Whether using global room
    """
    base_dir: Path = field(default_factory=lambda: Path("/tmp/nclaude"))
    session_id: str = "claude"
    is_global: bool = False

    @property
    def log_path(self) -> Path:
        """Path to messages.log file."""
        return self.base_dir / "messages.log"

    @property
    def lock_path(self) -> Path:
        """Path to lock file."""
        return self.base_dir / ".lock"

    @property
    def sessions_dir(self) -> Path:
        """Path to sessions directory (read pointers)."""
        return self.base_dir / "sessions"

    @property
    def pending_dir(self) -> Path:
        """Path to pending directory (daemon notifications)."""
        return self.base_dir / "pending"

    @property
    def project_name(self) -> str:
        """Get current project name from base_dir."""
        return self.base_dir.name

    def init(self) -> None:
        """Initialize workspace directories."""
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.log_path.touch()
        self.lock_path.touch()


def get_base_dir(override: Optional[str] = None, use_global: bool = False) -> Path:
    """Get nclaude base directory.

    Args:
        override: Explicit directory override (--dir flag or NCLAUDE_DIR)
        use_global: If True, use global room at ~/.nclaude/

    Returns:
        Path to base directory
    """
    # Global room takes precedence
    if use_global:
        return Path.home() / ".nclaude"

    # Explicit override
    if override:
        # If it's just a name, resolve relative to /tmp/nclaude/
        if "/" not in override:
            return Path(f"/tmp/nclaude/{override}")
        # If it's a path, try to get git repo name from it
        import subprocess
        try:
            result = subprocess.run(
                ["git", "-C", override, "rev-parse", "--show-toplevel"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                repo_name = Path(result.stdout.strip()).name
                return Path(f"/tmp/nclaude/{repo_name}")
            else:
                # Not a git repo, use directory name
                return Path(f"/tmp/nclaude/{Path(override).name}")
        except Exception:
            return Path(f"/tmp/nclaude/{Path(override).name}")

    # Env var override
    if "NCLAUDE_DIR" in os.environ:
        return Path(os.environ["NCLAUDE_DIR"])

    # Try git-aware path
    _, repo_name, _ = get_git_info()
    if repo_name:
        return Path(f"/tmp/nclaude/{repo_name}")

    # Fallback for non-git directories
    return Path("/tmp/nclaude")


def create_config(
    dir_override: Optional[str] = None,
    session_override: Optional[str] = None,
    use_global: bool = False,
) -> Config:
    """Create a Config instance with proper defaults.

    Args:
        dir_override: Explicit directory (--dir flag)
        session_override: Explicit session ID
        use_global: Whether to use global room

    Returns:
        Configured Config instance
    """
    base_dir = get_base_dir(dir_override, use_global)
    session_id = session_override or get_auto_session_id()

    return Config(
        base_dir=base_dir,
        session_id=session_id,
        is_global=use_global,
    )


# Global peers file (shared across all projects)
PEERS_FILE = Path("/tmp/nclaude/.peers")
