---
description: Check all messages (pending + new) - use this to sync with other Claudes
---

Check for ALL unread messages from other Claude sessions. This is the recommended command for humans to tell Claude to sync up.

```
nclaude check
```

Report all messages found. If no messages, say "All caught up - no new messages."

**Note:** nclaude messaging is now backed by aqua. Messages persist in:
- Project: `.aqua/aqua.db` (if aqua init was run)
- Global: `~/.aqua/global.db`

**Important:** If you're waiting for a reply from another Claude:
- Use `/nclaude:wait 30` to block until a message arrives (up to 30 seconds)
- Or ask the user to trigger you again - messages arrive between turns
