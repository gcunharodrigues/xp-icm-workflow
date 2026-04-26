#!/usr/bin/env bats
# CI-only — bats nao rodavel local em Windows.
#
# Integration tests para scripts/agent-team-protocol.py worktree helpers.
# Spawn worktree -> verifica filesystem + branch -> cleanup -> idempotencia.

setup() {
    SKILL_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/../.." && pwd)"
    PROTOCOL_PY="${SKILL_ROOT}/scripts/agent-team-protocol.py"
    TMP_PROJECT="$(mktemp -d)"
    cd "$TMP_PROJECT"
    git init -q -b main
    git config user.email "test@test"
    git config user.name "test"
    echo "# initial" > README.md
    git add README.md
    git commit -q -m "initial"
    export PYTHON="${PYTHON:-python}"
}

teardown() {
    cd /
    rm -rf "$TMP_PROJECT"
}

@test "spawn_worktree creates worktree dir and branch" {
    run "$PYTHON" -c "
import sys
sys.path.insert(0, '${SKILL_ROOT}/scripts')
import importlib.util
spec = importlib.util.spec_from_file_location('atp', '${PROTOCOL_PY}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
p = m.spawn_worktree('${TMP_PROJECT}', '042-feat-x', 1, 'task-a', 'main')
print(p)
"
    [ "$status" -eq 0 ]
    [ -d "${TMP_PROJECT}/.worktrees/workspace-042-feat-x/wave-1/task-a" ]

    branches="$(git -C "$TMP_PROJECT" branch --list)"
    [[ "$branches" == *"wave-042-feat-x-1/task-a"* ]]
}

@test "spawn_worktree raises WorktreeExists on duplicate path" {
    "$PYTHON" -c "
import sys
sys.path.insert(0, '${SKILL_ROOT}/scripts')
import importlib.util
spec = importlib.util.spec_from_file_location('atp', '${PROTOCOL_PY}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
m.spawn_worktree('${TMP_PROJECT}', '042-feat-x', 1, 'task-a', 'main')
"

    run "$PYTHON" -c "
import sys
sys.path.insert(0, '${SKILL_ROOT}/scripts')
import importlib.util
spec = importlib.util.spec_from_file_location('atp', '${PROTOCOL_PY}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
try:
    m.spawn_worktree('${TMP_PROJECT}', '042-feat-x', 1, 'task-a', 'main')
    sys.exit(99)
except m.WorktreeExists:
    sys.exit(0)
"
    [ "$status" -eq 0 ]
}

@test "spawn_worktree raises WorktreeError on missing base_branch" {
    run "$PYTHON" -c "
import sys
sys.path.insert(0, '${SKILL_ROOT}/scripts')
import importlib.util
spec = importlib.util.spec_from_file_location('atp', '${PROTOCOL_PY}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
try:
    m.spawn_worktree('${TMP_PROJECT}', '042-feat-x', 1, 'task-a', 'no-such-branch')
    sys.exit(99)
except m.WorktreeError:
    sys.exit(0)
"
    [ "$status" -eq 0 ]
}

@test "cleanup_worktree removes the worktree" {
    "$PYTHON" -c "
import sys
sys.path.insert(0, '${SKILL_ROOT}/scripts')
import importlib.util
spec = importlib.util.spec_from_file_location('atp', '${PROTOCOL_PY}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
m.spawn_worktree('${TMP_PROJECT}', '042-feat-x', 1, 'task-a', 'main')
m.cleanup_worktree('${TMP_PROJECT}', '042-feat-x', 1, 'task-a')
"
    [ ! -d "${TMP_PROJECT}/.worktrees/workspace-042-feat-x/wave-1/task-a" ]
}

@test "cleanup_worktree idempotent (no raise on already-removed)" {
    run "$PYTHON" -c "
import sys
sys.path.insert(0, '${SKILL_ROOT}/scripts')
import importlib.util
spec = importlib.util.spec_from_file_location('atp', '${PROTOCOL_PY}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
m.cleanup_worktree('${TMP_PROJECT}', '042-feat-x', 1, 'task-never-spawned')
"
    [ "$status" -eq 0 ]
}

@test "mailbox_dir creates if absent" {
    WS_ROOT="${TMP_PROJECT}/workspaces/042-feat-x"
    mkdir -p "$WS_ROOT/stages"

    run "$PYTHON" -c "
import sys
sys.path.insert(0, '${SKILL_ROOT}/scripts')
import importlib.util
spec = importlib.util.spec_from_file_location('atp', '${PROTOCOL_PY}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
p = m.mailbox_dir('${WS_ROOT}', 1)
print(p)
"
    [ "$status" -eq 0 ]
    [ -d "${WS_ROOT}/stages/04_implementation_waves/output/wave-1/mailbox" ]
}
