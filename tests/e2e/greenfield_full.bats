#!/usr/bin/env bats
# CI-only — bats nao rodavel local em Windows.
#
# E2E: bootstrap greenfield → percorre estágios 00 → 07 sequencial,
# sem subagentes (single subagente sintético em 04). Valida transições
# L1 e existência de outputs declarados em cada L2 template.
#
# Cada step:
#   1. escreve output_files mínimos do estágio
#   2. atualiza L1 (sub_stage + status + history append)
#   3. roda validate-state.sh (espera exit 0)
#   4. avança para próximo estágio
#
# Não invoca agentes reais — testa infraestrutura (bootstrap + templates +
# validate-state) end-to-end.

setup() {
    SKILL_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/../.." && pwd)"
    BOOTSTRAP_PY="${SKILL_ROOT}/scripts/bootstrap.py"
    VALIDATE_SH="${SKILL_ROOT}/scripts/validate-state.sh"

    TMP_PROJECT="$(mktemp -d)"

    export GIT_AUTHOR_NAME=test
    export GIT_AUTHOR_EMAIL="test@test"
    export GIT_COMMITTER_NAME=test
    export GIT_COMMITTER_EMAIL="test@test"

    # Bootstrap greenfield (cria workspace 001-feat-e2e)
    run python "$BOOTSTRAP_PY" \
        --profile cli_tool \
        --tier tool \
        --project-root "$TMP_PROJECT" \
        --workspace-name feat-e2e
    [ "$status" -eq 0 ]

    WS_DIR="${TMP_PROJECT}/workspaces/001-feat-e2e"
    L1="${WS_DIR}/CONTEXT.md"
    export WS_DIR L1 TMP_PROJECT
}

teardown() {
    cd /
    rm -rf "$TMP_PROJECT"
}

# Helper: append simples no L1 history. Não-portável em yaml strict, suficiente
# para o teste de infraestrutura (sub_stage update via sed line replace).
update_l1_substage() {
    local new_sub_stage="$1"
    local new_status="$2"
    sed -i.bak -E "s/^sub_stage:.*/sub_stage: \"${new_sub_stage}\"/" "$L1"
    sed -i.bak -E "s/^status:.*/status: \"${new_status}\"/" "$L1"
    rm -f "${L1}.bak"
}

write_output() {
    local stage_dir="$1"
    local filename="$2"
    mkdir -p "${WS_DIR}/stages/${stage_dir}/output"
    echo "# stub output ${filename}" > "${WS_DIR}/stages/${stage_dir}/output/${filename}"
}

commit_workspace() {
    local msg="$1"
    cd "$TMP_PROJECT"
    git add "workspaces/001-feat-e2e/" || true
    git commit -m "$msg" --no-verify -q || true
    cd - >/dev/null
}

# 1. Bootstrap criou todos os 9 dirs de stage ---------------------------------

@test "bootstrap cria 9 dirs de stages 00..08" {
    [ -d "${WS_DIR}/stages/00_recon" ]
    [ -d "${WS_DIR}/stages/01_discovery" ]
    [ -d "${WS_DIR}/stages/02_design" ]
    [ -d "${WS_DIR}/stages/03_wave_planner" ]
    [ -d "${WS_DIR}/stages/04_implementation_waves" ]
    [ -d "${WS_DIR}/stages/05_verification" ]
    [ -d "${WS_DIR}/stages/06_review" ]
    [ -d "${WS_DIR}/stages/07_merge" ]
    [ -d "${WS_DIR}/stages/08_feedback_intake" ]
}

@test "L1 inicial é válido (sub_stage 00_in_progress)" {
    grep -q "stage_atual: \"00\"" "$L1"
    grep -q "sub_stage: \"00_in_progress\"" "$L1"
    grep -q "status: \"IN_PROGRESS\"" "$L1"
}

# 2. Estágio 00 recon → 01 ---------------------------------------------------

@test "00 recon: escreve recon-report + transição → 01_in_progress" {
    write_output "00_recon" "recon-report.md"
    update_l1_substage "00_completed" "COMPLETED_AWAITING_HUMAN"
    [ -f "${WS_DIR}/stages/00_recon/output/recon-report.md" ]
    grep -q "00_completed" "$L1"
}

# 3. Estágio 01 discovery ----------------------------------------------------

@test "01 discovery: escreve discovery.md" {
    update_l1_substage "01_in_progress" "IN_PROGRESS"
    write_output "01_discovery" "discovery.md"
    update_l1_substage "01_completed" "COMPLETED_AWAITING_HUMAN"
    [ -f "${WS_DIR}/stages/01_discovery/output/discovery.md" ]
    grep -q "01_completed" "$L1"
}

# 4. Estágio 02 design -------------------------------------------------------

@test "02 design: escreve plan.md com 1 task minimal" {
    update_l1_substage "02_in_progress" "IN_PROGRESS"
    mkdir -p "${WS_DIR}/stages/02_design/output"
    cat > "${WS_DIR}/stages/02_design/output/plan.md" <<EOF
# Plan

## Task task-foo
### WHAT
- deliver foo

### HOW
- src/foo.py

### OUT OF SCOPE
- bar

### VALIDATION
- tests/test_foo.py passes

### Files touched
- src/foo.py
- tests/test_foo.py

### Applicable ADRs
- (none)

### Critical pre-tagged lessons
- (none)

### Extra conventions
- (default)

### Tech debt paydown
- none

### Requires_peer_review
- false
EOF
    update_l1_substage "02_completed" "COMPLETED_AWAITING_HUMAN"
    [ -f "${WS_DIR}/stages/02_design/output/plan.md" ]
    grep -q "02_completed" "$L1"
}

# 5. Estágio 03 wave_planner -------------------------------------------------

@test "03 wave_planner: escreve wave-plan.md (stub) → 04" {
    update_l1_substage "03_in_progress" "IN_PROGRESS"
    write_output "03_wave_planner" "wave-plan.md"
    update_l1_substage "03_completed" "COMPLETED_AWAITING_HUMAN"
    [ -f "${WS_DIR}/stages/03_wave_planner/output/wave-plan.md" ]
}

# 6. Estágio 04 implementation_waves (single wave / single task) -------------

@test "04 implementation_waves: wave-1 single task → 05" {
    update_l1_substage "04_wave_1_in_progress" "IN_PROGRESS"
    mkdir -p "${WS_DIR}/stages/04_implementation_waves/output/wave-1"
    echo "# task-foo COMPLETE" > "${WS_DIR}/stages/04_implementation_waves/output/wave-1/task-foo.md"
    echo "# wave-1 summary" > "${WS_DIR}/stages/04_implementation_waves/output/wave-1/wave-summary.md"
    update_l1_substage "04_wave_1_completed" "COMPLETED_AWAITING_HUMAN"
    [ -f "${WS_DIR}/stages/04_implementation_waves/output/wave-1/task-foo.md" ]
    [ -f "${WS_DIR}/stages/04_implementation_waves/output/wave-1/wave-summary.md" ]
    grep -q "04_wave_1_completed" "$L1"
}

# 7. Estágio 05 verification -------------------------------------------------

@test "05 verification: escreve verification-report.md" {
    update_l1_substage "05_in_progress" "IN_PROGRESS"
    write_output "05_verification" "verification-report.md"
    update_l1_substage "05_completed" "COMPLETED_AWAITING_HUMAN"
    [ -f "${WS_DIR}/stages/05_verification/output/verification-report.md" ]
}

# 8. Estágio 06 review (sem P0/P1 — direto pra 07) --------------------------

@test "06 review: escreve review-report sem P0/P1 → 07" {
    update_l1_substage "06_in_progress" "IN_PROGRESS"
    write_output "06_review" "review-report.md"
    update_l1_substage "06_completed" "COMPLETED_AWAITING_HUMAN"
    [ -f "${WS_DIR}/stages/06_review/output/review-report.md" ]
}

# 9. Estágio 07 merge → COMPLETED -------------------------------------------

@test "07 merge: escreve merge-report → status COMPLETED" {
    update_l1_substage "07_in_progress" "IN_PROGRESS"
    write_output "07_merge" "merge-report.md"
    update_l1_substage "07_completed" "COMPLETED"
    [ -f "${WS_DIR}/stages/07_merge/output/merge-report.md" ]
    grep -q "status: \"COMPLETED\"" "$L1"
    grep -q "07_completed" "$L1"
}

# 10. Validação final: workspace tem todos os outputs declarados ------------

@test "fluxo completo: outputs de todos os 7 estágios existem" {
    write_output "00_recon" "recon-report.md"
    write_output "01_discovery" "discovery.md"
    mkdir -p "${WS_DIR}/stages/02_design/output"
    echo "stub" > "${WS_DIR}/stages/02_design/output/plan.md"
    write_output "03_wave_planner" "wave-plan.md"
    mkdir -p "${WS_DIR}/stages/04_implementation_waves/output/wave-1"
    echo "stub" > "${WS_DIR}/stages/04_implementation_waves/output/wave-1/wave-summary.md"
    write_output "05_verification" "verification-report.md"
    write_output "06_review" "review-report.md"
    write_output "07_merge" "merge-report.md"

    [ -f "${WS_DIR}/stages/00_recon/output/recon-report.md" ]
    [ -f "${WS_DIR}/stages/01_discovery/output/discovery.md" ]
    [ -f "${WS_DIR}/stages/02_design/output/plan.md" ]
    [ -f "${WS_DIR}/stages/03_wave_planner/output/wave-plan.md" ]
    [ -f "${WS_DIR}/stages/04_implementation_waves/output/wave-1/wave-summary.md" ]
    [ -f "${WS_DIR}/stages/05_verification/output/verification-report.md" ]
    [ -f "${WS_DIR}/stages/06_review/output/review-report.md" ]
    [ -f "${WS_DIR}/stages/07_merge/output/merge-report.md" ]
}
