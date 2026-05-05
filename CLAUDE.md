# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Modification workflow

**Every non-trivial change follows this flow:**

```bash
# 1. Create branch from main
git checkout main
git checkout -b feat/<short-slug>

# 2. Apply changes (edits, tests, etc)
# ...

# 3. Commit(s) on the branch
git add <paths>
git commit -m "feat: description"

# 4. Run tests (required before merge)
bash tests/run.sh --no-bats   # or: python -m pytest tests/unit/

# 5. Merge to main (fast-forward) + push (if remote configured)
git checkout main
git merge --ff-only feat/<short-slug>
git push origin main          # only if remote configured

# 6. Delete branch (local + remote if applicable)
git branch -d feat/<short-slug>
git push origin --delete feat/<short-slug>   # only if remote
```

**Rules:**
- Branch is discarded after merge — do not accumulate stale branches.
- Tests must pass before merge (`538+/538+ tests` baseline).
- `--ff-only` enforces linear merge; conflict = rebase the branch first.
- Trivial fix (typo, comment) may be committed directly to `main` without a branch.
- No remote configured in this skill repo — `git push` steps become no-op
  until a remote is added.

## Pre-merge drift audit (mandatory)

**Every PR touching `references/`, `templates/`, `scripts/`, `SKILL.md`, `CLAUDE.md`, `README.md` MUST run:**

```bash
pytest tests/unit/test_no_drift.py -v
```

**Active detectors (21, grouped):**
- A: Version consistent across canonical files (canonical = `scripts/bootstrap.py:SKILL_VERSION`).
- A': Changelog has entry for canonical version.
- B: Profile count (canonical = `len(CANONICAL_PROFILES)` in `profile-merge.py`).
- C/D: Status enum sync (`validate_state.py:ALLOWED_STATUSES` ↔ `references/state-machine-schema.md`) + allow-list anti-typo.
- E: Markdown cross-refs in `references/` (direction `link → file` — target exists).
- F: Shell + git-hook templates without CRLF.
- H: Auxiliary scripts with `CURRENT_SKILL_VERSION` stay in sync with bootstrap (generic — catches future scripts).
- 4-block parser: canonical heading levels + regex match in template.
- v3.8.0 (forensic+): canonical doc exists, bootstrap runtime_refs mentions it, L2 stage 04 cross-ref + `MAX_FORENSIC_RETRIES`, wave-execution sub-steps, state-machine error_type values.
- SKILL.md indexes canonical docs (whitelist `SKILL_MD_INDEXED_DOCS`, direction `file → mention`).

**If a test fails:**
- Do NOT merge until fixed.
- Add an entry to the test whitelist (`VERSION_WHITELIST` / `PROFILE_COUNT_WHITELIST`) ONLY if the divergence is legitimate (historical changelog, archived kickoff, explicit legacy fixture).
- Otherwise: fix the drift in the diverging file.

**Why automated:** the repo is highly-coupled (version in 5+ files, profile count in 8+, status enum in 3+). Auditing manually in a fresh session is unreliable. Test gate blocks drift at commit time, without needing to remember.

## Rule: SKILL_VERSION bump requires multi-file sweep (v3.7.0, extended v3.7.2)

**Every change to `scripts/bootstrap.py:SKILL_VERSION` requires synchronized updates to:**

1. **`SKILL.md`** header `# xp-icm-workflow vX.Y.Z`
2. **`README.md`** badge `version-vX.Y.Z` + new section `## vX.Y.Z — <title>` at the top of the version list
3. **`references/design-system.md`** frontmatter `format (vX.Y.Z)` + line `> **Version:** vX.Y.Z`
4. **`references/preview-loop-protocol.md`** title `build-iterate visual (vX.Y.Z)` + line `> **Version:** vX.Y.Z`
5. **`references/changelog.md`** new entry `## vX.Y.Z — <title> (YYYY-MM-DD)` at the top with a `### Changes` section listing concrete modifications
6. **`scripts/migrate-workspace.py`** `CURRENT_SKILL_VERSION = "X.Y.Z"` + last entry of `SUPPORTED_VERSIONS` tuple = X.Y.Z + new function `migrate_<from>_to_<X_Y_Z>` (even if bump-only) + entry in `STEP_FUNCTIONS` dispatcher
7. **`tests/unit/test_migrate_workspace.py`** update/add cases for the new step (smoke + idempotency)

**Automatic validation:**
- `test_no_drift.py::test_version_consistency_canonical_files` (5 canonical files — items 1-4 + #6)
- `test_no_drift.py::test_changelog_has_entry_for_canonical_version` (#5)
- `test_no_drift.py::test_scripts_skill_version_sync` (generic — scans `scripts/**/*.py` for `CURRENT_SKILL_VERSION` + tuple last entry, catches future auxiliary scripts)
- `test_migrate_workspace.py::test_current_skill_version_matches_bootstrap` (direct cross-check)

Failure in any = do NOT merge.

**Additional rule (v3.7.0):** README.md also requires a `## vX.Y.Z` section entry summarizing changes (not just a badge bump). If changes are very broad, the README section may be brief with a cross-ref to `references/changelog.md`.

**Additional rule (v3.7.2):** detector H catches auxiliary scripts that adopt the `CURRENT_SKILL_VERSION` pattern in the future — no need to surgically update `VERSION_MUST_MATCH` for each new script (but a fixed pattern may be added for double coverage).

## Commands

```bash
# Install deps
pip install -r requirements.txt

# Run all tests (pytest + bats if available)
bash tests/run.sh

# Run pytest only (faster local iteration)
bash tests/run.sh --no-bats

# CI mode (coverage XML)
bash tests/run.sh --ci

# Run single test file
pytest tests/unit/test_bootstrap.py -v

# Run single test by name
pytest tests/unit/test_bootstrap.py::test_validate_slug -v

# Pre-flight runtime check
bash scripts/check-runtime.sh
```

## Architecture

This is a **filesystem-based project orchestration skill** for Claude Code implementing ICM (Interpretable Context Methodology). The core idea: folder structure replaces traditional orchestration; each stage = 1 Claude session.

### 5-Layer Context Model

| Layer | File | Role |
|---|---|---|
| L0 | `workspaces/NNN/CLAUDE.md` | Identity — immutable, always loaded |
| L1 | `workspaces/NNN/CONTEXT.md` | State machine — YAML frontmatter, always loaded |
| L2 | `workspaces/NNN/stages/NN/CONTEXT.md` | Stage instructions — current stage only |
| L3 | `_config/`, `_references/`, `docs/` | Rules & reference — loaded as needed |
| L4 | `stages/NN/output/` | Working outputs — product artifacts |

### 9-Stage Pipeline

`00:recon → 01:discovery → 02:design → 03:wave-planner → 04:implementation-waves → 05:verification → 06:review → 07:merge → 08:feedback-intake`

Stage 04 exception: each wave = 1 lead session; subagents spawned via `Agent(isolation: "worktree")` (ephemeral worktree per task, created by the harness), branch `wave-<NNN>-<N>/<task-slug>` derived from `BASE_BRANCH`. Canonical doc: `references/wave-execution-protocol.md`.

### Key Scripts (`/scripts/`)

- **bootstrap.py** — One-shot workspace creation (folder structure, L0/L1/L2 files, git branch, pre-commit hooks, atomic commit, project-root CLAUDE.md render)
- **profile-merge.py** — Merges 11 profiles × 4 tiers → deterministic effective hash (sha256)
- **handoff.py** — Renders `_kickoff.md` (L4) + manages `<project_root>/CLAUDE.md` ICM region (update/remove/deactivate)
- **wave-planner-script.py** — Parses `plan.md` → DAG → cycle detection (DFS 3-color) → topological sort (Kahn) → sub-wave subdivision (HITL tasks isolated cap=1)
- **wave-planner-llm-review.py** — Optional LLM review subagent for wave plan validation
- **agent-brief-render.py** — Generates AGENT-BRIEF for stage 04 subagent dispatch (parses plan.md task → behavioral brief with acceptance criteria)
- **recovery-wizard.py** — Detects/repairs 7 workspace inconsistency types (HASH_MISMATCH, MISSING_COMMIT, MISSING_OUTPUT, STALE_IN_PROGRESS, BRANCH_MISSING, CLAUDE_MD_ROOT_STALE, CLAUDE_MD_ROOT_MISSING)
- **validate_state.py** — L1 YAML validation against state-machine-schema
- **lessons-match.py** — Extracts top-3 relevant lessons for current task

### Profile System

11 profiles (e.g., `app_web_backend`, `app_web_frontend`, `fullstack`, `ml_project`, `agent_ia`) × 4 tiers (`experimental`, `tool`, `development`, `production`). Config keys: `stages_skipped`, `tdd_required`, `security_gate`, `stop_points_calibration`. See `templates/_config/profile-matrix.md`.

### Naming Conventions

- **Workspace ID:** `NNN-slug` (e.g., `042-feat-auth`), auto-incremented
- **Branches:** `workspace/NNN-slug` (state files), `wave-NNN-N/<task-slug>` (code)
- **Commits:** prefix `workspace NNN: <action>` — enforced by pre-commit hook
- **Task slugs:** `^[a-z0-9][a-z0-9-]*$`

### L1 State Machine

YAML frontmatter in `CONTEXT.md` tracks: `workspace`, `profile_base`, `profile_effective_hash`, `tier`, `stage_atual`, `sub_stage`, `status`, `iteration`, `history[]`, `last_transition`. Schema spec: `references/state-machine-schema.md`.

### Template Placeholders

Templates in `/templates/` use `{{WORKSPACE}}`, `{{PROFILE}}`, `{{TIER}}`, `{{PROFILE_EFFECTIVE_HASH}}`, `{{SKILL_VERSION}}`, `{{STAGES_SKIPPED}}`, etc.

## Key Reference Docs

- `SKILL.md` — Skill entry point, CLI args, intent inference protocol
- `references/session-handoff-protocol.md` — 1-stage-1-session flow
- `references/state-machine-schema.md` — L1 YAML spec
- `references/wave-planner-algorithm.md` — DAG construction details
- `references/stop-points-canonical.md` — 12 stop points + tier thresholds
- `references/example-run.md` — Full 9-session E2E walkthrough
- `references/maintainer-checklist.md` — How to modify the skill (new script, doc, template, stage, version bump)

## Tests

548 tests, 83%+ coverage. `tests/unit/` uses pytest + Hypothesis (property-based). `tests/integration/` and `tests/e2e/` use bats (CI-only, Ubuntu). Mock LLM responses in `tests/mocks/llm_review_responses/`. Fixtures in `tests/fixtures/`.

Playwright plugin disabled in `pyproject.toml` (workaround — leave it).

## v3.9.0 — Layered dev↔QA loop + lead-resolution tier

Stage 04 gains 3 QA layers, executed **always, all tiers**:

- **L1 writer** (subagent) — vertical TDD: tracer-first + loop `RED → GREEN → CI scope → REFACTOR` (anti-horizontal slicing). Drops Akita 15-item inline (self-grading bias documented: Huang ICLR 2024, arxiv 2510.11822, arxiv 2509.16533).
- **L2 forensic+ extended** — 7 deterministic git-only checks (4 original v3.8.0 + 3 new): Check 5 acceptance↔test mapping, Check 6 OUT OF SCOPE violations, Check 7 ADR import drift. HARD → skip L3, surgical retry.
- **L3 orthogonal critic** — Agent fresh context, `model = TIER_CEILING[tier]` always, anti-sycophancy hardcoded in `templates/critic-prompt.md`. Output triplet (claim, evidence file:line, counterexample, severity BLOCKING|MAJOR|MINOR; decision APPROVE|REJECT|ABSTAIN).

**Per-task loop cap 3 attempts.** Exhausted OR convergence trip (Jaccard ≥ 0.7) OR catastrophic detected → **lead-resolution tier**:

- **B1 REWRITE_SPEC** — lead rewrites spec more rigorously, 1 final writer spawn.
- **B3 DIRECT_IMPL** — lead writes directly on branch `wave-<NNN>-<N>/<slug>-lead-resolved`, passes L2+L3 equally.
- **B4 VOID_TASK** — `### VOIDED` block in plan.md with concrete rationale, wave-planner --recalculate.

Cap 1 attempt per bucket. Sequence B1→B3→B4. Stage 05 audit (new sub-step 5.5) detects loosen/silenced/vague — FAIL = `BLOCKED_ERROR error_type: lead_resolution_audit_failed`.

**Pick-model heuristic** (`scripts/pick-model.py`): `compute_score(estimated_lines, hot_paths, security_sensitive, public_api_change, algorithm_heavy, doc_only/config_only/css_only, tier)` + tier ceiling cap. Writer ≤ ceiling; critic = ceiling always.

Canonical docs: `references/critic-protocol.md`, `references/lead-resolution-protocol.md`, `references/mocking-guidelines.md` (boundaries-only mocking, mattpocock alignment).

Active changes in:
- `scripts/forensic-plus.py` (+Checks 5/6/7, JSON schema bump backward-compat)
- `scripts/lead-diagnose.py` (new) — Jaccard cluster + catastrophic detector + bucket recommend + surgical brief render
- `scripts/pick-model.py` (new) — score + tier ceiling + writer/critic split
- `scripts/agent-brief-render.py` (--tier flag integrates pick-model)
- `templates/critic-prompt.md` (new)
- `templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl` (new flow: vertical TDD → L2 → L3 → diagnose → retry/lead-bucket; step 9 lead-resolution)
- `templates/workspace/stages/05_verification/CONTEXT.md.tpl` (sub-step 5.5 audit lead resolutions)
- `references/4-block-contract-template.md` (rewrite §3 vertical TDD; §5 Akita DELETED)
- `references/forensic-plus-protocol.md` (7 checks)
- `references/state-machine-schema.md` (+status LEAD_RESOLUTION_IN_PROGRESS, +5 error_types)
- `scripts/migrate-workspace.py` (3.8.0→3.9.0 step bump-only)
- `scripts/recovery-wizard.py` (+LEAD_RESOLUTION_STALE)
- `scripts/validate_state.py` (VALID_STATUSES += LEAD_RESOLUTION_IN_PROGRESS)
- 9 new drift detectors in `tests/unit/test_no_drift.py`
- `tests/unit/test_lead_diagnose.py` (new, 17 cases)
- `tests/unit/test_pick_model.py` (new, 22 cases incl. property-based via Hypothesis)
- `tests/unit/test_forensic_plus.py` (+6 cases v3.9.0)
- `tests/unit/test_migrate_workspace.py` (+5 cases v3.9.0)

934 tests passing, 74% coverage.

## v3.10.0 — E2E coverage reinforcement

Stage 04 gains 4 complementary E2E enforcement fronts (Level 2 of the reinforcement plan):

1. **Wave-planner detection (advisory).** `scripts/wave-planner-script.py:USER_FACING_PATHS_BY_PROFILE` maps 11 profiles → tuple of path prefixes (backend: `routes/ controllers/ handlers/ endpoints/ api/ graphql/`; frontend: `pages/ views/ app/ components/pages/ src/routes/`; fullstack union; cli: `cmd/ cli/ commands/`; agent_ia: `prompts/ agents/ tools/`; data_analysis: empty). `_task_requires_e2e()` checks whether `files_touched` matches. `render_wave_plan` emits column `E2E required?` in the task table + annotation `> **E2E coverage required**` when ≥1 task flagged.

2. **Forensic+ Check 8 (enforcement).** Task with `Requires E2E update: true` in plan.md MUST have ≥1 file modified in `e2e/`/`cypress/`/`playwright/`/`tests/e2e/`/`tests/integration/`/`test/e2e/`/`__e2e__/` in the diff. HARD in tier dev/prod, SOFT in exp/tool. Override via `**E2E:** skip - <rationale>` in the 4-block (Stage 05 audit validates concrete rationale).

3. **L4 wave gate step 11b (universal tier dev/prod).** Stage 04 step 11 expanded into 11a (universal global CI) / 11b (E2E suite tier dev/prod with non-empty `user_facing_paths`) / 11c (cross-task coherence production). Red 11b → `BLOCKED_ERROR error_type: e2e_suite_failed` → diagnose-protocol → human gate A/B/C.

4. **Stage 05 sub-step 4.7 (audit).** Audits that e2e suite exists + last git modification < 7 days OR no user-facing tasks delivered + CI report e2e green. Failures: `e2e_suite_missing` / `e2e_suite_stale` / `e2e_skip_unjustified`.

Canonical doc: `references/e2e-coverage-protocol.md`.

Active changes in:
- `scripts/forensic-plus.py` +Check 8 (`check_e2e_coverage()`); plan parser extracts `Requires E2E update` field + `**E2E:** skip` override; JSON schema `e2e_coverage_missing`.
- `scripts/wave-planner-script.py` +`USER_FACING_PATHS_BY_PROFILE` constant + `_task_requires_e2e()` helper; render_wave_plan includes E2E column + annotation.
- `scripts/recovery-wizard.py` +`CODE_E2E_SUITE_STALE` in CANONICAL_ORDER.
- `scripts/migrate-workspace.py` +`migrate_3_9_0_to_3_10_0` (bump-only).
- `references/4-block-contract-template.md` +`### Requires E2E update` optional field.
- `references/forensic-plus-protocol.md` Check 8 spec + 8 checks tier×severity matrix.
- `references/state-machine-schema.md` +error_types e2e_suite_failed/missing/stale/skip_unjustified.
- `templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl` step 11 → 11a/11b/11c.
- `templates/workspace/stages/05_verification/CONTEXT.md.tpl` step 4.7 NEW.
- 6 new drift detectors in `tests/unit/test_no_drift.py`.
- `tests/unit/test_forensic_plus.py` +5 cases v3.10.0; `tests/unit/test_wave_planner_dag.py` +2 cases E2E column; `tests/unit/test_migrate_workspace.py` +5 cases v3.10.0.

951 tests passing, 74% coverage.

## v3.8.0 — Forensic+ wave reviewer (structural anti-fraud)

Step 8 of the 12-step pipeline (stage 04) expanded into sub-steps 8a/8b/8c/8d. 8a = `scripts/forensic-plus.py` audits each AFK task in the wave (skip HITL): 4 git-only checks (test assertions ≥2, files outside declared `files_touched`, scope creep > 3× `### Estimated lines`, TODO/FIXME/HACK added). Tier-aware severity (HARD/SOFT). HARD → `approved_pending_ci: false` + re-spawn cap `MAX_FORENSIC_RETRIES = 2` (3rd HARD → `BLOCKED_ERROR error_type: forensic_max_retries`); SOFT → `wave-summary.md § Forensic+ summary`; none → approved. Script crash (exit 1) → `BLOCKED_ERROR error_type: forensic_script_crash`.

Canonical doc: `references/forensic-plus-protocol.md`. Active changes in:
- `scripts/forensic-plus.py` (new, 188 lines)
- `templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl` step 8 → 8a/8b/8c/8d
- `references/wave-execution-protocol.md` step 8 expansion
- `references/wave-planner-algorithm.md` §10 flag rename: `skip_wave_reviewer` → `skip_cross_task_audit` (alias backward-compat until v3.9.0)
- `scripts/wave-planner-script.py` `render_wave_plan` emit annotation 1-task wave
- `references/4-block-contract-template.md` `### Estimated lines` optional (Check 3)
- `references/state-machine-schema.md` documents `error_type: forensic_max_retries|forensic_script_crash`
- 4 new drift detectors in `tests/unit/test_no_drift.py` (canonical doc exists, bootstrap runtime_refs, L2 cross-ref, wave-execution sub-steps)

## v3.6.0 — Preview loop (build-iterate visual)

Profile `app_web_frontend` + `fullstack` gain preview loop opt-in-by-default.
Canonical doc: `references/preview-loop-protocol.md`. Covers 10 consolidated decisions:

| # | Topic | Decision |
|---|---|---|
| 1 | Dev server lifecycle | Starts on stage 04 entry, killed on exit. PID in `.icm-main/.dev-server.pid` |
| 2 | Mock data | Tier-based: exp/tool=fixtures; dev=msw_faker; prod=msw_faker_zod |
| 3 | Feedback comm | Free combo + priming kickoff. Stop `ambiguous_feedback` |
| 4 | Current URL | CDP live (`--remote-debugging-port=9222 --user-data-dir=.icm-chrome-profile`) |
| 5 | Verification | `tsc` each Edit; lint+Playwright wave-end or on request |
| 6 | Storybook? | Vite/Next preview pages in `preview/` excluded from production build |
| 7 | Screenshot tool | No standardization; kickoff tip (Win+Shift+S, ShareX) |
| 8 | Iter cap | No cap. Human closes when OK |
| 9 | Design cascade | Threshold 5 affected components → confirm |
| 10 | Multi-screen | CDP default URL only; replay on request + auto-detect keywords |

Active changes in:
- `scripts/profile-merge.py:_preview_loop_config` emits `preview_loop` block in frontend/fullstack
- `scripts/bootstrap.py:detect_package_manager` (npm/pnpm/yarn/bun via lockfile)
- `scripts/recovery-wizard.py` new types `DEV_SERVER_ORPHAN` + `CDP_DISCONNECTED`
- `templates/.claude/scripts/launch-chrome-cdp.{bat,sh}` helpers
- `templates/workspace/stages/02_design/CONTEXT.md.tpl` step 7.6 (mock schema)
- `templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl` entry/exit hooks + new stop points

## v3.3.0 — patterns adopted from mattpocock/skills

8 patterns (Tier 1+2) + Design It Twice (T3 promoted). Canonical doc for each in `references/`:

| Pattern | Doc | Consuming stage(s) |
|---|---|---|
| Project root CLAUDE.md | `project-root-claude-md.md` | bootstrap + handoff (cross-session signaling) |
| AGENT-BRIEF template | `agent-brief-template.md` | 04 (lead → subagent context injection) |
| Ubiquitous Language | `context-format.md` | 01 (grilling) → 02+ (consume) |
| ADR 3-criteria gate | `adr-format.md` | 02 (decisions) |
| Diagnose 6-phase | `diagnose-protocol.md` | 05 fallback (CI fail) |
| HITL/AFK | `task-types-hitl-afk.md` | 02 → 03 → 04 |
| Triage state machine | `triage-state-machine.md` | 08 (feedback intake) |
| OUT-OF-SCOPE kb | `out-of-scope-kb.md` | 02 (iter>0) + 08 (wontfix) |
| Design It Twice | `design-it-twice.md` | 02 (core modules) |

## Outstanding items for next session

Items identified in previous sessions but not yet addressed. Ordered by priority.

### v3.10.0 deferrals (E2E reinforcement Tier 3)

- **Mutation testing oracle** — Stryker/mutmut opt-in via `mutation_oracle: true` in profile-effective. Targets critical paths (auth/payments/migrations). Sub-wave gate L4. Detects weak E2E even when green.
- **Full preview-loop suite at wave-end** — currently sample-check 1-click in v3.6.0; replace with full Playwright suite in profiles `preview_loop_enabled`.
- **L4 semantic cross-task coherence** — currently regex shared file/API (v3.9.0). Subagent fresh context comparing contracts cross-task.
- **profile-effective.yaml schema E2E section** — `e2e.user_facing_paths`, `e2e.e2e_command`, `e2e.e2e_suite_root`, `e2e.e2e_freshness_days` config'd per workspace. Currently hardcoded in `scripts/wave-planner-script.py:USER_FACING_PATHS_BY_PROFILE`.
- **agent-brief E2E section render** — `scripts/agent-brief-render.py` injects E2E section when `Requires E2E update: true`. Currently only forensic+ Check 8 enforces.

### v3.9.0 deferrals (Layered QA loop)

- **`akita-derive.py` post-hoc telemetry** — script extracts Akita-style metrics retroactively from legacy task reports. Stage 08 decision if telemetry is missing.

### v3.3.0 Tier 3 originals (still open)

- **Deep modules + deletion test** — architecture review tool for stage 02. Canonical doc inspired by [mattpocock/skills/engineering/improve-codebase-architecture]. Add `references/deep-modules.md` + checklist in `templates/workspace/stages/02_design/CONTEXT.md.tpl` + tests `test_deep_modules_doc.py`.
- **Git guardrails hook (production tier)** — `templates/.claude/hooks/block-dangerous-git.sh` that blocks `git push --force`, `reset --hard`, `clean -fd`, `branch -D`, `checkout .` via PreToolUse hook. Bootstrap adds conditionally when `tier=production`. Inspired by [mattpocock/skills/misc/git-guardrails-claude-code].
- **PreToolUse anti-`/init`** — hook that blocks `/init` invocation while an ICM workspace is active (G14 from the adversarial review of plan v3.3.0). Current mitigation is only a textual warning in the ICM region of the CLAUDE.md root.
- **Full zoom-out instruction in stage 00** — placeholder in L2 but missing a structured section guiding the agent when it encounters an unknown module (map callers + add candidate terms to the glossary pre-stage-01).

### Optional tests

- `tests/unit/test_context_md_template.py` — validate render of `_config/CONTEXT.md` template + frontmatter.
- `tests/unit/test_adr_gate.py` — property-based tests for the 3-criteria gate.
- `tests/unit/test_diagnose_doc.py` — smoke test parsability + 6 phases present.
- `tests/unit/test_triage_state_machine.py` — classification + valid transitions.
- `tests/integration/test_pre_commit_whitelist.bats` — bats CI-only test that `CLAUDE.md` root passes whitelist in workspace branch (G6).

(Redundant coverage — canonical docs already exercised via `runtime_refs` list in bootstrap. Tests above are explicit reinforcement.)

### Smoke manual end-to-end

Checklist updated in `references/smoke-manual-checklist.md` but execution on a real project not run in this session. Covers:

- Greenfield bootstrap (verifies all new files created)
- Brownfield WITH markers (content outside markers preserved byte-for-byte)
- Brownfield WITHOUT markers (inserts after `^# `)
- Multi-workspace (2 blocks in CLAUDE.md root)
- Handoff transitions update the owning workspace block
- Exit A of the last workspace activates the idle region
- Recovery wizard detects `CLAUDE_MD_ROOT_STALE` when L1 diverges
- Pre-commit hook allows CLAUDE.md root in workspace branch
- HITL task stays isolated in wave cap=1

### Original plan

Full plan at `~/.claude/plans/primeiro-fa-a-um-plano-sunny-glade.md` (Context, Redundancy assessment, Adversarial review G1-G17, design decisions, approved scope). Refers the next session's implementer for historical context.

### Branch v3-implementation

5 sequential commits (`74f050b` → `321ad3f`). Ready for PR or merge to main once smoke manual validates.
