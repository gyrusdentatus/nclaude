---
description: Connect to nclaude hub for real-time messaging
---

Connect this Claude session to the nclaude hub.

```bash
python3 scripts/client.py connect "${NCLAUDE_ID:-$(git rev-parse --show-toplevel | xargs basename)-$(git rev-parse --abbrev-ref HEAD)}"
```

After connecting, you can:
- Send messages: `/nclaude:hsend @claude-b hello`
- Receive messages: `/nclaude:hrecv`
- See who's online: The connect response shows online sessions

Requires hub to be running (`/nclaude:hub start`).
