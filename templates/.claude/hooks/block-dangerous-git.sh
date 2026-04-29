#!/usr/bin/env bash
# block-dangerous-git.sh — PreToolUse hook (v3.4.1, production tier).
#
# Bloqueia comandos git destrutivos no Claude Code:
#   - git push --force / -f
#   - git push --force-with-lease (warning, nao bloqueia)
#   - git reset --hard
#   - git clean -fd / --force
#   - git branch -D <name>
#   - git checkout . / git restore .
#   - git rebase com --no-edit
#
# Inspirado em [mattpocock/skills/misc/git-guardrails-claude-code].
#
# Instalacao: apenas em workspaces com tier=production. Bootstrap adiciona
# condicionalmente. Doc: references/git-hooks.md.
#
# Uso PreToolUse: hook recebe JSON via stdin com campos `tool_name` e
# `tool_input`. Sai com codigo 0 = permite, 1 = bloqueia (Claude Code
# interpreta como rejection do tool call).

set -uo pipefail

# Le payload JSON via stdin
payload=$(cat)

# Apenas Bash tool eh relevante
tool_name=$(echo "$payload" | grep -oE '"tool_name"\s*:\s*"[^"]+"' | head -1 | sed -E 's/.*"([^"]+)"$/\1/')
if [ "$tool_name" != "Bash" ] && [ "$tool_name" != "PowerShell" ]; then
    exit 0
fi

# Extrai o comando
cmd=$(echo "$payload" | grep -oE '"command"\s*:\s*"[^"]*"' | head -1 | sed -E 's/.*"([^"]*)"$/\1/')
if [ -z "$cmd" ]; then
    exit 0
fi

# Patterns destrutivos — reject hard
declare -a blocked=(
    'git[[:space:]]+push[[:space:]]+(--force([[:space:]]|$)|-f([[:space:]]|$))'
    'git[[:space:]]+reset[[:space:]]+--hard'
    'git[[:space:]]+clean[[:space:]]+-[a-z]*f'
    'git[[:space:]]+branch[[:space:]]+-D[[:space:]]'
    'git[[:space:]]+checkout[[:space:]]+\.'
    'git[[:space:]]+restore[[:space:]]+\.'
)

for pattern in "${blocked[@]}"; do
    if echo "$cmd" | grep -Eq "$pattern"; then
        cat >&2 <<EOM
ICM guardrail: comando git destrutivo bloqueado em tier=production.

Comando: $cmd

Razao: este workspace tem tier=production. Operacoes destrutivas (force
push, reset --hard, clean -f, branch -D, checkout ./restore .) podem
perder trabalho irreversivel ou sobrescrever historia compartilhada.

Se precisar mesmo executar:
  1. Confirme com humano por que a alternativa segura nao serve.
  2. Tier=production exige preserve por padrao — considere tier=development
     temporario via override.
  3. Documente decisao em decisions.md (workspace) antes de executar.
EOM
        exit 1
    fi
done

exit 0
