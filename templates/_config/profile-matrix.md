# Canonical profile × tier matrix

This is the **human-readable source** of the matrix that `scripts/profile-merge.py` applies during the
profile + tier (+ override) merge. The script has a hardcoded copy for
performance/atomicity — in case of divergence, the script is the operational source of truth;
this document exists for review and onboarding.

## Canonical profiles (11)

| Profile             | Short description                                                        |
|---------------------|--------------------------------------------------------------------------|
| `app_web_backend`   | HTTP backend API/service (FastAPI, Django, Express…)                     |
| `app_web_frontend`  | Browser SPA/SSR (Next.js, SvelteKit, Remix…)                             |
| `fullstack`         | Backend + frontend coexist in the same repo (Next.js+API routes, T3, Remix+Prisma, Django+React colocated). For monorepo apps/web+apps/api split, prefer 2 workspaces. |
| `dashboard`         | Analytical dashboard (Streamlit, Dash, Looker, Superset…)                |
| `data_analysis`     | One-off analysis, report-oriented notebook                               |
| `ml_project`        | Full ML pipeline (training, eval, serving)                               |
| `agent_ia`          | LLM agent/orchestrator with tools (skills, MCP, scripts)                 |
| `cli_tool`          | Standalone command-line tool                                             |
| `framework_library` | Reusable library/framework (published to a registry)                     |
| `technical_article` | Long-form technical article with embedded code                           |
| `experiment`        | Throwaway spike/POC or quick benchmark                                   |

## Canonical tiers (4)

| Tier            | When to use                                                              |
|-----------------|--------------------------------------------------------------------------|
| `experimental`  | Spike/POC; code is likely throwaway                                      |
| `tool`          | Internal tool used recurrently but not critical                          |
| `development`   | System under construction that will enter real use                       |
| `production`    | System in production with real users and/or sensitive data               |

## Defaults per tier (no profile override)

| Key                         | experimental         | tool                  | development           | production                  |
|-----------------------------|----------------------|-----------------------|-----------------------|-----------------------------|
| `tdd_required`              | False (optional)     | False (recommended)   | True (required)       | True (required)             |
| `security_gate`             | False                | False                 | True (on)             | True (on+LGPD)              |
| `tech_debt_tracking`        | False                | True                  | True                  | True                        |
| `peer_review_required`      | False                | False                 | False                 | True                        |
| `cap_subagents_per_wave`    | 2                    | 3                     | 5                     | 5                           |
| `stop_points_calibration.item_5` (paid service) | warning, R$ 50  | hard, R$ 200    | hard, R$ 500          | hard, R$ 1000               |
| `stop_points_calibration.item_7` (over-eng.)    | warning         | warning         | hard                  | hard                        |
| `stop_points_calibration.item_8` (PII/LGPD)     | warning         | hard            | hard                  | hard+DPO                    |
| `stages_skipped` (default)  | `[]`                 | `[]`                  | `[]`                  | `[]`                        |
| `test_specs.coverage_threshold` | 0 (no minimum)  | 60                    | 80                    | 90                          |

## test_specs per profile

The `test_specs` field is computed by `scripts/profile-merge.py` based on profile + tier.
**It is not in the list of allowed `overrides`** — it is derived, not configurable via `.icm-profile.local.yaml`.

### `test_specs` structure

```yaml
test_specs:
  test_types_required: []         # list: unit, integration, e2e, component, eval, pipeline, model_eval
  coverage_threshold: 0           # int % (lines/branches); 0 = no minimum
  test_location: "tests/"         # test file location convention
  http_integration: false         # backend: must test real HTTP endpoints
  db_integration: false           # backend: must test against real/test DB
  component_testing: false        # frontend: must use component testing (RTL/etc)
  e2e_required: false             # frontend: E2E mandatory
  visual_regression: false        # frontend: visual regression (prod only)
  a11y_testing: false             # frontend: accessibility (axe)
  eval_strategy: null             # agent_ia: "golden_output_similarity" | null
  eval_threshold: null            # agent_ia: float 0-1 | null
  deterministic_tools_only: false # agent_ia: only tool calls are unit-testable
  pipeline_testing: false         # ml_project: tests data pipeline
  model_regression: false         # ml_project: model performance regression
```

### test_specs per profile (canonical values)

| Profile | test_types_required | Notes |
|---|---|---|
| `app_web_backend` | `[unit, integration]` | `http_integration: True`, `db_integration: True` |
| `app_web_frontend` | `[unit, component, e2e]` | `component_testing: True`, `e2e_required: True` (dev+prod), `visual_regression: True` (prod), `a11y_testing: True` (dev+prod), `test_location: src/` (co-located), `design_system_required: True` |
| `fullstack` | `[unit, integration, component, e2e]` | Superset backend+frontend: `http_integration: True`, `db_integration: True`, `component_testing: True`, `e2e_required: True` (dev+prod), `visual_regression: True` (prod), `a11y_testing: True` (dev+prod), `design_system_required: True`, `test_location: tests/` |
| `dashboard` | `[unit, integration]` | `http_integration: True`, similar to backend |
| `data_analysis` | `[unit]` | Notebooks: test transformation functions; no mandatory integration |
| `ml_project` | `[unit, pipeline, model_eval]` | `pipeline_testing: True`, `model_regression: True` (dev+prod) |
| `agent_ia` | `[unit_tools, integration_prompt, eval]` | `eval_strategy: golden_output_similarity`, `deterministic_tools_only: True`, `eval_threshold: 0.85` (dev+prod) |
| `cli_tool` | `[unit, integration]` | integration = subprocess testing, stdin/stdout capture |
| `framework_library` | `[unit, integration]` | coverage_threshold +10% (libraries require higher coverage as they are reused) |
| `technical_article` | `[unit]` (if code is present) | Article without executable code: `test_types_required: []` |
| `experiment` | `[]` | No test requirements — throwaway spike |

## Profile-specific overrides (applied on top of tier defaults)

### `experiment`

- `stages_skipped` = `["03", "05", "06", "08"]` in **all** tiers.
- Rationale: throwaway spike skips tests (03), formal architecture (05),
  documentation (06), and operationalization (08).

### `technical_article`

- `stages_skipped = ["03"]` (article does not run CI/test automation; tier `experimental` inherits `["03", "05", "06", "08"]` with `03` already included — deduplicated automatically by `profile-merge.py`).
- `cap_subagents_per_wave` = 5 (long article can parallelize review).

### `framework_library`

- `cap_subagents_per_wave` = 3 (framework requires design cohesion; lower cap).

### `ml_project`

- `cap_subagents_per_wave` = 3 (ML pipelines require continuity of
  hyperparameters and data; high parallelism fragments understanding).

### `app_web_backend`, `app_web_frontend` and `fullstack`

- `security_gate` = True in any tier ≠ `experimental`. A web app exposed to the
  network always passes through a security gate, even on `tool`.

### `app_web_frontend` and `fullstack`

- `design_system_required` = True (all tiers). Stage 02 design creates/updates
  `<project_root>/.icm-main/DESIGN.md` (Google Stitch DESIGN.md spec format).
  Canonical doc: `references/design-system.md`. Subagents in stage 04 receive
  DESIGN.md on channel 2 when the task has frontend files.
- **Preview loop config (v3.6.0):** additional flags derived by
  `profile-merge.py`, feeding the build-iterate visual cycle described in
  `references/preview-loop-protocol.md`:

  | Key                         | Value per tier                                                                                       |
  |-----------------------------|------------------------------------------------------------------------------------------------------|
  | `preview_loop_enabled`      | `True` in all tiers                                                                                  |
  | `mock_data_strategy`        | experimental → `fixtures` · tool → `fixtures` · development → `msw_faker` · production → `msw_faker_zod` |
  | `cdp_live_enabled`          | `True` in all tiers (opt-out via override `cdp_live_enabled: false`)                                 |
  | `visual_iter_cap`           | `null` in all tiers (no cap — human closes when OK)                                                  |
  | `design_cascade_threshold`  | `5` in all tiers (tunable via override)                                                              |
  | `preview_pages_path`        | `preview/` (convention, not configurable)                                                            |

  Applicable defaults: dev server starts at stage 04 entry + stops at exit
  (`scripts/bootstrap.py` detects package manager via lockfile);
  Chrome CDP via `templates/.claude/scripts/launch-chrome-cdp.{bat,sh}`;
  preview pages at `preview/<component>/page.tsx` excluded from production build.
  Recovery wizard covers `DEV_SERVER_ORPHAN` + `CDP_DISCONNECTED`.

## Local override: `.icm-profile.local.yaml`

Full schema:

```yaml
extends: app_web_backend         # required; ∈ canonical profiles
tier: development                # required; ∈ canonical tiers
overrides:                       # optional; dict with keys from the matrix
  cap_subagents_per_wave: 3
  stages_skipped: ["08"]
custom_stop_points:              # optional; D3 — additional project-specific stops
  - id: custom_1
    description: "project-specific check"
    threshold:
      experimental: warning
      development: hard
revisit_after: "2026-08-01"      # optional; ISO 8601 (Q16 A')
confirm_unsafe: false            # default false; true required to disable critical gates (Q16 A'')
```

### Allowed `overrides` keys

Only the 7 canonical matrix keys:

- `stages_skipped`
- `tdd_required`
- `security_gate`
- `tech_debt_tracking`
- `peer_review_required`
- `cap_subagents_per_wave`
- `stop_points_calibration`

Any other key in `overrides` → validation error.

### Guard-rail: `confirm_unsafe`

An override that **disables** (from True → False) any of these three gates requires
`confirm_unsafe: true` in the file:

- `tdd_required`
- `security_gate`
- `peer_review_required`

Without `confirm_unsafe: true` → `ProfileMergeError("unsafe override requires confirm_unsafe: true")`.

Enabling gates (False → True) is always safe and does not require confirmation.

### `custom_stop_points` (D3)

Optional list of additional project-specific stop points. Each item requires:

- `id` — non-empty string.
- `description` — non-empty string.
- `threshold` — non-empty dict whose keys ∈ canonical tiers and whose values
  represent the mode (`warning` / `hard` / etc.) per tier.

### `revisit_after` (Q16 A')

Strict ISO 8601: `YYYY-MM-DD` or `YYYY-MM-DDTHH:MM:SS`. Other formats
(`august/2026`, `2026-08`, etc.) → error.

## Deterministic hash

`scripts/profile-merge.py` computes SHA256 hex (64 chars) of the effective profile
serialized in YAML with `sort_keys=True`, `default_flow_style=False`,
`allow_unicode=True`. Same input → same hash always. Useful for recording the project
state and detecting drift in `.icm-profile.local.yaml`.
