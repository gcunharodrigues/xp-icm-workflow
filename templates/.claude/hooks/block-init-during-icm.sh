#!/usr/bin/env bash
# block-init-during-icm.sh — PreToolUse hook (v3.4.1).
#
# Bloqueia invocacao de `/init` enquanto ha workspace ICM ativo (status
# != COMPLETED em workspaces/.index.md). Mitigacao G14 do adversarial
# review do plan v3.3.0.
#
# Razao: `/init` regenera CLAUDE.md a partir do codigo — pode sobrescrever
# regiao ICM (entre <!-- ICM-START --> e <!-- ICM-END -->), perdendo
# dashboard de workspaces ativos.
#
# Doc: references/project-root-claude-md.md (Contrato com /init).
#
# Uso PreToolUse: hook recebe JSON via stdin com `tool_name` e
# `tool_input`. Para SlashCommand tool, `tool_input.name == "init"`
# eh o trigger.

set -uo pipefail

payload=$(cat)

tool_name=$(echo "$payload" | grep -oE '"tool_name"\s*:\s*"[^"]+"' | head -1 | sed -E 's/.*"([^"]+)"$/\1/')

# Aceita SlashCommand ou comando direto via Bash
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

# Detecta workspace ativo via workspaces/.index.md no cwd
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
    exit 0  # sem workspace ativo, /init livre
fi

cat >&2 <<EOM
ICM guardrail: /init bloqueado enquanto workspace ICM ativo.

Workspace ativo: $active_workspace
Project root:    $project_root

Razao: /init regenera CLAUDE.md a partir do codigo do projeto e pode
sobrescrever a regiao ICM (entre <!-- ICM-START --> e <!-- ICM-END -->)
que contem o dashboard de workspaces ativos. Sessoes futuras perderiam
contexto e sessao atual ficaria orfa.

Para regenerar a parte codebase do CLAUDE.md sem tocar a regiao ICM:
  1. Finalize o workspace ($active_workspace) via Saida A da fase 08.
  2. Apos status=COMPLETED no .index.md, /init opera livremente
     (regiao ICM ja esta em modo idle).

Doc: references/project-root-claude-md.md.
EOM

exit 1
