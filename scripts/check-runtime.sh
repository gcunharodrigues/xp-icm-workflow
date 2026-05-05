#!/usr/bin/env bash
set -euo pipefail

errors=0

check() {
  local name="$1"; local cmd="$2"
  if eval "$cmd" >/dev/null 2>&1; then
    echo "OK    $name"
  else
    echo "FAIL  $name"
    errors=$((errors+1))
  fi
}

echo "=== Runtime check ==="
check "Python 3.11+"   "python -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)'"
check "PyYAML"         "python -c 'import yaml'"
check "pytest"         "python -c 'import pytest'"
check "git 2.30+"      "git --version | grep -Eq 'git version 2\.(3[0-9]|[4-9][0-9])'"
check "bash POSIX"     "bash -c 'set -euo pipefail; echo OK'"

if ! command -v bats >/dev/null 2>&1; then
  echo "WARN  bats not installed (CI-only ok)"
fi

if [ "$errors" -gt 0 ]; then
  echo ""
  echo "Runtime check FAILED ($errors issues). See system-requirements.md for setup."
  exit 1
fi
