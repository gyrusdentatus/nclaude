#!/bin/bash
# SessionStart hook: Initialize nclaude session
# - Set NCLAUDE_ID from Claude Code session_id
# - Initialize "last seen" message count

INPUT=$(cat)

# Extract session_id
CC_SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // empty' 2>/dev/null)
if [ -n "$CC_SESSION_ID" ]; then
    SHORT_ID=$(echo "$CC_SESSION_ID" | cut -c1-12)
    NCLAUDE_ID="cc-${SHORT_ID}"

    # Persist to env file
    if [ -n "$CLAUDE_ENV_FILE" ]; then
        echo "export NCLAUDE_ID=\"${NCLAUDE_ID}\"" >> "$CLAUDE_ENV_FILE"
    fi

    export NCLAUDE_ID
fi

# Initialize "last seen" count to current total (start fresh)
SEEN_FILE="/tmp/nclaude-seen-${NCLAUDE_ID:-default}"
TOTAL=$(nclaude status 2>/dev/null | jq -r '.message_count // 0')
echo "$TOTAL" > "$SEEN_FILE"

# Check for messages on start
CHECK_OUTPUT=$(nclaude check 2>/dev/null)

# Get whoami info
WHOAMI=$(nclaude whoami 2>/dev/null)

# Check for stale aliases and auto-update ones pointing to previous cc-* sessions
ALIASES_JSON=$(nclaude alias 2>/dev/null | jq -r '.aliases // {}')
STALE_ALIASES=""
if [ "$ALIASES_JSON" != "{}" ] && [ -n "$NCLAUDE_ID" ]; then
    # Find aliases pointing to cc-* that aren't current session
    for alias_name in $(echo "$ALIASES_JSON" | jq -r 'keys[]'); do
        target=$(echo "$ALIASES_JSON" | jq -r --arg n "$alias_name" '.[$n]')
        # If target is a cc-* session but not current, it might be stale
        if [[ "$target" == cc-* ]] && [[ "$target" != "$NCLAUDE_ID" ]]; then
            STALE_ALIASES="${STALE_ALIASES}${alias_name}:${target} "
        fi
    done
fi
BASE_DIR=$(echo "$WHOAMI" | jq -r '.base_dir // empty')
LOG_PATH=$(echo "$WHOAMI" | jq -r '.log_path // empty')

# Parse check output for message counts
PENDING_COUNT=$(echo "$CHECK_OUTPUT" | jq -r '.pending_count // 0')
NEW_COUNT=$(echo "$CHECK_OUTPUT" | jq -r '.new_count // 0')
PENDING_MSGS=$(echo "$CHECK_OUTPUT" | jq -c '.pending_messages // []')
NEW_MSGS=$(echo "$CHECK_OUTPUT" | jq -c '.new_messages // []')

# Output JSON with full identity and message status
STALE_ARG=""
if [ -n "$STALE_ALIASES" ]; then
    STALE_ARG="--arg stale_aliases \"$STALE_ALIASES\""
fi

jq -n \
  --arg session_id "${NCLAUDE_ID:-unknown}" \
  --arg base_dir "$BASE_DIR" \
  --arg log_path "$LOG_PATH" \
  --argjson pending_messages "$PENDING_MSGS" \
  --argjson new_messages "$NEW_MSGS" \
  --argjson pending_count "$PENDING_COUNT" \
  --argjson new_count "$NEW_COUNT" \
  --arg stale_aliases "${STALE_ALIASES:-}" \
  '{
    session_id: $session_id,
    base_dir: $base_dir,
    log_path: $log_path,
    pending_messages: $pending_messages,
    new_messages: $new_messages,
    pending_count: $pending_count,
    new_count: $new_count,
    total: ($pending_count + $new_count)
  } + (if $stale_aliases != "" then {stale_aliases: $stale_aliases, hint: "Run nclaude alias <name> to update stale aliases to current session"} else {} end)'

echo "nclaude session initialized: ${NCLAUDE_ID:-default}"
exit 0
