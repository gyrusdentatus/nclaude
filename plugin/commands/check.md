---
description: Check all messages (pending + new) - use this to sync with other Claudes
---

Check for ALL messages from other Claude sessions. This is the recommended command for humans to tell Claude to sync up.

First, check pending messages from daemon:
```
nclaude pending
```

Then, check for any new messages:
```
nclaude read
```

Report all messages found. If no messages from either source, say "All caught up - no new messages."

**Important:** If you're waiting for a reply from another Claude:
- Use `/nclaude:wait 30` to block until a message arrives (up to 30 seconds)
- Or ask the user to trigger you again in a moment - messages arrive between turns, not during idle time
- Claude has no concept of time while idle - new messages only become visible when hooks fire
