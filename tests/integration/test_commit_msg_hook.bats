#!/usr/bin/env bats
# Integration tests para templates/.git-hooks/commit-msg.
#
# Commit-msg valida prefix da mensagem em workspace branches.
# Stage canonico: git roda commit-msg DEPOIS user fornecer msg em
# COMMIT_EDITMSG. Hook recebe path do arquivo como $1.
#
# Inclui regression test pro bug v1: pre-commit lia msg do commit
# anterior porque rodava antes de COMMIT_EDITMSG ser persistido. Bug
# fixado movendo validacao de prefix pra commit-msg (este hook).
#
# CI-only via Ubuntu runner.
# Execucao: bats tests/integration/test_commit_msg_hook.bats

setup() {
    SKILL_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/../.." && pwd)"
    HOOK_SRC="${SKILL_ROOT}/templates/.git-hooks/commit-msg"

    TMP_REPO="$(mktemp -d)"
    cd "$TMP_REPO"
    git init -q
    git config user.email "test@test"
    git config user.name "test"

    mkdir -p .git/hooks
    cp "$HOOK_SRC" .git/hooks/commit-msg
    chmod +x .git/hooks/commit-msg

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

# Helper: cria msg file e roda hook com path
run_msg_hook() {
    local msg="$1"
    local msg_file="${TMP_REPO}/.git/COMMIT_EDITMSG"
    printf '%s' "$msg" > "$msg_file"
    run .git/hooks/commit-msg "$msg_file"
}

# 1. Branch nao-workspace passa livremente ------------------------------------

@test "non-workspace branch passes any msg" {
    git checkout -q -b feature/random
    run_msg_hook "anything goes"
    [ "$status" -eq 0 ]
}

# 2. workspace + msg com prefix correto --> accept ----------------------------

@test "workspace branch accepts msg with correct prefix" {
    git checkout -q -b workspace/042-feat-auth
    mkdir -p workspaces/042-feat-auth
    echo "ctx" > workspaces/042-feat-auth/CONTEXT.md
    git add workspaces/042-feat-auth/CONTEXT.md
    run_msg_hook "workspace 042: stage 02 outputs"
    [ "$status" -eq 0 ]
}

# 3. workspace + msg sem prefix --> reject ------------------------------------

@test "workspace branch rejects msg without 'workspace NNN:' prefix" {
    git checkout -q -b workspace/042-feat-auth
    mkdir -p workspaces/042-feat-auth
    echo "ctx" > workspaces/042-feat-auth/CONTEXT.md
    git add workspaces/042-feat-auth/CONTEXT.md
    run_msg_hook "fix: bad message"
    [ "$status" -eq 1 ]
    [[ "$output" == *"workspace 042:"* ]]
}

# 4. ADR sem prefix mas com (workspace NNN no corpo --> accept ----------------

@test "workspace branch accepts ADR commit without prefix when '(workspace NNN ' present" {
    git checkout -q -b workspace/042-feat-auth
    mkdir -p docs/decisions
    echo "adr" > docs/decisions/0001-some-decision.md
    git add docs/decisions/0001-some-decision.md
    run_msg_hook "docs(adr): record decision (workspace 042 design)"
    [ "$status" -eq 0 ]
}

# 5. ADR sem prefix nem (workspace NNN no corpo --> reject --------------------

@test "workspace branch rejects ADR commit without prefix nor '(workspace NNN '" {
    git checkout -q -b workspace/042-feat-auth
    mkdir -p docs/decisions
    echo "adr" > docs/decisions/0001-some-decision.md
    git add docs/decisions/0001-some-decision.md
    run_msg_hook "docs(adr): record decision"
    [ "$status" -eq 1 ]
}

# 6. Linhas de comentario do git sao ignoradas --------------------------------

@test "commit-msg ignores '#' comment lines" {
    git checkout -q -b workspace/042-feat-auth
    mkdir -p workspaces/042-feat-auth
    echo "ctx" > workspaces/042-feat-auth/CONTEXT.md
    git add workspaces/042-feat-auth/CONTEXT.md
    # msg com header de comentario do git no topo
    printf '%s\n' "# Please enter the commit message" "# Lines starting with '#' will be ignored" "workspace 042: real message" > .git/COMMIT_EDITMSG
    run .git/hooks/commit-msg "${TMP_REPO}/.git/COMMIT_EDITMSG"
    [ "$status" -eq 0 ]
}

# 7. Skip durante rebase ------------------------------------------------------

@test "commit-msg skips during rebase-merge" {
    git checkout -q -b workspace/042-feat-auth
    mkdir -p .git/rebase-merge
    run_msg_hook "anything during rebase"
    [ "$status" -eq 0 ]
}

@test "commit-msg skips during rebase-apply" {
    git checkout -q -b workspace/042-feat-auth
    mkdir -p .git/rebase-apply
    run_msg_hook "anything during rebase"
    [ "$status" -eq 0 ]
}

# 8. Hook recebe msg ATUAL via $1, nao msg do commit anterior (regression v1) -

@test "regression: commit-msg validates CURRENT msg, not previous commit's" {
    git checkout -q -b workspace/042-feat-auth
    mkdir -p workspaces/042-feat-auth
    echo "ctx" > workspaces/042-feat-auth/CONTEXT.md
    git add workspaces/042-feat-auth/CONTEXT.md

    # Simula sequencia de 2 commits: primeiro com prefix valido, segundo
    # com prefix invalido. Bug v1: pre-commit lia msg do primeiro durante
    # o segundo via .git/COMMIT_EDITMSG (stale). Fix: commit-msg recebe
    # path da msg atual em $1.
    printf '%s' "workspace 042: previous valid" > .git/COMMIT_EDITMSG
    # Mas hook recebe path para um arquivo TEMPORARIO com msg atual
    actual_msg_file="${TMP_REPO}/.git/CURRENT_MSG_TMP"
    printf '%s' "bad current msg" > "$actual_msg_file"
    run .git/hooks/commit-msg "$actual_msg_file"
    [ "$status" -eq 1 ]
    [[ "$output" == *"workspace 042:"* ]]
}

# 9. $1 ausente --> exit 0 (deixa git tratar) ---------------------------------

@test "commit-msg without msg file path exits 0 silently" {
    git checkout -q -b workspace/042-feat-auth
    run .git/hooks/commit-msg
    [ "$status" -eq 0 ]
}

# 10. $1 aponta pra arquivo inexistente --> exit 0 ----------------------------

@test "commit-msg with nonexistent msg file exits 0 silently" {
    git checkout -q -b workspace/042-feat-auth
    run .git/hooks/commit-msg "/tmp/nonexistent-msg-file-xyz"
    [ "$status" -eq 0 ]
}
