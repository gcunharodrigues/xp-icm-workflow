#!/usr/bin/env bash
#
# git-hook-installer.sh — instala pre-commit hook do workspace ICM.
#
# Idempotente:
#   - Se hook já existe e diff = 0 vs template, skip (no-op).
#   - Se hook existe e diff != 0, faz backup .bak.<timestamp> e overwrite.
#   - Se hook ausente, copia template direto.
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
template="$skill_root/templates/.git-hooks/pre-commit"

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

if [ ! -f "$template" ]; then
  echo "ERROR: template nao encontrado: $template" >&2
  exit 1
fi

target="$git_dir_abs/hooks/pre-commit"
target_dir="$(dirname "$target")"

mkdir -p "$target_dir"

if [ -f "$target" ]; then
  if cmp -s "$template" "$target"; then
    echo "OK    pre-commit hook ja instalado e atualizado (no-op)"
    exit 0
  fi
  ts="$(date -u +%Y%m%dT%H%M%SZ)"
  backup="${target}.bak.${ts}"
  cp "$target" "$backup"
  echo "WARN  hook existente difere do template. Backup: $backup"
fi

cp "$template" "$target"
chmod +x "$target"

if [ ! -x "$target" ]; then
  echo "WARN  chmod +x nao aplicou (filesystem nao suporta?). Hook copiado mas pode nao executar." >&2
fi

echo "OK    pre-commit hook instalado em $target"
