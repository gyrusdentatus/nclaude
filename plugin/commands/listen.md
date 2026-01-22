---
description: Start background listener for incoming messages
argument-hint: [interval-seconds]
---

Start the nclaude listen daemon in the background. This monitors for new messages and queues them for the `pending` command.

**Note for humans**: Run this in a separate terminal:

```bash
nclaude listen --interval ${1:-5}
```

The daemon will:
- Check for new messages every N seconds (default: 5)
- Write pending message IDs to a queue file
- Ring the terminal bell when new messages arrive

Use `Ctrl+C` to stop the listener.

**For Claude sessions**: The listener runs in the user's terminal, not inside Claude. Tell the user to start it manually if they want real-time notifications.
