#!/usr/bin/env bash
# HITL (Human-In-The-Loop) feedback loop template
#
# Use when a bug requires human interaction but you still want structure.
# Driver for the human: prompt → wait → capture → loop.
#
# Doc: <SKILL_DIR>/references/diagnose-protocol.md (Phase 1, item 10).
#
# Customize: edit REPRO_STEPS, OBSERVE_CMD, PASS_PATTERN.

set -euo pipefail

# === CONFIGURATION ===
REPRO_STEPS='Click the "Login" button. Enter credentials. Submit.'
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
    echo "Reproduce the bug:"
    echo "  $REPRO_STEPS"
    echo ""
    read -r -p "Press ENTER after reproducing (or Ctrl+C to exit): "

    echo ""
    echo "Capturing observation..."
    output=$(eval "$OBSERVE_CMD")
    echo "$output"
    echo ""

    if echo "$output" | grep -q "$PASS_PATTERN"; then
        echo "✅ Bug did not reproduce (PASS_PATTERN found)."
        break
    else
        echo "❌ Bug reproduced (PASS_PATTERN absent)."
        read -r -p "Continue to next iteration? [y/n]: " cont
        if [ "$cont" != "y" ]; then
            echo "Loop interrupted by user."
            exit 1
        fi
    fi
done

echo ""
echo "Loop finished after $iteration iteration(s)."
