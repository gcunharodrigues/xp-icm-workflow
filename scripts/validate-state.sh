#!/usr/bin/env bash
# POSIX wrapper for validate_state.py.
#
# Usage:
#   scripts/validate-state.sh --workspace <path>
#
# Allows override of the Python interpreter via env var:
#   PYTHON=python3.13 scripts/validate-state.sh --workspace ./ws
#
# Exit codes:
#   0 — valid state
#   1 — invalid state (message on stderr)

set -euo pipefail

PYTHON="${PYTHON:-python}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$PYTHON" "$SCRIPT_DIR/validate_state.py" "$@"
