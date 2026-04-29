# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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

Stage 04 exception: each wave = 1 lead session; subagents spawned via `Agent` tool (no worktrees), branch setup mandatory.

### Key Scripts (`/scripts/`)

- **bootstrap.py** — One-shot workspace creation (folder structure, L0/L1/L2 files, git branch, pre-commit hooks, atomic commit)
- **profile-merge.py** — Merges 10 profiles × 4 tiers → deterministic effective hash (sha256)
- **handoff.py** — Renders `_kickoff.md` (L4) for session transitions
- **wave-planner-script.py** — Parses `plan.md` → DAG → cycle detection (DFS 3-color) → topological sort (Kahn) → sub-wave subdivision
- **wave-planner-llm-review.py** — Optional LLM review subagent for wave plan validation
- **recovery-wizard.py** — Detects/repairs 6 workspace inconsistency types (HASH_MISMATCH, MISSING_COMMIT, MISSING_OUTPUT, STALE_IN_PROGRESS, BRANCH_MISSING)
- **validate_state.py** — L1 YAML validation against state-machine-schema
- **lessons-match.py** — Extracts top-3 relevant lessons for current task

### Profile System

10 profiles (e.g., `app_web_backend`, `ml_project`, `agent_ia`) × 4 tiers (`experimental`, `tool`, `development`, `production`). Config keys: `stages_skipped`, `tdd_required`, `security_gate`, `stop_points_calibration`. See `templates/_config/profile-matrix.md`.

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

## Tests

502 tests, 83% coverage. `tests/unit/` uses pytest + Hypothesis (property-based). `tests/integration/` and `tests/e2e/` use bats (CI-only, Ubuntu). Mock LLM responses in `tests/mocks/llm_review_responses/`. Fixtures in `tests/fixtures/`.

Playwright plugin disabled in `pyproject.toml` (workaround — leave it).
