# Canonical Stop Points

> **Version:** v3.0.0-beta5
> **Path resolution:** `scripts/` paths in this document refer to `<SKILL_DIR>/scripts/`, where `SKILL_DIR` is defined in L0 (`CLAUDE.md`).
> **Purpose:** canonical list of the 12 stop points for the `xp-icm-workflow` skill + thresholds calibrated by tier for items 5/7/8 + standardized A/B/C menu template + L1 update protocol.

Resolution **Q5** from the plan: fixed list of 12 stops; items 5, 7, 8 calibrated by tier per `templates/_config/profile-matrix.md` (keys `stop_points_calibration.item_5/7/8`); remaining 9 always `hard` in any tier.

---

## 1. Canonical list (15 items)

| # | id | Description |
|---|---|---|
| 1 | `stack` | Technology stack (language, framework, runtime) |
| 2 | `db` | Database (engine, schema design) |
| 3 | `external_api` | External API (paid? rate-limit? privacy?) |
| 4 | `new_dep` | New dependency (license? maintenance? size?) |
| 5 | `paid_service` | Paid service (recurring cost?) — **calibrated by tier** |
| 6 | `irreversible` | Irreversible decision (drop table, destructive schema migration) |
| 7 | `over_eng` | Over-engineering detected (3+ new abstraction layers) — **calibrated by tier** |
| 8 | `pii` | PII/sensitive data (GDPR/LGPD, obfuscation) — **calibrated by tier** |
| 9 | `prod_migration` | Schema migration with data in production |
| 10 | `adr_drift` | Stack that differs from what was declared in an existing ADR |
| 11 | `workspace_corrupt` | ICM workspace corrupted (L1/L2 inconsistent — stops and requests recovery) |
| 12 | `profile_mismatch` | Profile/tier inconsistent with task scope |
| 13 | `ambiguous_feedback` | (v3.6.0 preview loop) Low-confidence human visual feedback — agent does NOT speculate and proceed |
| 14 | `design_system_cascade` | (v3.6.0 preview loop) Token change affects > `design_cascade_threshold` components |
| 15 | `runtime_cleanup_failed` | (v3.7.0) Pre-exit stage 08 runtime cleanup failed or human cancelled — **strict universal** all tiers |

### 1.1 Detail per item

#### 1 — `stack`
Change or first choice of language, framework, or primary runtime.

- **Signals:**
  - Discovery proposes a language not yet declared in an ADR.
  - Plan includes a new runtime (Node, Python, Go) not present in the project.
  - Framework migration (Express → Fastify, Django → FastAPI).
  - Greenfield project with no pre-fixed stack.
- **Typical trade-offs:** ecosystem maturity vs team preference; performance vs DX; architectural cohesion vs feature fit.

#### 2 — `db`
Database engine choice or substantive schema redesign.

- **Signals:**
  - First persistence layer for the project.
  - Engine change (Postgres → Mongo, SQLite → Postgres).
  - Schema redesign that renames/drops tables in use.
  - New storage class (cache, queue, OLAP).
- **Typical trade-offs:** ACID vs flexibility; operational cost vs performance; portability vs engine feature fit.

#### 3 — `external_api`
Integration with a third-party API.

- **Signals:**
  - Plan includes an HTTP call to an uncontrolled service.
  - API requires API key, OAuth, SLA contract.
  - Non-trivial rate-limit (<100 req/min).
  - Data leaving the project boundary (privacy review).
- **Typical trade-offs:** delivery speed vs lock-in; external SLA vs autonomy; compliance vs cost of in-house implementation.

#### 4 — `new_dep`
Addition of a new runtime or dev dependency.

- **Signals:**
  - `requirements.txt` / `package.json` gains a new entry.
  - Package with no releases in the last 12 months.
  - Non-permissive license (GPL, AGPL, custom).
  - Size > 5 MB or transitive tree > 50 packages.
- **Typical trade-offs:** speed vs supply-chain risk; reuse vs lock-in; downstream maintenance.

#### 5 — `paid_service` (calibrated)
SaaS service with recurring cost.

- **Signals:**
  - Mandatory paid plan above the free tier.
  - Estimated monthly cost > tier threshold (see §2).
  - Significant vendor lock-in (non-exportable data).
  - Auto-scale with a cost floor.
- **Typical trade-offs:** dev velocity vs recurring OPEX; sovereignty vs convenience; cost predictability vs flexibility.

#### 6 — `irreversible`
Operation that destroys data or history in a non-recoverable way.

- **Signals:**
  - `DROP TABLE`, `TRUNCATE`, destructive schema migration (drop column with data).
  - `git push --force` on a shared branch.
  - Credential rotation without a grace window.
  - Hard-delete of records without prior soft-delete.
- **Typical trade-offs:** simplicity vs reversibility; space/performance vs auditability; now vs undo window.

#### 7 — `over_eng` (calibrated)
Over-engineering signal in design.

- **Signals:**
  - 3+ new abstraction layers to solve 1 concrete problem.
  - Enterprise patterns (factories, mediators, brokers) without demonstrated need.
  - Preventive generalization without a second real use case.
  - Configurability with no second consumer.
- **Typical trade-offs:** future flexibility vs reading cost; YAGNI vs early reuse.

#### 8 — `pii` (calibrated)
Handling of personal or sensitive data.

- **Signals:**
  - Schema includes CPF, national ID, email, phone, health data.
  - Logs potentially leaking PII in plain text.
  - Cross-service sharing without obfuscation/encryption.
  - Indefinite retention without a declared policy.
- **Typical trade-offs:** UX vs LGPD compliance; debug vs minimization; performance vs encryption.

#### 9 — `prod_migration`
Schema migration running against production data.

- **Signals:**
  - Migration touches a table with volume > 100k rows.
  - Blocking DDL in RDBMS (ALTER TABLE with full rewrite).
  - Type/constraint change that invalidates existing rows.
  - No pre-agreed maintenance window.
- **Typical trade-offs:** zero-downtime vs simplicity; incremental backfill vs single shot; rollback plan vs forward-only.

#### 10 — `adr_drift`
Plan diverges from an existing ADR.

- **Signals:**
  - Approved ADR declares stack X, plan proposes Y.
  - Architectural decision touches a component with an active ADR.
  - Old ADR "Rationale" still valid — but plan ignores it.
  - ADR not formally superseded.
- **Typical trade-offs:** keep ADR (compliance cost) vs supersede (re-justification cost) vs hybrid coexistence (divergence cost).

#### 11 — `workspace_corrupt`
Inconsistency between L1 (`CONTEXT.md` frontmatter) and the real filesystem state.

- **Signals:**
  - Pre-flight check detects hash mismatch, missing outputs, missing commit_sha (see §Heuristics in `references/state-machine-schema.md`).
  - L1 says `IN_PROGRESS` but no commits in workspace for > 24h.
  - `waves.current=N` without corresponding `wave-N/<task>` branches.
- **Typical trade-offs:** resume via Recovery Wizard vs abandon workspace vs spawn new workspace.
- **Note:** this stop point is special — always fires `hard` and proposes Recovery Wizard directly, not a free A/B/C menu.

#### 12 — `profile_mismatch`
Profile/tier chosen at bootstrap does not match the real scope of the task in progress.

- **Signals:**
  - Tier `experimental` but plan includes production data.
  - Profile `technical_article` but task involves code running in CI.
  - `ml_project / tool` but plan requires formal peer-review.
  - Scope grew beyond what was declared in L0.
- **Typical trade-offs:** change profile/tier (regenerates matrix, re-validation cost) vs spawn new workspace with correct profile vs reduce current task scope.

#### 13 — `ambiguous_feedback` (v3.6.0 preview loop)
Human visual feedback with low confidence: vague description, unannotated screenshot, contradiction between text and visual.

- **Signals:**
  - Human says "I don't like it" without pointing to a specific element.
  - Screenshot annotated with arrows on multiple elements without cross-referenced textual description.
  - Text requests change X but annotated screenshot shows a different element.
- **Typical trade-offs:** agent speculates (risk of changing the wrong thing) vs pauses and asks (friction but correct).
- **Calibration:** always `hard` (any tier). Triggerable only during stage 04 with `preview_loop_enabled: true`.
- Doc: `references/preview-loop-protocol.md`.

#### 14 — `design_system_cascade` (v3.6.0 preview loop)
A token (color, spacing, typography) change affects more components than `preview_loop.design_cascade_threshold` (default 5).

- **Signals:**
  - Human requests "change primary to green", agent Grep shows 17 affected components.
  - Change in `spacing.md` propagates to the entire app.
  - Typography override affects multiple sections.
- **Typical trade-offs:** global cascade (DESIGN.md becomes source of truth, broad visual change) vs local override (only this component, DESIGN.md stays aspirational) vs cancel.
- **Calibration:** always `hard` (any tier). Triggerable only during stage 04 with `preview_loop_enabled: true`.
- Doc: `references/preview-loop-protocol.md`.

#### 15 — `runtime_cleanup_failed` (v3.7.0)
Pre-exit stage 08 runtime cleanup (exit A close, B restart, C spawn) detected a non-clean category and human cancelled, or the cleanup command returned an error.

Applicable ONLY in stage 08 (`applicable_stop_points: ["runtime_cleanup_failed"]`). Other stages do NOT trigger it — runtime cleanup is a final transition gate, not an architectural decision.

- **Signals:**
  - `runtime-status.py --exit-code` returns 1 and human answers `[n]` in some category.
  - Cleanup command fails (kill permission denied, branch protected, docker daemon down).
  - Human abandons checklist mid-confirmation.
- **Typical trade-offs:** resolve now (interrupt flow) vs defer cleanup (workspace becomes inconsistent, recovery wizard detects later) vs cancel stage 08 (status reverts to `COMPLETED_AWAITING_HUMAN`).
- **Calibration:** always `hard` — strict universal all tiers (not calibrated by tier).
- **Specific A/B/C menu** (does not use standard template §3):
  ```
  Runtime cleanup failed in category(ies): <list>

  [a] resolved manually, resume checklist
  [b] skip category + proceed with exit <A|B|C> (workspace becomes inconsistent)
  [c] cancel stage 08 (status reverts to COMPLETED_AWAITING_HUMAN)
  ```
- Doc: `references/runtime-cleanup-protocol.md`.

---

## 2. Thresholds calibrated by tier (items 5, 7, 8)

Source: `templates/_config/profile-matrix.md` (keys `stop_points_calibration.item_5`, `item_7`, `item_8`). In case of divergence, `<SKILL_DIR>/scripts/profile-merge.py` is the operational source of truth.

| Item | experimental | tool | development | production |
|---|---|---|---|---|
| 5 — `paid_service` | warning, R$ 50 | hard, R$ 200 | hard, R$ 500 | hard, R$ 1000 |
| 7 — `over_eng` | warning | warning | hard | hard |
| 8 — `pii` | warning | hard | hard | hard+DPO |

Remaining 12 stops (1, 2, 3, 4, 6, 9, 10, 11, 12, 13, 14, 15) always `hard` in any tier.

### 2.1 Severity modes

| Mode | Behavior |
|---|---|
| `warning` | Agent warns in prose in session output, continues work with a note; **does not block**. Does not update L1 `status`. Optional append to `history` as `event: stop_point_warning`. |
| `hard` | Agent stops, writes A/B/C menu (template §3), updates L1 `status: BLOCKED_STOP_POINT`, waits for human response. |
| `hard+DPO` | `hard` + explicit recommendation "involve DPO/legal before proceeding" in the menu. Status same. |

---

## 3. Standardized A/B/C menu template

Triggered: agent in any stage upon detecting a stop point with mode `hard` or `hard+DPO`.

```markdown
# 🛑 STOP POINT — <id> (<short description>)

## Summary
<1-2 paragraphs describing what was detected and why it triggered>

## Trade-offs
- A) <option A — description>
- B) <option B — description>
- C) <option C — usually "keep as is / escalate to human">

## Reversibility
- A: <reversible? how? at what cost?>
- B: <reversible? how? at what cost?>
- C: <reversible>

## Agent recommendation
<A/B/C> + justification in 1 paragraph, citing trade-offs and project context (tier, profile, applicable lessons).

## Human action

Reply in chat:
- "A" / "B" / "C" to choose
- Free text for another option / to request more info

Awaiting response. L1 updated: `status: BLOCKED_STOP_POINT`.
```

In `hard+DPO` mode, add an extra line right after the recommendation:

> **LGPD Notice:** involve DPO/legal before proceeding. Technical decision does not replace legal validation.

---

## 4. L1 update when triggered

Session MUST execute atomically (1 commit):

1. Append to `history`:
   ```yaml
   - at: "<ISO 8601 UTC>"
     event: "stop_point_triggered"
     stop_point_id: "<id>"
     note: "<short text describing the trigger>"
   ```
2. Set `status: BLOCKED_STOP_POINT`.
3. Set `last_action: "stop point <id> triggered"` + `last_action_at: <ISO>`.
4. Set `next_action: "awaiting human response to A/B/C menu"`.
5. Atomic commit (`workspace: stop_point <id> triggered`). Pre-commit hook validates L1↔outputs atomicity.

Status enum and schema come from `references/state-machine-schema.md`.

---

## 5. Human response — resume protocol

Human replies in chat with `A`, `B`, `C`, or free text. Session:

1. Reads response.
2. Appends to `history`:
   ```yaml
   - at: "<ISO 8601 UTC>"
     event: "stop_point_resolved"
     stop_point_id: "<id>"
     resolution: "A" | "B" | "C" | "custom"
     note: "<summary of human decision>"
   ```
3. Sets `status: IN_PROGRESS`.
4. Updates `last_action`/`next_action` per choice.
5. Continues work per chosen option.
6. **ADR spawn:** if the choice implies an architectural decision (typical for stops 1, 2, 3, 6, 10), spawn `docs/decisions/NNNN-<slug>.md` — **only in stage 02 design**. In other stages, annotate in the `decisions-pending.md` of the next workspace's stage 02 or record as tech debt.

---

## 6. Custom stop points (D3)

Override in `.icm-profile.local.yaml` field `custom_stop_points` (full schema in `templates/_config/profile-matrix.md`). Additional project-specific list. Each item requires `id`, `description`, `threshold` (dict tier→mode).

Bootstrap (`<SKILL_DIR>/scripts/profile-merge.py`) validates the schema and bootstrap includes custom stops in `recon-report.md` for visibility. Sessions consult both the canonical list and `custom_stop_points` from the effective profile.

---

## 7. Stages where stop points are expected

Typical applicability table. `n/a` means the stage rarely triggers that stop by the nature of the work.

| Stage | Most common stops |
|---|---|
| 00 recon | 11 (`workspace_corrupt`), 12 (`profile_mismatch`) |
| 01 discovery | 1 (`stack`), 3 (`external_api`), 5 (`paid_service`), 8 (`pii`) |
| 02 design | 1, 2 (`db`), 4 (`new_dep`), 5, 6 (`irreversible`), 7 (`over_eng`), 8, 10 (`adr_drift`) |
| 03 wave_planner | n/a (wave-planner is deterministic — gap-fill if applicable) |
| 04 implementation_waves | 4, 6, 7, 9 (`prod_migration`), 10 |
| 05 verification | n/a |
| 06 review | 7, 8, 10 |
| 07 merge | 6, 9 |
| 08 feedback_intake | n/a (stage 08 is analysis + A/B/C iteration decision; stops detected here carry over to the next workspace via exit C) |

The table is indicative. Any stage can trigger any stop if the signal appears — there is no enforced whitelist.
