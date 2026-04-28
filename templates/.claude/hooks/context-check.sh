#!/usr/bin/env bash
# context-check.sh — PostToolUse hook que detecta contexto >= 70%
# e dispara handoff antecipado obrigatório (ICM protocol).
#
# Lê transcript diretamente (independente de statusline.sh).
# Cooldown de 60s entre alertas (1 por minuto, não por tool call).
# Threshold: 70% — margem para completar handoff antes do compact real (~90%).
#
# Instalação: .claude/settings.local.json → hooks.PostToolUse → "bash workspaces/<NNN-slug>/.claude/hooks/context-check.sh"
# Bootstrap: ICM stage 00 (infraestrutura de governança).
#
# Race-safe: usa mkdir atômico como lock. Instâncias concorrentes
# (ex: 4 Agent calls em paralelo) skip automaticamente.

# SEM set -e — pipefail sozinho + exits manuais. set -e quebra
# pipes que legitimamente retornam vazio (find sem resultados).
set -uo pipefail

THRESHOLD=70
COOLDOWN_SEC=60

# 1. Lock concorrente via mkdir (atômico em POSIX e Windows Git Bash).
# Se outra instância está rodando (ex: durante spawn de subagentes),
# skip imediatamente sem bloquear.
LOCKDIR="/tmp/claude-ctx-check-$(basename "$(pwd)")"
if ! mkdir "$LOCKDIR" 2>/dev/null; then
    # Outra instância rodando. Verificar se é stale (>120s).
    lock_age=999
    if stat -c %Y "$LOCKDIR" >/dev/null 2>&1; then
        lock_mtime=$(stat -c %Y "$LOCKDIR" 2>/dev/null || echo 0)
    elif stat -f %m "$LOCKDIR" >/dev/null 2>&1; then
        lock_mtime=$(stat -f %m "$LOCKDIR" 2>/dev/null || echo 0)
    else
        lock_mtime=0
    fi
    now=$(date +%s)
    lock_age=$(( now - lock_mtime ))
    # Stale lock — remover e seguir.
    if (( lock_age > 120 )); then
        rmdir "$LOCKDIR" 2>/dev/null || exit 0
    else
        exit 0
    fi
fi
# Garantir cleanup do lock ao sair.
trap 'rmdir "$LOCKDIR" 2>/dev/null' EXIT

# 2. Proteção contra interrupção de operação git em andamento.
git_dir="$(git rev-parse --git-dir 2>/dev/null || echo .git)"
if [ -d "${git_dir}/rebase-merge" ] || [ -d "${git_dir}/rebase-apply" ]; then
    exit 0
fi
if [ -f "${git_dir}/MERGE_MSG" ] || [ -f "${git_dir}/CHERRY_PICK_HEAD" ]; then
    exit 0
fi
if [ -f "${git_dir}/index.lock" ]; then
    exit 0
fi

# 3. Encontra transcript mais recente modificado nos últimos 5 min.
# Pipe sem pipefail aqui — find vazio não é erro, apenas "nada a fazer".
transcript=""
# shellcheck disable=SC2155
transcript=$(find "$HOME/.claude/projects" -name "*.jsonl" -mmin -5 2>/dev/null | head -1) || true
# Se find retornou múltiplos, pegar o mais recente
if [ -n "$transcript" ] && command -v ls >/dev/null 2>&1; then
    # Pegar o arquivo mais recente entre os encontrados
    most_recent=$(find "$HOME/.claude/projects" -name "*.jsonl" -mmin -5 2>/dev/null | xargs ls -t 2>/dev/null | head -1) || true
    if [ -n "$most_recent" ]; then
        transcript="$most_recent"
    fi
fi
[ -z "$transcript" ] && exit 0
[ ! -f "$transcript" ] && exit 0

# 4. Extrai última entrada de usage do transcript.
last_usage=""
last_usage=$(tail -n 300 "$transcript" 2>/dev/null | grep '"usage"' | tail -n 1) || true
[ -z "$last_usage" ] && exit 0

# 5. Parse tokens (jq obrigatório — dependência documentada).
if ! command -v jq >/dev/null 2>&1; then
    exit 0
fi

inp=$(echo "$last_usage" | jq -r '.message.usage.input_tokens // 0' 2>/dev/null) || inp=0
cc=$(echo "$last_usage"  | jq -r '.message.usage.cache_creation_input_tokens // 0' 2>/dev/null) || cc=0
cr=$(echo "$last_usage"  | jq -r '.message.usage.cache_read_input_tokens // 0' 2>/dev/null) || cr=0
ctx_used=$(( inp + cc + cr ))

# 6. Detecta janela de contexto (1M para modelos [1m], 200k padrão).
model_id=$(echo "$last_usage" | jq -r '.model // ""' 2>/dev/null) || model_id=""
if echo "$model_id" | grep -qi '\[1m\]\|1M'; then
    ctx_window=1000000
else
    ctx_window=200000
fi

ctx_pct=$(( ctx_used * 100 / ctx_window ))
(( ctx_pct < THRESHOLD )) && exit 0

# 7. Cooldown: 1 alert por minuto.
ALERT_LOCK="/tmp/claude-ctx-alert-$(basename "$(pwd)")"
now=$(date +%s)
if [ -f "$ALERT_LOCK" ]; then
    alert_mtime=$(stat -c %Y "$ALERT_LOCK" 2>/dev/null || stat -f %m "$ALERT_LOCK" 2>/dev/null || echo 0)
    alert_age=$(( now - alert_mtime ))
    (( alert_age < COOLDOWN_SEC )) && exit 0
fi
touch "$ALERT_LOCK"

cat <<EOF
================================================================================
⚠ CONTEXTO EM ${ctx_pct}% — HANDOFF ANTECIPADO OBRIGATÓRIO
================================================================================

PARE tudo. Contexto degradado = protocolo ICM violado.

Execute handoff antecipado agora:

1. Atualizar _kickoff.md com progresso cumulativo
   - Adicionar prev_outputs da task completada
   - Remover tasks completadas de pending_for_this_stage

2. Atualizar L1 (CONTEXT.md) com sub_stage atual

3. Commit intermediário (outputs + L1 + _kickoff.md)
   git add workspaces/<NNN>/stages/04_implementation_waves/output/ \
           workspaces/<NNN>/CONTEXT.md \
           workspaces/<NNN>/stages/04_implementation_waves/_kickoff.md
   git commit -m "workspace <NNN>: context checkpoint + handoff antecipado"

4. Imprimir KICKOFF block verbal pro user

5. SAIR da sessão — user abre nova com prompt KICKOFF

NÃO continue trabalhando. Handoff primeiro.
================================================================================
EOF
