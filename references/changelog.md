# Changelog — xp-icm-workflow

Version history for the skill. The current version lives in the `SKILL.md` frontmatter.

> **Note:** Entire changelog written in en-US (v3.12.0+).

---

## v3.12.1 — Script CLI contract hardening + residual pt-BR cleanup (2026-05-05)

### Changes

- **wave-planner-script.py:** `_extract_section` now filters both `none` (English) and `nenhum` (legacy Portuguese) as empty-dependency sentinels. Parenthetical notes in dependency values automatically stripped (e.g. `config-module (needs api_key)` → `config-module`).
- **handoff.py:** `_parse_prev_outputs_arg` uses regex split `,(?=\s*stages/\d+)` — commas inside summaries no longer break parsing. Error message improved with expected format.
- **`references/script-cli-reference.md`** (new): Canonical CLI reference for all 18 scripts with exact format contracts for `--prev-outputs`, `--pending`, plan.md dependency sentinels, and 4-block headers.
- **Stage templates:** Cross-ref to `script-cli-reference.md` added in stages 00, 01, 02, 03, 05, 08 handoff steps.
- **Residual pt-BR cleanup:** All remaining `nenhum`/`nenhuma` in test fixtures, test code, and e2e bats files translated to English. v3.12.0 claimed zero pt-BR but missed `scripts/wave-planner-script.py:175` and test files.
- **Tests:** +8 new tests (none filtering, nenhum backward compat, parenthetical stripping, comma-in-summary parsing, missing colon error).

## v3.12.0 — Zero pt-BR (2026-05-05)

### Changes

- Eliminated all preserved pt-BR keywords (4-block headers, stop point IDs, retrospective headers, exit markers).
- Parser regex updated to match en-US headers (`### WHAT`, `### HOW`, `### OUT OF SCOPE`, `### VALIDATION`, `### Applicable ADRs`).
- File rename `references/feedback-intake-fase08.md` → `references/feedback-intake-stage08.md`.
- Stop point ID `feedback_ambiguous` → `ambiguous_feedback`.
- Migration step `migrate_3_11_0_to_3_12_0` handles L1 history + plan.md 4-block rewrite.
- Historical changelog translated to en-US (mixed-language cutoff marker removed).
- ADR `ubiquitous-language-adr.md` amended: zero pt-BR keywords preserved.
- `scripts/i18n-audit.py` PRESERVED_KEYWORDS whitelist updated (removed all 4-block + retrospective + ADR field literals); `references/changelog.md` removed from FILE_WHITELIST.

---

## v3.11.0 — Full migration to en-US (2026-05-04)

### Changes

- **MIGRATION:** All user-facing text translated from pt-BR to en-US. Scope: templates (`templates/workspace/stages/*/CONTEXT.md.tpl`, `templates/_config/`, `templates/.claude/`), reference docs (`references/*.md`), scripts (docstrings, comments, error messages), `SKILL.md`, `README.md`, `CLAUDE.md` skill section.
- **BUMP:** SKILL_VERSION 3.10.0 → 3.11.0 (`scripts/bootstrap.py`); 5 canonical files synced (SKILL.md, README.md badge + section, `references/design-system.md`, `references/preview-loop-protocol.md`, `scripts/migrate-workspace.py`).
- **NEW:** `scripts/migrate-workspace.py` +`migrate_3_10_0_to_3_11_0` (bump-only). Optionally injects `language: en-US` into L1 frontmatter if absent. SUPPORTED_VERSIONS += "3.11.0".
- **NO SCHEMA CHANGE:** L0/L1/L2 YAML structure unchanged. Behavioral logic unchanged. Pure language normalization — existing workspaces continue without interruption.

### Notes

No schema or behavioral change. All existing workspaces (any tier, any stage) migrate cleanly via bump-only step. The `language: en-US` field injection in L1 is advisory (additive, non-breaking).

---

## v3.10.0 — E2E coverage reinforcement (2026-05-04)

### Changes

- **NEW:** `references/e2e-coverage-protocol.md` — canonical doc for E2E reinforcement. 4 fronts: (1) wave-planner detects user-facing paths and auto-emits annotation, (2) forensic+ Check 8 validates that tasks with `Requires E2E update: true` have ≥1 file in e2e/cypress/playwright, (3) L4 wave gate runs E2E suite universal tier dev/prod (profile-independent), (4) Stage 05 audits suite freshness < 7 days.
- **EXTENDED:** `scripts/forensic-plus.py` +Check 8 user-journey coverage (HARD dev/prod, SOFT exp/tool). Plan parser extracts `Requires E2E update` field + detects `**E2E:** skip - <rationale>` override. JSON schema bump `e2e_coverage_missing` (backward-compat).
- **EXTENDED:** `scripts/wave-planner-script.py` +`USER_FACING_PATHS_BY_PROFILE` constant (defaults 11 profiles) + helper `_task_requires_e2e()`. render_wave_plan includes column `E2E required?` in task table + annotation `> **E2E coverage required**` when ≥1 task flagged.
- **EXTENDED:** `scripts/recovery-wizard.py` +`CODE_E2E_SUITE_STALE` in CANONICAL_ORDER (alert when suite > 7 days without update + user-facing tasks delivered).
- **EXTENDED:** `scripts/migrate-workspace.py` +entry `migrate_3_9_0_to_3_10_0` (bump-only, backward-compat). SUPPORTED_VERSIONS += "3.10.0".
- **EXTENDED:** `references/forensic-plus-protocol.md` Check 8 spec + expanded tier×severity matrix 8 checks. v3.9.0 → v3.10.0.
- **EXTENDED:** `references/4-block-contract-template.md` schema +`### Requires E2E update` optional field (auto-emitted by wave-planner; subagent MUST add e2e files; override `**E2E:** skip - <rationale>`).
- **EXTENDED:** `references/state-machine-schema.md` additional error_types: `e2e_suite_failed`, `e2e_suite_missing`, `e2e_suite_stale`, `e2e_skip_unjustified`.
- **EXTENDED:** `templates/.../04_implementation_waves/CONTEXT.md.tpl` step 11 expanded into 11a/11b/11c (universal CI / E2E suite tier dev/prod / cross-task coherence). Inputs +e2e-coverage-protocol.md.
- **EXTENDED:** `templates/.../05_verification/CONTEXT.md.tpl` step 4.7 NEW (audit E2E suite exists + freshness + skip rationale). BLOCKED_ERROR cause list +e2e_suite_*. Inputs +e2e-coverage-protocol.md.
- **BUMP:** SKILL_VERSION 3.9.0 → 3.10.0 (`scripts/bootstrap.py`); 5 canonical files synced (SKILL.md, README.md badge + section, design-system.md, preview-loop-protocol.md, bootstrap.py runtime_refs +e2e-coverage-protocol.md).

### Notes

E2E coverage gaps in ICM v3.9.0: tracer-first covers isolated task (not regression); wave gate L4 e2e profile-conditional (frontend/fullstack only); Stage 05 relied on project CI without audit. v3.10.0 closes gaps via 4 complementary fronts — wave-planner advisory (annotation), forensic+ enforcement (Check 8 HARD), wave gate universal (step 11b), stage 05 audit (4.7).

Level 3 (mutation testing oracle, full preview-loop suite wave-end) deferred to v3.11.0+.

---

## v3.9.0 — Layered dev↔QA loop + lead-resolution tier (2026-05-04)

### Changes

- **NEW:** `references/critic-protocol.md` — L3 orthogonal LLM critic canonical doc. Fresh context, anti-sycophancy hardcoded, triplet output (claim, evidence, counterexample, severity), decision APPROVE/REJECT/ABSTAIN. Critic model = `TIER_CEILING[tier]` always. Covers semantic gap of forensic+ (wrong logic, disguised ADR drift, missing edge cases).
- **NEW:** `references/lead-resolution-protocol.md` — buckets B1 REWRITE_SPEC / B3 DIRECT_IMPL / B4 VOID_TASK. Trigger conditions T1 (cap 3 retries) / T2 (Jaccard ≥ 0.7 convergence trip) / T3 (catastrophic detector universal). Cap 1 attempt per bucket. Stage 05 audit trail.
- **NEW:** `references/mocking-guidelines.md` — mattpocock alignment. Mock only boundaries (HTTP/DB/time/randomness/env); never internals. Per-profile guidance + tier-aware enforcement via forensic+ Check 6.
- **NEW:** `scripts/lead-diagnose.py` — Jaccard cluster + catastrophic detector (tests broken outside scope, build globally broken, scope creep > 5×) + bucket recommendation + surgical brief render. Output diagnose.md schema.
- **NEW:** `scripts/pick-model.py` — deterministic heuristic. compute_score (estimated_lines, hot_paths, security_sensitive, public_api_change, algorithm_heavy, doc_only/config_only/css_only, tier) + tier ceiling cap. Writer/critic split.
- **NEW:** `templates/critic-prompt.md` — renderable prompt template for Agent tool (anti-sycophancy + triplet schema).
- **EXTENDED:** `scripts/forensic-plus.py` — +Checks 5/6/7 (acceptance↔test mapping, OUT OF SCOPE violations, ADR import drift). JSON schema bump backward-compat (new optional fields).
- **EXTENDED:** `scripts/agent-brief-render.py` — optional `--tier` flag integrates `pick-model.py`; brief header gains `model_recommended_writer/critic` + `complexity_score`.
- **EXTENDED:** `scripts/migrate-workspace.py` — entry `migrate_3_8_0_to_3_9_0` (bump-only, backward-compat). SUPPORTED_VERSIONS += "3.9.0".
- **EXTENDED:** `scripts/recovery-wizard.py` — new type `LEAD_RESOLUTION_STALE` (workspace in LEAD_RESOLUTION_IN_PROGRESS with no progress > 24h).
- **EXTENDED:** `scripts/validate_state.py:VALID_STATUSES` += `LEAD_RESOLUTION_IN_PROGRESS` (additive, schema maintained).
- **REWRITE:** `references/4-block-contract-template.md` — § 3 vertical TDD + tracer-first + dedicated anti-horizontal slicing section. § 5 Akita 15-items DELETED. § 6 `auth-middleware` example updated without Akita output. v3.0.0-beta5 → v3.9.0.
- **REWRITE:** `references/forensic-plus-protocol.md` — 7 checks (4 original + 3 new), consolidated tier×severity matrix. v3.8.0 → v3.9.0.
- **EXTENDED:** `references/state-machine-schema.md` — status `LEAD_RESOLUTION_IN_PROGRESS` (additive, 7th canonical status). Additional error_types: `lead_resolution_audit_failed`, `lead_resolution_all_buckets_failed`, `lead_decision_missing`, `critic_unavailable`, `critic_abstain_loop`.
- **REWRITE:** `templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl` — new flow (vertical TDD → L2 forensic+ → L3 critic always → diagnose → retry/lead-bucket). Drop Akita refs. Step 8 expanded into 8a-8e. Step 9 new (lead-resolution). Inputs +4 docs (critic, lead-resolution, forensic-plus, mocking-guidelines).
- **EXTENDED:** `templates/workspace/stages/05_verification/CONTEXT.md.tpl` — sub-step 5.5 audit lead resolutions (B1 tighten / B3 critic concerns addressed / B4 concrete rationale). FAIL → `BLOCKED_ERROR error_type: lead_resolution_audit_failed`.
- **DROP:** Akita 15-items inline removed from subagent task report. QA delegated to orthogonal layers (L2 extended forensic+ + L3 critic). Self-grading bias documented (Huang ICLR 2024, arxiv 2510.11822, arxiv 2509.16533).
- **BUMP:** SKILL_VERSION 3.8.0 → 3.9.0 (`scripts/bootstrap.py`); 5 canonical files synced (SKILL.md, README.md badge + section, design-system.md, preview-loop-protocol.md, bootstrap.py runtime_refs +3 new docs).

### Notes

Self-grading drop is a philosophy change, not a capability change. Forensic+ Checks 4/6/7 + critic L3 cover quality dimensions that Akita intended to audit (clean code, secrets/PII, ADR compliance), with an orthogonal gate immune to sycophancy. `akita-derive.py` optional post-hoc for telemetry — deferred until stage 08 reports gap.

Cross-family critic (E2 abandoned) and mutation testing oracle (R2) remain out of scope. Compensated by stage 06 human review + stage 08 feedback intake.

---

## v3.8.0 — Forensic+ wave reviewer (2026-05-03)

### Changes

- **NEW:** `scripts/forensic-plus.py` — structural audit per task in step 8 wave-reviewer (4 git-only checks).
- **NEW:** `references/forensic-plus-protocol.md` — canonical doc.
- **NEW:** schema `task-<slug>.md` frontmatter gains `forensic_violations`, `forensic_passed`, `forensic_max_severity`, `forensic_respawn_count` (optional, backward compat).
- **NEW:** `wave-summary.md` gains section `## Forensic+ summary`.
- **NEW:** `plan.md` task accepts optional `### Estimated lines` (Check 3 scope creep).
- **CHANGE:** step 8 of the 12-step pipeline expanded into 8a/8b/8c/8d (`references/wave-execution-protocol.md` + L2 stage 04 template).
- **CHANGE:** wave-plan.md flag `skip_wave_reviewer` renamed to `skip_cross_task_audit`. Backward-compat alias maintained in v3.8.0; removed in v3.9.0.
- **CHANGE:** `state-machine-schema.md` documents new `error_type: forensic_max_retries|forensic_script_crash` (no enum change).
- **DEPS:** no new runtime dependencies. PyYAML already present in `requirements.txt`.
- **TESTS:** +20 unit (`test_forensic_plus.py`), +6 snapshot fixtures, +4 drift detectors, +1 bats e2e.

### Migration

`migrate_3_7_2_to_3_8_0` is bump-only — existing workspaces are compatible without destructive mutation. New fields in task-md frontmatter have a tolerant parser with defaults for absent fields.

### Rationale

Subagent self-grading (Auto-QA Akita 15-items) suffers from documented bias (Huang et al. ICLR 2024, Self-Correction Benchmark 2025). Forensic+ adds external structural auditing without importing expensive prompt-only re-grading. Leverages ICM's unique strength (forensic git-log audit) expanding coverage from 1 vector (qa_loops_used vs commits) to 4 structural fraud vectors.

---

## v3.7.2 — Exit A/C last active: auto-/init + ICM cleanup opt-in (2026-05-01)

### Why v3.7.2

Real ICM session (workspace 002 spawned from 001 via Exit C) revealed 4 gaps:

1. No instruction to run `/init` at the end of stage 8 — the idle region cited
   "run /init" but it was not an action executed in the session.
2. `.index.md` became stale with a closed workspace listed as `active`.
   SessionStart hook read the index and detected closed 001 as active.
3. `.claude/settings.local.json` accumulated hook entries per workspace
   (bootstrap append, Exit A/C never removed them).
4. `.icm-main/` worktree + workspace branch + subagent worktrees remained
   orphaned after Exit A/C; the human saw the root in workspace branch tree
   as a "duplicate" of `.icm-main/`.

### Changes

**Stage 08 Exit A/C last active workspace:**

- **Auto-`/init` invocation** — `handoff.py remove-block --exit-2-if-last-active`
  returns exit 2 when deactivate was triggered. Stage 08 template captures this and
  invokes `Skill(skill: "init")` in the SAME session before exiting. Exit B
  untouched. Multi-workspace with remaining active workspaces skips (prohibited).
- **ICM cleanup opt-in** — `scripts/icm-cleanup.py` new: pre-checks
  (uncommitted abort, --force bypass), removes orphaned subagent worktrees,
  removes `.icm-main/` worktree, checks out main, deletes workspace branch,
  prunes. Menu `[s/n/dry-run]` in stage 08 template invokes the script.
  Doc: `references/icm-cleanup-protocol.md`.
- **`.index.md` cleanup** — `handoff.py:_update_index_status` rewrites
  workspace line from `active` → `COMPLETED`. Called in `remove_workspace_block`.
- **`settings.local.json` hooks unregister** — `handoff.py:_unregister_workspace_hooks`
  removes entries for the closed workspace. Preserves non-ICM hooks.
- **SessionStart hook prefers L1** — `icm-session-check.sh` now iterates
  `workspaces/*/CONTEXT.md` frontmatter status instead of `.index.md`.

**Recovery wizard:**

- New detector `STALE_ICM_MAIN_AFTER_CLOSE` (16th in CANONICAL_ORDER):
  fires when workspace is COMPLETED + `.icm-main/` present + zero other
  active workspaces. Plan A registers warning suggesting `icm-cleanup.py`
  (destructive, does not auto-execute). Helper `_count_active_workspaces`.

### Tests

41 new tests: `test_handoff_remove_block_exit_code.py` (5),
`test_stage08_template_init_invocation.py` (8),
`test_close_cleanup_v3_7_1.py` (10), `test_icm_cleanup.py` (10),
`test_recovery_stale_icm_main.py` (8). Suite: 823 passed (was 782),
no regression.

### Doc

- `references/icm-cleanup-protocol.md` (new) — D1-D5 decisions, algorithm,
  edge cases, idempotency.
- `references/project-root-claude-md.md` — auto-`/init` trigger.
- `templates/workspace/stages/08_feedback_intake/CONTEXT.md.tpl` — Exit
  A/C steps rewritten.

### v3.7.1 (intermediate, merged into 3.7.2)

`.index.md` + settings.local.json hooks fixes implemented in a separate
commit (`ed838ce`) but version skipped — grouped into v3.7.2.

### Post-release drift fix (2026-05-01)

`scripts/migrate-workspace.py` remained at `CURRENT_SKILL_VERSION = "3.7.0"`
after the 3.7.0→3.7.2 bootstrap bump — the original `test_no_drift.py` only
covered 4 canonical files (SKILL.md, README.md, design-system.md,
preview-loop-protocol.md), not auxiliary scripts.

Fixes:

- `scripts/migrate-workspace.py`: `CURRENT_SKILL_VERSION` 3.7.0 → 3.7.2,
  `SUPPORTED_VERSIONS` add `"3.7.2"`, new `migrate_3_7_0_to_3_7_2`
  (bump-only — v3.7.1 collapsed into 3.7.2 without schema change), dispatcher
  entry `"3.7.0->3.7.2"`, docstring + CLI example bumped.
- `tests/unit/test_migrate_workspace.py`: 6 new tests cover new step,
  full chain 3.3.0→canonical, sync with `bootstrap.SKILL_VERSION`.
- `tests/unit/test_no_drift.py`: new detector H `test_scripts_skill_version_sync`
  scans `scripts/**/*.py` for `CURRENT_SKILL_VERSION` + last entry of
  `SUPPORTED_VERSIONS` tuple, validates == canonical. Whitelist only for
  `migrate-v3.3-to-v3.4.py` (fixed historical target). `VERSION_MUST_MATCH`
  gains surgical entry for `migrate-workspace.py`.
- `CLAUDE.md` root: "bump SKILL_VERSION" rule extended to include
  `scripts/migrate-workspace.py` in the list of synchronized files.

Suite: 831 passed (was 823), 0 regression.

---

## v3.7.0 — Runtime cleanup + spawn-pending + handoff fixes (2026-05-01)

### Why v3.7.0

20 gaps identified during real usage of workspace 001-001-saas-psicologo-mvp
(transition Exit C → 002). Categories: orphaned side-effects (uvicorn, vite,
docker, background tasks), working tree consistency (.icm-main dirt,
incomplete gitignore, wave branch sweep, tech debt append during intake),
cosmetic skill bugs (handoff.py "Exit A" hardcoded in both A/C, profile-matrix
version drift), UX/runbook (long spawn command, missing runtime checklist,
non-strict mini-menu), edge cases (mid-flow crash recovery, lessons gap C/B,
restart B baseline dirty).

v3.7.0 closes 10 concrete changes:

### Changes

**1. Drift detector hardened (`tests/unit/test_no_drift.py`):**
- `PROFILE_COUNT_PARENS_RE` catches "Canonical profiles (N):" format.
- `PROFILE_COMBO_RE` validates "(N × T = M combos)" triple consistency.
- SKILL.md L158/L162 sweep: 10→11 profiles, 40→44 combos, +fullstack.

**2. handoff.py outcome-aware idle render (`scripts/handoff.py`):**
- `_render_icm_idle(closed_at, *, outcome={A,C}, spawn_to=None)` — branch
  by outcome instead of hardcoded "Exit A".
- `remove_workspace_block` + `deactivate_project_claude_md` propagate
  outcome+spawn_to via kwargs with backward-compat defaults.
- CLI `remove-block` + `deactivate-project-md` gain `--outcome`+`--spawn-to`.
- Validation: outcome=C requires spawn_to; outcome ∉ {A,C} raises.

**3. New runtime registry (`scripts/runtime-registry.py`):**
- CRUD in `workspaces/<NNN>/_state/runtime-registry.json` (gitignored).
- Kinds: dev_server, background_task, docker_container, subagent_worktree.
- `_is_pid_alive` cross-platform (POSIX `os.kill`, Windows `ctypes`
  `OpenProcess`+`GetExitCodeProcess`).
- `purge_dead` removes entries with dead PIDs.
- `detect_legacy_pid_files`: identifies `.icm-main/.dev-server.pid` v3.6.0
  for graceful migration.
- CLI: register, list, unregister, purge-dead, detect-legacy.

**4. Runtime status checklist (`scripts/runtime-status.py`):**
- 6 categories: dev_servers, background_tasks, docker, wave_branches,
  working_tree, untracked.
- `check_all` aggregates; CLI supports `--check <category>`, `--format json|text`,
  `--exit-code` (gating).
- Graceful failures: docker daemon down/git absent → assumed clean.

**5. Migrate workspace orchestrator (`scripts/migrate-workspace.py`):**
- Floor v3.3.0 (beta1/beta2 unsupported).
- Chains v3.3 → v3.4 → v3.5 → v3.6 → v3.7.
- Hybrid trigger: COMPLETED/AWAITING auto-prompt; IN_PROGRESS warning-only.
- Automatic backup in `<pr>/.icm-migration-backup/<ts>/<ws>/`.
- Idempotent. Step v3.6→v3.7 substantive: bump L0 + create `_state/` +
  migrate `.icm-main/.dev-server.pid` → registry (if PID alive).

**6. Bootstrap.py — spawn-pending + spawn-from + gitignore extend:**
- `detect_spawn_pending` parse + validates 9-field schema.
- `resolve_spawn_source` consolidates file + CLI arg (sources: file, arg,
  conflict, none). Conflict marks file_value/arg_value for human menu.
- `consume_spawn_pending` unlink after successful bootstrap (idempotent).
- CLI `--spawn-from <slug>` (dest=spawn_from, explicit fallback).
- GITIGNORE_LINES extended: `.icm/spawn-pending.json`, `workspaces/*/_state/`,
  `**/coverage/`, `**/coverage.json`, `**/tsconfig.tsbuildinfo`, `**/.vite/`.

**7. Recovery wizard new type `RUNTIME_REGISTRY_STALE` (v3.7.0):**
- 14th entry in CANONICAL_ORDER.
- Detects entries with dead PIDs in registry; suggests `purge-dead` (human
  confirms, no auto-purge).
- `_pid_alive_for_registry` testable wrapper.

**8. Pre-commit hook block `_state/` paths:**
- Reject staged paths `workspaces/*/_state/*` (privacy: PID/port leak in
  public PRs). Message guides to local-only gitignored directory.

**9. L2 stage 08 substantive update:**
- `applicable_stop_points: ["runtime_cleanup_failed"]` (was `[]`).
- §"Runtime Cleanup Checklist" before §Process — 6 categories, strict
  universal all tiers, `runtime-status.py` command documented.
- Process step 0 mandatory (run checklist).
- Exit A step 3: tech debt append during intake (optional, only if feedback
  explicitly cites debt) + step 6: handoff.py remove-block --outcome A.
- Exit C step 3: render `.icm/spawn-pending.json` full schema
  (spawn_from, intake_report_*, agent_brief structured 4 fields +
  notes_free, proposed_*, intake_commit_sha, created_at) + step 5:
  remove-block --outcome C --spawn-to.

**10. L2 stage 04 entry/exit hook → registry calls:**
- Entry: `runtime-registry.py list --kind dev_server`, register on start.
- Exit: list + kill process + unregister entries.
- Legacy v3.6.0 PID file path documented with migration via
  `migrate-workspace.py`.

### New refs

- `references/runtime-cleanup-protocol.md` (~150 LOC) — canonical protocol
  6 categories × default cleanup × human override + per-OS quirks +
  recovery if cleanup fails mid-exit.
- `references/spawn-handoff-protocol.md` — spawn-pending.json schema +
  cross-branch read pattern via git show + bootstrap detection flow +
  edge cases (clone, slug collision, multiple pending).

### Updated refs

- `references/feedback-intake-stage08.md` — §"Mandatory runtime cleanup
  pre-exit (v3.7+)" with 9 explicit steps.
- `references/stop-points-canonical.md` — 14 → 15 items, #15
  `runtime_cleanup_failed` (signals, trade-offs, strict universal calibration,
  specific A/B/C menu).

### Templates

- `workspace/CLAUDE.md.tpl` new R10: runtime side-effects are
  human responsibility. Skill detects + prints checklist + awaits
  confirmation per category. NEVER kills a process automatically.
- `_config/stop-points.md` 12 → 13 items; #13 `runtime_cleanup_failed`
  with specific A/B/C menu.

### Backward compat

- Workspaces v3.6.0 in-flight: run `migrate-workspace.py --workspace-root <ws>`
  to migrate PID file → registry. Idempotent.
- Workspaces v3.3 → v3.6: chains migrations in the orchestrator.
- Workspaces beta1/beta2 (pre-v3.3.0): unsupported. Manual migration.

### Consolidated decisions (12)

| # | Topic | Resolution |
|---|---|---|
| 1 | Tech debt append stage 08 | (b) relax — Exit A/B append optional |
| 2 | Cross-platform tooling | (b) pure Python `runtime-status.py`. Drop Makefile |
| 3 | Profile count drift | (c) sweep + harden detector |
| 4 | Tier override checklist | (a) strict universal |
| 5 | Spawn handoff | (c) `.icm/spawn-pending.json` + `--spawn-from` arg fallback |
| 6 | Registry path + migration | (c×y) `_state/` workspace-scoped + migrate dev-server graceful |
| 7 | Pre-commit `_state/` | (a) block staged paths |
| 8 | Migration trigger | (d) hybrid COMPLETED auto-prompt; IN_PROGRESS warning |
| 9 | Migration floor | (b) v3.3.0 |
| 10 | Cleanup failure | (b) stop point #13 (#15 in references/) |
| 11 | agent_brief schema | (c+d) structured 4 blocks + git show cross-branch |
| 12 | Stage 04 entry hook | (c) helper docs + custom dev server fallback |

### Tests

49 new tests (handoff outcome 7, runtime-registry 13, bootstrap spawn-pending
14, recovery RUNTIME_REGISTRY_STALE 4, runtime-status 8, migrate-workspace 15).
Total: 781 → 781+ tests green, zero regression.

---

## v3.6.0 — Preview loop (build-iterate visual) (2026-04-30)

### Why v3.6.0

Frontend ICM up to v3.5.0 covered DESIGN.md tokens (Google Stitch) but
lacked a build-iterate visual cycle. The human asked "show me how it looks"
and ICM had no integrated response beyond "spawn subagent to implement".
No coordinated hot-reload, no visual feedback loop, no automatic mock data,
no CDP integration.

v3.6.0 closes the gap: profile `app_web_frontend` + `fullstack`
gain an opt-in-by-default preview loop that orchestrates dev server,
tier-based mock data, live Chrome CDP, preview pages, uniform verification,
free-form feedback, design system cascade, and multi-screen replay.
Canonical doc: `references/preview-loop-protocol.md`.

### Changes

**1. New canonical doc (`references/preview-loop-protocol.md`):**
- 10 consolidated decisions (dev server lifecycle, tier-based mock data,
  feedback combo, live CDP, uniform verification,
  preview pages, free screenshot, no iter cap, design cascade
  threshold 5, multi-screen on request).
- Covers canonical stack, commands by package manager, helper
  scripts, CDP read scope, graceful fallback.
- Anti-patterns + new recovery wizard types documented.

**2. CDP helper scripts (`templates/.claude/scripts/`):**
- `launch-chrome-cdp.bat` (Windows): launches Chrome with
  `--remote-debugging-port=9222 --user-data-dir=.icm-chrome-profile`.
- `launch-chrome-cdp.sh` (POSIX): same function, auto-detects
  Chrome/Chromium on macOS/Linux.

**3. Profile flags (`profile-merge.py` + `profile-matrix.md`):**
- New function `_preview_loop_config(profile, tier)` emits block
  `preview_loop` in `profile-effective.yaml`:
  - `preview_loop_enabled: true`
  - `mock_data_strategy` tier-based (`fixtures` | `msw_faker` | `msw_faker_zod`)
  - `cdp_live_enabled: true`
  - `visual_iter_cap: null`
  - `design_cascade_threshold: 5`
  - `preview_pages_path: preview/`
- Applies ONLY to `app_web_frontend` + `fullstack`.

**4. Stage 02 design template — step 7.6:**
- Preview Loop mock data schema + preview pages flag.
- Tier ≥ development: designer writes Zod schema in plan.md.
- Tasks with reusable component gain `requires_preview_page: true`.
- Routes map `output/routes.md` populated for CDP fallback.
- Optional ASCII wireframe for non-trivial layout.

**5. Stage 04 implementation template — entry/exit hooks + sub-steps:**
- Entry hook: detect package manager via lockfile, start dev server
  in background, save PID in `.icm-main/.dev-server.pid`,
  print kickoff priming.
- Tier-aware verification rewritten: `tsc` per Edit, lint+Playwright
  wave-end, full on request.
- New stop points `ambiguous_feedback` + `design_system_cascade`.
- Exit hook: kill PID, delete PID file, preserve `.icm-chrome-profile/`.

**6. New recovery wizard types (`scripts/recovery-wizard.py`):**
- `DEV_SERVER_ORPHAN`: PID file exists + process dead. Plan A:
  delete PID file + log, register warning. Cross-platform (POSIX
  via `os.kill(pid, 0)`, Windows via `ctypes.OpenProcess`).
- `CDP_DISCONNECTED`: `.icm-chrome-profile/` exists + Chrome not
  listening on :9222. Plan A: warning, suggests helper relaunch
  (does not delete profile dir).
- Helpers `_is_pid_alive(pid)` + `_is_port_listening(host, port)`
  added (no external deps).

**7. Bootstrap (`scripts/bootstrap.py`):**
- `SKILL_VERSION = "3.6.0"`.
- `.icm-chrome-profile/` added to `GITIGNORE_LINES`.
- New function `detect_package_manager(project_root)` returns
  `(pm, dev_cmd)` based on lockfile (priority
  `bun > pnpm > yarn > npm`).

**8. Cross-refs:**
- `references/design-system.md` v3.6.0 → section "Build-iterate visual
  loop" + cross-ref to new doc.
- `templates/_config/profile-matrix.md` → preview loop flags table
  in `app_web_frontend` and `fullstack` sections.

---

## v3.5.0 — Stage 04 protocol gaps fix (2026-04-29)

### Why v3.5.0

10 protocol gaps identified in stage 04 wave execution during
review of a real execution. Each gap masked edge cases that produced
inconsistent state (orphaned worktrees, non-deterministic merge order,
mid-wave conflict with no resume flow, insufficient HITL granularity).
Additionally: 12 files with cross-file drift and introduction of a drift
prevention test gate.

### Changes

**1. Doc drift fix (CLAUDE.md skill root + README.md):**
- "no worktrees" line removed; replaced with reference to
  `Agent(isolation: "worktree")` (alignment with v3.4.0+).
- README.md "10 profiles" → "11 profiles" (pre-existing drift since v3.4.4).

**2. Branch lifecycle determinism (L2 stage 04):**
- Step 2 makes explicit: lead creates branch BEFORE spawn (`git branch
  wave-<NNN>-<N>/<slug> <BASE_BRANCH>`), Agent harness does worktree
  add on existing branch. Orphaned branch detectable via `git branch
  --merged`.
- Step 11 gains deterministic `--force` decision matrix:
  `auto_qa_passed: true` in task report → safe `--force`; otherwise
  BLOCKED_ERROR.

**3. Subagent protocol additions (L2 stage 04):**
- Step 8 declares wave-reviewer WITHOUT `isolation: "worktree"` — reads
  via `git show wave-<branch>:<file>` / `git diff <BASE>...<wave>`.
- Step 4.6 + step 6: subagent writes `qa_loops_used: <N>` in
  `task-<slug>.md` frontmatter; reviewer audits against git log
  of wave branch (anti-fraud).
- HITL handling rewritten with task-level granularity: mixed wave
  spawns Agents for non-HITL tasks in parallel, HITL tasks
  registered with `status: AWAITING_HITL`. New status:
  `BLOCKED_HITL` (distinct from `BLOCKED_ERROR`).

**4. Merge orchestration (L2 stage 04):**
- Step 7 gains sort buffer: `{task_slug: agent_result}` → sorts
  by index in `plan.md > tasks[]` before step 9. Merge order =
  plan order, not return order.
- Step 1 writes `pre_wave_sha` in L1 history event `wave_started`
  (used by rollback).
- New doc `references/conflict-resolution-protocol.md`: lead pauses
  on `BLOCKED_ERROR`, writes `merge-conflict-<slug>.md`, human gate
  A/B/C (resolved / abort task / abort wave). Lead NEVER resolves
  conflict autonomously.
- New doc `references/ci-rollback-protocol.md`: step 10 red
  → diagnose-protocol mandatory (cap 3 attempts, fix < 50 LOC) →
  rollback (`git reset --hard <pre_wave_sha>`) → human gate A/B/C
  (redo wave / redo task / abandon). Wave branches preserved
  during BLOCKED_ERROR.

**5. `.icm-main` robustness (L2 stage 04):**
- Sync `cd .icm-main && git pull --ff-only` now conditional:
  only executes if `git worktree list --porcelain | grep -q
  ".icm-main"` returns a match. Silent skip otherwise (`.icm-main` is
  an optional convention set up by recovery wizard / bootstrap).

**6. Consolidated canonical doc:**
- New `references/wave-execution-protocol.md` consolidates
  12-step pipeline, actors, branches, status, cross-references.
  Single source of truth — other docs point here.

**7. Stale files audit (Chunk 6):**
- `scripts/bootstrap.py` SKILL_VERSION 3.4.1 → 3.5.0 (CRITICAL —
  real version injected into new workspaces).
- `scripts/validate_state.py` ALLOWED_STATUSES const + BLOCKED_HITL
  in enum.
- `references/state-machine-schema.md` row BLOCKED_HITL.
- `references/design-system.md` v3.4.4 → v3.5.0.
- CLAUDE.md + SKILL.md + profile-merge.py + test_profile_merge.py:
  10 → 11 profiles (pre-existing drift).
- `scripts/recovery-wizard.py` new detector `MISSING_PRE_WAVE_SHA`
  + auto-fix marks `unknown` for waves pre-v3.5.0.
- `references/task-types-hitl-afk.md`: task-level granularity section
  + status BLOCKED_HITL.
- `references/subagent-protocol.md`: cross-ref to
  wave-execution-protocol.md (anti-duplication).
- `references/example-run.md`: walkthrough synced with fields
  `pre_wave_sha` / `qa_loops_used`.
- `references/smoke-manual-checklist.md`: 10 checks v3.5.0.

**8. Permanent drift prevention (Chunk 7):**
- New `tests/unit/test_no_drift.py` (5 detectors):
  - Consistent version (canonical = `bootstrap.py:SKILL_VERSION`).
  - Profile count (canonical = `len(CANONICAL_PROFILES)`).
  - Status enum sync (validate_state.py ↔ schema.md).
  - Cross-refs markdown resolve in `references/`.
- `validate_state.py` exports `ALLOWED_STATUSES` const at module level
  → single source for drift test.
- CLAUDE.md gains section "Pre-merge drift audit (mandatory)" — test
  gate blocks drift at commit time, no need to remember.

### Migrations / breaking changes

No breaking changes for existing v3.4.x workspaces:
- New status `BLOCKED_HITL` is additive (old workspaces don't
  use it, but validator accepts it).
- `qa_loops_used` in task report is additive (old workspaces
  without the field remain valid; reviewer treats absent as N/A).
- `pre_wave_sha` in L1 history is additive (recovery wizard gains
  new optional detector `MISSING_PRE_WAVE_SHA` for waves
  started pre-v3.5.0; auto-fix marks `pre_wave_sha: unknown`).

### Tests

- `tests/unit/test_v3_5_0_wave_protocol.py` — 14 tests covering
  all closed gaps (section presence in L2, existence of new docs,
  version bump, changelog entry).
- `tests/unit/test_no_drift.py` — 5 tests covering permanent drift detection.
  Automatically blocks regression.

### Plan

- `docs/plans/2026-04-29-stage-04-gaps-fix.md` — complete implementation
  plan (7 chunks, 30 tasks).

---

## v3.4.4 — Profile fullstack + Design system (DESIGN.md format) (2026-04-29)

### Why v3.4.4

Two additions in one version:

1. **Profile `fullstack`** — projects where backend + frontend coexist
   in the same repo (Next.js with API routes, Remix + Prisma, T3 stack,
   Django + React colocated). `app_web_backend` left half the frontend
   gates disabled (component testing, e2e, a11y, visual regression);
   `app_web_frontend` left half the backend gates disabled
   (http_integration, db_integration). Result: UI bugs escaped
   audit in real fullstack projects.
2. **Design system L3** — stage 02 design for profiles
   `app_web_frontend` and `fullstack` now creates/updates
   `<project_root>/.icm-main/DESIGN.md` (Google Stitch spec format)
   as the visual source of truth. Subagents in stage 04 gain
   the relevant subset via channel 2.

### Changes

**1. Profile `fullstack` (11th canonical profile):**
- `scripts/profile-merge.py`: `CANONICAL_PROFILES` adds
  `"fullstack"`. `_test_specs` new branch returning superset
  backend + frontend (`test_types_required: [unit, integration,
  component, e2e]`, `http_integration`, `db_integration`,
  `component_testing`, `e2e_required`, `visual_regression` (prod),
  `a11y_testing` (dev+prod), `design_system_required: True`).
- `_apply_profile_rules`: `fullstack` gains `security_gate: True`
  in any tier ≠ `experimental` (same as app_web_backend and
  app_web_frontend).
- `templates/_config/profile-matrix.md`: tables updated to
  reflect 11 profiles + new overrides row combining
  app_web_backend, app_web_frontend, fullstack.

**2. Design system L3 + DESIGN.md format:**
- New `references/design-system.md` (~290 lines) adopting the
  DESIGN.md spec from Google Stitch as canonical format:
  - YAML frontmatter schema: `colors`, `typography`, `rounded`,
    `spacing`, `components` + token reference syntax `{path.to.token}`
  - Section order: Overview → Colors → Typography → Layout →
    Elevation & Depth → Shapes → Components → Do's and Don'ts
  - 3-layer token architecture (primitive → semantic → component)
  - Component spec table template (Default/Hover/Active/Disabled)
  - Flow per ICM stage 00-08 mapped
  - Stage 02 menu A/B/C: create from scratch / inspire awesome-design-md /
    extract from URL via designlang externally
  - Reference gallery: VoltAgent/awesome-design-md (69 brands)
  - Optional external tool: Manavarya09/design-extract (designlang)
  - Escape hatch: ui-ux-pro-max-skill with explicit boundary
- L0 (`templates/workspace/CLAUDE.md.tpl`): adds path
  `<project_root>/.icm-main/DESIGN.md` in "Absolute paths"
- L2 stage 02 (`02_design/CONTEXT.md.tpl`):
  - Inputs gains 2 rows (design-system.md doc + DESIGN.md brownfield)
  - Process step 7.5 NEW conditional on profile
- L2 stage 04 (`04_implementation_waves/CONTEXT.md.tpl`):
  - Process step 3 (channel 2 inject) gains conditional clause
    for tasks with flag `requires_design_system: true`
- Bootstrap (`scripts/bootstrap.py`): `runtime_refs` tuple adds
  `"design-system.md"` (copied to `_references/runtime/` in workspace)

### Compatibility

Existing non-fullstack v3.4.x workspaces continue working
(backward compatible). Old workspace wanting to migrate to fullstack:
edit L0 + recompute hash via `profile-merge.py --profile fullstack`.

Profile `app_web_frontend` gains `design_system_required: True`
retroactively — old workspaces without DESIGN.md continue OK
(stage 02 detects absence and offers A/B/C menu on resume).

### Tests

18 new tests:
- `tests/unit/test_profile_merge.py`: class `TestFullstackProfile`
  with 7 tests (test types superset, backend+frontend dimensions,
  visual_regression prod-only, design_system_required for 2 profiles,
  absence in others, distinct hash)
- `tests/unit/test_design_system_doc.py`: 11 smoke tests for canonical doc

Total suite: 649 tests green. Coverage 76% maintained.

---

## v3.4.3 — Wave worktree cleanup (2026-04-29)

### Why v3.4.3

Bug observed in real usage: after each wave in stage 04, ephemeral worktrees
created by subagents (Agent tool with `isolation: "worktree"`)
remained orphaned in `<project_root>/.icm-wave-*` (or path returned by the
tool), and `wave-<NNN>-<N>/<task-slug>` branches polluted the `git branch`
listing. Lead never executed cleanup after merge.

### Changes

**1. L2 stage 04: new step 11 post-merge cleanup:**
- After sequential merge + global CI gate green, lead executes:
  ```bash
  git worktree remove <path-to-worktree>     # paths captured from Agent tool results
  git branch -d wave-<NNN>-<N>/<task-slug>   # safe because merged --no-ff
  ```
- Robust fallback if path was lost: `git worktree list --porcelain`
  filtered by branch pattern.
- Non-fatal failure — registers warning in `wave-summary.md`, proceeds.
- `git branch -d` refuses non-merged (intentional). Do not use `-D`.

**2. Recovery Wizard: new type `WAVE_WORKTREE_ORPHAN`:**
- Detect: `git worktree list` shows worktrees with branch pattern
  `wave-<NNN>-` (NNN=workspace num) AND branch already merged into base_branch.
- Plan A (auto-cleanup): `git worktree remove <path>` + `git branch -d`.
  Cleanup safe because detection filtered by already-merged.
- Skip orphans with non-merged branch (signal of incomplete wave — human
  attention required, no auto-cleanup).
- New helpers: `_list_worktrees`, `_is_branch_merged`.

**3. Updated docs:**
- `references/worktree-model.md` section 3 (mandatory cleanup).
- `references/subagent-protocol.md` section 5.1 (Post-merge cleanup).
- `references/recovery-wizard.md` (new type).

### Compatibility

Workspaces v3.4.0/v3.4.1/v3.4.2 with accumulated orphaned worktrees: run
Recovery Wizard manually when it appears. Plan A auto-cleanup removes
everything at once. New workspaces created via v3.4.3 start with
automatic cleanup in the stage 04 protocol.

### Tests

8 new tests in `tests/unit/test_v3_4_3_wave_cleanup.py`. Total suite
627 tests green.

---

## v3.4.2 — Inline gate + tech debt drain (2026-04-29)

### Why v3.4.2

Bug-fix patch correcting an end-of-stage loop observed in real usage
(workspace 001-001-saas-psicologo-mvp): session printed kickoff +
exited WITHOUT waiting for human gate; new session detected pending status,
asked for approval, and re-printed the kickoff — confusing. Plus 2 accumulated
tech debt items.

### Changes

**1. Inline gate before kickoff in all stages (main bug fix):**
- L2 templates of stages 01-07 updated to split End of stage handoff
  into two phases within the SAME session.
- Phase 1 WORK_DONE: update L1 (sub_stage=NN_completed,
  status=COMPLETED_AWAITING_HUMAN), atomic commit 1/2 (outputs + L1,
  WITHOUT kickoff), print gate prompt, WAIT for human.
- Phase 2 GATE_APPROVED (after "approved"): update L1
  (stage_atual=NN+1, sub_stage=NN+1_in_progress, status=IN_PROGRESS),
  render kickoff, atomic commit 2/2, print KICKOFF block, EXIT.
- Stage 04: gate only on last-wave→05 transition (mid-wave continues auto).
- Stage 06: gate only in case A (without P0/P1). Loopback to 04 is auto.
- Stage 07: gate approves merge-report; after approval, auto-transitions
  07→08 with status=COMPLETED_AWAITING_HUMAN (workspace remains alive
  awaiting real-world feedback, without a second gate).
- Canonical doc: `references/session-handoff-protocol.md` (diagram
  updated in "Session anatomy" section).

**2. Recovery Wizard: new type `KICKOFF_WITHOUT_GATE`:**
- Detects buggy workspaces (created before v3.4.2) with stage NN+1
  kickoff present while L1 indicates `stage_atual=NN,
  status=COMPLETED_AWAITING_HUMAN`.
- Action: offers human (a) approve retroactive gate (keep kickoff,
  transition L1) or (b) delete kickoff and return to stage NN work.

**3. Tech debt: `agent-brief-render.py` outdated regex:**
- Regex was searching for `### Task: <slug>` (H3) + `**WHAT:**` (bold marker).
- Canonical schema (`references/4-block-contract-template.md`) is
  `## Task <SLUG>:` (H2) + `### WHAT` (H3).
- Mismatch caused leads to render briefs manually in stage 04.
- Fix: regex updated to canonical H2/H3 schema.

**4. Tech debt: bootstrap auto-merge `settings.local.json` in project_root:**
- Before: bootstrap rendered only `.example`; human copied manually
  to activate PostToolUse hook for `context-check.sh`.
- Inconsistency: workspace scope (`workspaces/<NNN>/.claude/settings.local.json`)
  was already auto-created with idempotent merge, but project_root scope was not.
- Fix: bootstrap now does idempotent merge in
  `<project_root>/.claude/settings.local.json` (preserves user customizations
  + adds/updates only the ICM entry identifiable by
  `command` containing `context-check.sh`). Keeps `.example` for documentation.

### Compatibility

Workspaces v3.4.0/v3.4.1 already in progress: run Recovery Wizard manually
when the bug symptom appears (kickoff already generated but gate not approved).
New workspaces created via v3.4.2 start with gate-inline.

---

## v3.4.1 — Backlog (migration, handoff Exit A, Tier 3) (2026-04-29)

### Why v3.4.1

Sequence patch after v3.4.0 that finishes deferred items from the KICKOFF
(deferred 4+5) and drains the Tier 3 backlog inherited from v3.3.0.

### Changes

**1. Migration script v3.3 → v3.4 (deferred 4):**
- New `scripts/migrate-v3.3-to-v3.4.py`. Detects v3.3.x workspaces via
  `icm_skill_version` in L0, creates `.icm-main/` worktree, ensures
  `docs/decisions/.keep` in base branch, updates `.gitignore`, bumps
  `icm_skill_version` to 3.4.0. CLI: `--project-root <path>
  [--workspace <NNN-slug>] [--update-paths] [--dry-run]`.
- Idempotent: re-running causes no harm. v3.4.x workspaces are skipped.
- 24 unit tests in `tests/unit/test_migrate_v3_3_to_v3_4.py`.

**2. Handoff Exit A migrates CLAUDE.md root (deferred 5):**
- `handoff.py:deactivate_project_claude_md` now also persists the idle CLAUDE.md
  in the base branch via `.icm-main/CLAUDE.md` + commit.
- Without this, the root CLAUDE.md would disappear when the workspace branch
  was deleted after archiving.
- Idempotent: re-execution with same content generates no extra commit.
- Canonical doc: `references/project-root-claude-md.md` (section "Owner
  transition at Exit A").
- 4 unit tests in `tests/unit/test_handoff_saida_a_v3_4_1.py`.

**3. Tier 3 backlog drained:**
- **Deep modules + deletion test** (`references/deep-modules.md`):
  canonical architecture review doc for stage 02. 5-item checklist:
  minimal interface, information hiding, single responsibility, deletion
  test, alternative in ADR. Added to `runtime_refs` of bootstrap +
  L2 stage 02. Smoke test in `tests/unit/test_deep_modules_doc.py`.
- **Git guardrails hook** (`templates/.claude/hooks/block-dangerous-git.sh`):
  PreToolUse hook that blocks push --force, reset --hard, clean -fd,
  branch -D, checkout/restore `.`. Installed ONLY in tier=production workspaces
  (conditional in `bootstrap.py`).
- **PreToolUse anti-/init** (`templates/.claude/hooks/block-init-during-icm.sh`):
  blocks `/init` invocation while ICM workspace is active. Mitigation
  G14. Installed in all workspaces.
- **Zoom-out flow stage 00**: structured section in
  `templates/workspace/stages/00_recon/CONTEXT.md.tpl` guiding agent
  when encountering an unknown module (Grep callers → root caller → annotate
  glossary → do not document now → 3-level limit).

**4. Optional tests drained:**
- `test_v3_3_docs_smoke.py` (12 tests): parsability + minimal structure
  of `adr-format.md`, `diagnose-protocol.md`, `triage-state-machine.md`,
  and `templates/workspace/_config/CONTEXT.md.tpl` (T1.3).
- `test_deep_modules_doc.py` (4 tests).

### Backlog for v3.5+

- Smoke manual end-to-end test in a real project (greenfield/brownfield/
  multi-workspace) — checklist in `references/smoke-manual-checklist.md`,
  requires a real project outside unit test scope.
- `tests/integration/test_pre_commit_whitelist.bats` (CI Ubuntu only).

---

## v3.4.0 — Cross-branch worktree model `.icm-main/` (2026-04-29)

### Why v3.4.0

ICM v3.3.x workspaces suffered from **path invisibility** between branches:
the workspace branch (`workspace/NNN-slug`) did not have `docs/decisions/`,
`docs/lessons.md`, `docs/tech_debt.md`, `src/`, `tests/` in the working tree
because those paths only lived in `base_branch`. L0/L2 declared absolute paths
`<project_root>/docs/decisions/...` but Read tool returned ENOENT in
workspace branch sessions.

Fragile workarounds (stash/checkout/commit/checkout/pop, `git show base:`,
temp checkout in main) violated L1↔outputs atomicity and polluted history.

v3.4.0 introduces a **permanent linked worktree** `<project_root>/.icm-main/`
(checked out at base_branch since bootstrap; gitignored in all branches).
Sessions at any stage read cross-branch via Read tool directly;
cross-branch writes (ADRs, lessons, tech_debt) commit via
`cd .icm-main && git commit ...` in a single transaction on the base branch.

Canonical doc: `references/worktree-model.md`.

### Changes

**Worktree model (canonical):**
- `references/worktree-model.md` (NEW) — canonical source of Option B model; structure, commands, usage rules, failures + recovery, comparison with options A/C/D.

**Bootstrap:**
- `scripts/bootstrap.py` — `SKILL_VERSION` 3.3.0 → 3.4.0; `GITIGNORE_LINES` gains `.icm-main/`; new functions `_ensure_base_branch_docs(project_root)` (creates `docs/decisions/`, `docs/lessons.md`, `docs/tech_debt.md` in base branch) and `_setup_main_worktree(project_root, base_branch)` (creates linked worktree via `git worktree add`); main flow calls both BEFORE creating workspace branch; `_scaffold_workspace_dirs` no longer creates `docs/*` in project root (moved to `_ensure_base_branch_docs`).

**Templates L0/L2:**
- `templates/workspace/CLAUDE.md.tpl` — absolute paths gain "Real branch" column; new entry "Base branch worktree (`.icm-main/`)" lists ADRs/lessons/tech_debt/src/tests under that prefix; §3 Branches rewritten to document parallel worktree; §6 ADRs gains canonical workflow via `cd .icm-main && git commit`; §8 new "Cross-branch reads via `.icm-main/`" (superpowers numbering goes to §9).
- `templates/workspace/stages/00_recon/CONTEXT.md.tpl` — `docs/`, `src/` paths migrated to `.icm-main/...`; pre-flight validates worktree exists.
- `templates/workspace/stages/01_discovery/CONTEXT.md.tpl` — paths migrated to `.icm-main/...`.
- `templates/workspace/stages/02_design/CONTEXT.md.tpl` — paths migrated; process step 6 "Spawn new ADRs" rewritten with `cd .icm-main && git commit` workflow; new "Parallel worktree" section.
- `templates/workspace/stages/03_wave_planner/CONTEXT.md.tpl` — paths migrated.
- `templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl` — paths migrated; new subagent worktree section (`Agent(isolation: "worktree")`); lead syncs `.icm-main/` via `git pull --ff-only` after merge.
- `templates/workspace/stages/05_verification/CONTEXT.md.tpl` — paths migrated.
- `templates/workspace/stages/06_review/CONTEXT.md.tpl` — paths migrated; tech_debt update via `cd .icm-main`.
- `templates/workspace/stages/07_merge/CONTEXT.md.tpl` — paths migrated.
- `templates/workspace/stages/08_feedback_intake/CONTEXT.md.tpl` — paths migrated; lessons append via `cd .icm-main`.

**Hooks:**
- `templates/.git-hooks/pre-commit` — whitelist tightened: removed `docs/decisions/*.md`, `docs/lessons.md`, `docs/tech_debt.md` (must go via `.icm-main/`); keeps `workspaces/.index.md`, `.gitignore`, `CLAUDE.md`; new rule rejects paths in `.icm-main/*` (worktree paths must not be tracked by workspace branch — gitignore must cover).
- `templates/.claude/hooks/icm-session-check.sh` (NEW) — SessionStart hook validates (1) current branch = active workspace branch; (2) `.icm-main/` worktree exists; (3) worktree on correct base_branch. Prints visible warning, does not block.
- `templates/project_root/.claude/settings.local.json.example` (NEW) — example local settings with SessionStart + PostToolUse hooks pointing to scripts in workspace.

**Recovery:**
- `scripts/recovery-wizard.py` — 3 new codes: `WORKTREE_MISSING` (critical, suggests `git worktree add .icm-main <BASE_BRANCH>`); `WORKTREE_WRONG_BRANCH` (warning, suggests `git checkout`); `WRONG_BRANCH_CHECKOUT` (warning, main branch != workspace branch during active workspace).

**Migration v3.3.x → v3.4.0:**
- Existing pre-v3.4.0 workspaces continue working, but sessions in workspace branch fail when trying `Read docs/decisions/...` (legacy paths). Manual migration: (1) `git worktree add .icm-main <BASE_BRANCH>` in project_root; (2) add `.icm-main/` to `.gitignore` in all branches; (3) optional — update L0/L2 paths to use `.icm-main/` prefix. Recovery wizard detects and signals.

---

## v3.3.0 — Tier 1 + Tier 2 patterns adopted from mattpocock/skills (2026-04-29)

### Why v3.3.0

Comparative analysis of the `mattpocock/skills` repo identified 13 applicable patterns. This release adopts 8 of them (Tier 1 + Tier 2 + dependency), addressing 6 UX/quality gaps in the current skill. The other 5 remain as future work (Tier 3).

### Changes

**T1.1 — `<project_root>/CLAUDE.md` + dynamic handoff:**
- `templates/project_root/CLAUDE.md.tpl` (NEW) — template with `<!-- ICM-START/END -->` markers delimiting the skill's exclusive region.
- `scripts/handoff.py` — `WorkspaceBlock` dataclass; `update_project_claude_md`, `remove_workspace_block`, `deactivate_project_claude_md`, `list_active_workspace_ids`. Round-trip JSON via `<!-- ICM-DATA:... -->` comments. Atomic write tmp+fsync+rename (G15). CLI subcommands.
- `scripts/bootstrap.py` — `_render_project_claude_md` called during bootstrap; root CLAUDE.md included in staging.
- `scripts/recovery-wizard.py` — codes `CLAUDE_MD_ROOT_STALE`/`CLAUDE_MD_ROOT_MISSING` (G5); plan A regenerates block from L1.
- `templates/.git-hooks/pre-commit` — whitelist root CLAUDE.md (G6).
- `references/project-root-claude-md.md` (NEW) — canonical doc covering G1-G17 (brownfield, multi-workspace, /init contract, atomicity, concurrency).
- `references/session-handoff-protocol.md` — §verbal block simplified (removes KICKOFF copy-paste; root CLAUDE.md covers read order).
- `tests/unit/test_project_root_claude_md.py` (NEW) — 17 tests covering greenfield, brownfield (with/without markers), multi-workspace, idempotency, atomic write, round-trip JSON.

**T1.2 — AGENT-BRIEF template:**
- `references/agent-brief-template.md` (NEW) — canonical format (durability over precision, behavioral not procedural, complete acceptance criteria, explicit scope boundaries). Mapping to plan.md 4-block.
- `scripts/agent-brief-render.py` (NEW) — extracts task from plan.md, parses 4-block, renders AGENT-BRIEF. CLI; warns on anti-patterns (absolute paths, line numbers).
- `tests/unit/test_agent_brief_render.py` (NEW) — 10 tests.

**T1.3 — CONTEXT.md ubiquitous language layer:**
- `templates/workspace/_config/CONTEXT.md.tpl` (NEW) — domain glossary (L3), empty at bootstrap, populated in stage 01.
- `references/context-format.md` (NEW) — format Term/Definition/Avoid/Relationships/Example dialogue/Flagged ambiguities.
- `scripts/bootstrap.py` — render of `_config/CONTEXT.md` during scaffold.

**T1.4 — ADR 3-criteria gate:**
- `references/adr-format.md` (NEW) — gate (hard to reverse + surprising without context + real trade-off); minimal template; optional sections.
- `templates/workspace/docs/decisions/_template.md` (NEW) — template for individual ADR.

**T2.5 — Diagnose 6-phase:**
- `references/diagnose-protocol.md` (NEW) — 6 phases (build feedback loop → reproduce → hypothesise → instrument → fix+regression test → cleanup+post-mortem). 3-5 ranked falsifiable hypotheses. Tag logs `[DEBUG-xxxx]`.
- `templates/workspace/_config/hitl-loop.template.sh` (NEW) — HITL bash loop template for Phase 1 item 10.

**T2.6 — HITL/AFK classification:**
- `references/task-types-hitl-afk.md` (NEW) — HITL vs AFK definition + classification criteria. AFK is default. HITL requires justification.

**T2.7 — Triage state machine:**
- `references/triage-state-machine.md` (NEW) — categories (bug/enhancement) + states (needs-triage / needs-info / ready-for-action / wontfix). Mapping → Exit A/B/C. AGENT-BRIEF generated for B and C.

**T2.8 — OUT-OF-SCOPE kb:**
- `templates/workspace/_out-of-scope/README.md.tpl` (NEW) — directory convention. 1 file per rejected concept.
- `references/out-of-scope-kb.md` (NEW) — when to create (rejected enhancement), when to consult (stage 02 iter>0, stage 08 triage). Full format.
- `scripts/bootstrap.py` — creates `_out-of-scope/` in scaffold + renders README.

**Bootstrap.py general:**
- 8 new canonical refs added to `runtime_refs` list (copied to `<workspace>/_references/runtime/`).
- `SKILL_VERSION = "3.3.0"`.

### Out of scope in this release (Tier 3 — future work)

- Deep modules + deletion test in stage 02
- Design It Twice (3 parallel interfaces) in stage 02
- Git guardrails hook (production tier)
- Explicit zoom-out instruction in stage 00
- SKILL.md description tightening (write-a-skill format)

### Tests

- 538 tests passing (+10 vs v3.2.0). Coverage maintained.
- New: `test_project_root_claude_md.py` (17), `test_agent_brief_render.py` (10).

### Refs

- Plan: `<plans>/primeiro-fa-a-um-plano-sunny-glade.md` (gaps G1-G17 addressed via adversarial review)
- Source patterns: github.com/mattpocock/skills (engineering/triage, engineering/diagnose, engineering/grill-with-docs, engineering/tdd, engineering/to-issues)

---

## v3.2.0 — Test infrastructure: test_specs, test-recipes, TDD evidence (2026-04-28)

### Why v3.2.0

Audit identified 7 gaps in the skill's test infrastructure: no distinction by test type in plan.md, no test planning in stage 02, stage 05 completely excluding `tests/`, profile-matrix without `test_specs`, items 1-3 of Akita without mandatory evidence, no test recipes by profile, and stage 01 without capturing existing test context.

### Changes

- **`scripts/profile-merge.py`:** new function `_test_specs(profile, tier)` — derives `test_specs` for 10 profiles covering `test_types_required`, `coverage_threshold` (calibrated by tier), `http_integration`, `db_integration`, `component_testing`, `eval_strategy`, `eval_threshold` and similar. Field integrated in `merge_profile()` — not overridable via `.icm-profile.local.yaml`.
- **`templates/_config/profile-matrix.md`:** `test_specs.coverage_threshold` row in defaults table (0 / 60 / 80 / 90 per tier). New section "test_specs per profile" documents canonical values for 10 profiles.
- **`templates/_references/test-recipes/` (10 NEW files):** test recipes per profile — `app_web_backend`, `app_web_frontend`, `agent_ia`, `ml_project`, `cli_tool`, `framework_library`, `dashboard`, `data_analysis`, `experiment`, `technical_article`. Frameworks, patterns, anti-patterns and quick checklist per profile.
- **`scripts/bootstrap.py`:** copies `_references/test-recipes/<profile>.md` to workspace during bootstrap.
- **`templates/workspace/stages/01_discovery/CONTEXT.md.tpl`:** Input #12 test-recipe (conditional). New step 9 "Gather Test Context" — captures existing suite, framework, coverage policy, eval strategy; output in `§Test Context` of discovery.md.
- **`templates/workspace/stages/02_design/CONTEXT.md.tpl`:** New mandatory step 8 "Define global Test Strategy for workspace". Transition condition: `plan.md` must contain `§Test Strategy` + every code task must declare ≥1 test file in `Files touched`.
- **`references/wave-planner-algorithm.md`:** §2 "Mandatory test file rule" — tasks with code files (`src/`, `.py`, `.ts`, etc.) must declare ≥1 test file; violation = `BLOCKED_ERROR "test file missing for task <slug>"`; exception for `doc-only`/`config-only`.
- **`references/4-block-contract-template.md`:** rule in `Files touched` requires ≥1 test file per code task. Items 1-3 of Akita now require mandatory evidence: test file name + test case name; coverage ≥ threshold; 3× consecutive execution.
- **`templates/workspace/stages/05_verification/CONTEXT.md.tpl`:** Step 4.5 — audit `coverage report` vs `test_specs.coverage_threshold` (PASS/CONDITIONAL/FAIL per tier). Step 4.6 — sample-check 3 random wave-plan tasks verifying test types in FS. `Do Not Read` constraint relaxed: partial read of `tests/` via `git ls-files` + coverage report.

### Tests

Existing suite maintained. Wave Planner test file rule covered by `test_wave_planner_dag.py`. `_test_specs()` is pure — directly unit-testable.

---

## v3.1.0 — Agent Teams → subagents (2026-04-27)

### Why v3.1.0

Complete replacement of the Agent Teams model (based on git worktrees + custom mailbox) by the native subagent model of Claude Code (Agent tool). The new model eliminates the complexity of worktrees, mailbox and sequential rebase, using isolated branches and merges instead of rebases. Simplifies stage 04 orchestration and reduces error surface.

### Changes

- **`references/subagent-protocol.md` (NEW):** canonical subagent protocol replaces `agent-team-protocol.md`. Uses native Agent tool instead of git worktrees + mailbox. No manual sync barrier — lead awaits direct return from each subagent.
- **`references/agent-team-protocol.md` (DEPRECATED):** removed from active flow. Preserved in `references/v2.4-snapshot/` for historical reference.
- **`references/file-flow-diagram.md` (DEPRECATED):** removed from active flow. Original diagram referred to the worktrees/mailbox model.

### Terminology updated in all active references

- "Agent Team" / "agent team" / "Agent Teams" → "subagent" / "subagents" / "subagent"
- "teammate" / "teammates" → "subagent" / "subagents"
- "worktree" / "git worktree" → "isolated branch" / "isolated branches" (task isolation context)
- "mailbox" / "custom mailbox" → "Agent tool output" (lead-subagent signaling context)
- "rebase" (sequential wave) → "merge" (workflow now uses merge instead of rebase)
- "agent-team-protocol.md" (reference) → "subagent-protocol.md"

### Updated files

- `references/session-handoff-protocol.md`
- `references/4-block-contract-template.md`
- `references/stage-templates.md`
- `references/xp-workflow-integration.md`
- `references/wave-planner-algorithm.md`
- `references/stop-points-canonical.md`
- `references/state-machine-schema.md`
- `references/recovery-wizard.md`
- `references/superpowers-mapping.md`
- `references/doc-reading-protocol.md`
- `references/smoke-manual-checklist.md`
- `references/example-run.md`
- `references/changelog.md` (this file)

### Preserved semantics

- Files in `references/v2.4-snapshot/` were not altered (immutable historical snapshot).
- Historical changelog entries (v2.4 and earlier) retain the original terminology "Agent Teams" / "worktrees" — they are historical records.
- `using-git-worktrees` remains as an auxiliary skill in the superpowers mapping (the skill still exists in the superpowers plugin, but the ICM protocol no longer requires it).

---

## v3.0.0-beta5 — Git governance overhaul + subagent protocol (2026-04-28)

### Why beta5

Git audit revealed 7 problems: subagents without explicit branch checkout, lead staying in base_branch after merge, context-check.sh crashing under parallel Agent calls, conflict between ICM prefix and Conventional Commits, wave branches with no hooks, partial bootstrap without recovery, and silent chmod on Windows.

### Changes

- **`references/subagent-protocol.md`:** §2.4 mandatory branch setup in subagent prompt (`git checkout -b` + validation). §5 sequential merge now does pre-flight stash, returns to workspace branch after each merge, unstashes at the end.
- **`templates/.claude/hooks/context-check.sh`:** rewritten. Removed `set -e` (caused crash in empty pipes). Atomic lock via `mkdir` (eliminates race condition with 4+ parallel Agent calls). Each parse command with `|| fallback`. Explicit jq check. Guard against git mid-operation.
- **`references/git-hooks.md`:** R8 — commit-msg emits warning in wave branches without Conventional Commit. New section "Wave branches" documenting separation of workspace prefix vs conventional.
- **`templates/.git-hooks/commit-msg`:** R8 implemented — detects `^wave-[0-9]+-[0-9]+/` and validates Conventional Commit types (does not block, warns only).
- **`references/recovery-wizard.md`:** 6th inconsistency `BOOTSTRAP_PARTIAL` (scaffold committed without hooks). Action A: install hooks. Action B: rollback + re-bootstrap. Canonical order updated.
- **`templates/workspace/_config/xp-conventions.md.tpl`:** resolved conflict workspace prefix vs Conventional Commits. Workspace branches = `workspace NNN: <desc>`. Wave branches = `<type>: <desc>`.
- **`scripts/bootstrap.py`:** chmod warning on POSIX (no longer silent `pass`). On Windows accepts silently (expected behavior).
- **`SKILL.md`:** header bump beta4 → beta5.

### Tests

Existing suite maintained. New hook rules (R8) covered by `test_commit_msg_hook.bats` in CI. Bootstrap chmod tested in `test_bootstrap.py`.

---

## v3.0.0-beta4 — 07→08 automatic transition + 08 intent inference (2026-04-26)

### Why beta4

User identified a semantic bug in beta3: stage 07 closed workspace as `COMPLETED` without automatic transition to stage 08, leaving feedback intake as a manual act disconnected from the main flow. Stage 08 remained orphaned; human had to remember to trigger it manually. Decision revised:

- Stage 07 **is not terminal**. Transitions immediately to 08 after merge confirmed.
- Stage 08 = actual terminal. Workspace stays in `COMPLETED_AWAITING_HUMAN` waiting for human to return with free-form feedback after real project use (no deadline).
- Stage 08 **infers intent** from free-form feedback (no raw A/B/C menu). Mini-confirm before executing.

### Changes

- **`templates/workspace/stages/07_merge/CONTEXT.md.tpl`:**
  - `next_stage: null` → `next_stage: "08"`.
  - Process step 7 updated: transitions 07_completed → immediately 08_in_progress + status COMPLETED_AWAITING_HUMAN.
  - Process step 8 NEW: render `_kickoff.md` in `stages/08_feedback_intake/`.
  - End-of-stage handoff replaced: KICKOFF block 07→08 without A/B/C menu, instructions "open new session AFTER real use, paste free-form feedback".

- **`templates/workspace/stages/08_feedback_intake/CONTEXT.md.tpl`:**
  - Pre-flight adjusted: accepts `status: COMPLETED_AWAITING_HUMAN` with `sub_stage: 08_in_progress` (automatic transition from 07).
  - Process step 4 replaced: "human free-form feedback" instead of "4 guided blocks".
  - Process step 5 NEW: **intent inference** with heuristics mapping → A/B/C + confidence score + clarification if < 0.6.
  - Process step 6 NEW: mini-confirm `[y/n/edit]` instead of raw A/B/C menu.
  - NEW section "Intent inference (canonical heuristics)": mapping bug→stage X, signals per exit, confidence, mini-confirm template.

- **`references/session-handoff-protocol.md`:** section "Stage 07 terminal" rewritten as "Stage 07 → 08 automatic transition". New section "Stage 08 actual terminal" covering inferred exits A/B/C. Stage 08 trigger: normal new session (no special command).

- **`SKILL.md`:** header bump beta3 → beta4. Section "After bootstrap" updated: stage 07 → 08 automatic; stage 08 exits inferred.

### Tests

527 passed maintained (templates have no direct tests; semantic changes do not affect handoff.py / state machine schema).

### Migration

Workspaces beta3 already created that are in COMPLETED status after 07: no automatic action required. If user wants to trigger feedback intake, just edit L1 manually: `stage_atual=08`, `sub_stage=08_in_progress`, `status=COMPLETED_AWAITING_HUMAN`. Workspaces beta1/beta2 remain legacy batched (decision 4B).

---

## v3.0.0-beta3 — 1-stage-1-session + dual handoff (2026-04-26)

### Why beta3

Beta1/beta2 used batched sessions (Q3 from plan v1: design 00+01+02 in one session, closing 05+06+07 in one session). In real usage, context grew beyond the 2-8k target per L2. Total token spend non-linear vs number of sub_stages in the batch.

User signaled empirical gain from **fresh context** > cache miss cost. Decision revised: **1 stage = 1 session** (decision A1, supersedes Q3-A from plan v1). Each stage pays 1 cache miss (~2-3k tokens warm-up) in exchange for lean context + lower total token spend.

### Changes

- **`references/session-handoff-protocol.md` (NEW):** canonical doc for the "1 stage = 1 session" protocol. `_kickoff.md` schema (L4-kickoff layer), handoff commit atomicity, anti-patterns. Stage 04 keeps wave-aware (1 lead session per wave; sub-waves within same session). Stage 07 terminal (generates no kickoff). Stage 08 exits A/B/C.
- **`templates/workspace/stages/_kickoff.md.tpl` (NEW):** generic kickoff template with placeholders.
- **`scripts/handoff.py` (NEW):** `render_kickoff`, `write_kickoff`, `extract_kickoff_metadata`, `validate_kickoff_present`. CLI mode for debug. 25 unit tests + snapshot fixture.
- **9 L2 templates updated:** each `templates/workspace/stages/<NN>_<name>/CONTEXT.md.tpl` gained `_kickoff.md` row in Inputs table (conditional) + new "End of stage handoff" section with checklist + verbal KICKOFF block for user. Stages 04, 07, 08 with specific customizations. +541 lines total.
- **`SKILL.md`:** section "After bootstrap" rewritten with 1-stage-1-session protocol. Cache miss vs fresh context trade-off documented.

### Migration beta1/beta2 (decision 4B)

**No forced migration.** Workspaces created before beta3 remain in batched mode (legacy). Only workspaces created after beta3 use 1-stage-1-session.

### Tests

527 passed (+25 new). Coverage 82%. Bats CI-only.

---

## v3.0.0-beta2 — Hook fix + intent inference + anti-superpowers (2026-04-26)

### Why beta2

Beta1 had a critical bug in the pre-commit hook: it read `.git/COMMIT_EDITMSG` in pre-commit stage, but git only persists the message AFTER the hook passes. Hook validated the PREVIOUS commit's message (or empty on first). Temporary workaround (install hook after bootstrap commits) only protected bootstrap; future user commits remained validating stale message.

### Changes

- **fix(hooks) — `0afcba7`:** split into 2 canonical stages. `pre-commit` keeps file checks + L1↔outputs atomicity. `commit-msg` (NEW) receives path in `$1` with current message; validates prefix + ADR exception. Installer + bootstrap updated. Regression test guarantees CURRENT message via `$1`.
- **feat(skill) — `77348b7`:** SKILL.md "Intent inference" with profile/tier heuristics (10 mappings) + confirm menu + initial seed in `stages/01_discovery/_seed.md`. Anti-superpowers rule (non-negotiable) reflected in L0 (rule 8).

### Tests

502 passed. Coverage 83%.

---

## v3.0.0-beta1 — Complete rewrite (2026-04-26)

> The filesystem is the program. The skill is midwife, not orchestrator.

### Summary

End-to-end rewrite in 7 waves. Skill v2.4 (persistent orchestrator, 1 main + N subagents, 6 stages) replaced by ICM v3 architecture (one-shot midwife + filesystem governs cycle + 9 stages + Agent Teams + Wave Planner LLM review + Recovery Wizard). v2.4 preserved in `references/v2.4-snapshot/` (immutable historical snapshot).

### Why v3

**Structural problems detected in v2.4:**

- **B1**: Leaked absolute path (orchestrator lost CWD at subagent boundaries → wrote to wrong directory).
- **B2**: Relative paths `../../` confused subagents.
- **B3**: Stop points in subagent without well-defined return protocol.
- **B6**: Loose sync barrier in parallel implementation phase.
- **V3**: Superpowers skills invoked inside each stage loaded ~2-5k tok each, inflating context.
- **Rule conflict**: subagent running `/xp-workflow` inside stage 03 collided with ICM protocol.

**Guiding decisions:**

1. Filesystem is the program, skill is just bootstrap.
2. One phase = one new session (Anthropic 5min prompt cache).
3. Superpowers skills become references (200tok summaries), not invocations.
4. 4-block contract mandatory per task.
5. Profile + Tier in L0 calibrate rigor (10 profiles × 4 tiers = 40 combos).
6. Mandatory stop points + standard A/B/C menu in every stage with a decision.
7. Formal dev↔QA loop via auto-QA Akita 15-item.
8. Parallelism waves only where safe (DAG by file footprint).
9. Git worktrees per teammate (physical race mitigation).
10. Reconnaissance Phase before everything.
11. Universal feedback intake stage 08 (not just production).
12. Self-revision DROPPED — skill is midwife, not evolutionary runtime.

### Breaking Changes

- **CLI**: `/xp-icm-workflow` now requires `profile=` and `tier=` (with interactive fallback). No default `app_web_backend`+`development`.
- **Folder structure**: 9 stages (00 recon → 08 feedback intake) replace the 6 from v2.4 (00 bootstrap → 06 merge). Numbering and names changed.
- **Branches**: now 3 types — `<base_branch>` (code), `workspace/NNN-slug` (state-only), `wave-NNN-N/<task-slug>` (wave code). v2.4 had only 1.
- **State machine L1**: strict YAML frontmatter (PyYAML safe_load) with stage-specific `sub_stage` enum. Schema validated in pre-flight.
- **Pre-commit hook**: installed by default. Blocks `--no-verify` bypass and validates L1↔outputs atomicity + prefixes.
- **Superpowers skills**: NOT invoked at runtime. Replaced by 200tok summaries pre-copied in `<workspace>/_references/superpowers-summary/`. Escape hatch via `Skill()` requires registering `event: skill_escape_hatch` in L1 history.
- **ADRs**: formalized lifecycle — born in stage 02, go to `<project_root>/docs/decisions/`, direct editing prohibited (use superseding ADR).
- **Self-revision**: removed. v2.4 had Phase 7 (conversational self-revision); v3 drops it.

### What's New (Waves 1-6)

| Wave | Delivered |
|---|---|
| 1 — Foundations | L1 state-machine schema with per-stage sub_stage enum; 4 deterministic scripts (profile-merge, lessons-match, wave-planner-script, validate_state); POSIX bash pre-commit hook with 6 rules; L0/L1 templates; profile-matrix 10×4; pyproject.toml with pytest-playwright workaround. |
| 2 — Bootstrap + Recovery | SKILL.md rewritten (one-shot midwife); bootstrap.sh + bootstrap.py with greenfield/existing/external_repo; recovery-wizard.py detecting 6 inconsistencies R2.7+R4.5 with 3 actions A/B/C; idempotent git-hook-installer.sh. |
| 3 — Stage Templates + L2 | 9 L2 templates (00..08) with canonical schema (frontmatter + Inputs + Do Not Read + per-stage sub_stage enum + applicable_stop_points); 4 references (stage-templates, stop-points-canonical 12 items, 4-block-contract + 7-step TDD cycle + Akita 15-item, feedback-intake-stage08 with 3 exits A/B/C); workspace stop-points.md resolved by tier. |
| 4 — Agent Teams + Wave Planner LLM | references/wave-planner-algorithm.md (DAG + LLM review subagent R2.4); references/subagent-protocol.md (spawn via Agent tool + mid-wave reduce); scripts/wave-planner-llm-review.py with mock mode (`--mock-response`), prod (`--llm-response`) and prompt (exit 2). |
| 5 — Superpowers summaries | 10 200tok summaries in `templates/_references/superpowers-summary/` (brainstorming, writing-plans, dispatching-parallel-agents, TDD, subagent-DD, verification, requesting-review, receiving-review, finishing-branch, debugging); references/superpowers-mapping.md, xp-workflow-integration.md, example-run.md rewritten; bootstrap.py copies summaries + 7 runtime refs to workspace. |
| 6 — CI + Smoke | `.github/workflows/test-skill.yml` (Ubuntu Python 3.13 + bats); tests/run.sh with `--ci` and `--no-bats` flags; README badges; references/smoke-manual-checklist.md (10 canonical items pre-release). |

### Final suite stats

- **502 tests green** (100% Python 3.13 Windows + Linux CI).
- **Coverage 83%** total. Pure scripts 87-96%. Bootstrap 49% (orchestration covered via bats e2e). Recovery 73%.
- **Bats CI-only**: integration (test_git_hooks, test_bootstrap, test_worktrees) + e2e (recovery_orphan, greenfield_full, existing_repo, external_repo).
- **Hypothesis property-based**: state-machine + wave-planner DAG (preserves deps, sub_waves respect cap).
- **LLM Mocks**: 3 fixtures in `tests/mocks/llm_review_responses/` (approve_clean, propose_implicit_dep, invalid_verdict).

### Migration Guide v2.4 → v3

**Existing v2.4 workspaces**: do NOT migrate automatically. Recommended strategy:

1. v2.4 workspace finishes current cycle (reaches `STAGE: COMPLETED`).
2. For new feature: bootstrap v3 workspace from scratch with `/xp-icm-workflow profile=X tier=Y`.
3. Lessons collected in `docs/lessons.md` migrate automatically (compatible format).
4. ADRs in `docs/decisions/` migrate automatically (same format).
5. v2.4 snapshot preserved in `references/v2.4-snapshot/` for archaeology.

**CLI mapping**:

| v2.4 | v3 |
|---|---|
| `/xp-icm-workflow` (no args) | `/xp-icm-workflow profile=<X> tier=<Y>` (required) |
| `STAGE: 03_implementation` | `stage_atual: "04"` + `sub_stage: "04_wave_<N>_in_progress"` |
| Ad-hoc subagent spawn | Agent Team in stage 04 (lead + N teammates in git worktrees) |
| Superpowers skills invoked inline | 200tok pre-copied summaries (escape hatch via L1 history) |

**Stable conventions** (unchanged between v2.4 and v3):

- Layer Loading Protocol (L0 → L1 → L2 → L3 → L4).
- ADR format (Context / Decision / Consequences / Status).
- Edit-source principle.
- Brazilian Portuguese for content, English for identifiers.

### Promotion criteria v3.0.0-beta1 → v3.0.0

Documented in `references/smoke-manual-checklist.md`:

- ✅ Formal suite: ≥80% coverage critical paths, ≥60% rest. CI green 7 consecutive days.
- ✅ ≥3 real projects used v3.0.0-beta1 without serious regression.
- ✅ Cost comparison: v3 ≤ 60% of v2.4 in ≥3 projects.
- ✅ 10 smoke checklist items PASS in ≥3 projects.
- ✅ Lessons collected in `docs/lessons.md` of the skill itself (future wave 8 maintenance).

---

## v2.4.0 — Conciseness refactor + adversarial corrections

### Structural refactor (conciseness without loss)

- **SKILL.md reduced from 1291 → ~600 lines** without losing hard-gates, principles or contracts.
- Templates of `CONTEXT.md` for the 6 stages + root `CLAUDE.md` and root `CONTEXT.md` templates moved to `references/stage-templates.md`.
- Extensibility section moved to `references/extending-skill.md`.
- Version history moved to this file (`references/changelog.md`).
- New `references/example-run.md` with an example of stage transition.
- "Phase 1 — Stage Execution" compacted: delegation protocol and fix loop remain in SKILL.md (load-bearing at runtime), template detail goes in reference.
- Stage Transition Checklist declared 1× in dedicated section; stages reference by name instead of duplicating.
- Delegation Principle with repeated mention only where risk is real (Stages 03/04/05).
- ICM Design Principles in SKILL.md remain as 5 titles + 1 sentence each; detail in reference `icm-paper-summary.md`.
- Convention prefix `[L3:cfg]` / `[L4:in]` in Inputs table — reduces repeated prose without losing operational distinction between constraint vs input.

### Adversarial corrections round 1 (subagent review)

- **Gap A (example-run)**: subagent prompt in `example-run.md` now includes `decisions.md` — aligns with Delegation Protocol in SKILL.md.
- **Gap B (L1 vs L3 contradiction)**: `docs/decisions/` now L3 consistent throughout SKILL.md (Edit-Source section corrected).
- **Gap C (race condition in parallel reports)**: parallel subagents write to `output/reports/task-<slug>.md` (their own files). Orchestrator consolidates later in `implementation-report.md` — eliminates race. Delegation Protocol, output format and example-run updated.
- **Gap D (Phase 0 did not respect AGENTS.md)**: added Step 0.0 "Respect Instruction Priority" — reads `AGENTS.md` and `CLAUDE.md` from parent project BEFORE creating workspace.
- **Gap E (`stages/XX/references/` folder never used)**: removed from default structure. Now optional, create only if there is stage-specific reference material.
- **Gap F (tension ADRs L3 but created at run time)**: added section "ADR Lifecycle" — clarifies birth in Stage 02, immediate promotion to L3, editing via Edit-Source.
- **Gap G ("DELEGATE, do not execute" ambiguous)**: reformulated Orchestration Boundary — distinguishes skill invocation (01-02) from subagent delegation (03+), clarifies what orchestrator may read.

### Adversarial corrections round 2 (complete cross-file review)

- **Gap S (Stage 03 template misaligned with Gap C correction)**: `references/stage-templates.md` updated — Stage 03 template now reflects new `reports/task-*.md` structure + consolidation in `implementation-report.md`. Outputs, Process step 7 and Verify aligned with SKILL.md.
- **Gap T (xp-workflow-integration had `docs/*` as L1)**: "Shared Documents" table corrected — `docs/decisions/`, `docs/tech_debt.md`, `docs/lessons.md` now L3 consistent with Gap B. Table also includes new artifacts `reports/task-*.md`.
- **Gap U (superpowers-mapping rule 4 omitted parallel reports)**: rule 4 now lists individual `reports/task-*.md` as artifacts that orchestrator reads.
- **Gap Z (STAGE ambiguity after transition)**: Stage Transition Checklist item 3 now specifies that, after marking stage completed in history, the `STAGE` field of root `CONTEXT.md` is updated to point to the NEXT stage as `IN_PROGRESS`. Last stage marks `STAGE: COMPLETED`. Example-run aligned.

### Adversarial corrections round 3 (fine cross-file details)

- **Gap AB/AK (Bootstrap step numbering broken)**: `stage-templates.md` referenced "Step 0.5" and "Step 0.4" but SKILL.md combined into "Step 0.4-0.6". Aligned.
- **Gap AD (example-run describing wrong root CONTEXT.md post-Z)**: Step 2 of `example-run.md` now reflects that upon entering Stage 03 the `STAGE` field is already `03_implementation, IN_PROGRESS` (not `02_design COMPLETED`).
- **Gap AE (Stage 03 review gate omitted individual reports)**: SKILL.md updated — review gate now mentions reading individual `reports/task-*.md` AND/OR consolidated.
- **Gap AF (superpowers-mapping listed lessons as subagent input)**: corrected — only orchestrator reads `lessons.md`; subagent receives filtered lessons injected in prompt.
- **Gap AH (wrong section count)**: SKILL.md and `stage-templates.md` said "six sections" but listed 7 (State, Skill, Inputs, Process, Outputs, Verify, Review Gate). Corrected to "seven sections".
- **Gap AJ (extending-skill item 4 omitted root templates)**: checklist now includes updating root `CLAUDE.md` and root `CONTEXT.md` when the new skill impacts workspace identity or routing.
- **Gap AL (lessons.md flow not explicit)**: SKILL.md Stage 03 Process step 5 now makes explicit that orchestrator reads `lessons.md`, extracts applicable lessons and injects into delegation prompt — subagent does not read the file directly.
- **Gap AM (example-run anti-consistency ADR 0003)**: subagent prompt context rules (a) now say "DO NOT read ADRs 0001-0002"; ADR 0003 (stack) is summarized in `## Workspace Context` of the prompt — do not duplicate reading.

### Adversarial corrections round 4 (fresh subagent)

- **Gap AN (broken Stage 03 numbering)**: "Orchestrator process" had steps 1-6 and then "After all complete" restarted at 6-8 — collision. Now sequential 1-10, coherent.
- **Gap AO (regression Gap C — who writes implementation-report)**: Text "Format of `implementation-report.md` (subagents write, orchestrator reads)" contradicted the post-Gap C architecture. Corrected: format describes `output/reports/task-<slug>.md` (each subagent writes its own); consolidated is aggregation done by orchestrator or consolidator.
- **Gap AP (Stage 03 template omitted parallel reports)**: `stage-templates.md` Delegation Principle and Review Gate said "orchestrator reads ONLY implementation-report.md". Now mentions individual reports + consolidated, consistent with SKILL.md and superpowers-mapping.
- **Gap AQ (example-run history without ADRs)**: Stage Transition Checklist in example now includes ADRs created in Stage 02 in the transition history.
- **Gap AR (schema→shema typo)**: 2 occurrences of `0004-shema-habits.md` corrected to `0004-schema-habits.md`.
- **Gap AS (docs/ tree inline with comma)**: folder structure SKILL.md Step 0.3 now shows `docs/` with 3 sub-items in tree (decisions/, lessons.md, tech_debt.md), classified as L3.

Functional behavior equivalent to v2.3.0 + resolution of all ambiguities, contradictions and structural risks detected in 4 rounds of adversarial review (33 gaps corrected). No hard-gate removed.

---

## v2.3.0 — Hard Gates and Strict Separation

- Stage Transition Protocol (5-item hard gate checklist between stages).
- Orchestration Boundary Rule (table by stage type + auto-correction).
- Fix Loop Protocol (review → delegate → review loop for P0/P1 issues).
- Review Gates 01-06 with explicit transition checklist.
- Mandatory State section in all 6 `CONTEXT.md` templates.

---

## v2.2.0 — Extensibility

- Self-Improvement section with 8-item checklist for updating when a new skill is incorporated.
- New skill classification questions.
- Changelog entry format.

---

## v2.1.0 — Delegation Principle

- Orchestrator NEVER reads source code directly.
- Stage 03 always delegates to subagents (no longer optional).
- `CONTEXT.md` templates for Stages 03, 04 and 05 updated with "DO NOT READ src/ or tests/".
- `implementation-report.md` format specified.
- Error recovery updated for subagents.
- References (`superpowers-mapping`, `xp-workflow-integration`) updated to reflect delegation.

---

## v2.0.0 — Revision based on audit against ICM paper

- Layer Loading Protocol with mandatory order and explicit scoping.
- Operational distinction Layer 3 vs Layer 4 (constraint vs input).
- Token budget and context pollution.
- Incremental compilation with selective re-execution.
- Verify section in stage contracts.
- Edit-source principle operationalized.
- Session resume reads Layer 2/3 of current stage.
- Context scoping for subagents.
- "Configure the factory" principle.
- Workspace builder.
- 5 explicit ICM design principles.

---

## v1.2.0 — Final revision

- Standardized relative paths.
- References to `src/`, `tests/` corrected (not inside `stages/`).
- Update of root `CONTEXT.md` in all stages.
- "Absolute path" corrected to "relative path" in subagents.

---

## v1.1.0 — Post-audit corrections

- State file (root `CONTEXT.md`).
- Session resume.
- Formal ADR propagation.
- Explicit subagent contract.
- Complete inputs in templates.
- Error recovery distinct by origin.

---

## v1.0.0 — Initial XP-ICM Workflow

- ICM + `/xp-workflow` + superpowers integration.
