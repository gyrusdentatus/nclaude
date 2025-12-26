---
description: Receive real-time messages from hub
---

Receive messages from the nclaude hub.

```bash
python3 scripts/client.py recv --timeout ${1:-5}
```

Options:
- `--timeout N` - Wait up to N seconds for a message (default: 5)

Returns the next message in the queue, or empty if no messages.

Use this after `/nclaude:connect` to receive real-time messages from other Claude sessions.
