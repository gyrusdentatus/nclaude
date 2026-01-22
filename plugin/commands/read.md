---
description: Read new messages from other Claude sessions
---

Read new messages from the nclaude chat. Execute this command:

```
nclaude read
```

Optional filters:
```
nclaude read --limit 10        # Limit to 10 messages
nclaude read --filter TASK     # Only TASK messages
nclaude read --all             # All messages (not just new)
```

Display any new messages in a readable format. If no new messages, say "No new messages."
