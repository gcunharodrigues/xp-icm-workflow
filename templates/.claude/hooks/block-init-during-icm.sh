#!/usr/bin/env bash
# block-init-during-icm.sh — PreToolUse hook (v3.4.1).
#
# Blocks invocation of `/init` while an ICM workspace is active (status
# != COMPLETED in workspaces/.index.md). Mitigation G14 from the adversarial
# review of plan v3.3.0.
#
# Reason: `/init` regenerates CLAUDE.md from the code — it can overwrite
# the ICM region (between <!-- ICM-START --> and <!-- ICM-END -->), losing
# the active workspace dashboard.
#
# Doc: references/project-root-claude-md.md (Contract with /init).
#
# PreToolUse usage: hook receives JSON via stdin with `tool_name` and
# `tool_input`. For SlashCommand tool, `tool_input.name == "init"`
# is the trigger.

set -uo pipefail

payload=$(cat)

tool_name=$(echo "$payload" | grep -oE '"tool_name"\s*:\s*"[^"]+"' | head -1 | sed -E 's/.*"([^"]+)"$/\1/')

# Accepts SlashCommand or direct command via Bash
is_init=0
case "$tool_name" in
    SlashCommand)
        slash_name=$(echo "$payload" | grep -oE '"name"\s*:\s*"[^"]+"' | head -1 | sed -E 's/.*"([^"]+)"$/\1/')
        if [ "$slash_name" = "init" ]; then
            is_init=1
        fi
        ;;
esac

if [ "$is_init" -eq 0 ]; then
    exit 0
fi

# Detect active workspace via workspaces/.index.md in cwd
project_root="$(pwd)"
index="$project_root/workspaces/.index.md"
active_workspace=""
if [ -f "$index" ]; then
    while IFS= read -r line; do
        if echo "$line" | grep -Eq '^\| *[0-9]{3} *\|'; then
            status=$(echo "$line" | awk -F'|' '{print $6}' | sed 's/ *//g')
            id=$(echo "$line" | awk -F'|' '{print $2}' | sed 's/ *//g')
            slug=$(echo "$line" | awk -F'|' '{print $3}' | sed 's/ *//g')
            if [ -n "$slug" ] && [ "$status" != "COMPLETED" ]; then
                active_workspace="${id}-${slug}"
                break
            fi
        fi
    done < "$index"
fi

if [ -z "$active_workspace" ]; then
    exit 0  # no active workspace, /init is free
fi

cat >&2 <<EOM
ICM guardrail: /init blocked while ICM workspace is active.

Active workspace: $active_workspace
Project root:     $project_root

Reason: /init regenerates CLAUDE.md from the project code and can
overwrite the ICM region (between <!-- ICM-START --> and <!-- ICM-END -->)
which contains the active workspace dashboard. Future sessions would lose
context and the current session would be orphaned.

To regenerate the codebase portion of CLAUDE.md without touching the ICM region:
  1. Close the workspace ($active_workspace) via Exit A of stage 08.
  2. After status=COMPLETED in .index.md, /init operates freely
     (the ICM region is already in idle mode).

Doc: references/project-root-claude-md.md.
EOM

exit 1
