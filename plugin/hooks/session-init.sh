#!/bin/bash
# SessionStart hook: Initialize nclaude session
# - Generate semantic session ID: {repo}/{branch}-{instance}
# - Initialize "last seen" message count
# - Initialize Aqua coordination if available

INPUT=$(cat)

# Generate semantic session ID: {repo}/{branch}-{instance}
# This is more meaningful than cc-abc123 random IDs
REPO_NAME=$(basename "$(git rev-parse --show-toplevel 2>/dev/null)" 2>/dev/null || echo "unknown")
BRANCH=$(git branch --show-current 2>/dev/null || echo "main")
BRANCH_SAFE=$(echo "$BRANCH" | tr '/' '-' | tr ' ' '-')

# Find next available instance via aqua ps (if aqua exists)
PREFIX="${REPO_NAME}/${BRANCH_SAFE}"
NCLAUDE_ID="${PREFIX}-1"  # Default

if command -v aqua &> /dev/null; then
    for i in 1 2 3 4 5 6 7 8 9; do
        CANDIDATE="${PREFIX}-${i}"
        if ! aqua ps 2>/dev/null | grep -q "^${CANDIDATE}[[:space:]]"; then
            NCLAUDE_ID="$CANDIDATE"
            break
        fi
    done
fi

# Persist to env file
if [ -n "$CLAUDE_ENV_FILE" ]; then
    echo "export NCLAUDE_ID=\"${NCLAUDE_ID}\"" >> "$CLAUDE_ENV_FILE"
fi

export NCLAUDE_ID

# Initialize Aqua coordination (if aqua is installed AND project has .aqua/)
# NOTE: Aqua is opt-in. User must run 'aqua init' manually to enable it.
AQUA_STATUS=""
if command -v aqua &> /dev/null && [ -d ".aqua" ]; then
    # Add .aqua/ to .gitignore if not already present
    if [ -f ".gitignore" ] && ! grep -q "^\.aqua/$" .gitignore 2>/dev/null; then
        echo ".aqua/" >> .gitignore
    fi

    # Try to refresh existing agent or join as new
    REFRESH_OUT=$(aqua refresh --json 2>/dev/null)
    if [ $? -eq 0 ]; then
        AQUA_STATUS="refreshed"
    else
        # Not registered, join with nclaude ID
        JOIN_OUT=$(aqua join -n "${NCLAUDE_ID}" --json 2>/dev/null)
        if [ $? -eq 0 ]; then
            AQUA_STATUS="joined"
        fi
    fi
fi
# If no .aqua/ directory - don't initialize (user must run 'aqua init' manually)

# Initialize "last seen" count to current total (start fresh)
SEEN_FILE="/tmp/nclaude-seen-${NCLAUDE_ID:-default}"
TOTAL=$(nclaude status 2>/dev/null | jq -r '.message_count // 0')
echo "$TOTAL" > "$SEEN_FILE"

# Check for messages on start
CHECK_OUTPUT=$(nclaude check 2>/dev/null)

# Get whoami info
WHOAMI=$(nclaude whoami 2>/dev/null)

# Check for stale aliases
# Old format: cc-abc123, new format: repo/branch-N
# Stale = same repo/branch prefix but different instance, or old cc-* format
ALIASES_JSON=$(nclaude alias 2>/dev/null | jq -r '.aliases // {}')
STALE_ALIASES=""
if [ "$ALIASES_JSON" != "{}" ] && [ -n "$NCLAUDE_ID" ]; then
    for alias_name in $(echo "$ALIASES_JSON" | jq -r 'keys[]'); do
        target=$(echo "$ALIASES_JSON" | jq -r --arg n "$alias_name" '.[$n]')
        # Skip if it's the current session
        if [[ "$target" == "$NCLAUDE_ID" ]]; then
            continue
        fi
        # Old cc-* format is definitely stale
        if [[ "$target" == cc-* ]]; then
            STALE_ALIASES="${STALE_ALIASES}${alias_name}:${target} "
        # Same repo/branch but different instance number might be stale
        elif [[ "$target" == "${PREFIX}-"* ]] && [[ "$target" != "$NCLAUDE_ID" ]]; then
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
  --arg aqua_status "${AQUA_STATUS:-}" \
  '{
    session_id: $session_id,
    base_dir: $base_dir,
    log_path: $log_path,
    pending_messages: $pending_messages,
    new_messages: $new_messages,
    pending_count: $pending_count,
    new_count: $new_count,
    total: ($pending_count + $new_count)
  } + (if $stale_aliases != "" then {stale_aliases: $stale_aliases, hint: "Run nclaude alias <name> to update stale aliases to current session"} else {} end)
    + (if $aqua_status != "" then {aqua: $aqua_status} else {} end)'

echo "nclaude session initialized: ${NCLAUDE_ID:-default}"
exit 0
