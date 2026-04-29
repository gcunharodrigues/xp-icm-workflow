#!/usr/bin/env bash
# HITL (Human-In-The-Loop) feedback loop template
#
# Use quando bug exige interação humana mas você ainda quer estrutura.
# Driver para o humano: prompt → wait → capture → loop.
#
# Doc: <SKILL_DIR>/references/diagnose-protocol.md (Phase 1, item 10).
#
# Customize: edite REPRO_STEPS, OBSERVE_CMD, PASS_PATTERN.

set -euo pipefail

# === CONFIGURAÇÃO ===
REPRO_STEPS='Click no botão "Login". Digite credenciais. Submit.'
OBSERVE_CMD='tail -n 20 /var/log/app.log'
PASS_PATTERN='login successful'
MAX_ITERATIONS=10

# === LOOP ===
iteration=0
while [ "$iteration" -lt "$MAX_ITERATIONS" ]; do
    iteration=$((iteration + 1))
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Iteration $iteration / $MAX_ITERATIONS"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "Reproduza o bug:"
    echo "  $REPRO_STEPS"
    echo ""
    read -r -p "Pressione ENTER após reproduzir (ou Ctrl+C para sair): "

    echo ""
    echo "Capturando observação..."
    output=$(eval "$OBSERVE_CMD")
    echo "$output"
    echo ""

    if echo "$output" | grep -q "$PASS_PATTERN"; then
        echo "✅ Bug não reproduziu (PASS_PATTERN encontrado)."
        break
    else
        echo "❌ Bug reproduziu (PASS_PATTERN ausente)."
        read -r -p "Continuar próxima iteration? [y/n]: " cont
        if [ "$cont" != "y" ]; then
            echo "Loop interrompido pelo usuário."
            exit 1
        fi
    fi
done

echo ""
echo "Loop terminou após $iteration iteração(ões)."
