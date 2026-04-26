#!/usr/bin/env bash
#
# git-hook-installer.sh — instala hooks ICM (pre-commit + commit-msg).
#
# Idempotente por hook:
#   - Se ja existe e diff = 0 vs template, skip (no-op).
#   - Se existe e diff != 0, faz backup .bak.<timestamp> e overwrite.
#   - Se ausente, copia template direto.
#
# Por que 2 hooks: stages canonicos do git separam file checks
# (pre-commit) de msg validation (commit-msg). Pre-commit nao ve a
# msg do commit atual — ler COMMIT_EDITMSG retorna msg do anterior.
# Detalhes em references/git-hooks.md.
#
# Uso:
#   bash scripts/git-hook-installer.sh <project_root>

set -euo pipefail

if [ "$#" -lt 1 ]; then
  echo "ERROR: uso: bash scripts/git-hook-installer.sh <project_root>" >&2
  exit 1
fi

project_root="$1"
script_dir="$(cd "$(dirname "$0")" && pwd)"
skill_root="$(dirname "$script_dir")"
templates_dir="$skill_root/templates/.git-hooks"

if [ ! -d "$project_root" ]; then
  echo "ERROR: project_root nao existe: $project_root" >&2
  exit 1
fi

git_dir="$(git -C "$project_root" rev-parse --git-dir 2>/dev/null || true)"

if [ -z "$git_dir" ]; then
  echo "ERROR: project_root nao eh repo git: $project_root" >&2
  exit 1
fi

case "$git_dir" in
  /*)  git_dir_abs="$git_dir" ;;
  *)   git_dir_abs="$project_root/$git_dir" ;;
esac

hooks_dir="$git_dir_abs/hooks"
mkdir -p "$hooks_dir"

# Lista canonica de hooks gerenciados pela skill
HOOKS="pre-commit commit-msg"

ts="$(date -u +%Y%m%dT%H%M%SZ)"
status_overall=0

for hook in $HOOKS; do
  template="$templates_dir/$hook"
  target="$hooks_dir/$hook"

  if [ ! -f "$template" ]; then
    echo "ERROR: template nao encontrado: $template" >&2
    status_overall=1
    continue
  fi

  if [ -f "$target" ]; then
    if cmp -s "$template" "$target"; then
      echo "OK    $hook ja instalado e atualizado (no-op)"
      continue
    fi
    backup="${target}.bak.${ts}"
    cp "$target" "$backup"
    echo "WARN  $hook existente difere do template. Backup: $backup"
  fi

  cp "$template" "$target"
  chmod +x "$target"

  if [ ! -x "$target" ]; then
    echo "WARN  chmod +x nao aplicou em $hook (filesystem nao suporta?). Hook copiado mas pode nao executar." >&2
  fi

  echo "OK    $hook instalado em $target"
done

exit "$status_overall"
