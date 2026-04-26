#!/usr/bin/env bats
# CI-only — bats nao rodavel local em Windows.
#
# E2E test para recovery-wizard.py em workspace orfa.
# Usa fixture tests/fixtures/workspace_orphan/ como ponto de partida.

setup() {
  SKILL_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  FIXTURE="$SKILL_ROOT/tests/fixtures/workspace_orphan"
  TMP_WS="$BATS_TEST_TMPDIR/workspace_orphan"
  cp -r "$FIXTURE" "$TMP_WS"
  export PYTHON="${PYTHON:-python}"
}

@test "dry-run nao modifica L1 e exit 0" {
  before_hash=$(sha256sum "$TMP_WS/CONTEXT.md" | awk '{print $1}')

  run "$PYTHON" "$SKILL_ROOT/scripts/recovery-wizard.py" \
    --workspace "$TMP_WS" --dry-run

  [ "$status" -eq 0 ]
  [[ "$output" == *"Recovery Plan"* ]] || [[ "$output" == *"consistent"* ]]

  after_hash=$(sha256sum "$TMP_WS/CONTEXT.md" | awk '{print $1}')
  [ "$before_hash" = "$after_hash" ]
}

@test "apply A modifica L1 + history append + exit 0" {
  before_hash=$(sha256sum "$TMP_WS/CONTEXT.md" | awk '{print $1}')

  run "$PYTHON" "$SKILL_ROOT/scripts/recovery-wizard.py" \
    --workspace "$TMP_WS" --apply A

  [ "$status" -eq 0 ]

  after_hash=$(sha256sum "$TMP_WS/CONTEXT.md" | awk '{print $1}')
  [ "$before_hash" != "$after_hash" ]

  # Confirma history append (recovery_applied event)
  grep -q "recovery_applied" "$TMP_WS/CONTEXT.md"
}

@test "apply C marca BLOCKED_ERROR + exit 0" {
  run "$PYTHON" "$SKILL_ROOT/scripts/recovery-wizard.py" \
    --workspace "$TMP_WS" --apply C

  [ "$status" -eq 0 ]
  grep -q "status: BLOCKED_ERROR" "$TMP_WS/CONTEXT.md"
  grep -q "recovery_applied" "$TMP_WS/CONTEXT.md"
}

@test "workspace inexistente exit 1" {
  run "$PYTHON" "$SKILL_ROOT/scripts/recovery-wizard.py" \
    --workspace "$BATS_TEST_TMPDIR/nope" --dry-run

  [ "$status" -eq 1 ]
}
