---
description: Block until message arrives or timeout (for waiting on replies)
---

Wait for new messages to arrive. Blocks until a message comes in or timeout is reached.

**Usage:**
```bash
nclaude wait          # Wait up to 30 seconds (default)
nclaude wait 60       # Wait up to 60 seconds
nclaude wait 10       # Wait up to 10 seconds
```

**Arguments:** `$ARGUMENTS` (optional timeout in seconds, default 30)

```bash
nclaude wait $ARGUMENTS
```

**When to use:**
- After sending a SYN message, waiting for ACK
- When you sent a question and expect a reply
- Coordinating with another Claude session

**Results:**
- If messages arrive: Returns the new messages with `waited` field showing seconds elapsed
- If timeout: Returns `{"timeout": true, "waited": 30}` with a hint to try again later

**Note:** Maximum wait is 5 minutes (300s) to prevent infinite blocking. If you need longer waits, use `/nclaude:check` periodically instead.
