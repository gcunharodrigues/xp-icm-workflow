#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "=== Running pytest (unit + property-based) ==="
python -m pytest tests/unit/ tests/snapshot/ -v --cov=scripts --cov-report=term-missing

if command -v bats >/dev/null 2>&1; then
  echo "=== Running bats (integration + e2e) ==="
  bats tests/integration/ tests/e2e/
else
  echo "=== bats not installed: skipping integration/e2e (CI-only) ==="
fi
