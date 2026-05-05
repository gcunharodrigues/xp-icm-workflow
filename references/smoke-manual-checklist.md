---
name: smoke-manual-checklist
purpose: Manual smoke test checklist pre-release (plan §8.2)
gate: v3.0.0-beta5 → v3.0.0 promotion
required_projects: 3
---

# Smoke manual — pre-release v3.0.0-beta5

> Before promoting `v3.0.0-beta5` to `v3.0.0`: run all 10 items in ≥3 distinct real projects. Document result per project in `references/smoke-results-<project>-<YYYY-MM-DD>.md`.

## General criteria (all items)

- ✅ **PASS** if: behavior per documentation + no crash + no FS/git corruption.
- ❌ **FAIL** if: crash, write outside declared scope, regression of any prior Wave, loss of human work.
- ⚠️ **WARN** if: correct behavior but confusing UX / poor message / unexpected extra step. Note for Wave 8 (future improvements).

## The 13 items

### 1. Real greenfield

`profile=app_web_backend tier=development project_root=<new-path>`. Walk through 00→07 on a small project (3-5 tasks).

**Verify:**
- [ ] Bootstrap exit 0, 9 dirs created, L0/L1 with no leftover placeholders
- [ ] Each stage transitions as declared by L2
- [ ] Pre-commit hook blocks bypass attempts
- [ ] Total token spend ≤ 60% of v2.4 at same scale (if baseline exists)

### 2. Existing repo Aura ecosystem

Repo already with CLAUDE.md, ADRs in `docs/decisions/`, `docs/lessons.md`.

**Verify:**
- [ ] Recon (stage 00) correctly detects type `existing`
- [ ] Active ADRs appear in recon-report (index only, without reading body)
- [ ] Discovery (stage 01) does NOT repeat questions already answered in CLAUDE.md
- [ ] Inheritable lessons cited in recon-report

### 3. External repo

Read-only clone of any skill (e.g., `superpowers/skills/brainstorming`).

**Verify:**
- [ ] Bootstrap does not accidentally commit to upstream master/main
- [ ] Current branch = `workspace/NNN-<slug>`
- [ ] master/main of the clone remains at 1 commit (upstream initial)
- [ ] Local hook installed but not propagated to upstream

### 4. tier=production with 5 subagents

Plan.md with ≥5 parallelizable tasks.

**Verify:**
- [ ] Wave Planner builds correct DAG (no cycle, deps respected)
- [ ] 5 branches created in `wave-NNN-1/<task-slug>`
- [ ] Each subagent on isolated branch `wave-NNN-1/<task-slug>`
- [ ] Sync barrier waits for all COMPLETE before wave-reviewer
- [ ] Clean sequential merge OR conflict escalated to human with clear message
- [ ] CI global gate green before wave 2

### 5. Real stop point

Design (stage 02) lists new paid dependency (e.g., SaaS Auth0 R$ 300/month).

**Verify:**
- [ ] Stop point `paid_service` fires per tier calibration
- [ ] A/B/C menu written with trade-offs + recommendation + reversibility
- [ ] L1 status becomes `BLOCKED_STOP_POINT`, history append
- [ ] Human replies "B", session resumes `IN_PROGRESS`
- [ ] history append `stop_point_resolved` with choice

### 6. Override yaml with guard-rail

`.icm-profile.local.yaml` with `tdd_required: false` on `tier=production` (without `confirm_unsafe`).

**Verify:**
- [ ] Bootstrap refuses with `ProfileMergeError("dangerous override requires confirm_unsafe: true")`
- [ ] Add `confirm_unsafe: true`, retry → bootstrap accepts
- [ ] L0 reflects `tdd_required: false` in profile-effective.yaml

### 7. Recovery Wizard

Force orphan workspace: kill session mid-stage 04 (kill process during wave-1 spawn).

**Verify:**
- [ ] Next session pre-flight detects inconsistency (R2.7)
- [ ] Recovery Wizard triggers automatically with 3 actions A/B/C
- [ ] Apply A (rebuild from history) → L1 reconstructed
- [ ] Session resumes from correct `stage_atual` without losing work

### 8. Feedback intake stage 08 — 3 exits

Workspace COMPLETED → human triggers stage 08 manually, 3 times (3 workspaces or 1 with 3 iterations).

**Verify:**
- [ ] **Exit A** (close): status → `COMPLETED`, sub_stage → `08_decided_A`, lessons append in `docs/lessons.md`
- [ ] **Exit B** (restart stage X): X ∈ {01..07} accepted (refuses 00 and 08), iteration++, old outputs moved to `output-iteration-<N>/`, status → `IN_PROGRESS`, stage_atual → X
- [ ] **Exit C** (spawn new): message to human with exact command, sub_stage → `08_decided_C`, spawn_to set, session exits without bootstrapping 043

### 9. Cost $ comparison

Same canonical project (3-5 tasks) run on v2.4 and v3.0-beta1. Measure total input + output tokens.

**Verify:**
- [ ] v3 ≤ 60% of v2.4 (target plan §8.3)
- [ ] Gain comes from: 200tok summaries vs formal skill invocation + sub_stage tracking + lean sessions
- [ ] Document numbers in `references/smoke-results-<project>.md`

### 10. Absolute path (Windows / cross-drive)

Workspace in `D:\workspaces\NNN-<slug>\`, project in `C:\projects\X\`.

**Verify:**
- [ ] L0 resolves `project_root: C:/projects/X/` correctly
- [ ] Code written goes into `C:\projects\X\src\` (NEVER inside the workspace)
- [ ] Branches created in `C:\projects\X\` (format `wave-NNN-N/<task-slug>`)
- [ ] Pre-commit hook validates prefix `workspaces/NNN/` on workspace branch (does not allow writing to `src/`)

### 11. Test Infrastructure — profile-effective.yaml

`profile=app_web_backend tier=development`. Verify test_specs generation.

**Verify:**
- [ ] `profile-effective.yaml` contains field `test_specs` with sub-fields `test_types_required`, `coverage_threshold`, `http_integration`, `db_integration`
- [ ] `coverage_threshold` = 80 for tier=development (per defaults table)
- [ ] `test_types_required` = `[unit, integration]` for profile `app_web_backend`
- [ ] Field `test_specs` absent from `.icm-profile.local.yaml` — not overridable

### 12. Test Strategy in plan.md (stage 02)

Walk through stage 02 on a real workspace.

**Verify:**
- [ ] Stage 02 produces section `§Test Strategy` in plan.md (framework, pyramid, threshold, critical path)
- [ ] Every task with files in `src/` declares ≥1 test file in `Files touched`
- [ ] Task without test file in `Files touched` for functional code → Wave Planner fires `BLOCKED_ERROR "test file missing for task <slug>"`
- [ ] Stage 02 transition condition blocks if Test Strategy is absent

### 13. Test-recipe copied in bootstrap

Bootstrap with any profile (e.g., `agent_ia`, `ml_project`).

**Verify:**
- [ ] `workspace/_references/test-recipes/<profile>.md` exists after bootstrap
- [ ] Recipe content matches `templates/_references/test-recipes/<profile>.md` from the skill
- [ ] Stage 01 lists the file in the Inputs table (Input #12) as `conditional`
- [ ] Stage 05 step 4.6 runs sample-check and reports PASS/CONDITIONAL/FAIL

## Acceptance criteria for promoting beta1 → v3.0.0 (plan §8.3)

- ✅ Formal suite: ≥80% coverage on critical, ≥60% on rest. CI green 7 consecutive days.
- ✅ ≥3 real projects used v3.0.0-beta1 without severe regression (bug destroying work).
- ✅ $ comparison documented: v3 ≤ 60% v2.4 in ≥3 projects.
- ✅ 10 items from this checklist PASS in ≥3 projects.
- ✅ Lessons collected in `docs/lessons.md` of the skill itself (Wave 7 creates).

## Report template per project

```markdown
# Smoke result — <project> — <YYYY-MM-DD>

| # | Item | Status | Notes |
|---|---|---|---|
| 1 | Real greenfield | ✅/❌/⚠️ | ... |
| 2 | Existing repo | ✅/❌/⚠️ | ... |
| 3 | External repo | ✅/❌/⚠️ | ... |
| 4 | 5 subagents | ✅/❌/⚠️ | ... |
| 5 | Real stop point | ✅/❌/⚠️ | ... |
| 6 | Override guard-rail | ✅/❌/⚠️ | ... |
| 7 | Recovery Wizard | ✅/❌/⚠️ | ... |
| 8 | Feedback intake A/B/C | ✅/❌/⚠️ | ... |
| 9 | Cost $ vs v2.4 | ✅/❌/⚠️ | v3=Xtok / v2.4=Ytok = Z% |
| 10 | Absolute path | ✅/❌/⚠️ | ... |
| 11 | test_specs in profile-effective | ✅/❌/⚠️ | ... |
| 12 | Test Strategy in plan.md | ✅/❌/⚠️ | ... |
| 13 | test-recipe copied in bootstrap | ✅/❌/⚠️ | ... |

## Bugs found
- ...

## UX warnings
- ...

## Lessons
- ...
```

---

## v3.3.0 — new smoke manual items

After bootstrap in `tier=development`, verify:

- [ ] `<project_root>/CLAUDE.md` created with ICM region (`<!-- ICM-START/END -->`)
- [ ] `<workspace>/_config/CONTEXT.md` (L3 ubiquitous language) present, frontmatter `layer: L3, scope: ubiquitous_language`
- [ ] `<workspace>/_out-of-scope/README.md` present
- [ ] `<workspace>/_references/runtime/agent-brief-template.md` present
- [ ] `<workspace>/_references/runtime/context-format.md` present
- [ ] `<workspace>/_references/runtime/adr-format.md` present
- [ ] `<workspace>/_references/runtime/diagnose-protocol.md` present
- [ ] `<workspace>/_references/runtime/triage-state-machine.md` present
- [ ] `<workspace>/_references/runtime/out-of-scope-kb.md` present
- [ ] `<workspace>/_references/runtime/design-it-twice.md` present
- [ ] `<workspace>/_config/hitl-loop.template.sh` present
- [ ] `docs/decisions/_template.md` present

On workspace branch:
- [ ] Edit `<project_root>/CLAUDE.md` and `git add CLAUDE.md` — pre-commit hook allows (G6 whitelist)
- [ ] Recovery wizard detects `CLAUDE_MD_ROOT_STALE` when L1.stage_atual diverges from the block in CLAUDE.md root

Brownfield:
- [ ] Bootstrap on a project with pre-existing CLAUDE.md preserves content outside ICM markers byte-for-byte
- [ ] Without markers: inserts ICM region right after the first `^# ` (main title)

Multi-workspace:
- [ ] Bootstrap of second workspace adds block preserving the first

Exit A of last workspace:
- [ ] ICM region replaced by message "No active ICM workspace + run /init"

## v3.5.0 — wave protocol checks

- [ ] L1 history records `pre_wave_sha` in `wave_started` event (step 1 of stage 04).
- [ ] Task report has `qa_loops_used: <N>` + `auto_qa_passed: <bool>` in frontmatter.
- [ ] Wave-reviewer runs without worktree (CWD = lead workspace; reads via `git show`).
- [ ] Sort buffer applies plan order pre-merge (even if Agents return out of order).
- [ ] Conflict mid-wave: lead pauses at `BLOCKED_ERROR`, writes `merge-conflict-<slug>.md`, human gate A/B/C.
- [ ] CI global red: diagnose-protocol first, rollback with `pre_wave_sha`, gate A/B/C.
- [ ] Mixed wave with 1 HITL task: non-HITL tasks complete in parallel, final status `BLOCKED_HITL`.
- [ ] Cleanup `--force` only with `auto_qa_passed: true` in task report.
- [ ] `.icm-main` conditional sync (silent skip if absent).
- [ ] Validator accepts `BLOCKED_HITL` in L1 status.

## v3.9.0 — layered dev↔QA loop checks

### Bootstrap
- [ ] Workspace tier=experimental: new CONTEXT.md.tpl with L3 critic enabled (Haiku ceiling).
- [ ] Workspace tier=production: new CONTEXT.md.tpl with L3 critic Opus.
- [ ] Bootstrap copies 3 new docs to `_references/runtime/` (critic-protocol, lead-resolution-protocol, mocking-guidelines).

### Pick-model
- [ ] `pick-model.py` task `complexity_score: 1` + tier=production → writer Haiku + critic Opus.
- [ ] `pick-model.py` task `complexity_score: 6` + tier=experimental → writer Haiku + critic Haiku (ceiling caps).
- [ ] `pick-model.py` task `complexity_score: 5` + tier=development → writer Opus + critic Opus.
- [ ] `agent-brief-render.py --tier production` injects `model_recommended_writer/critic` + `complexity_score` in header.

### Lead-diagnose
- [ ] `lead-diagnose.py` round 1 fail + Jaccard < 0.7 → recommend `surgical_retry` (no trigger met).
- [ ] `lead-diagnose.py` round 2 fail + Jaccard ≥ 0.7 vs round 1 → recommend `escalate_to_lead, reason: convergence_trip`.
- [ ] `lead-diagnose.py` catastrophic signal (forensic_files_outside > 5) → recommend `escalate_to_lead, reason: catastrophic, bucket_hint: B3`.
- [ ] diagnose.md schema: trigger condition + Jaccard table + bucket recommend + surgical brief (when B1).

### Forensic+ extended
- [ ] `forensic-plus.py` Check 5 fixture (acceptance criterion without test mapping) → HARD in production.
- [ ] `forensic-plus.py` Check 6 fixture (diff touches NÃO QUERO pattern `Mock interno de jose`) → HARD in dev/prod.
- [ ] `forensic-plus.py` Check 7 fixture (import lib forbidden by ADR `## Forbidden imports`) → HARD in dev/prod.
- [ ] ADR without section `## Forbidden imports` → check 7 silently skipped (backward compat).

### Lead-resolution tier
- [ ] B1 REWRITE_SPEC: lead rewrites task spec, 1 final writer spawn, output passes L2+L3 equally.
- [ ] B3 DIRECT_IMPL: lead writes directly in branch `wave-<NNN>-<N>/<slug>-lead-resolved`, output passes L2+L3 equally (not auto-approved).
- [ ] B4 VOID_TASK: `### VOIDED` block in plan.md with concrete rationale, wave-planner --recalculate.
- [ ] L1 status `LEAD_RESOLUTION_IN_PROGRESS` during bucket execution.
- [ ] Recovery wizard detects `LEAD_RESOLUTION_STALE` if status > 24h without progress.

### Stage 05 audit
- [ ] Sub-step 5.5 audit lead resolutions detects B1 loosen (FAIL), B3 critic concerns silenced (FAIL), B4 vague rationale (FAIL).
- [ ] B1/B3/B4 correctly applied → audit PASS.
- [ ] FAIL → `BLOCKED_ERROR error_type: lead_resolution_audit_failed`.

### Migration
- [ ] migrate-workspace v3.8.0→v3.9.0 idempotent on smoke fixture.
- [ ] Existing workspace L0 frontmatter gains `icm_skill_version: "3.9.0"` without breaking parse.
- [ ] Status enum updated (`LEAD_RESOLUTION_IN_PROGRESS` valid in validate_state.py).

### E2E
- [ ] Workspace lifecycle stage 04 wave with 2 tasks (1 forensically valid + 1 forced B3 catastrophic).
- [ ] Lead resolves via B3 (writes directly, passes L2+L3).
- [ ] Stage 05 audit approves lead resolution.
- [ ] Handoff stage 04 → 05 green.

## v3.10.0 — E2E coverage reinforcement checks

### Bootstrap
- [ ] Workspace tier=production profile=app_web_backend: new CONTEXT.md.tpl with step 11b E2E suite gate.
- [ ] Bootstrap copies `e2e-coverage-protocol.md` to `_references/runtime/`.

### Wave-planner detection
- [ ] Plan with task touching `src/routes/checkout.ts` profile=app_web_backend → wave-plan.md shows `yes (auto)` in E2E required column + annotation `> **E2E coverage required**`.
- [ ] Plan with task touching `notebooks/eda.ipynb` profile=data_analysis → E2E required column = `no`, no annotation.
- [ ] Profile fullstack picks up frontend AND backend paths.

### Forensic+ Check 8
- [ ] Task with `Requires E2E update: true` in plan.md WITHOUT file in `e2e/`/`cypress/`/`playwright/`/`tests/e2e/` in diff → HARD in tier dev/prod, SOFT in tier exp/tool.
- [ ] Task with `Requires E2E update: true` + e2e file present → no violation.
- [ ] Task with `**E2E:** skip - rationale` → Check 8 silent skip.
- [ ] Task without field `Requires E2E update` → Check 8 silent skip.

### Stage 04 wave gate L4
- [ ] tier production profile=backend + e2e_command declared → step 11b runs E2E suite. Red → BLOCKED_ERROR error_type=e2e_suite_failed → diagnose protocol.
- [ ] tier exp profile=backend without e2e_command → step 11b skip silently (warning).
- [ ] profile=data_analysis (user_facing_paths empty) → step 11b skip entirely.

### Stage 05 audit (4.7)
- [ ] E2E suite absent in workspace tier dev/prod with non-empty user_facing_paths → BLOCKED_ERROR error_type=e2e_suite_missing.
- [ ] E2E suite > 7 days with user-facing tasks delivered → BLOCKED_ERROR error_type=e2e_suite_stale.
- [ ] Task with `**E2E:** skip` without rationale → BLOCKED_ERROR error_type=e2e_skip_unjustified.
- [ ] CI report e2e red → FAIL.

### Recovery wizard
- [ ] Detector E2E_SUITE_STALE alerts workspace with suite > 7 days + recent user-facing tasks in wave-summary.

### Migration
- [ ] migrate-workspace v3.9.0→v3.10.0 idempotent on smoke fixture.
- [ ] Existing workspace L0 frontmatter gains `icm_skill_version: "3.10.0"` without breaking parse.

### E2E (meta-test of reinforcement)
- [ ] Workspace lifecycle: create plan with 2 tasks (1 user-facing forensic-flagged, 1 not); confirm wave-plan.md shows E2E annotation; designer adds `Requires E2E update: true`; subagent A forgets e2e file → Check 8 HARD; subagent B adds e2e/checkout.spec.ts → PASS; L4 wave gate runs suite; Stage 05 4.7 audits freshness green.
