---
description: Check for pending messages (deprecated - use check instead)
---

**DEPRECATED:** The listen daemon is no longer needed with aqua backend.

Use `/nclaude:check` instead:

```
nclaude check
```

The messaging system now uses aqua's SQLite database which provides:
- Persistent message storage
- Unread message tracking
- No need for background daemon
