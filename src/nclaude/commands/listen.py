"""Listen command implementation - deprecated with aqua backend."""

import json
from typing import Any, Dict


def cmd_listen(
    interval: int = 5,
) -> None:
    """Run daemon that monitors for new messages.

    DEPRECATED: The listen daemon is not needed with aqua backend.
    Use the UserPromptSubmit hook for message notifications instead.

    Args:
        interval: Polling interval in seconds (ignored)
    """
    print(json.dumps({
        "status": "deprecated",
        "message": "The listen daemon is deprecated with aqua backend.",
        "hint": "Message notifications are handled by UserPromptSubmit hook. "
                "Use 'nclaude check' or 'nclaude wait' for message polling.",
    }), flush=True)
