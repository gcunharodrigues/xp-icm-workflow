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

# Detectar workspace ativo via workspaces/.index.md.
# Procura linha com Status != "COMPLETED" (heurística simples).
index="$project_root/workspaces/.index.md"
active_workspace=""
if [ -f "$index" ]; then
    # Linha format: | NNN | slug | profile/tier | created | Status |
    while IFS= read -r line; do
        if echo "$line" | grep -Eq '^\| *[0-9]{3} *\|'; then
            slug=$(echo "$line" | awk -F'|' '{print $3}' | sed 's/ *//g')
            status=$(echo "$line" | awk -F'|' '{print $6}' | sed 's/ *//g')
            id=$(echo "$line" | awk -F'|' '{print $2}' | sed 's/ *//g')
            if [ -n "$slug" ] && [ "$status" != "COMPLETED" ]; then
                active_workspace="${id}-${slug}"
                break
            fi
        fi
    done < "$index"
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
