#!/usr/bin/env bash
# Wrapper POSIX para validate_state.py.
#
# Uso:
#   scripts/validate-state.sh --workspace <path>
#
# Permite override do interpretador Python via env var:
#   PYTHON=python3.13 scripts/validate-state.sh --workspace ./ws
#
# Exit codes:
#   0 — estado valido
#   1 — estado invalido (mensagem em stderr)

set -euo pipefail

PYTHON="${PYTHON:-python}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$PYTHON" "$SCRIPT_DIR/validate_state.py" "$@"
