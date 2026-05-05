#!/usr/bin/env bash
# icm-session-check.sh — SessionStart hook (v3.4.0).
#
# Runs once when Claude Code opens a session in the project_root. Validates:
#   1. current branch = active workspace branch (if there is a workspace IN_PROGRESS).
#   2. `.icm-main/` worktree exists.
#   3. `.icm-main/` is checked out at base_branch.
#
# Prints a warning to stdout (visible in chat) if something is wrong. Does not block
# session start — only signals the human.
#
# Doc: references/worktree-model.md + references/git-hooks.md.
#
# Usage:
#   `.claude/settings.local.json` points the SessionStart hook to this script.
#   Absolute path resolved via $PROJECT_ROOT (Claude Code passes cwd).

set -uo pipefail

project_root="$(pwd)"

# Detect active workspace via L1 (`workspaces/<NNN>/CONTEXT.md` frontmatter).
# v3.7.1: prefers L1 over `.index.md` — L1 is canonical, index is a cache
# that can go stale (pre-v3.7.1 bug: exits A/C updated L1 but not index).
# Iterates dirs in workspaces/, reads status from frontmatter, first NON-COMPLETED is active.
ws_dir="$project_root/workspaces"
active_workspace=""
if [ -d "$ws_dir" ]; then
    # Sort by name (NNN-slug ascending) for determinism.
    for ctx in "$ws_dir"/*/CONTEXT.md; do
        [ -f "$ctx" ] || continue
        # Frontmatter status: extract the `status: <VALUE>` line from the initial YAML block
        # (between the first 2 occurrences of `^---$`).
        status=$(awk '
            BEGIN { in_fm=0; count=0 }
            /^---$/ { count++; if (count==1) { in_fm=1; next } else { exit } }
            in_fm && /^status:/ { sub(/^status: */, ""); gsub(/["\047]/, ""); print; exit }
        ' "$ctx" 2>/dev/null | head -1 | tr -d '[:space:]')
        if [ -n "$status" ] && [ "$status" != "COMPLETED" ]; then
            ws_basename=$(basename "$(dirname "$ctx")")
            active_workspace="$ws_basename"
            break
        fi
    done
fi

# No active workspace → nothing to check
if [ -z "$active_workspace" ]; then
    exit 0
fi

# Detect current branch in project_root
current_branch=$(git -C "$project_root" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
expected_ws_branch="workspace/${active_workspace}"

warnings=()

if [ "$current_branch" != "$expected_ws_branch" ]; then
    warnings+=(
        "⚠️  Current branch in $project_root is '$current_branch', expected '$expected_ws_branch' (active workspace)."
        "    To resume the ICM workspace, run: git -C \"$project_root\" checkout $expected_ws_branch"
    )
fi

# Validate .icm-main/ worktree
worktree="$project_root/.icm-main"
if [ ! -d "$worktree" ]; then
    # Detect base_branch from L1
    l1="$project_root/workspaces/$active_workspace/CONTEXT.md"
    base_branch=""
    if [ -f "$l1" ]; then
        base_branch=$(grep -E '^base_branch:' "$l1" | head -1 | sed -E 's/^base_branch: *"?([^"]+)"?/\1/')
    fi
    base_branch="${base_branch:-main}"
    warnings+=(
        "⚠️  '.icm-main/' worktree missing in $project_root."
        "    Cross-branch model v3.4.0 requires a worktree linked to the base branch."
        "    To create: git -C \"$project_root\" worktree add .icm-main $base_branch"
    )
else
    wt_branch=$(git -C "$worktree" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
    l1="$project_root/workspaces/$active_workspace/CONTEXT.md"
    base_branch=""
    if [ -f "$l1" ]; then
        base_branch=$(grep -E '^base_branch:' "$l1" | head -1 | sed -E 's/^base_branch: *"?([^"]+)"?/\1/')
    fi
    base_branch="${base_branch:-main}"
    if [ -n "$wt_branch" ] && [ "$wt_branch" != "$base_branch" ]; then
        warnings+=(
            "⚠️  '.icm-main/' worktree is on '$wt_branch', expected '$base_branch'."
            "    To fix: cd $worktree && git checkout $base_branch"
        )
    fi
fi

if [ ${#warnings[@]} -gt 0 ]; then
    echo "════════════════════════════════════════════════════════════════"
    echo "ICM SessionStart check — workspace $active_workspace"
    echo "════════════════════════════════════════════════════════════════"
    for w in "${warnings[@]}"; do
        echo "$w"
    done
    echo "════════════════════════════════════════════════════════════════"
fi

exit 0
