# Wave Planner Algorithm — Canonical Spec

> **Version:** v3.0.0-beta5
> **Skill:** `xp-icm-workflow`
> **Stage:** `03 wave_planner`
> **Path resolution:** paths `scripts/` in this document refer to `<SKILL_DIR>/scripts/`, where `SKILL_DIR` is defined in L0 (`CLAUDE.md`).
> **Purpose:** canonical document of the Wave Planner algorithm. Formalizes the deterministic baseline pipeline (Session 2 of stage 03, already implemented in `<SKILL_DIR>/scripts/wave-planner-script.py`) **+** the LLM review subagent (R2.4) that validates the DAG before the human gate.

> **Origin decisions:** Q7 (DAG by footprint + isolated branches), Q17 (cap by tier/profile), Q18 (LLM review ALWAYS), E3 (sub-waves), F2 (skip wave-reviewer 1-task), R2.4 (LLM review subagent via Task tool).

> **Status:** the deterministic pipeline is validated by `tests/unit/test_wave_planner_dag.py` (33 tests green). LLM review subagent is wave 4 of the rewrite; tests with mocks in `tests/mocks/llm_review_responses/`.

---

## 1. Inputs and outputs

| Layer | Input | Output |
|---|---|---|
| Deterministic | `stages/02_design/output/plan.md` + `tier` + `profile` + `workspace_id` | `stages/03_wave_planner/output/wave-plan.md` (draft) + `ambiguities-resolved.md` |
| LLM review | wave-plan.md draft + plan.md + ambiguities | wave-plan.md final + `llm_review_findings.md` |

Deterministic CLI:

```bash
python <SKILL_DIR>/scripts/wave-planner-script.py \
  --plan stages/02_design/output/plan.md \
  --tier development \
  --profile app_web_backend \
  --workspace 042-feat-auth \
  --output stages/03_wave_planner/output/wave-plan.md
```

Stdout: `total_tasks=N total_waves=M total_sub_waves=K ambiguities=A`. Exit 0 ok; exit 1 error (cycle, schema, duplicate slug).

---

## 2. Task schema in plan.md

Each task is parsed from `plan.md` according to `references/4-block-contract-template.md`. Extracts:

| Field | Source in plan.md | Use in Wave Planner |
|---|---|---|
| `slug` | header `## Task <slug>:` (kebab-case) | DAG node |
| `files_touched` | section `### Files touched` | edge by conflict; mandatory test file validation |
| `depends_on` | section `### Depends on` (optional) | explicit edge |
| `peer_review` | `### Requires_peer_review` | metadata (does not affect DAG) |
| `adrs` | `### ADRs aplicáveis` | metadata |
| `conventions_extras` | `### Conventions extras` | metadata; `doc-only`/`config-only` exempts from test file rule |

**Parsing rules:**
- Duplicate slug → error.
- Slug outside kebab-case → error.
- Dep pointing to nonexistent slug → error.
- **Mandatory test file rule:** every task whose `files_touched` contains files matching code patterns (`src/`, `app/`, `lib/`, `pkg/`, extensions `.py`, `.ts`, `.js`, `.go`, `.rb`, `.rs`, `.java`, `.kt`, `.cs`) **must** declare ≥1 corresponding test file (recognized patterns: `tests/`, `test_*.py`, `*_test.py`, `*.test.ts`, `*.spec.ts`, `*.test.js`, `*.spec.js`, `spec/`, `__tests__/`). Violation → `BLOCKED_ERROR` with message `test file missing for task <slug>`. Exception: `Conventions extras` contains `doc-only` or `config-only` → automatic exemption.

---

## 3. DAG construction

Plan §4.3:

- **Node:** a task.
- **Directed edge `(t1, t2)`** if:
  - `t2.depends_on` cites `t1` (explicit dep), **OR**
  - `files_touched(t1) ∩ files_touched(t2) ≠ ∅` AND t1 appears before t2 in `plan.md` (conflict serializes by order of appearance).

Footprint conflict forces tasks into different waves — does not override human order.

---

## 4. Cycle detection

DFS 3-colors (white/gray/black). On touching a GRAY node in the stack → cycle.

Message: `cycle detected: t1 -> t2 -> t3 -> t1`. Exit 1.

---

## 5. Topological sort into waves (Kahn by levels)

Level N = nodes with in-degree zero in the remaining graph. After emitting wave-N, removes edges and recalculates. Ties within the level resolved by order of appearance in `plan.md` (deterministic).

---

## 6. Cap by tier/profile

Effective cap = `min(TIER_CAP[tier], PROFILE_CAP_OVERRIDE[profile])`.

| Tier | Base cap |
|---|---|
| `experimental` | 2 |
| `tool` | 3 |
| `development` | 5 |
| `production` | 5 |

Profile overrides:

| Profile | Override |
|---|---|
| `framework_library` | 3 |
| `ml_project` | 3 |
| `technical_article` | 5 |

Example: `tier=production` + `profile=ml_project` → cap = `min(5, 3) = 3`.

---

## 7. Sub-wave subdivision (E3)

When `len(wave-N) > cap`, subdivides into `wave-N.a, wave-N.b, ...`, each with up to `cap` tasks. Sub-wave `(k+1)` only starts after `(k)` is merged into `base_branch` + CI green.

Schema `wave-plan.md` gains field `sub_wave_id` (letters a-z; fallback `x<idx>` if >26).

Branch naming: `wave-<workspace>-N.a/<task-slug>`, `wave-<workspace>-N.b/<task-slug>`, etc.

---

## 8. Footprint ambiguity detection

Heuristic: pairs of tasks that touch the **same directory** but do **not share an exact file** (dir-overlap without file-overlap).

Example: `task-a` touches `src/auth/middleware.ts`, `task-b` touches `src/auth/`. The deterministic algorithm does **not** create an edge (no exact intersection) **but** records the ambiguity in `ambiguities-resolved.md` for LLM review to confirm separation.

Deterministic applies fallback rule: serializes by order of appearance (same rule as file conflict). LLM review may confirm/contest.

---

## 9. LLM review subagent (R2.4)

After generating `wave-plan.md` draft + `ambiguities-resolved.md`, the Wave Planner spawns a dedicated subagent via Task tool with a fixed prompt:

```
You are a wave-planner-reviewer. You receive the DAG draft + plan.md + ambiguities.

Task: read tasks + graph + ambiguities. Verify if there are:
1. Ambiguous footprints unresolved by the deterministic algorithm
2. Undeclared implicit deps (e.g.: task B needs the schema migrated by task A
   but does not declare the dep)
3. Sub-waves that could re-parallelize (cap reduced by mistake)

Structured JSON output:
{
  "verdict": "APPROVE" | "PROPOSE_CHANGES",
  "issues": [
    {"type": "implicit_dep", "from": "task-a", "to": "task-b", "reason": "..."},
    {"type": "ambiguous_footprint", "tasks": ["task-x", "task-y"], "suggestion": "..."}
  ],
  "proposed_dag_changes": [...]   // only if PROPOSE_CHANGES
}
```

Wave Planner applies the JSON:

- **APPROVE** → frontmatter `llm_review: APPROVE`, proceeds to human gate.
- **PROPOSE_CHANGES** → applies diff → re-runs deterministic → loop until `APPROVE` or cap 2 cycles (E2). 3rd iteration diverges → escalates to human with diffs (`llm_review_iterations: 2 (max reached, human decided)`).

**Skip threshold:** waves with ≤2 tasks skip LLM review (cost > benefit). Script `wave-planner-llm-review.py` increments counter `llm_review_skipped_count` in L1 when skip occurs (flag `--workspace-context <L1-CONTEXT.md>`).

**Mockable:** pytest mocks Task tool with JSON fixtures in `tests/mocks/llm_review_responses/` — CI runs without token cost.

---

## 10. Wave-reviewer skip exception (F2 — renamed v3.8.0)

A wave with **1 task** skips the wave-reviewer **cross-task** audit (no coherence check possible). Forensic+ (step 8a) still runs, and global CI covers the escape.

Schema `wave-plan.md` marks `skip_cross_task_audit: true` on the applicable wave. Stage 04 lead reads this flag and adjusts the protocol (skip step 8b cross-task, but keep 8a Forensic+ + 8c forensic git log).

> **Backward compat (v3.7.x → v3.8.0):** the legacy name `skip_wave_reviewer` is recognized as an alias by wave-planner-script.py during v3.8.0. New wave-plans always emit `skip_cross_task_audit`. v3.9.0 removes the alias.

---

## 11. Output wave-plan.md schema

```yaml
---
generated_at: 2026-04-25T14:32:00Z
plan_source: stages/02_design/output/plan.md
profile: app_web_backend
tier: development
workspace: 042-feat-auth
cap_subagentes_per_wave: 5
total_tasks: 4
total_waves: 2
total_sub_waves: 2
ambiguities_count: 0
llm_review: APPROVE              # APPROVE | PROPOSE_CHANGES | SKIPPED
llm_review_iterations: 1
---

# Wave Plan

## Wave 1 (sub-wave 1.a) — 2 parallel tasks

| Task slug | Files touched | Depends on | Branch |
|---|---|---|---|
| add-user-model | src/models/user.ts, tests/models/user.test.ts | - | wave-042-feat-auth-1/add-user-model |
| add-config-schema | src/config/schema.ts, tests/config.test.ts | - | wave-042-feat-auth-1/add-config-schema |

## Wave 2 (sub-wave 2.a) — 2 parallel tasks

| Task slug | Files touched | Depends on | Branch |
|---|---|---|---|
| add-login-endpoint | src/api/login.ts, tests/api/login.test.ts | add-user-model | wave-042-feat-auth-2/add-login-endpoint |
| add-logout-endpoint | src/api/logout.ts, tests/api/logout.test.ts | add-user-model | wave-042-feat-auth-2/add-logout-endpoint |

## Audit

- Tasks with file conflict serialized: none
- No ambiguity recorded.
```

---

## 12. Mid-wave cap reduce (D'')

Stage 04 lead may reduce the cap **mid-wave** if drift is observed:

- 3 stuck cycles without convergence from some subagent;
- prolonged idle waiting (Agent tool output with no progress);
- token budget growing disproportionately.

Action: ends partial wave with `BLOCKED_ERROR` + snapshot for human. Detail in `references/subagent-protocol.md` (sibling).

---

## 13. Automated validation

`tests/unit/test_wave_planner_dag.py` (33 tests green):

- Cycle detection (covers self-loop, 2/3/N node cycle).
- Correct topo sort (preserves plan.md order on ties).
- Sub-wave split respects cap.
- File conflict generates edge in correct order.
- Detect ambiguities covers dir-overlap without file-overlap.
- Property-based via Hypothesis: all deps preserved, no cap exceeded.

Wave 4 (LLM review) adds:

- `tests/unit/test_wave_planner_llm_review.py`: mocks Task tool with fixtures.
- `tests/integration/test_wave_planner_e2e.py`: deterministic pipeline + LLM review mocked → wave-plan.md final.
- Snapshot tests: expected `wave-plan.md` vs generated in `tests/fixtures/wave-plan-expected/`.

---

## 14. Concrete example: fictional 4-task plan.md

Input `plan.md` summarized:

```markdown
## Task add-user-model
### Files touched
- src/models/user.ts
- tests/models/user.test.ts

## Task add-config-schema
### Files touched
- src/config/schema.ts

## Task add-login-endpoint
### Files touched
- src/api/login.ts
### Depends on
- add-user-model

## Task add-logout-endpoint
### Files touched
- src/api/logout.ts
### Depends on
- add-user-model
```

Pipeline (`tier=development`, `profile=app_web_backend`, cap=5):

1. **Parse:** 4 tasks.
2. **DAG:** edges `(add-user-model, add-login-endpoint)`, `(add-user-model, add-logout-endpoint)`. No file conflict.
3. **Topo:** Wave 1 = `[add-user-model, add-config-schema]`. Wave 2 = `[add-login-endpoint, add-logout-endpoint]`.
4. **Sub-waves:** both waves ≤ cap → `1.a` and `2.a` (no split).
5. **Ambiguities:** none (distinct dirs).
6. **LLM review:** subagent returns `APPROVE` (explicit deps match semantics).
7. **Output:** wave-plan.md as per §11.

Stdout: `total_tasks=4 total_waves=2 total_sub_waves=2 ambiguities=0`.

---

## v3.3.0 — HITL/AFK rule

Wave planner respects the `**Type:**` field in each task of plan.md.

- **AFK tasks** (default): grouped in topological sub-waves up to cap per
  tier (experimental: 2, tool: 3, development: 5, production: 5).
- **HITL tasks**: each becomes an **isolated sub-wave cap=1**. Lead session
  does NOT spawn subagent — generates AGENT-BRIEF, displays to human, status
  `COMPLETED_AWAITING_HUMAN, sub_stage=04_wave_N_hitl_pending`, EXIT.

Function `subdivide_waves(waves, cap, task_types)`. If `task_types` is None
or empty, all tasks treated as AFK (backward compat).

Output `wave-plan.md` adds column `Type` to the table per sub-wave.

Canonical doc: `references/task-types-hitl-afk.md`.
