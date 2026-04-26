#!/usr/bin/env bats
# Integration tests para scripts/bootstrap.sh + scripts/bootstrap.py.
#
# CI-only via Ubuntu runner (bats nao roda em Windows local).
# Execucao: bats tests/integration/test_bootstrap.bats
#
# Estrategia: cada teste cria project_root tmp, invoca bootstrap.sh com flags
# nao-interativas, verifica filesystem + git resultantes.

setup() {
    SKILL_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/../.." && pwd)"
    BOOTSTRAP_SH="${SKILL_ROOT}/scripts/bootstrap.sh"
    BOOTSTRAP_PY="${SKILL_ROOT}/scripts/bootstrap.py"

    TMP_PROJECT="$(mktemp -d)"

    # Identidade git pra commits no project_root
    export GIT_AUTHOR_NAME=test
    export GIT_AUTHOR_EMAIL="test@test"
    export GIT_COMMITTER_NAME=test
    export GIT_COMMITTER_EMAIL="test@test"
}

teardown() {
    cd /
    rm -rf "$TMP_PROJECT"
}

# 1. Greenfield: bootstrap em diretorio sem .git -----------------------------

@test "greenfield bootstrap creates workspace, branch, scaffold, commits" {
    run python "$BOOTSTRAP_PY" \
        --profile cli_tool \
        --tier tool \
        --project-root "$TMP_PROJECT" \
        --workspace-name feat-foo
    [ "$status" -eq 0 ]

    # Project agora tem .git inicializado
    [ -d "${TMP_PROJECT}/.git" ]

    # Branch atual e workspace/001-feat-foo
    actual_branch="$(git -C "$TMP_PROJECT" rev-parse --abbrev-ref HEAD)"
    [ "$actual_branch" = "workspace/001-feat-foo" ]

    # Scaffold dirs presentes
    [ -d "${TMP_PROJECT}/workspaces/001-feat-foo/stages/00_recon" ]
    [ -d "${TMP_PROJECT}/workspaces/001-feat-foo/stages/08_feedback_intake" ]
    [ -d "${TMP_PROJECT}/workspaces/001-feat-foo/_config" ]
    [ -d "${TMP_PROJECT}/workspaces/001-feat-foo/_references/superpowers-summary" ]

    # L0 e L1 com placeholders substituidos (sem `{{X}}` sobrando)
    [ -f "${TMP_PROJECT}/workspaces/001-feat-foo/CLAUDE.md" ]
    [ -f "${TMP_PROJECT}/workspaces/001-feat-foo/CONTEXT.md" ]
    ! grep -E "\{\{[A-Z_]+\}\}" "${TMP_PROJECT}/workspaces/001-feat-foo/CLAUDE.md"
    ! grep -E "\{\{[A-Z_]+\}\}" "${TMP_PROJECT}/workspaces/001-feat-foo/CONTEXT.md"

    # 3 commits: initial + scaffold + persist sha
    n_commits="$(git -C "$TMP_PROJECT" rev-list --count HEAD)"
    [ "$n_commits" -eq 3 ]
}

# 2. Existing repo: bootstrap detecta base_branch existente ------------------

@test "existing repo bootstrap captures base_branch correctly" {
    cd "$TMP_PROJECT"
    git init -q -b trunk
    echo "code" > main.py
    git add main.py
    git commit -q -m "existing"

    run python "$BOOTSTRAP_PY" \
        --profile app_web_backend \
        --tier development \
        --project-root "$TMP_PROJECT" \
        --workspace-name feat-bar
    [ "$status" -eq 0 ]

    # base_branch capturado = trunk (nao main!)
    grep -q 'base_branch: "trunk"' "${TMP_PROJECT}/workspaces/001-feat-bar/CLAUDE.md"
    grep -q 'base_branch: "trunk"' "${TMP_PROJECT}/workspaces/001-feat-bar/CONTEXT.md"
}

# 3. .icm-profile.local.yaml override e aplicado -----------------------------

@test "bootstrap with .icm-profile.local.yaml override applies it" {
    cd "$TMP_PROJECT"
    cat > .icm-profile.local.yaml <<EOF
extends: cli_tool
tier: development
overrides:
  cap_teammates_per_wave: 4
EOF

    run python "$BOOTSTRAP_PY" \
        --profile cli_tool \
        --tier development \
        --project-root "$TMP_PROJECT" \
        --workspace-name feat-override \
        --override "${TMP_PROJECT}/.icm-profile.local.yaml"
    [ "$status" -eq 0 ]

    # profile-effective.yaml deve refletir cap = 4
    grep -q "cap_teammates_per_wave: 4" \
        "${TMP_PROJECT}/workspaces/001-feat-override/_config/profile-effective.yaml"
}

# 4. Sem profile/tier --> exit 1 ----------------------------------------------

@test "bootstrap without profile or tier fails" {
    run python "$BOOTSTRAP_PY" \
        --profile cli_tool \
        --project-root "$TMP_PROJECT" \
        --workspace-name feat-nope
    [ "$status" -ne 0 ]
}

# 5. .index.md atualizado corretamente ---------------------------------------

@test "bootstrap appends to workspaces/.index.md" {
    run python "$BOOTSTRAP_PY" \
        --profile cli_tool \
        --tier tool \
        --project-root "$TMP_PROJECT" \
        --workspace-name first
    [ "$status" -eq 0 ]

    [ -f "${TMP_PROJECT}/workspaces/.index.md" ]
    grep -q "| 001 | first | cli_tool/tool" "${TMP_PROJECT}/workspaces/.index.md"

    # Segundo bootstrap deve incrementar para 002
    git -C "$TMP_PROJECT" checkout -q main
    run python "$BOOTSTRAP_PY" \
        --profile cli_tool \
        --tier tool \
        --project-root "$TMP_PROJECT" \
        --workspace-name second
    [ "$status" -eq 0 ]

    grep -q "| 002 | second |" "${TMP_PROJECT}/workspaces/.index.md"
}

# 6. .gitignore idempotente --------------------------------------------------

@test "bootstrap updates .gitignore idempotently" {
    cd "$TMP_PROJECT"
    git init -q -b main
    cat > .gitignore <<EOF
node_modules/
.worktrees/
EOF
    git add .gitignore
    git commit -q -m "initial"

    cd /
    run python "$BOOTSTRAP_PY" \
        --profile cli_tool \
        --tier tool \
        --project-root "$TMP_PROJECT" \
        --workspace-name feat-gi
    [ "$status" -eq 0 ]

    # .worktrees/ aparece UMA vez (nao duplicada)
    n="$(grep -c '^\.worktrees/$' "${TMP_PROJECT}/.gitignore")"
    [ "$n" -eq 1 ]

    # node_modules/ preservado
    grep -q "node_modules/" "${TMP_PROJECT}/.gitignore"

    # .icm-profile.local.yaml adicionado
    grep -q ".icm-profile.local.yaml" "${TMP_PROJECT}/.gitignore"
}

# 7. Pre-commit hook instalado e executavel ----------------------------------

@test "bootstrap installs pre-commit hook (executable)" {
    run python "$BOOTSTRAP_PY" \
        --profile cli_tool \
        --tier tool \
        --project-root "$TMP_PROJECT" \
        --workspace-name feat-hook
    [ "$status" -eq 0 ]

    [ -f "${TMP_PROJECT}/.git/hooks/pre-commit" ]
    [ -x "${TMP_PROJECT}/.git/hooks/pre-commit" ]

    # Conteudo deve bater com template fonte
    diff -q "${SKILL_ROOT}/templates/.git-hooks/pre-commit" \
        "${TMP_PROJECT}/.git/hooks/pre-commit"
}

# 8. Workspace dir ja existente --> exit 1 -----------------------------------

@test "bootstrap aborts when workspace dir already exists" {
    cd "$TMP_PROJECT"
    git init -q -b main
    mkdir -p workspaces/001-feat-dup
    echo "stale" > workspaces/001-feat-dup/CONTEXT.md
    git add workspaces/001-feat-dup/CONTEXT.md
    git commit -q -m "stale workspace dir"

    cd /
    run python "$BOOTSTRAP_PY" \
        --profile cli_tool \
        --tier tool \
        --project-root "$TMP_PROJECT" \
        --workspace-name feat-dup
    [ "$status" -ne 0 ]
    [[ "$output" == *"ja existe"* ]] || [[ "$output" == *"workspace dir"* ]]
}

# 9. profile-effective.yaml persistido com hash -----------------------------

@test "bootstrap persists profile-effective.yaml with hash" {
    run python "$BOOTSTRAP_PY" \
        --profile experiment \
        --tier experimental \
        --project-root "$TMP_PROJECT" \
        --workspace-name feat-effective
    [ "$status" -eq 0 ]

    eff="${TMP_PROJECT}/workspaces/001-feat-effective/_config/profile-effective.yaml"
    [ -f "$eff" ]
    grep -q "__hash__:" "$eff"
    grep -q "profile: experiment" "$eff"
    grep -q "tier: experimental" "$eff"
}

# 10. Slug invalido --> exit 1 -----------------------------------------------

@test "bootstrap rejects invalid slug" {
    run python "$BOOTSTRAP_PY" \
        --profile cli_tool \
        --tier tool \
        --project-root "$TMP_PROJECT" \
        --workspace-name "FEAT_BAD"
    [ "$status" -ne 0 ]
    [[ "$output" == *"slug"* ]]
}
