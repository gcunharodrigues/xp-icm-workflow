#!/usr/bin/env bash
# Orquestrador da suite de testes.
#
# Local (Windows/macOS sem bats): roda só pytest.
# CI Ubuntu: roda pytest + bats integration + e2e.
#
# Flags:
#   --ci          ativa coverage XML report adequado a GH Actions
#   --no-bats     pula integration/e2e mesmo se bats instalado (debug rapido)

set -euo pipefail

cd "$(dirname "$0")/.."

CI_MODE=0
SKIP_BATS=0
for arg in "$@"; do
  case "$arg" in
    --ci) CI_MODE=1 ;;
    --no-bats) SKIP_BATS=1 ;;
    *) echo "unknown flag: $arg" >&2; exit 2 ;;
  esac
done

echo "=== Running pytest (unit + property-based) ==="
if [ "$CI_MODE" = "1" ]; then
  python -m pytest tests/unit/ tests/snapshot/ \
    --cov=scripts \
    --cov-report=term-missing \
    --cov-report=xml
else
  python -m pytest tests/unit/ tests/snapshot/ -v --cov=scripts --cov-report=term-missing
fi

if [ "$SKIP_BATS" = "1" ]; then
  echo "=== --no-bats flag: skipping integration/e2e ==="
elif command -v bats >/dev/null 2>&1; then
  echo "=== Running bats (integration + e2e) ==="
  bats tests/integration/ tests/e2e/
else
  echo "=== bats not installed: skipping integration/e2e (CI-only) ==="
fi
