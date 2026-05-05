#!/usr/bin/env bash
# context-check.sh — PostToolUse hook that detects context >= 70%
# and triggers a mandatory early handoff (ICM protocol).
#
# Reads transcript directly (independent of statusline.sh).
# Cooldown of 60s between alerts (1 per minute, not per tool call).
# Threshold: 70% — margin to complete handoff before real compact (~90%).
#
# Installation: .claude/settings.local.json → hooks.PostToolUse → "bash workspaces/<NNN-slug>/.claude/hooks/context-check.sh"
# Bootstrap: ICM stage 00 (governance infrastructure).
#
# Race-safe: uses atomic mkdir as lock. Concurrent instances
# (e.g.: 4 Agent calls in parallel) skip automatically.

# NO set -e — pipefail alone + manual exits. set -e breaks
# pipes that legitimately return empty (find with no results).
set -uo pipefail

THRESHOLD=70
COOLDOWN_SEC=60

# 1. Concurrent lock via mkdir (atomic on POSIX and Windows Git Bash).
# If another instance is running (e.g.: during subagent spawn),
# skip immediately without blocking.
LOCKDIR="/tmp/claude-ctx-check-$(basename "$(pwd)")"
if ! mkdir "$LOCKDIR" 2>/dev/null; then
    # Another instance running. Check if it is stale (>120s).
    lock_age=999
    if stat -c %Y "$LOCKDIR" >/dev/null 2>&1; then
        lock_mtime=$(stat -c %Y "$LOCKDIR" 2>/dev/null || echo 0)
    elif stat -f %m "$LOCKDIR" >/dev/null 2>&1; then
        lock_mtime=$(stat -f %m "$LOCKDIR" 2>/dev/null || echo 0)
    else
        lock_mtime=0
    fi
    now=$(date +%s)
    lock_age=$(( now - lock_mtime ))
    # Stale lock — remove and continue.
    if (( lock_age > 120 )); then
        rmdir "$LOCKDIR" 2>/dev/null || exit 0
    else
        exit 0
    fi
fi
# Ensure lock cleanup on exit.
trap 'rmdir "$LOCKDIR" 2>/dev/null' EXIT

# 2. Guard against interrupting an in-progress git operation.
git_dir="$(git rev-parse --git-dir 2>/dev/null || echo .git)"
if [ -d "${git_dir}/rebase-merge" ] || [ -d "${git_dir}/rebase-apply" ]; then
    exit 0
fi
if [ -f "${git_dir}/MERGE_MSG" ] || [ -f "${git_dir}/CHERRY_PICK_HEAD" ]; then
    exit 0
fi
if [ -f "${git_dir}/index.lock" ]; then
    exit 0
fi

# 3. Find the most recently modified transcript within the last 5 min.
# Pipe without pipefail here — empty find is not an error, just "nothing to do".
transcript=""
# shellcheck disable=SC2155
transcript=$(find "$HOME/.claude/projects" -name "*.jsonl" -mmin -5 2>/dev/null | head -1) || true
# If find returned multiple files, pick the most recent one
if [ -n "$transcript" ] && command -v ls >/dev/null 2>&1; then
    # Pick the most recent file among the ones found
    most_recent=$(find "$HOME/.claude/projects" -name "*.jsonl" -mmin -5 2>/dev/null | xargs ls -t 2>/dev/null | head -1) || true
    if [ -n "$most_recent" ]; then
        transcript="$most_recent"
    fi
fi
[ -z "$transcript" ] && exit 0
[ ! -f "$transcript" ] && exit 0

# 4. Extract the last usage entry from the transcript.
last_usage=""
last_usage=$(tail -n 300 "$transcript" 2>/dev/null | grep '"usage"' | tail -n 1) || true
[ -z "$last_usage" ] && exit 0

# 5. Parse tokens (jq required — documented dependency).
if ! command -v jq >/dev/null 2>&1; then
    exit 0
fi

inp=$(echo "$last_usage" | jq -r '.message.usage.input_tokens // 0' 2>/dev/null) || inp=0
cc=$(echo "$last_usage"  | jq -r '.message.usage.cache_creation_input_tokens // 0' 2>/dev/null) || cc=0
cr=$(echo "$last_usage"  | jq -r '.message.usage.cache_read_input_tokens // 0' 2>/dev/null) || cr=0
ctx_used=$(( inp + cc + cr ))

# 6. Detect context window (1M for [1m] models, 200k default).
model_id=$(echo "$last_usage" | jq -r '.model // ""' 2>/dev/null) || model_id=""
if echo "$model_id" | grep -qi '\[1m\]\|1M'; then
    ctx_window=1000000
else
    ctx_window=200000
fi

ctx_pct=$(( ctx_used * 100 / ctx_window ))
(( ctx_pct < THRESHOLD )) && exit 0

# 7. Cooldown: 1 alert per minute.
ALERT_LOCK="/tmp/claude-ctx-alert-$(basename "$(pwd)")"
now=$(date +%s)
if [ -f "$ALERT_LOCK" ]; then
    alert_mtime=$(stat -c %Y "$ALERT_LOCK" 2>/dev/null || stat -f %m "$ALERT_LOCK" 2>/dev/null || echo 0)
    alert_age=$(( now - alert_mtime ))
    (( alert_age < COOLDOWN_SEC )) && exit 0
fi
touch "$ALERT_LOCK"

cat <<EOF
================================================================================
⚠ CONTEXT AT ${ctx_pct}% — MANDATORY EARLY HANDOFF
================================================================================

STOP everything. Degraded context = ICM protocol violated.

Execute early handoff now:

1. Update _kickoff.md with cumulative progress
   - Add prev_outputs from the completed task
   - Remove completed tasks from pending_for_this_stage

2. Update L1 (CONTEXT.md) with current sub_stage

3. Intermediate commit (outputs + L1 + _kickoff.md)
   git add workspaces/<NNN>/stages/04_implementation_waves/output/ \
           workspaces/<NNN>/CONTEXT.md \
           workspaces/<NNN>/stages/04_implementation_waves/_kickoff.md
   git commit -m "workspace <NNN>: context checkpoint + early handoff"

4. Print KICKOFF block verbally to the user

5. EXIT the session — user opens a new one with the KICKOFF prompt

DO NOT keep working. Handoff first.
================================================================================
EOF
