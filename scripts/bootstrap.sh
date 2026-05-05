#!/usr/bin/env bash
# xp-icm-workflow — one-shot bootstrap
#
# Creates an ICM workspace inside a project_root: dedicated branch, stage
# scaffold, L0/L1 with filled placeholders, effective profile + hash, project
# index, updated .gitignore, pre-commit hook installed, atomic commits.
#
# Usage:
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
#   2. <project_root>/.icm-profile.local.yaml (extends + tier; prompt y/n/edit).
#   3. Interactive prompt (menu).
#
# profile + tier are required; if missing from all sources, abort.
#
# Anti-bypass: NEVER edit .git/hooks or use --no-verify.

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
        echo "error: runtime check failed. See system-requirements.md." >&2
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
Usage: bash scripts/bootstrap.sh \\
    --profile <NAME> --tier <NAME> --project-root <abs-path> \\
    [--workspace-name <slug>] [--logs-root <abs-path>] [--override <yaml>]

Profiles: app_web_backend, app_web_frontend, fullstack, dashboard,
          data_analysis, ml_project, agent_ia, cli_tool,
          framework_library, technical_article, experiment
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
        *) echo "error: unknown arg: $1" >&2; usage; exit 1 ;;
    esac
done

# ----------------------------------------------------------------------------
# Resolve project_root (default = $PWD)
# ----------------------------------------------------------------------------

if [ -z "$PROJECT_ROOT" ]; then
    PROJECT_ROOT="$PWD"
fi

if [ ! -d "$PROJECT_ROOT" ]; then
    echo "error: project_root is not a directory: $PROJECT_ROOT" >&2
    exit 1
fi

# Normalize absolute path
PROJECT_ROOT="$(cd "$PROJECT_ROOT" && pwd)"

# ----------------------------------------------------------------------------
# .icm-profile.local.yaml detection (Q9 source 2)
# ----------------------------------------------------------------------------

if [ -z "$OVERRIDE_PATH" ]; then
    if [ -f "${PROJECT_ROOT}/.icm-profile.local.yaml" ]; then
        OVERRIDE_PATH="${PROJECT_ROOT}/.icm-profile.local.yaml"
    elif [ -f "${PWD}/.icm-profile.local.yaml" ] && [ "${PWD}" != "${PROJECT_ROOT}" ]; then
        OVERRIDE_PATH="${PWD}/.icm-profile.local.yaml"
    fi
fi

# If override has extends + tier, prompt human (skip in CI / non-tty)
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
        echo "Detected .icm-profile.local.yaml: extends=$ext tier=$tier_from_yaml"
        printf "Use this profile/tier? [y/n/edit]: "
        read -r answer || answer="n"
        case "$answer" in
            s|S|sim|y|Y)
                [ -z "$PROFILE" ] && PROFILE="$ext"
                [ -z "$TIER" ] && TIER="$tier_from_yaml"
                ;;
            edit|e|E)
                echo "Edit $OVERRIDE_PATH and re-run bootstrap." >&2
                exit 0
                ;;
            *) ;;  # nao usa
        esac
    fi
fi

# ----------------------------------------------------------------------------
# Interactive prompt if profile/tier still missing (Q9 source 3)
# ----------------------------------------------------------------------------

if [ -z "$PROFILE" ] && [ -t 0 ] && [ -t 1 ]; then
    cat <<EOF
Choose profile:
  1) app_web_backend       7) cli_tool
  2) app_web_frontend      8) framework_library
  3) fullstack             9) technical_article
  4) dashboard            10) experiment
  5) data_analysis        11) agent_ia
  6) ml_project
EOF
    printf "Number: "
    read -r idx
    case "$idx" in
        1) PROFILE="app_web_backend" ;;
        2) PROFILE="app_web_frontend" ;;
        3) PROFILE="fullstack" ;;
        4) PROFILE="dashboard" ;;
        5) PROFILE="data_analysis" ;;
        6) PROFILE="ml_project" ;;
        7) PROFILE="cli_tool" ;;
        8) PROFILE="framework_library" ;;
        9) PROFILE="technical_article" ;;
        10) PROFILE="experiment" ;;
        11) PROFILE="agent_ia" ;;
    esac
fi

if [ -z "$TIER" ] && [ -t 0 ] && [ -t 1 ]; then
    cat <<EOF
Choose tier:
  1) experimental    3) development
  2) tool            4) production
EOF
    printf "Number: "
    read -r idx
    case "$idx" in
        1) TIER="experimental" ;;
        2) TIER="tool" ;;
        3) TIER="development" ;;
        4) TIER="production" ;;
    esac
fi

if [ -z "$PROFILE" ] || [ -z "$TIER" ]; then
    echo "error: --profile and --tier are required (CLI, yaml override or prompt)." >&2
    usage >&2
    exit 1
fi

# ----------------------------------------------------------------------------
# Workspace slug (CLI or prompt)
# ----------------------------------------------------------------------------

if [ -z "$WORKSPACE_NAME" ]; then
    if [ -t 0 ] && [ -t 1 ]; then
        printf "Workspace slug (kebab-case, e.g. feat-auth): "
        read -r WORKSPACE_NAME
    fi
fi

if [ -z "$WORKSPACE_NAME" ]; then
    echo "error: --workspace-name required (no prompt in non-interactive mode)." >&2
    exit 1
fi

# ----------------------------------------------------------------------------
# Pre-check: workspace dir does not exist (recovery wizard)
# ----------------------------------------------------------------------------

# Compute provisional NNN for check; bootstrap.py also checks, but here
# we give a friendly message before creating the branch.
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
        echo "workspace dir already exists: ${WORKSPACE_DIR}" >&2
        echo "delegating to recovery-wizard..." >&2
        exec python "${SKILL_ROOT}/scripts/recovery-wizard.py" \
            --project-root "$PROJECT_ROOT" \
            --workspace "${NEXT_NNN}-${WORKSPACE_NAME}"
    fi
    echo "error: workspace dir already exists: ${WORKSPACE_DIR}" >&2
    echo "(recovery-wizard not yet available; remove manually or choose another slug)" >&2
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

OK Workspace ${WS} created.
Branch:   ${BR} (from ${BB})
Profile:  ${PROFILE} / ${TIER}
Hash:     ${HASH:0:16}...
Next:     open a new session and read ${PROJECT_ROOT}/workspaces/${WS}/CLAUDE.md
          then ${PROJECT_ROOT}/workspaces/${WS}/CONTEXT.md
          then ${PROJECT_ROOT}/workspaces/${WS}/stages/00_recon/CONTEXT.md
EOF
