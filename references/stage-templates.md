# Stage Templates — Canonical L2 Spec (xp-icm-workflow v3.0.0-beta5)

> **Purpose:** defines the **mandatory schema** of the 9 L2 templates in `templates/workspace/stages/<NN>_<slug>/CONTEXT.md.tpl`. Each L2 is a *stage contract*: declares what the agent reads, processes and writes when that stage is active.

> **Status:** spec. Concrete L2 templates in `templates/workspace/stages/*/CONTEXT.md.tpl`. Any schema change here requires regenerating the 9 .tpl + updating `tests/unit/test_l2_templates.py`.

> **Do not confuse:** this doc is the spec of the **L2 template**. The resulting `.tpl` carries placeholders `{{PROJECT_ROOT}}` and `{{WORKSPACE}}` that bootstrap resolves. The materialized result in `<project_root>/workspaces/<NNN-slug>/stages/<NN>_<slug>/CONTEXT.md` is the effective L2 read by sessions.

---

## The 9 stages

| NN | Name (slug)              | One-sentence summary |
|----|--------------------------|----------------|
| 00 | `recon`                  | Project/repository reconnaissance: detects stack, branch, existing ADRs and lessons; generates baseline for subsequent stages. |
| 01 | `discovery`              | Guided brainstorming: audience, functional/non-functional requirements, alternatives, MVP IN/OUT, risks, metrics. |
| 02 | `design`                 | Architectural plan + formal ADRs; data modeling, API contracts, task breakdown with 4-block contract + global Test Strategy. |
| 03 | `wave_planner`           | Builds task DAG, groups into waves respecting subagent cap and dependencies; LLM review subagent signs the plan. |
| 04 | `implementation_waves`   | Parallel execution via subagents on isolated branches; lead orchestrates Agent tool spawn/exit/sequential merge; one sub-stage per wave. |
| 05 | `verification`           | Technical verification of what was delivered: CI, coverage vs threshold (test_specs), sample-check test types, conformance to plan and ADRs; PASS/CONDITIONAL/FAIL. |
| 06 | `review`                 | Code review on 7 dimensions (correctness, security, tests, design, standards, readability, performance) + feedback reception. |
| 07 | `merge`                  | Finalizes branch: direct merge, PR, release tag or cleanup; updates lessons/tech_debt; closes the delivery cycle. |
| 08 | `feedback_intake`        | Post-real-use: 3 exits — A) close workspace, B) restart stage X (`iteration++`), C) spawn new workspace inheriting lessons+ADRs. |

---

## Mandatory L2 template schema

Every `stages/<NN>_<slug>/CONTEXT.md.tpl` MUST contain the 12 sections below, **in order**. The test parser fails if any is missing.

### 1. YAML frontmatter

```yaml
---
layer: L2
stage: "<NN>"                              # string "00".."08"
stage_name: "<slug>"                       # ∈ {recon, discovery, design, wave_planner, implementation_waves, verification, review, merge, feedback_intake}
sub_stage_enum:                            # canonical list for the stage (see §Sub_stage enum)
  - "<NN>_in_progress"
  - "<NN>_completed"
applicable_stop_points:                    # list of stop-points-canonical.md IDs applicable here
  - "<sp_id>"
output_files:                              # paths relative to stage dir
  - "output/<file>.md"
next_stage: "<MM>"                         # next default stage; null if 08 or if profile skips
---
```

**Required fields:** `layer`, `stage`, `stage_name`, `sub_stage_enum`, `applicable_stop_points`, `output_files`, `next_stage`. All validated by Round 2 parser.

**Rule:** `stage_name` in snake_case without numeric prefix (the number is in `stage`). `sub_stage_enum` matches **exactly** with `references/state-machine-schema.md` §Sub-stage enum.

### 2. Title + purpose (1 paragraph)

```markdown
# Stage {{STAGE_NN}} — {{STAGE_NAME}} (L2)

<1 paragraph: what this stage delivers to the workspace, in direct language. No filler.>
```

### 3. `Inputs (reads ONLY these, in order)` table

Literal format §4.11 of the plan. Minimum 3 rows (L0, L1, L2 of the stage). Subsequent stages add prior outputs and ADRs/conventions.

```markdown
## Inputs (reads ONLY these, in order)

| # | Path | Layer | Required? |
|---|------|-------|--------------|
| 1 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/CLAUDE.md | L0 | yes |
| 2 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/CONTEXT.md | L1 | yes |
| 3 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/<NN>_<slug>/CONTEXT.md | L2 | yes |
| 4 | <stage-specific path>                         | L3/L4 | yes/conditional |
| ... | ...                                            | ...   | ... |
```

**Placeholders:** only `{{PROJECT_ROOT}}` and `{{WORKSPACE}}` (Jinja-style). Bootstrap resolves. Never use `../../`.

**`conditional` marking:** row whose requirement depends on profile/tier (e.g., `tech_debt.md` only if `tech_debt_tracking: true`). Column must say `conditional: <rule>`.

### 4. `Does Not Read (negative constraint)` section

Explicit negative list. Agent refuses to read directories/files outside the Inputs and outside the declared track here.

```markdown
## Does Not Read (negative constraint)

- {{PROJECT_ROOT}}/src/, {{PROJECT_ROOT}}/tests/   (exceptions: <listed>)
- ADRs not listed in this wave's plan.md
- Outputs from stages other than those declared in Inputs
- {{PROJECT_ROOT}}/docs/lessons.md (lessons are pre-injected by lead, if applicable)
```

### 5. Read order

Numbered, preserves Inputs order. Reinforces the Layer Loading Protocol.

```markdown
## Read order

1. L0 — identity
2. L1 — state machine
3. L2 (this file) — stage instructions
4..N. Other Inputs paths, in table order
```

### 6. Process

Stage steps in numbered format. Each step small and verifiable. Includes:

- Pre-flight check (existence of Input paths).
- Superpowers skills to invoke (see §11).
- Decisions that trigger a stop point.
- Point where sub_stage transitions to `<NN>_completed`.
- L1 update + atomic commit.

### 7. Expected outputs

Paths **relative to `stages/<NN>/output/`**. Same as the `output_files` field of frontmatter. Each item describes minimum content (1 sentence).

```markdown
## Outputs

- `output/<file>.md` — <minimum description of content>
- `output/reports/<...>` (if applicable)
```

### 8. Sub_stage transitions

Lists valid enums for the stage (pulled from `state-machine-schema.md`) + textual rule for the IN_PROGRESS → COMPLETED transition.

```markdown
## Sub_stage transitions

Valid enum: <list of sub_stage_enum from frontmatter>

IN_PROGRESS → COMPLETED transition fires when:
- All outputs declared in §Outputs exist in FS.
- Verify (§6 Process step X) passed.
- Human approved (gate of §12) — when applicable.
```

Stage 04 documents dynamic sub_stages `04_wave_<N>_in_progress` / `04_wave_<N>_completed`. Stage 08 documents the 4 terminal values `08_decided_A/B/C` in addition to `08_in_progress`.

### 9. Settable statuses

Subset of the 5 canonical ones from `references/state-machine-schema.md`.

```markdown
## Canonical statuses available in this stage

- `IN_PROGRESS` — active work.
- `COMPLETED_AWAITING_HUMAN` — outputs ready, awaiting human gate.
- `BLOCKED_STOP_POINT` — A/B/C menu triggered (see §10).
- `BLOCKED_ERROR` — runtime/CI/merge failed.
- `COMPLETED` — ONLY stage 07 (exit) or 08 exit A.
```

Stages 00–06 never set `COMPLETED` (workspace terminal). Stages 03 and 06 may omit `BLOCKED_ERROR` if profile skips.

### 10. Applicable stop points

Canonical reference to `references/stop-points-canonical.md` (written in parallel). Lists IDs applicable to the stage.

```markdown
## Applicable stop points

Canonical catalog in `references/stop-points-canonical.md`. IDs fireable here:

- `sp_<id>` — <1 line of what triggers it>
- ...

Trigger: agent pauses, writes A/B/C menu to output, updates L1 `status: BLOCKED_STOP_POINT`. Human replies, session resumes with `IN_PROGRESS`.
```

Canonical catalog in `references/stop-points-canonical.md` defines the 12 IDs and thresholds per tier. L2 of the stage cites ONLY canonical IDs. Authoritative mapping:

| Stage | Applicable stop points (canonical IDs) |
|---|---|
| 00 recon | `workspace_corrupt`, `profile_mismatch` |
| 01 discovery | `stack`, `external_api`, `paid_service`, `pii` |
| 02 design | `stack`, `db`, `new_dep`, `paid_service`, `irreversible`, `over_eng`, `pii`, `adr_drift` |
| 03 wave_planner | (none — wave-planner is deterministic) |
| 04 implementation_waves | `new_dep`, `irreversible`, `over_eng`, `prod_migration`, `adr_drift` |
| 05 verification | (none — CI failure is `BLOCKED_ERROR`, not stop point) |
| 06 review | `over_eng`, `pii`, `adr_drift` |
| 07 merge | `irreversible`, `prod_migration` |
| 08 feedback_intake | (none — exits A/B/C are direct decision) |

### 11. Reference superpowers skills

Points to the 200tok summary to consult. Absolute path via placeholder; files will be created in Wave 5 of the skill — paths are contracts.

```markdown
## Reference superpowers skills

200tok summary: `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/superpowers-summary/<X>-200tok.md`

Formal skill: `superpowers:<name>` (escape hatch — real invocation only if complexity warrants).
```

#### Stage ↔ superpowers skill mapping

| Stage | Main superpowers skill | 200tok summary |
|---|---|---|
| 00 recon | `brainstorming` + `writing-plans` (light) | `brainstorming-200tok.md` |
| 01 discovery | `brainstorming` | `brainstorming-200tok.md` |
| 02 design | `writing-plans` | `writing-plans-200tok.md` |
| 03 wave_planner | `dispatching-parallel-agents` | `dispatching-parallel-agents-200tok.md` |
| 04 implementation_waves | `test-driven-development` + `subagent-driven-development` | `test-driven-development-200tok.md`, `subagent-driven-development-200tok.md` |
| 05 verification | `verification-before-completion` | `verification-before-completion-200tok.md` |
| 06 review | `requesting-code-review` + `receiving-code-review` | `requesting-code-review-200tok.md` |
| 07 merge | `finishing-a-development-branch` | `finishing-a-development-branch-200tok.md` |
| 08 feedback_intake | (none direct) | uses local `references/feedback-intake-stage08.md` |

### 12. Gates

Explicitly declares who releases the stage.

```markdown
## Gates

- **Human:** <when human approval or output editing is required>
- **Automatic (CI):** <linters, tests, hooks that must be green>
- **Approval to transition:** <exact rule for sub_stage IN_PROGRESS → COMPLETED>
```

Stage 04 references a composite gate: peer review subagent + wave-reviewer + green merge.

---

## Sub_stage enum per stage (canonical)

Replica of `references/state-machine-schema.md` §Sub-stage enum. Each L2 frontmatter must match **exactly** the corresponding column.

| Stage | Valid values |
|---|---|
| 00 Recon | `00_in_progress`, `00_completed` |
| 01 Discovery | `01_in_progress`, `01_completed` |
| 02 Design | `02_in_progress`, `02_completed` |
| 03 Wave Planner | `03_in_progress`, `03_completed` |
| 04 Implementation Waves | `04_wave_<N>_in_progress`, `04_wave_<N>_completed` (N positive integer) |
| 05 Verification | `05_in_progress`, `05_completed` |
| 06 Review | `06_in_progress`, `06_completed` |
| 07 Merge | `07_in_progress`, `07_completed` |
| 08 Feedback Intake | `08_in_progress`, `08_decided_A`, `08_decided_B`, `08_decided_C` |

**Prefix rule:** `sub_stage` ALWAYS starts with prefix `<stage>_`. Mismatch triggers Recovery Wizard inconsistency (see `references/state-machine-schema.md` §R2.7).

---

## Stages skipped by profile

Source: `templates/_config/profile-matrix.md`. Skill resolves `stages_skipped` in the profile + tier + override merge and materializes ONLY the non-skipped L2s.

| Profile | `stages_skipped` |
|---|---|
| `experiment` | `["03", "05", "06", "08"]` (all tiers) |
| `technical_article` | `["03"]` (all tiers) |
| Other 9 profiles | `[]` |

Local override in `.icm-profile.local.yaml` can add/remove (subject to `confirm_unsafe` for critical gates). L1 declares the final `stages_skipped` in `_config/profile-effective.yaml`; bootstrap does NOT create folders for skipped stages.

**When a stage is skipped:** L1 does not skip transitions — `next_stage` of the prior L2 points directly to the next NON-skipped stage. E.g., in `experiment`, `next_stage` of stage 02 design is `04` (skips 03).

---

## Automated validation (Round 2)

`tests/unit/test_l2_templates.py` parses each `templates/workspace/stages/<NN>_<slug>/CONTEXT.md.tpl` and validates:

1. **Frontmatter parseable** (PyYAML strict load) and contains the 7 required fields.
2. **`sub_stage_enum`** matches exactly with `references/state-machine-schema.md` §Sub-stage enum (exception: stage 04 validates regex `^04_wave_<int>_(in_progress|completed)$`).
3. **Jinja placeholders**: only `{{PROJECT_ROOT}}` and `{{WORKSPACE}}`. Any other placeholder (`{{...}}`) → fail. Verifies both are substitutable (re.findall finds ≥1 occurrence each — except stage 00 which may not use `WORKSPACE` in paths beyond the default L0/L1/L2).
4. **Inputs table present** with exact header `## Inputs (reads ONLY these, in order)` and ≥3 data rows (L0, L1, L2 minimum) — parser counts table rows after the header.
5. **Section `## Does Not Read (negative constraint)`** present with ≥1 item.
6. **`output_files` from frontmatter** matches paths cited in the `## Outputs` section (set equality).
7. **`applicable_stop_points`** ⊆ IDs declared in `references/stop-points-canonical.md` (loads catalog, does `issubset`).
8. **`next_stage`** ∈ {`"00".."08"`, `null`}; null exclusive to stage 08.
9. **Skill 200tok path** referenced in §11 exists as a string (actual file only in Wave 5 — test only checks path format).

Failure in any item → CI blocks wave merge.

---

## Concrete example — L2 stage 02 design (resolved placeholders)

Fictional workspace: `042-feat-auth`, `project_root=/repo/aura-luz-api`, profile `app_web_backend`, tier `development`.

```markdown
---
layer: L2
stage: "02"
stage_name: "design"
sub_stage_enum:
  - "02_in_progress"
  - "02_completed"
applicable_stop_points:
  - "stack"
  - "db"
  - "new_dep"
  - "paid_service"
  - "irreversible"
  - "over_eng"
  - "pii"
  - "adr_drift"
output_files:
  - "output/plan.md"
  - "output/decisions.md"
next_stage: "03"
---

# Stage 02 — design (L2)

Produces an executable architectural plan + formal ADRs. Each non-trivial decision becomes an A/B/C menu. Output feeds the Wave Planner (stage 03) with tasks containing 4-block contract, files touched and applicable ADRs.

## Inputs (reads ONLY these, in order)

| # | Path | Layer | Required? |
|---|------|-------|--------------|
| 1 | /repo/aura-luz-api/workspaces/042-feat-auth/CLAUDE.md | L0 | yes |
| 2 | /repo/aura-luz-api/workspaces/042-feat-auth/CONTEXT.md | L1 | yes |
| 3 | /repo/aura-luz-api/workspaces/042-feat-auth/stages/02_design/CONTEXT.md | L2 | yes |
| 4 | /repo/aura-luz-api/workspaces/042-feat-auth/stages/01_discovery/output/discovery.md | L4 | yes |
| 5 | /repo/aura-luz-api/workspaces/042-feat-auth/stages/00_recon/output/baseline.md | L4 | yes |
| 6 | /repo/aura-luz-api/docs/decisions/ | L3 | conditional: read existing ADRs referenced in discovery.md |
| 7 | /repo/aura-luz-api/docs/tech_debt.md | L3 | conditional: tier ≠ experimental |
| 8 | /repo/aura-luz-api/workspaces/042-feat-auth/_config/xp-conventions.md | L3 | yes |
| 9 | /repo/aura-luz-api/workspaces/042-feat-auth/_config/stop-points.md | L3 | yes |
| 10 | /repo/aura-luz-api/workspaces/042-feat-auth/_references/superpowers-summary/writing-plans-200tok.md | L3 | yes |

## Does Not Read (negative constraint)

- /repo/aura-luz-api/src/, /repo/aura-luz-api/tests/
- ADRs in /repo/aura-luz-api/docs/decisions/ NOT referenced in discovery.md
- Outputs from stages 03+ (do not exist yet)
- /repo/aura-luz-api/docs/lessons.md (lead will inject relevant lessons in stage 04)

## Read order

1. L0 — /repo/aura-luz-api/workspaces/042-feat-auth/CLAUDE.md
2. L1 — /repo/aura-luz-api/workspaces/042-feat-auth/CONTEXT.md
3. L2 — this file
4. discovery.md (main input)
5. baseline.md (recon)
6. ADRs listed in discovery
7. tech_debt.md (if tier permits)
8. xp-conventions.md, stop-points.md, writing-plans summary

## Process

1. Pre-flight: validate all Input paths exist; sub_stage `02_in_progress`.
2. Read in order; consult writing-plans 200tok summary.
3. For each non-trivial architectural decision, build A/B/C menu with recommendation.
4. Trigger stop point if: stack change, new modeling, new public API, new dependency, paid service, irreversible decision, over-engineering detected.
5. Write formal ADRs in /repo/aura-luz-api/docs/decisions/NNNN-<slug>.md (source of truth).
6. Write output/plan.md: tasks with 4-block contract (WHAT / HOW / OUT OF SCOPE / VALIDATION), files touched, Applicable ADRs, requires_peer_review.
7. Write output/decisions.md: INDEX (title + slug + status) — does not duplicate ADR.
8. Verify: each MVP requirement from discovery appears in ≥1 plan task OR is deferred with rationale.
9. **End-of-stage handoff:** follow gate-inline protocol (v3.4.2) — split in two phases in the same session. Phase 1: update L1 (`sub_stage=02_completed, status=COMPLETED_AWAITING_HUMAN, last_transition.from=02_in_progress, last_transition.to=02_completed`), atomic commit 1/2 (outputs + L1, WITHOUT kickoff), print gate prompt, wait for human. Phase 2 (after approval): update L1 (`stage_atual=03, sub_stage=03_in_progress, status=IN_PROGRESS`), render `_kickoff.md` in `stages/03_wave_planner/`, atomic commit 2/2 (kickoff + L1), print KICKOFF block, EXIT. Canonical doc: `references/session-handoff-protocol.md`.

## Outputs

- `output/plan.md` — plan with 4-block tasks, dependency DAG, files touched, applicable ADRs per task.
- `output/decisions.md` — INDEX of created ADRs (title + slug + status).

## Sub_stage transitions

Valid enum: `02_in_progress`, `02_completed`.

IN_PROGRESS → COMPLETED transition fires when:
- output/plan.md and output/decisions.md exist.
- Each MVP requirement from discovery is covered by ≥1 task or explicitly deferred.
- New ADRs committed in /repo/aura-luz-api/docs/decisions/.
- Human approved via gate (status `COMPLETED_AWAITING_HUMAN` → human replies).

## Canonical statuses available in this stage

- `IN_PROGRESS` — writing plan/ADRs.
- `COMPLETED_AWAITING_HUMAN` — outputs ready, human reviews.
- `BLOCKED_STOP_POINT` — A/B/C menu awaiting response.
- `BLOCKED_ERROR` — pre-commit hook rejected or Input path absent.

## Applicable stop points

Canonical catalog in `references/stop-points-canonical.md`. IDs fireable in stage 02 design:

- `stack` — language/framework/runtime change vs active ADR.
- `db` — new engine or schema design.
- `new_dep` — new npm/pip/cargo entry in manifest (license/maintenance/size).
- `paid_service` — recurring SaaS (calibrated by tier: warning R$50 / hard R$200/500/1000).
- `irreversible` — drop table, destructive migration.
- `over_eng` — 3+ new abstraction layers without a requirement (warning experimental/tool, hard development/production).
- `pii` — LGPD, sensitive data (warning experimental, hard tool/development, hard+DPO production).
- `adr_drift` — proposal diverges from existing ADR without declared superseding.

## Reference superpowers skills

200tok summary: `/repo/aura-luz-api/workspaces/042-feat-auth/_references/superpowers-summary/writing-plans-200tok.md`

Formal skill: `superpowers:writing-plans` (escape hatch).

## Gates

- **Human:** reviews output/plan.md and ADRs; approves or requests adjustments.
- **Automatic (CI):** pre-commit hook validates L1↔outputs atomicity and commit prefix `workspace/042-feat-auth`.
- **Approval to transition:** human explicitly approves (input in session); automatically becomes `02_completed` on the next commit.
```

---

## End of spec
