---
description: Send real-time message through hub with @mentions
---

Send a message through the nclaude hub (real-time mode).

Usage:
```
/nclaude:hsend @claude-b do the tests
/nclaude:hsend @claude-a @claude-c both review this PR
/nclaude:hsend everyone check the logs  # broadcast to all
```

This requires the hub to be running (`/nclaude:hub start`).

```bash
python3 scripts/client.py send "$*"
```

Messages with @mentions are routed only to those sessions.
Messages without @mentions are broadcast to all connected sessions.
