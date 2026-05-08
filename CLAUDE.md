# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Language

All documents and code must be written in English (en-US). This includes templates, references, scripts, comments, commit messages, and inline documentation. No exceptions.

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
- Tests must pass before merge (`188+/188+ tests` baseline from v4.0.0 core suite).
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

### v4.0 5-Stage Pipeline

`00:recon → 01:discovery → 02:design+plan → 04:implementation-waves → 08:feedback-intake`

Stages 03 (wave_planner), 05 (verification), 06 (review), 07 (merge) deprecated — merged into 02 and 04. Stage 02 runs wave-planner inline. Stage 04 gates include CI, E2E, and merge.

Stage 04: each wave = 1 lead session; subagents via manual worktrees at `.claude/worktrees/icm-wave-<NNN>-<N>/<slug>/` (`Agent(isolation=None, cwd=<worktree>)`), branch `wave-<NNN>-<N>/<task-slug>` from `BASE_BRANCH`. Merge via `.icm-main/` — project root never switches off workspace branch. Canonical docs: `references/wave-execution-protocol.md`, `references/isolation-protocol.md`.

### v4.0 L1 State Machine (3 statuses)

`IN_PROGRESS` | `BLOCKED` (+ mandatory `block_reason`: `human_gate`, `stop_point`, `error`, `hitl`, `lead_resolution`) | `COMPLETED`

v3 statuses (`COMPLETED_AWAITING_HUMAN`, `BLOCKED_STOP_POINT`, `BLOCKED_ERROR`, `BLOCKED_HITL`, `LEAD_RESOLUTION_IN_PROGRESS`) absorbed. Schema: `references/state-machine-schema.md`.

### Key Scripts (`/scripts/`)

- **bootstrap.py** — One-shot workspace creation (folder structure, L0/L1/L2 files, git branch, pre-commit hooks, atomic commit, project-root CLAUDE.md render)
- **profile-merge.py** — Merges 11 profiles × 4 tiers → deterministic effective hash (sha256)
- **handoff.py** — Renders `_kickoff.md` (L4) + manages `<project_root>/CLAUDE.md` ICM region (update/remove/deactivate)
- **wave-planner-script.py** — Parses `plan.md` → DAG → cycle detection (DFS 3-color) → topological sort (Kahn) → sub-wave subdivision (HITL tasks isolated cap=1)
- **wave-planner-llm-review.py** — Optional LLM review subagent for wave plan validation
- **agent-brief-render.py** — Generates AGENT-BRIEF for stage 04 subagent dispatch (parses plan.md task → behavioral brief with acceptance criteria)
- **recovery-wizard.py** — Detects/repairs 7 workspace inconsistency types
- **validate_state.py** — L1 YAML validation (v4: 3 statuses + block_reason)
- **lessons-match.py** — Extracts top-3 relevant lessons for current task
- **forensic-plus.py** — 8 deterministic git-only checks per task (0 token QA layer)
- **lead-diagnose.py** — Jaccard cluster + catastrophic detector + RETRY/VOID recommendation
- **pick-model.py** (deprecated v4.0) — Model selection moved to inline heuristic in agent-brief-render.py
- **render-critic-prompt.py** — Generates L3 orthogonal critic prompt
- **runtime-registry.py / runtime-status.py / icm-cleanup.py** — Dev server lifecycle + workspace cleanup

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
- `references/session-handoff-protocol.md` — 1-stage-1-session flow (v4 simplified section)
- `references/state-machine-schema.md` — L1 YAML spec (v4: 3 statuses + block_reason)
- `references/wave-execution-protocol.md` — 5-phase stage 04 pipeline
- `references/isolation-protocol.md` — Single manual worktree path, merge via .icm-main
- `references/v4-qa-stack.md` — Consolidated forensic+, critic, e2e, lead-resolution
- `references/lead-resolution-protocol.md` — RETRY/VOID (v4 simplified)
- `references/subagent-protocol.md` — Subagent orchestration, wave-reviewer, coordination
- `references/agent-brief-template.md` — AGENT-BRIEF format + isolation rules
- `references/wave-planner-algorithm.md` — DAG construction details
- `references/stop-points-canonical.md` — 15 stop points + tier thresholds
- `references/changelog.md` — Full version history
- `references/maintainer-checklist.md` — How to modify the skill

## Tests

188+ core tests passing (v4.0.0 baseline). `tests/unit/` uses pytest + Hypothesis (property-based). `tests/integration/` and `tests/e2e/` use bats (CI-only, Ubuntu). Mock LLM responses in `tests/mocks/llm_review_responses/`. Fixtures in `tests/fixtures/`.

Playwright plugin disabled in `pyproject.toml`.

Key test files:
- `test_no_drift.py` — 21 drift detectors (version, profile count, status enum, cross-refs, CRLF)
- `test_subagent_isolation_rules.py` — verifies CWD/write consistency across 6 governance files
- `test_lead_diagnose.py` — 21 cases (Jaccard, catastrophic detection, RETRY/VOID)
- `test_forensic_plus.py` — 41 cases (8 checks, tier-aware severity)
- `test_l2_templates.py` — validates all active stage templates

## v4.0.0 — Simplified workflow (2026-05-06)

**Stage collapse (9→5):** 03,05,06,07 deprecated. Merged into 02 and 04. Pipeline: 00→01→02→04→08.
**Status simplification (7→3):** `IN_PROGRESS`, `BLOCKED` (+ `block_reason`), `COMPLETED`.
**Subagent isolation fix:** CWD corrected to worktree root across all governance files. Task report lead-written from Agent tool output. Subagent never writes to workspace branch.
**Lead-resolution:** B1/B3/B4 → RETRY/VOID.
**Model selection:** pick-model.py deprecated; inline heuristic in agent-brief-render.py.
**Handoff:** L1 `prev_outputs`/`pending` replace `_kickoff.md` as primary mechanism.
**QA stack:** `references/v4-qa-stack.md` consolidates forensic+, critic, e2e, lead-resolution.
**Stage 08 /init ordering:** cleanup before /init, persist output to base branch.

Key docs: `v4-qa-stack.md`, `lead-resolution-protocol.md` (RETRY/VOID), `session-handoff-protocol.md` (v4 simplified section).

## v3.x Legacy (condensed)

v3.3.0: 8 patterns from mattpocock/skills (AGENT-BRIEF, ADR gate, Ubiquitous Language, Diagnose, HITL/AFK, Triage, OUT-OF-SCOPE, Design It Twice).
v3.6.0: Preview loop (build-iterate visual) for frontend/fullstack profiles.
v3.8.0: Forensic+ wave reviewer — 4 deterministic git-only checks per task.
v3.9.0: Layered QA loop — L1 writer (vertical TDD), L2 forensic+ extended (7 checks), L3 orthogonal critic. Lead-resolution B1/B3/B4. pick-model.py.
v3.10.0: E2E coverage reinforcement — Check 8, wave-planner E2E detection, L4 wave gate.
v3.12.1: Script CLI contract hardening, pt-BR cleanup. 951 tests.

Full history: `references/changelog.md`.

## Outstanding items

- Mutation testing oracle, full preview-loop suite at wave-end
- Deep modules + deletion test, Git guardrails hook (production tier)
- Full zoom-out instruction in stage 00
- Smoke manual end-to-end (checklist in `references/smoke-manual-checklist.md`)
