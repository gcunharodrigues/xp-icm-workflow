#!/usr/bin/env bats
# CI-only — bats nao rodavel local em Windows.
#
# E2E: bootstrap apontando para clone read-only de external_repo. Cenário típico:
# usuário quer rodar workspace ICM em cima de codebase de terceiros (analise,
# review, contribuição preparada). Workspace branch isola toda atividade ICM
# em `workspaces/`, base_branch (master/main do upstream) nunca recebe write.

setup() {
    SKILL_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/../.." && pwd)"
    BOOTSTRAP_PY="${SKILL_ROOT}/scripts/bootstrap.py"

    # Simula upstream: repo bare + clone com codigo
    UPSTREAM="$(mktemp -d)"
    TMP_PROJECT="$(mktemp -d)"

    # Cria upstream com algum historico
    cd "$UPSTREAM"
    git init -q -b master
    git config user.email "upstream@test"
    git config user.name "upstream"
    mkdir -p lib
    echo "// external lib" > lib/core.js
    git add .
    git commit -q -m "external initial"

    # Clona pra TMP_PROJECT como external_repo
    git clone -q "$UPSTREAM" "$TMP_PROJECT"
    cd "$TMP_PROJECT"
    git config user.email "test@test"
    git config user.name "test"

    export GIT_AUTHOR_NAME=test GIT_AUTHOR_EMAIL=test@test
    export GIT_COMMITTER_NAME=test GIT_COMMITTER_EMAIL=test@test
}

teardown() {
    cd /
    rm -rf "$TMP_PROJECT" "$UPSTREAM"
}

@test "bootstrap em external_repo (clone) detecta base_branch=master" {
    run python "$BOOTSTRAP_PY" \
        --profile cli_tool \
        --tier tool \
        --project-root "$TMP_PROJECT" \
        --workspace-name analysis-x
    [ "$status" -eq 0 ]

    grep -q "base_branch: \"master\"" "${TMP_PROJECT}/workspaces/001-analysis-x/CLAUDE.md"
}

@test "bootstrap nao toca lib/ do external upstream" {
    run python "$BOOTSTRAP_PY" \
        --profile cli_tool \
        --tier tool \
        --project-root "$TMP_PROJECT" \
        --workspace-name analysis-x
    [ "$status" -eq 0 ]

    [ -f "${TMP_PROJECT}/lib/core.js" ]
    grep -q "external lib" "${TMP_PROJECT}/lib/core.js"
}

@test "workspace branch criada de base master sem afetar master" {
    run python "$BOOTSTRAP_PY" \
        --profile cli_tool \
        --tier tool \
        --project-root "$TMP_PROJECT" \
        --workspace-name analysis-x
    [ "$status" -eq 0 ]

    # branch atual = workspace
    actual="$(git -C "$TMP_PROJECT" rev-parse --abbrev-ref HEAD)"
    [ "$actual" = "workspace/001-analysis-x" ]

    # master ainda existe e nao tem commits do workspace
    git -C "$TMP_PROJECT" show-ref --verify --quiet refs/heads/master
    master_count="$(git -C "$TMP_PROJECT" rev-list --count master)"
    [ "$master_count" -eq 1 ]  # so o initial do upstream
}

@test "pre-commit hook instalado no .git/hooks (clone, nao upstream)" {
    run python "$BOOTSTRAP_PY" \
        --profile cli_tool \
        --tier tool \
        --project-root "$TMP_PROJECT" \
        --workspace-name analysis-x
    [ "$status" -eq 0 ]

    [ -x "${TMP_PROJECT}/.git/hooks/pre-commit" ]
    # Hook nao foi propagado pro upstream (pra clones, hooks sao locais)
    [ ! -f "${UPSTREAM}/.git/hooks/pre-commit" ] || \
        ! grep -q "atomicidade L1" "${UPSTREAM}/.git/hooks/pre-commit" 2>/dev/null
}

@test "remote origin preservado apos bootstrap" {
    run python "$BOOTSTRAP_PY" \
        --profile cli_tool \
        --tier tool \
        --project-root "$TMP_PROJECT" \
        --workspace-name analysis-x
    [ "$status" -eq 0 ]

    remote_url="$(git -C "$TMP_PROJECT" remote get-url origin)"
    [ "$remote_url" = "$UPSTREAM" ]
}

@test "L1 inicial valido em external_repo (mesmo schema greenfield)" {
    run python "$BOOTSTRAP_PY" \
        --profile cli_tool \
        --tier tool \
        --project-root "$TMP_PROJECT" \
        --workspace-name analysis-x
    [ "$status" -eq 0 ]

    L1="${TMP_PROJECT}/workspaces/001-analysis-x/CONTEXT.md"
    grep -q "stage_atual: \"00\"" "$L1"
    grep -q "iteration: 0" "$L1"
    ! grep -E "\{\{[A-Z_]+\}\}" "$L1"  # placeholders todos resolvidos
}
