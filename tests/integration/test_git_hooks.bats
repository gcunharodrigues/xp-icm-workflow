#!/usr/bin/env bats
# Integration tests para templates/.git-hooks/pre-commit.
#
# CI-only via Ubuntu runner (bats nao roda em Windows local).
# Execucao: bats tests/integration/test_git_hooks.bats
#
# Estrategia: cada teste cria repo git temporario, copia o hook, faz stage de
# arquivos especificos, simula mensagem de commit em .git/COMMIT_EDITMSG, e
# invoca o hook diretamente. Verifica exit code + stderr.

setup() {
    SKILL_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/../.." && pwd)"
    HOOK_SRC="${SKILL_ROOT}/templates/.git-hooks/pre-commit"

    TMP_REPO="$(mktemp -d)"
    cd "$TMP_REPO"
    git init -q
    git config user.email "test@test"
    git config user.name "test"

    mkdir -p .git/hooks
    cp "$HOOK_SRC" .git/hooks/pre-commit
    chmod +x .git/hooks/pre-commit

    # commit inicial pra ter HEAD
    echo "init" > README.md
    git add README.md
    GIT_AUTHOR_DATE="2026-01-01T00:00:00Z" \
    GIT_COMMITTER_DATE="2026-01-01T00:00:00Z" \
    git commit -q -m "init" --no-verify
}

teardown() {
    cd /
    rm -rf "$TMP_REPO"
}

# Helper: roda o hook diretamente em determinada branch + mensagem
run_hook() {
    local msg="$1"
    printf '%s' "$msg" > .git/COMMIT_EDITMSG
    run .git/hooks/pre-commit
}

# 1. Branch nao-workspace passa livremente ------------------------------------

@test "non-workspace branch passes regardless of staged files" {
    git checkout -q -b feature/random
    echo "x" > src/foo.txt
    mkdir -p src
    echo "x" > src/foo.txt
    git add src/foo.txt
    run_hook "anything goes"
    [ "$status" -eq 0 ]
}

# 2. workspace branch + staged em src/ --> reject -----------------------------

@test "workspace branch rejects staged file outside workspace dir" {
    git checkout -q -b workspace/042-feat-auth
    mkdir -p src
    echo "x" > src/foo.py
    git add src/foo.py
    run_hook "workspace 042: edit src"
    [ "$status" -eq 1 ]
    [[ "$output" == *"File offendor"* ]]
    [[ "$output" == *"src/foo.py"* ]]
}

# 3. workspace branch + staged dentro do workspace + CONTEXT.md staged + msg correta --> accept

@test "workspace branch accepts staged in workspace dir with correct msg and CONTEXT" {
    git checkout -q -b workspace/042-feat-auth
    mkdir -p workspaces/042-feat-auth/stages/02/output
    echo "ctx" > workspaces/042-feat-auth/CONTEXT.md
    echo "out" > workspaces/042-feat-auth/stages/02/output/plan.md
    git add workspaces/042-feat-auth/CONTEXT.md
    git add workspaces/042-feat-auth/stages/02/output/plan.md
    run_hook "workspace 042: stage 02 outputs"
    [ "$status" -eq 0 ]
}

# 4. workspace branch com msg sem prefix --> reject ---------------------------

@test "workspace branch rejects commit msg without 'workspace NNN:' prefix" {
    git checkout -q -b workspace/042-feat-auth
    mkdir -p workspaces/042-feat-auth
    echo "ctx" > workspaces/042-feat-auth/CONTEXT.md
    git add workspaces/042-feat-auth/CONTEXT.md
    run_hook "fix: bad message"
    [ "$status" -eq 1 ]
    [[ "$output" == *"workspace 042:"* ]]
}

# 5. workspace branch + ADR sem prefix mas com (workspace NNN  --> accept ----

@test "workspace branch accepts ADR commit without prefix when '(workspace NNN ' present" {
    git checkout -q -b workspace/042-feat-auth
    mkdir -p docs/decisions
    echo "adr" > docs/decisions/0001-some-decision.md
    git add docs/decisions/0001-some-decision.md
    run_hook "docs(adr): record decision (workspace 042 design)"
    [ "$status" -eq 0 ]
}

# 6. outputs staged sem CONTEXT.md staged --> reject --------------------------

@test "workspace branch rejects stage outputs staged without CONTEXT.md" {
    git checkout -q -b workspace/042-feat-auth
    mkdir -p workspaces/042-feat-auth/stages/02/output
    echo "out" > workspaces/042-feat-auth/stages/02/output/plan.md
    git add workspaces/042-feat-auth/stages/02/output/plan.md
    run_hook "workspace 042: stage 02 outputs"
    [ "$status" -eq 1 ]
    [[ "$output" == *"Atomicidade"* ]]
    [[ "$output" == *"CONTEXT.md"* ]]
}

# 7. Durante rebase --> exit 0 sempre -----------------------------------------

@test "hook skips during rebase-merge in progress" {
    git checkout -q -b workspace/042-feat-auth
    mkdir -p .git/rebase-merge
    mkdir -p src
    echo "x" > src/foo.py
    git add src/foo.py
    run_hook "anything during rebase"
    [ "$status" -eq 0 ]
}

@test "hook skips during rebase-apply in progress" {
    git checkout -q -b workspace/042-feat-auth
    mkdir -p .git/rebase-apply
    mkdir -p src
    echo "x" > src/foo.py
    git add src/foo.py
    run_hook "anything during rebase"
    [ "$status" -eq 0 ]
}
