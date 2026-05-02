#!/usr/bin/env bash
# icm-session-check.sh — SessionStart hook (v3.4.0).
#
# Roda 1× quando Claude Code abre sessão no project_root. Valida:
#   1. branch atual = workspace branch ativo (se houver workspace IN_PROGRESS).
#   2. `.icm-main/` worktree existe.
#   3. `.icm-main/` checada em base_branch.
#
# Imprime warning na stdout (visível no chat) se algo errado. Não bloqueia
# session start — só sinaliza humano.
#
# Doc: references/worktree-model.md + references/git-hooks.md.
#
# Uso:
#   `.claude/settings.local.json` aponta hook SessionStart para este script.
#   Path absoluto resolvido via $PROJECT_ROOT (o Claude Code passa cwd).

set -uo pipefail

project_root="$(pwd)"

# Detectar workspace ativo via L1 (`workspaces/<NNN>/CONTEXT.md` frontmatter).
# v3.7.1: prefere L1 ao invés de `.index.md` — L1 é canônico, index é cache
# que pode ficar stale (bug pré-v3.7.1: saída A/C atualizava L1 mas não index).
# Itera dirs em workspaces/, lê status do frontmatter, primeiro NÃO-COMPLETED ativo.
ws_dir="$project_root/workspaces"
active_workspace=""
if [ -d "$ws_dir" ]; then
    # Ordena por nome (NNN-slug ascending) pra determinismo.
    for ctx in "$ws_dir"/*/CONTEXT.md; do
        [ -f "$ctx" ] || continue
        # Frontmatter status: extrai linha `status: <VALUE>` no bloco YAML inicial
        # (entre primeiras 2 ocorrências de `^---$`).
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

# Sem workspace ativo → não há nada a checar
if [ -z "$active_workspace" ]; then
    exit 0
fi

# Detectar branch atual no project_root
current_branch=$(git -C "$project_root" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
expected_ws_branch="workspace/${active_workspace}"

warnings=()

if [ "$current_branch" != "$expected_ws_branch" ]; then
    warnings+=(
        "⚠️  Branch atual em $project_root é '$current_branch', esperado '$expected_ws_branch' (workspace ativo)."
        "    Para retomar workspace ICM, rode: git -C \"$project_root\" checkout $expected_ws_branch"
    )
fi

# Validar .icm-main/ worktree
worktree="$project_root/.icm-main"
if [ ! -d "$worktree" ]; then
    # Detectar base_branch do L1
    l1="$project_root/workspaces/$active_workspace/CONTEXT.md"
    base_branch=""
    if [ -f "$l1" ]; then
        base_branch=$(grep -E '^base_branch:' "$l1" | head -1 | sed -E 's/^base_branch: *"?([^"]+)"?/\1/')
    fi
    base_branch="${base_branch:-main}"
    warnings+=(
        "⚠️  '.icm-main/' worktree ausente em $project_root."
        "    Modelo cross-branch v3.4.0 exige worktree linkada da base branch."
        "    Para criar: git -C \"$project_root\" worktree add .icm-main $base_branch"
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
            "⚠️  '.icm-main/' worktree está em '$wt_branch', esperado '$base_branch'."
            "    Para corrigir: cd $worktree && git checkout $base_branch"
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
