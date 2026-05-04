#!/usr/bin/env bats
# tests/integration/test_forensic_plus_e2e.bats
# Full-pipeline e2e: real git, real script, real plan.md fixture, asserts JSON output.

setup() {
  TMPDIR_E2E="$(mktemp -d)"
  export TMPDIR_E2E
}

teardown() {
  rm -rf "$TMPDIR_E2E"
}

@test "forensic-plus e2e: clean pass with all 4 checks dormant" {
  cd "$TMPDIR_E2E"
  git init -b main >/dev/null
  git config user.email test@example.com
  git config user.name Test

  mkdir -p src tests
  echo "x = 1" > src/foo.py
  git add -A && git commit -m base >/dev/null

  git checkout -b wave-001-1/add-foo >/dev/null
  echo "x = 2" > src/foo.py
  cat > tests/test_foo.py <<EOF
def test_a():
    assert 1 == 1
    assert 2 == 2
EOF
  git add -A && git commit -m work >/dev/null
  git checkout main >/dev/null

  cat > plan.md <<EOF
## Task add-foo:
### Files touched
- src/foo.py
- tests/test_foo.py
EOF

  run python "$BATS_TEST_DIRNAME/../../scripts/forensic-plus.py" \
    --workspace-num 001 --wave 1 --task-slug add-foo \
    --base-branch main --plan plan.md --tier development --output json
  [ "$status" -eq 0 ]
  echo "$output" | grep -q '"forensic_passed": true'
  echo "$output" | grep -q '"max_severity": "NONE"'
}

@test "forensic-plus e2e: HARD violation flagged" {
  cd "$TMPDIR_E2E"
  git init -b main >/dev/null
  git config user.email test@example.com
  git config user.name Test
  mkdir -p src tests
  echo "x = 1" > src/foo.py
  git add -A && git commit -m base >/dev/null
  git checkout -b wave-001-1/add-foo >/dev/null
  echo "x = 2" > src/foo.py
  cat > tests/test_foo.py <<EOF
def test_a():
    assert True
EOF
  echo "y = 1" > src/extra.py
  git add -A && git commit -m work >/dev/null
  git checkout main >/dev/null
  cat > plan.md <<EOF
## Task add-foo:
### Files touched
- src/foo.py
- tests/test_foo.py
EOF

  run python "$BATS_TEST_DIRNAME/../../scripts/forensic-plus.py" \
    --workspace-num 001 --wave 1 --task-slug add-foo \
    --base-branch main --plan plan.md --tier development --output json
  [ "$status" -eq 0 ]
  echo "$output" | grep -q '"forensic_passed": false'
  echo "$output" | grep -q '"max_severity": "HARD"'
  # Both Check 1 (test asserções) and Check 2 (files outside dev=HARD) fire.
  echo "$output" | grep -q '"check": "test_assertions_too_few"'
  echo "$output" | grep -q '"check": "files_outside_declared"'
}
