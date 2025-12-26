---
description: Control the nclaude real-time hub (start/stop/status)
---

Control the nclaude Unix socket hub for real-time messaging.

Usage:
```
/nclaude:hub start   # Start the hub server
/nclaude:hub stop    # Stop the hub server
/nclaude:hub status  # Check hub status
```

Start the hub:
```bash
python3 scripts/hub.py start &
```

Check status:
```bash
python3 scripts/hub.py status
```

Stop the hub:
```bash
python3 scripts/hub.py stop
```

The hub enables real-time @mention routing between Claude sessions.
