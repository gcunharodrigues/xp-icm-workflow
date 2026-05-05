# E2E Coverage Protocol — Canonical (v3.10.0)

> **Version:** v3.10.0
> **Skill:** `xp-icm-workflow`
> **Consumer stages:** `03_wave_planner` (auto-flag), `04_implementation_waves` (forensic+ Check 8 + L4 wave gate), `05_verification` (audit suite freshness)
> **Purpose:** canonical document for the E2E reinforcement in v3.10.0. Defines user-facing task detection, `requires_e2e_update` flag in the 4-block schema, forensic+ Check 8 (user-journey coverage), universal L4 wave gate for tier dev/prod, and Stage 05 e2e suite freshness audit.

## Summary (1 paragraph)

ICM v3.9.0 ensures L1+L2+L3+L4 QA layers per task, but E2E coverage was profile-conditional (only frontend/fullstack tier dev/prod in the L4 wave gate). v3.10.0 reinforces E2E on 4 fronts: (1) wave-planner detects user-facing paths and auto-emits `requires_e2e_update: true` on the task; (2) forensic+ Check 8 validates that a flagged task has ≥1 file in `e2e/`/`cypress/`/`playwright/`/`tests/e2e/` in the diff; (3) the L4 wave gate runs the E2E suite **universally** in tier dev/prod (profile-independent); (4) Stage 05 audits that the e2e suite exists + last run < 7 days. **Process coverage** (cross-module, cross-feature) is no longer delegated to the project CI and instead becomes an ICM gate.

## Why the reinforcement

Documented ICM v3.9.0 gaps:

| Gap | Risk |
|-----|------|
| Tracer-first (stage 04 step 4.1) covers the isolated task, not regression of an older feature | Wave N silently breaks a flow from wave 1 |
| L4 wave gate e2e only `frontend/fullstack` tier dev/prod | Backend tier dev has no ICM-imposed e2e |
| Stage 05 trusts project CI to run e2e — no ICM audit | Broken/stale e2e suite goes unnoticed |
| User-facing tasks may merge without a process test | False coverage |

v3.10.0 closes gaps via 4 structural changes without modifying the L1-L4 layer model.

## User-facing path detection

Wave-planner identifies tasks that touch user-facing paths via lookup in `_config/profile-effective.yaml:user_facing_paths` (configured per profile, sensible defaults below).

### Defaults per profile

| Profile | user_facing_paths default |
|---------|--------------------------|
| `app_web_backend` | `["routes/", "controllers/", "handlers/", "endpoints/", "api/", "graphql/"]` |
| `app_web_frontend` | `["pages/", "views/", "app/", "components/pages/", "src/routes/"]` |
| `fullstack` | union of backend + frontend |
| `cli_tool` | `["cmd/", "cli/", "commands/"]` |
| `agent_ia` | `["prompts/", "agents/", "tools/"]` |
| `framework_library` | `["api/", "exports/"]` (public surface) |
| `dashboard` | `["pages/", "views/", "dashboards/"]` |
| `data_analysis` | (empty — typically notebook-based, e2e not applicable) |
| `ml_project` | `["pipelines/", "inference/"]` |
| `technical_article` | (empty — doc-only) |
| `experiment` | (empty — POC, e2e opt-in) |

### Wave-planner emit logic

For each task `t` in plan.md:
```
if any(declared_path matches user_facing_paths)
   for declared_path in t.files_touched:
   t.metadata['requires_e2e_update'] = True
   wave-plan.md includes annotation
```

Manual override via plan.md task: `**E2E:** skip (rationale)` disables the check (stage 05 audit requires a rationale).

## 4-block schema extension

Tasks emitted by wave-planner with the flag gain an optional metadata field:

```markdown
## Task <slug>: <title>

### WHAT / HOW / OUT OF SCOPE / VALIDATION
<see 4-block-contract-template.md>

### Files touched
- src/routes/checkout.ts
- tests/checkout.test.ts

### Requires E2E update
- true   <!-- wave-planner emits when files_touched matches user_facing_paths -->

### E2E paths expected (optional)
- e2e/checkout-flow.spec.ts
- cypress/integration/checkout.cy.ts
```

A subagent reading a flagged task MUST add/update ≥1 file in an e2e directory (see pattern detection below).

## Forensic+ Check 8 — user-journey coverage

Added to `references/forensic-plus-protocol.md` § 7 checks.

Trigger: task has `Requires E2E update: true` in its metadata (OR `**E2E:** skip` is absent).

Detection:
```python
e2e_dirs = ["e2e/", "cypress/", "playwright/", "tests/e2e/", "tests/integration/", "test/e2e/"]
e2e_files_in_diff = [f for f in diff if any(d in f for d in e2e_dirs)]
if requires_e2e_update and not e2e_files_in_diff:
    violation
```

Severity:

| Tier | Severity |
|------|----------|
| experimental | SOFT |
| tool | SOFT |
| development | HARD |
| production | HARD |

Skip cases:
- Task has `**E2E:** skip` declared (skip silently — rationale audited at Stage 05).
- Task `Conventions extras: doc-only` or `config-only`.
- Task `type: HITL`.

Re-spawn brief (HARD violation):
```
Task declared `Requires E2E update: true` but diff does not touch e2e/cypress/playwright.
Add ≥1 test covering the end-to-end flow of the modified user-facing path.
Expected paths: e2e/<feature>.spec.ts, cypress/integration/<feature>.cy.ts.
If the change does not justify e2e (internal refactor with no behavior change),
add `**E2E:** skip - internal refactor, behavior preserved` to the 4-block.
```

## L4 wave gate — universal tier dev/prod

Stage 04 step 11 (L4 wave gate, formerly wave gate CI global) gains a sub-gate:

```
11a. CI global green (always — all tiers).
11b. E2E suite green (tier dev/prod, all profiles with non-empty user_facing_paths).
11c. Cross-task coherence check (production AND ≥2 tasks shared file/API).
```

E2E command lookup in `_config/profile-effective.yaml:e2e_command` (defaults: `npm run test:e2e` / `pnpm test:e2e` / `pytest tests/e2e/` / etc).

Failure at 11b → `BLOCKED_ERROR error_type: e2e_suite_failed` → diagnose protocol → rollback if inconclusive → human gate A/B/C (same machine as current step 10 CI global).

Skip 11b when:
- Profile with `user_facing_paths: []` (data_analysis, technical_article, experiment).
- `e2e_command` absent in profile-effective + tier exp/tool (warning, not BLOCKED).

## Stage 05 — audit e2e freshness

New sub-step `4.7 Audit E2E suite`:

1. Locate e2e suite via `_config/profile-effective.yaml:e2e_suite_root` (default `e2e/` or `cypress/` or `tests/e2e/`).
2. Verify suite exists and has ≥1 spec file.
3. Verify last modification of specs in git: `git log -1 --format=%ct -- <e2e_suite_root>`. Stale = > 7 days AND wave-summary shows ≥1 user-facing task delivered in the current wave.
4. Audit CI report (step 4) extracted e2e result — green OR yellow (CONDITIONAL) accepted; red = FAIL.

Failures:
- `e2e_suite_required: true` (tier dev/prod with non-empty user_facing_paths) AND suite absent → FAIL → `BLOCKED_ERROR error_type: e2e_suite_missing`.
- Stale suite + user-facing tasks delivered → FAIL → `BLOCKED_ERROR error_type: e2e_suite_stale`.
- Tasks with `**E2E:** skip` but without a rationale → FAIL → `BLOCKED_ERROR error_type: e2e_skip_unjustified`.

## Recovery wizard — E2E_SUITE_STALE

New type in `references/recovery-wizard.md`:

| Detector | Trigger | Action |
|----------|---------|--------|
| `E2E_SUITE_STALE` | `_config/profile-effective.yaml:e2e_suite_required: true` AND `git log -1 --format=%ct -- <e2e_suite_root>` > 7 days AND L1 history shows ≥1 recent user-facing wave | Warning + suggests re-running suite OR adding an `update-e2e-coverage` task in a new wave |

Auto-fix: none (human decides). Alert only.

## profile-effective.yaml — schema additions

```yaml
# Existing (v3.9.0):
preview_loop:
  preview_loop_enabled: true
  ...

# New (v3.10.0):
e2e:
  e2e_suite_required: true | false   # default depends on profile×tier
  e2e_suite_root: "e2e/" | "cypress/" | "tests/e2e/" | null
  e2e_command: "npm run test:e2e" | "pytest tests/e2e/" | null
  e2e_freshness_days: 7   # stale threshold
  user_facing_paths:
    - "routes/"
    - "controllers/"
    # ...
```

`profile-merge.py` injects sensible defaults per profile (see table in §User-facing path detection).

## AGENT-BRIEF — E2E section

When a task has `Requires E2E update: true`, brief render in `agent-brief-render.py` injects a section:

```markdown
**E2E expected paths:**
- e2e/<feature-slug>.spec.ts
- cypress/integration/<feature-slug>.cy.ts

**E2E pattern guidance:**
- Tracer-first: 1 test covering the end-to-end golden path (user → app → DB → response).
- Anti-mock policy: e2e uses the real app (no msw/jest.mock). Boundary mocks accepted only for paid external services (Stripe, SendGrid).
- Coverage: ≥1 happy path + ≥1 edge case (error state, validation fail, auth fail).
```

## New stop point — `e2e_skip_request`

Added to `references/stop-points-canonical.md`:

| ID | Trigger | Tier calibration | Menu |
|----|---------|-----------------|------|
| `e2e_skip_request` | Subagent argues user-facing task does not need e2e (cosmetic refactor, etc) | exp/tool: warning; dev/prod: hard | A: skip accepted (record rationale in plan.md) / B: force e2e anyway / C: split task (refactor + feature in separate waves) |

## Edge cases

| EC | Scenario | Behavior |
|----|----------|----------|
| EC1 | Profile `user_facing_paths: []` (data_analysis) — task does NOT receive flag | Check 8 skip; L4 e2e gate skip; Stage 05 audit skip |
| EC2 | User-facing task + tier experimental — Check 8 SOFT, L4 skip | Warning in wave-summary; merge proceeds |
| EC3 | User-facing task + Conventions extras: doc-only | Skip silently (doc does not justify e2e) |
| EC4 | E2E suite broken by flaky test (unrelated to the wave) | L4 fails → diagnose-protocol identifies flaky → human gate A/B/C |
| EC5 | e2e suite runs > 10min (slow CI gate) | profile-effective `e2e_timeout_minutes: 15` allows override |
| EC6 | Multi-language repo (frontend TS + backend Go) | `user_facing_paths` covers both prefixes; e2e_command may be a multi-step shell script |
| EC7 | Wave 1 task 1 (scaffold) with no user-facing feature yet | wave-planner does not emit flag; first global tracer becomes an explicit "setup-e2e-suite" task in the plan |
| EC8 | Task with `**E2E:** skip` WITHOUT rationale after `-` | Stage 05 audit `e2e_skip_unjustified` FAIL |

## Cross-references

- Forensic+ canonical: `references/forensic-plus-protocol.md` (Check 8 §)
- 4-block schema: `references/4-block-contract-template.md` (Requires E2E update field)
- Wave-planner algorithm: `references/wave-planner-algorithm.md` (auto-flag detection)
- Stop points: `references/stop-points-canonical.md` (`e2e_skip_request`)
- Stage 04 runtime: `templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl`
- Stage 05 runtime: `templates/workspace/stages/05_verification/CONTEXT.md.tpl`
- Recovery wizard: `references/recovery-wizard.md` (`E2E_SUITE_STALE`)
- State machine: `references/state-machine-schema.md` (error_types `e2e_suite_failed`, `e2e_suite_missing`, `e2e_suite_stale`, `e2e_skip_unjustified`)
- Mocking guidelines: `references/mocking-guidelines.md` (anti-mock policy in e2e — boundary mocks only)
