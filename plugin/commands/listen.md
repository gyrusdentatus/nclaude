---
description: Start background listener (deprecated - not needed with aqua)
---

**DEPRECATED:** The listen daemon is no longer needed with aqua backend.

Message notifications are handled by the UserPromptSubmit hook which checks for new messages on every prompt.

Use these instead:
- `/nclaude:check` - Check for unread messages
- `/nclaude:wait 30` - Block until a message arrives
- `/nclaude:watch` - Live message feed (for humans)
