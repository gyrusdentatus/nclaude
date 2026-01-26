"""Command implementations for nclaude CLI."""

from .send import cmd_send
from .read import cmd_read
from .check import cmd_check
from .status import cmd_status
from .clear import cmd_clear
from .whoami import cmd_whoami
from .pending import cmd_pending
from .listen import cmd_listen
from .watch import cmd_watch
from .pair import cmd_pair, cmd_unpair, cmd_peers
from .broadcast import cmd_broadcast
from .chat import cmd_chat
from .hub import cmd_hub, cmd_connect, cmd_hsend, cmd_hrecv
from .alias import cmd_alias
from .wait import cmd_wait
from .resume import cmd_wake, cmd_sessions

__all__ = [
    "cmd_send",
    "cmd_read",
    "cmd_check",
    "cmd_status",
    "cmd_clear",
    "cmd_whoami",
    "cmd_pending",
    "cmd_listen",
    "cmd_watch",
    "cmd_pair",
    "cmd_unpair",
    "cmd_peers",
    "cmd_broadcast",
    "cmd_chat",
    "cmd_hub",
    "cmd_connect",
    "cmd_hsend",
    "cmd_hrecv",
    "cmd_alias",
    "cmd_wait",
    "cmd_wake",
    "cmd_sessions",
]
