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
