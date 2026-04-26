#!/usr/bin/env bash
# xp-icm-workflow — bootstrap one-shot
#
# Cria workspace ICM dentro de um project_root: branch dedicada, scaffold de
# estagios, L0/L1 com placeholders preenchidos, profile efetivo + hash, indice
# do projeto, .gitignore atualizado, pre-commit hook instalado, commits
# atomicos.
#
# Uso:
#   bash scripts/bootstrap.sh \
#       --profile <NAME> \
#       --tier <NAME> \
#       --project-root <abs-path> \
#       [--workspace-name <slug>] \
#       [--logs-root <abs-path>] \
#       [--override <abs-path-yaml>]
#
# Args resolution (Q9 + L1):
#   1. CLI args (highest priority).
#   2. <project_root>/.icm-profile.local.yaml (extends + tier; prompt s/n/edit).
#   3. Pergunta interativa em PT (menu).
#
# profile + tier sao obrigatorios; se faltarem em todas as fontes, abort.
#
# Anti-bypass: NUNCA edite .git/hooks ou use --no-verify.

set -euo pipefail

# ----------------------------------------------------------------------------
# Resolucao de paths da skill
# ----------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# ----------------------------------------------------------------------------
# Pre-flight runtime check (J1)
# ----------------------------------------------------------------------------

if [ -x "${SKILL_ROOT}/scripts/check-runtime.sh" ]; then
    if ! bash "${SKILL_ROOT}/scripts/check-runtime.sh"; then
        echo "erro: runtime check falhou. Veja system-requirements.md." >&2
        exit 1
    fi
fi

# ----------------------------------------------------------------------------
# Parse args
# ----------------------------------------------------------------------------

PROFILE=""
TIER=""
PROJECT_ROOT=""
WORKSPACE_NAME=""
LOGS_ROOT=""
OVERRIDE_PATH=""

usage() {
    cat <<EOF
Uso: bash scripts/bootstrap.sh \\
    --profile <NAME> --tier <NAME> --project-root <abs-path> \\
    [--workspace-name <slug>] [--logs-root <abs-path>] [--override <yaml>]

Profiles: app_web_backend, app_web_frontend, dashboard, data_analysis,
          ml_project, agent_ia, cli_tool, framework_library,
          technical_article, experiment
Tiers:    experimental, tool, development, production
EOF
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --profile) PROFILE="$2"; shift 2 ;;
        --tier) TIER="$2"; shift 2 ;;
        --project-root) PROJECT_ROOT="$2"; shift 2 ;;
        --workspace-name) WORKSPACE_NAME="$2"; shift 2 ;;
        --logs-root) LOGS_ROOT="$2"; shift 2 ;;
        --override) OVERRIDE_PATH="$2"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "erro: arg desconhecido: $1" >&2; usage; exit 1 ;;
    esac
done

# ----------------------------------------------------------------------------
# Resolve project_root (default = $PWD)
# ----------------------------------------------------------------------------

if [ -z "$PROJECT_ROOT" ]; then
    PROJECT_ROOT="$PWD"
fi

if [ ! -d "$PROJECT_ROOT" ]; then
    echo "erro: project_root nao e diretorio: $PROJECT_ROOT" >&2
    exit 1
fi

# Normaliza path absoluto
PROJECT_ROOT="$(cd "$PROJECT_ROOT" && pwd)"

# ----------------------------------------------------------------------------
# .icm-profile.local.yaml detection (Q9 fonte 2)
# ----------------------------------------------------------------------------

if [ -z "$OVERRIDE_PATH" ]; then
    if [ -f "${PROJECT_ROOT}/.icm-profile.local.yaml" ]; then
        OVERRIDE_PATH="${PROJECT_ROOT}/.icm-profile.local.yaml"
    elif [ -f "${PWD}/.icm-profile.local.yaml" ] && [ "${PWD}" != "${PROJECT_ROOT}" ]; then
        OVERRIDE_PATH="${PWD}/.icm-profile.local.yaml"
    fi
fi

# Se override tem extends + tier, prompt humano (skip em CI / non-tty)
if [ -n "$OVERRIDE_PATH" ] && [ -t 0 ] && [ -t 1 ]; then
    extends_in_override="$(python -c "
import yaml,sys
try:
    d = yaml.safe_load(open('$OVERRIDE_PATH', encoding='utf-8'))
    if isinstance(d, dict):
        ext = d.get('extends')
        tier = d.get('tier')
        if ext and tier:
            print(f'{ext}|{tier}')
except Exception:
    pass
" 2>/dev/null || true)"
    if [ -n "$extends_in_override" ]; then
        ext="${extends_in_override%|*}"
        tier_from_yaml="${extends_in_override##*|}"
        echo "Detectado .icm-profile.local.yaml: extends=$ext tier=$tier_from_yaml"
        printf "Usar este profile/tier? [s/n/edit]: "
        read -r answer || answer="n"
        case "$answer" in
            s|S|sim|y|Y)
                [ -z "$PROFILE" ] && PROFILE="$ext"
                [ -z "$TIER" ] && TIER="$tier_from_yaml"
                ;;
            edit|e|E)
                echo "Edite $OVERRIDE_PATH e rerode bootstrap." >&2
                exit 0
                ;;
            *) ;;  # nao usa
        esac
    fi
fi

# ----------------------------------------------------------------------------
# Pergunta interativa se profile/tier ainda faltam (Q9 fonte 3)
# ----------------------------------------------------------------------------

if [ -z "$PROFILE" ] && [ -t 0 ] && [ -t 1 ]; then
    cat <<EOF
Escolha profile:
  1) app_web_backend       6) agent_ia
  2) app_web_frontend      7) cli_tool
  3) dashboard             8) framework_library
  4) data_analysis         9) technical_article
  5) ml_project           10) experiment
EOF
    printf "Numero: "
    read -r idx
    case "$idx" in
        1) PROFILE="app_web_backend" ;;
        2) PROFILE="app_web_frontend" ;;
        3) PROFILE="dashboard" ;;
        4) PROFILE="data_analysis" ;;
        5) PROFILE="ml_project" ;;
        6) PROFILE="agent_ia" ;;
        7) PROFILE="cli_tool" ;;
        8) PROFILE="framework_library" ;;
        9) PROFILE="technical_article" ;;
        10) PROFILE="experiment" ;;
    esac
fi

if [ -z "$TIER" ] && [ -t 0 ] && [ -t 1 ]; then
    cat <<EOF
Escolha tier:
  1) experimental    3) development
  2) tool            4) production
EOF
    printf "Numero: "
    read -r idx
    case "$idx" in
        1) TIER="experimental" ;;
        2) TIER="tool" ;;
        3) TIER="development" ;;
        4) TIER="production" ;;
    esac
fi

if [ -z "$PROFILE" ] || [ -z "$TIER" ]; then
    echo "erro: --profile e --tier sao obrigatorios (CLI, yaml override ou prompt)." >&2
    usage >&2
    exit 1
fi

# ----------------------------------------------------------------------------
# Workspace slug (CLI ou pergunta)
# ----------------------------------------------------------------------------

if [ -z "$WORKSPACE_NAME" ]; then
    if [ -t 0 ] && [ -t 1 ]; then
        printf "Workspace slug (kebab-case, ex: feat-auth): "
        read -r WORKSPACE_NAME
    fi
fi

if [ -z "$WORKSPACE_NAME" ]; then
    echo "erro: --workspace-name obrigatorio (sem prompt em modo nao-interativo)." >&2
    exit 1
fi

# ----------------------------------------------------------------------------
# Pre-check: workspace dir nao existe (recovery wizard)
# ----------------------------------------------------------------------------

# Calcular NNN provisorio para checagem; bootstrap.py tambem checa, mas aqui
# damos mensagem amigavel antes de criar branch.
INDEX_PATH="${PROJECT_ROOT}/workspaces/.index.md"
NEXT_NNN="$(python -c "
import sys
sys.path.insert(0, r'${SKILL_ROOT}/scripts')
from pathlib import Path
import importlib.util
spec = importlib.util.spec_from_file_location('bootstrap', r'${SKILL_ROOT}/scripts/bootstrap.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
print(f'{m.resolve_workspace_id(Path(r\"${INDEX_PATH}\")):03d}')
" 2>/dev/null || echo "001")"

WORKSPACE_DIR="${PROJECT_ROOT}/workspaces/${NEXT_NNN}-${WORKSPACE_NAME}"
if [ -d "$WORKSPACE_DIR" ]; then
    if [ -x "${SKILL_ROOT}/scripts/recovery-wizard.py" ]; then
        echo "workspace dir ja existe: ${WORKSPACE_DIR}" >&2
        echo "delegando para recovery-wizard..." >&2
        exec python "${SKILL_ROOT}/scripts/recovery-wizard.py" \
            --project-root "$PROJECT_ROOT" \
            --workspace "${NEXT_NNN}-${WORKSPACE_NAME}"
    fi
    echo "erro: workspace dir ja existe: ${WORKSPACE_DIR}" >&2
    echo "(recovery-wizard ainda nao disponivel; remova manualmente ou escolha outro slug)" >&2
    exit 1
fi

# ----------------------------------------------------------------------------
# Delega para bootstrap.py (faz toda a heavy lifting)
# ----------------------------------------------------------------------------

extra_args=()
if [ -n "$LOGS_ROOT" ]; then
    extra_args+=(--logs-root "$LOGS_ROOT")
fi
if [ -n "$OVERRIDE_PATH" ]; then
    extra_args+=(--override "$OVERRIDE_PATH")
fi

set +e
SUMMARY_JSON="$(python "${SKILL_ROOT}/scripts/bootstrap.py" \
    --profile "$PROFILE" \
    --tier "$TIER" \
    --project-root "$PROJECT_ROOT" \
    --workspace-name "$WORKSPACE_NAME" \
    --skill-root "$SKILL_ROOT" \
    "${extra_args[@]}")"
rc=$?
set -e

if [ "$rc" -ne 0 ]; then
    echo "$SUMMARY_JSON" >&2
    exit "$rc"
fi

# ----------------------------------------------------------------------------
# Print sucesso (PT)
# ----------------------------------------------------------------------------

WS="$(printf '%s' "$SUMMARY_JSON" | python -c 'import json,sys; print(json.load(sys.stdin)["workspace"])')"
BR="$(printf '%s' "$SUMMARY_JSON" | python -c 'import json,sys; print(json.load(sys.stdin)["branch"])')"
BB="$(printf '%s' "$SUMMARY_JSON" | python -c 'import json,sys; print(json.load(sys.stdin)["base_branch"])')"
HASH="$(printf '%s' "$SUMMARY_JSON" | python -c 'import json,sys; print(json.load(sys.stdin)["hash"])')"

cat <<EOF

OK Workspace ${WS} criado.
Branch:   ${BR} (de ${BB})
Profile:  ${PROFILE} / ${TIER}
Hash:     ${HASH:0:16}...
Proximo:  abra nova sessao e leia ${PROJECT_ROOT}/workspaces/${WS}/CLAUDE.md
          depois ${PROJECT_ROOT}/workspaces/${WS}/CONTEXT.md
          depois ${PROJECT_ROOT}/workspaces/${WS}/stages/00_recon/CONTEXT.md
EOF
