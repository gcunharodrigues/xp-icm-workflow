#!/usr/bin/env bats
# CI-only — bats nao rodavel local em Windows.
#
# E2E: bootstrap em projeto existente (com src/, tests/, ADRs, commits prévios).
# Verifica que workspace branch e criada de main correto, L0/L1 refletem
# profile/tier, scaffold completo, base_branch detectado automaticamente.

setup() {
    SKILL_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/../.." && pwd)"
    BOOTSTRAP_PY="${SKILL_ROOT}/scripts/bootstrap.py"

    TMP_PROJECT="$(mktemp -d)"
    cd "$TMP_PROJECT"

    git init -q -b main
    git config user.email "test@test"
    git config user.name "test"

    # Repo "existente": codigo + tests + ADRs + lessons
    mkdir -p src/auth tests/auth docs/decisions
    echo "# auth middleware" > src/auth/middleware.ts
    echo "# auth tests" > tests/auth/middleware.test.ts
    cat > docs/decisions/0001-stack.md <<EOF
# 0001 — Stack
## Context
Stack inicial.
## Decision
TypeScript + Express.
## Status
Accepted.
EOF
    echo "# Lessons" > docs/lessons.md
    git add .
    git commit -q -m "initial existing project"

    export GIT_AUTHOR_NAME=test GIT_AUTHOR_EMAIL=test@test
    export GIT_COMMITTER_NAME=test GIT_COMMITTER_EMAIL=test@test
}

teardown() {
    cd /
    rm -rf "$TMP_PROJECT"
}

@test "bootstrap em existing repo cria workspace sem tocar src/" {
    run python "$BOOTSTRAP_PY" \
        --profile app_web_backend \
        --tier development \
        --project-root "$TMP_PROJECT" \
        --workspace-name feat-auth-v2
    [ "$status" -eq 0 ]

    # Codigo existente NAO foi tocado
    [ -f "${TMP_PROJECT}/src/auth/middleware.ts" ]
    [ -f "${TMP_PROJECT}/tests/auth/middleware.test.ts" ]
    [ -f "${TMP_PROJECT}/docs/decisions/0001-stack.md" ]

    # Workspace criado
    [ -d "${TMP_PROJECT}/workspaces/001-feat-auth-v2/stages/00_recon" ]
    [ -d "${TMP_PROJECT}/workspaces/001-feat-auth-v2/_config" ]
    [ -f "${TMP_PROJECT}/workspaces/001-feat-auth-v2/CLAUDE.md" ]
    [ -f "${TMP_PROJECT}/workspaces/001-feat-auth-v2/CONTEXT.md" ]
}

@test "bootstrap detecta base_branch=main do repo existente" {
    run python "$BOOTSTRAP_PY" \
        --profile app_web_backend \
        --tier development \
        --project-root "$TMP_PROJECT" \
        --workspace-name feat-auth-v2
    [ "$status" -eq 0 ]

    grep -q "base_branch: \"main\"" "${TMP_PROJECT}/workspaces/001-feat-auth-v2/CLAUDE.md"
}

@test "L0 reflete profile + tier corretos" {
    run python "$BOOTSTRAP_PY" \
        --profile app_web_backend \
        --tier development \
        --project-root "$TMP_PROJECT" \
        --workspace-name feat-auth-v2
    [ "$status" -eq 0 ]

    grep -q "profile: \"app_web_backend\"" "${TMP_PROJECT}/workspaces/001-feat-auth-v2/CLAUDE.md"
    grep -q "tier: \"development\"" "${TMP_PROJECT}/workspaces/001-feat-auth-v2/CLAUDE.md"
}

@test "branch atual = workspace/001-feat-auth-v2 apos bootstrap" {
    run python "$BOOTSTRAP_PY" \
        --profile app_web_backend \
        --tier development \
        --project-root "$TMP_PROJECT" \
        --workspace-name feat-auth-v2
    [ "$status" -eq 0 ]

    actual="$(git -C "$TMP_PROJECT" rev-parse --abbrev-ref HEAD)"
    [ "$actual" = "workspace/001-feat-auth-v2" ]
}

@test "ADRs e lessons preservados (nao sobrescritos)" {
    run python "$BOOTSTRAP_PY" \
        --profile app_web_backend \
        --tier development \
        --project-root "$TMP_PROJECT" \
        --workspace-name feat-auth-v2
    [ "$status" -eq 0 ]

    grep -q "TypeScript + Express" "${TMP_PROJECT}/docs/decisions/0001-stack.md"
    [ -f "${TMP_PROJECT}/docs/lessons.md" ]
}

@test "L1 inicial em estagio 00 IN_PROGRESS" {
    run python "$BOOTSTRAP_PY" \
        --profile app_web_backend \
        --tier development \
        --project-root "$TMP_PROJECT" \
        --workspace-name feat-auth-v2
    [ "$status" -eq 0 ]

    L1="${TMP_PROJECT}/workspaces/001-feat-auth-v2/CONTEXT.md"
    grep -q "stage_atual: \"00\"" "$L1"
    grep -q "sub_stage: \"00_in_progress\"" "$L1"
    grep -q "status: \"IN_PROGRESS\"" "$L1"
}
