#!/usr/bin/env bash
#
# git-hook-installer.sh — install ICM hooks (pre-commit + commit-msg).
#
# Idempotent per hook:
#   - If already exists and diff = 0 vs template, skip (no-op).
#   - If exists and diff != 0, backup as .bak.<timestamp> and overwrite.
#   - If absent, copy template directly.
#
# Why 2 hooks: canonical git stages separate file checks
# (pre-commit) from msg validation (commit-msg). pre-commit cannot see the
# current commit message — reading COMMIT_EDITMSG returns the previous one.
# Details in references/git-hooks.md.
#
# Usage:
#   bash scripts/git-hook-installer.sh <project_root>

set -euo pipefail

if [ "$#" -lt 1 ]; then
  echo "ERROR: usage: bash scripts/git-hook-installer.sh <project_root>" >&2
  exit 1
fi

project_root="$1"
script_dir="$(cd "$(dirname "$0")" && pwd)"
skill_root="$(dirname "$script_dir")"
templates_dir="$skill_root/templates/.git-hooks"

if [ ! -d "$project_root" ]; then
  echo "ERROR: project_root does not exist: $project_root" >&2
  exit 1
fi

git_dir="$(git -C "$project_root" rev-parse --git-dir 2>/dev/null || true)"

if [ -z "$git_dir" ]; then
  echo "ERROR: project_root is not a git repo: $project_root" >&2
  exit 1
fi

case "$git_dir" in
  /*)  git_dir_abs="$git_dir" ;;
  *)   git_dir_abs="$project_root/$git_dir" ;;
esac

hooks_dir="$git_dir_abs/hooks"
mkdir -p "$hooks_dir"

# Canonical list of hooks managed by the skill
HOOKS="pre-commit commit-msg"

ts="$(date -u +%Y%m%dT%H%M%SZ)"
status_overall=0

for hook in $HOOKS; do
  template="$templates_dir/$hook"
  target="$hooks_dir/$hook"

  if [ ! -f "$template" ]; then
    echo "ERROR: template not found: $template" >&2
    status_overall=1
    continue
  fi

  if [ -f "$target" ]; then
    if cmp -s "$template" "$target"; then
      echo "OK    $hook already installed and up to date (no-op)"
      continue
    fi
    backup="${target}.bak.${ts}"
    cp "$target" "$backup"
    echo "WARN  $hook exists but differs from template. Backup: $backup"
  fi

  cp "$template" "$target"
  chmod +x "$target"

  if [ ! -x "$target" ]; then
    echo "WARN  chmod +x did not apply to $hook (filesystem unsupported?). Hook copied but may not execute." >&2
  fi

  echo "OK    $hook instalado em $target"
done

exit "$status_overall"
