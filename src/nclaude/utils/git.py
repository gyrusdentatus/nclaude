"""Git detection utilities for nclaude."""

import subprocess
from pathlib import Path
from typing import Optional, Tuple


def get_git_info() -> Tuple[Optional[Path], Optional[str], Optional[str]]:
    """Get git repo info for smart defaults.

    Returns:
        Tuple of (git_common_dir, repo_name, branch_name).
        All None if not in a git repo.
    """
    try:
        # Get git common dir (works for worktrees too)
        # For worktrees, this points to main repo's .git dir
        git_common = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            capture_output=True, text=True, timeout=5
        )
        if git_common.returncode != 0:
            return None, None, None

        common_dir = Path(git_common.stdout.strip()).resolve()

        # Derive repo name from common_dir (works for both regular repos and worktrees)
        # common_dir is either:
        #   - /path/to/repo/.git (regular repo) -> repo name is parent.name
        #   - /path/to/repo/.git (from worktree) -> same, repo name is parent.name
        if common_dir.name == ".git":
            repo_name = common_dir.parent.name
        else:
            # Fallback to show-toplevel if common_dir structure is unexpected
            repo_root = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True, text=True, timeout=5
            )
            repo_name = Path(repo_root.stdout.strip()).name if repo_root.returncode == 0 else "unknown"

        # Get current branch
        branch = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, timeout=5
        )
        branch_name = branch.stdout.strip() if branch.returncode == 0 else "detached"

        return common_dir, repo_name, branch_name
    except Exception:
        return None, None, None


def get_auto_session_id() -> str:
    """Generate session ID from git context.

    Returns:
        Session ID in format '{repo_name}-{branch}' or 'claude' as fallback.
        NCLAUDE_ID env var takes precedence if set.
    """
    import os

    if "NCLAUDE_ID" in os.environ:
        return os.environ["NCLAUDE_ID"]

    _, repo_name, branch_name = get_git_info()
    if repo_name and branch_name:
        # Sanitize branch name (replace / with -)
        branch_safe = branch_name.replace("/", "-")
        return f"{repo_name}-{branch_safe}"

    return "claude"
