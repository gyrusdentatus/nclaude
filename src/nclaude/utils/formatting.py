"""Message formatting and colorization utilities."""

# ANSI color codes
COLORS = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "red": "\033[1;31m",
    "green": "\033[1;32m",
    "yellow": "\033[1;33m",
    "blue": "\033[1;34m",
    "magenta": "\033[1;35m",
    "cyan": "\033[1;36m",
}


def colorize(text: str, color: str) -> str:
    """Wrap text in ANSI color codes."""
    return f"{COLORS.get(color, '')}{text}{COLORS['reset']}"


def format_message_line(line: str) -> str:
    """Format a single message line with appropriate colors.

    Args:
        line: Raw message line from log

    Returns:
        Colorized line for terminal output
    """
    if line.startswith("<<<["):
        # Multi-line message header
        return colorize(line, "cyan")
    elif line == "<<<END>>>":
        return colorize(line, "cyan")
    elif line.startswith("["):
        # Single-line message - colorize based on type
        if "[URGENT]" in line or "[ERROR]" in line:
            return colorize(line, "red")
        elif "[BROADCAST]" in line or "[HUMAN]" in line:
            return colorize(line, "yellow")
        elif "[STATUS]" in line:
            return colorize(line, "green")
        elif "[TASK]" in line or "[REPLY]" in line:
            return colorize(line, "magenta")
        else:
            return line
    else:
        # Message body content - indent
        return f"  {line}"
