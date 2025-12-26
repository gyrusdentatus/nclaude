---
description: Check all messages (pending + new) - use this to sync with other Claudes
---

Check for ALL messages from other Claude sessions. This is the recommended command for humans to tell Claude to sync up.

First, check pending messages from daemon:
```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/nclaude.py pending "${NCLAUDE_ID:-claude}"
```

Then, check for any new messages:
```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/nclaude.py read "${NCLAUDE_ID:-claude}"
```

Report all messages found. If no messages from either source, say "All caught up - no new messages."
