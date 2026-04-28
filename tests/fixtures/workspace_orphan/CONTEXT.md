---
workspace: "999-orphan-fixture"
profile_base: "app_web_backend"
profile_effective_hash: "0000000000000000000000000000000000000000000000000000000000000000"
tier: "development"
project_root: "/tmp/fake-project-root"
base_branch: "main"
workspace_branch: "workspace/999-orphan-fixture"
stage_atual: "02"
sub_stage: "02_in_progress"
status: "IN_PROGRESS"
iteration: 0
llm_review_skipped_count: 0
last_action: "design decisions snapshotted"
last_action_at: "2026-04-20T10:00:00Z"
next_action: "review decisions com humano"
last_transition:
  from: "01_completed"
  to: "02_in_progress"
  at: "2026-04-20T10:00:00Z"
  commit_sha: "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
history:
  - at: "2026-04-19T09:00:00Z"
    event: "stage_transition"
    from: "00_completed"
    to: "01_in_progress"
    commit_sha: "1111111111111111111111111111111111111111"
  - at: "2026-04-20T10:00:00Z"
    event: "stage_transition"
    from: "01_completed"
    to: "02_in_progress"
    commit_sha: "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
    note: "design start; output stages/02_design/output/decisions.md + stages/02_design/output/ghost.md"
---

# Workspace 999 — orphan fixture

Fixture orfa documentando 4 inconsistencias L1 simultaneamente:

1. **HASH_MISMATCH:** `profile_effective_hash` em L1 e zero (64 zeros)
   mas `_config/profile-effective.yaml` tem conteudo real -> hashes nao batem.
2. **MISSING_OUTPUT:** history menciona `stages/02_design/output/ghost.md`
   no campo `note` mas o arquivo nao existe no FS. (Apenas `decisions.md`
   foi escrito de fato.)
3. **STALE_IN_PROGRESS:** `status=IN_PROGRESS` com `last_action_at` em
   2026-04-20 — mais de 24h se a sessao corrente for >= 2026-04-22.
4. **MISSING_COMMIT:** `last_transition.commit_sha=deadbeef...` nao existe
   em git history — `git cat-file -e` falha.

Inconsistencia 5 (BRANCH_MISSING) so se aplica quando esta dentro de um repo
git real, entao e testada com fixtures programaticas em test_recovery_wizard.py.
