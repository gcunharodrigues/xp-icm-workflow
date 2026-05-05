---
layer: L3
source: references/stop-points-canonical.md
tier_resolved: "{{TIER}}"
generated_at: "{{CREATED_AT}}"
---

# Stop Points — workspace `{{WORKSPACE}}`

> Resolved for tier `{{TIER}}` at bootstrap. For a view of all tiers, see `references/stop-points-canonical.md` (in the skill, not the workspace).

Canonical list of 15 stop points + thresholds resolved for this workspace's tier + inline A/B/C menu template. The workspace is self-contained — this copy does not depend on the skill at runtime.

---

## 1. Canonical list (15 items)

| # | id | Description |
|---|---|---|
| 1 | `stack` | Technology stack (language, framework, runtime) |
| 2 | `db` | Database (engine, schema design) |
| 3 | `external_api` | External API (paid? rate-limit? privacy?) |
| 4 | `new_dep` | New dependency (license? maintenance? size?) |
| 5 | `paid_service` | Paid service (recurring cost?) — **calibrated** |
| 6 | `irreversible` | Irreversible decision (drop table, destructive schema migration) |
| 7 | `over_eng` | Over-engineering detected (3+ new abstraction layers) — **calibrated** |
| 8 | `pii` | PII/sensitive data (LGPD, obfuscation) — **calibrated** |
| 9 | `prod_migration` | Schema migration against production data |
| 10 | `adr_drift` | Stack diverges from what is declared in an existing ADR |
| 11 | `workspace_corrupt` | ICM workspace corrupted (L1/L2 inconsistent — stops and requests recovery) |
| 12 | `profile_mismatch` | Profile/tier inconsistent with task scope |
| 13 | `ambiguous_feedback` | (v3.6.0) Low-confidence human visual feedback — agent does NOT speculate |
| 14 | `design_system_cascade` | (v3.6.0) Token change affects > `design_cascade_threshold` components |
| 15 | `runtime_cleanup_failed` | Pre-exit stage 08 runtime cleanup failed or human cancelled — **v3.7.0** |

---

## 2. Detail per item

### 1. `stack` — Technology stack

**Mode in this tier:** `hard` (always)

Change or first choice of primary language, framework, or runtime.

- **Signals:**
  - Discovery proposes a language not yet declared in an ADR.
  - Plan includes a new runtime (Node, Python, Go) not present in the project.
  - Framework migration (Express → Fastify, Django → FastAPI).
  - Greenfield with no pre-fixed stack.
- **Typical trade-offs:** ecosystem maturity vs team preference; perf vs DX; architectural cohesion vs feature-fit.

### 2. `db` — Database

**Mode in this tier:** `hard` (always)

Database engine choice or substantial schema redesign.

- **Signals:**
  - First persistence in the project.
  - Engine change (Postgres → Mongo, SQLite → Postgres).
  - Schema redesign that renames/removes tables in use.
  - New storage class (cache, queue, OLAP).
- **Typical trade-offs:** ACID vs flexibility; operational cost vs perf; portability vs engine feature-fit.

### 3. `external_api` — External API

**Mode in this tier:** `hard` (always)

Integration with a third-party API.

- **Signals:**
  - Plan includes an HTTP call to an uncontrolled service.
  - API requires an API key, OAuth, or SLA contract.
  - Non-trivial rate-limit (<100 req/min).
  - Data leaving the project boundary (privacy review).
- **Typical trade-offs:** delivery speed vs lock-in; external SLA vs autonomy; compliance vs cost of in-house implementation.

### 4. `new_dep` — New dependency

**Mode in this tier:** `hard` (always)

Addition of a new runtime or dev dependency.

- **Signals:**
  - `requirements.txt` / `package.json` gains a new entry.
  - Package with no releases in the past 12 months.
  - Non-permissive license (GPL, AGPL, custom).
  - Size > 5 MB or transitive tree > 50 packages.
- **Typical trade-offs:** speed vs supply-chain risk; reuse vs lock-in; downstream maintenance.

### 5. `paid_service` — Paid service

**This workspace's tier:** `{{TIER}}`
**Mode applied:** `{{TIER_PAID_MODE}}` (monthly limit: R$ {{TIER_PAID_THRESHOLD_BRL}})

SaaS service with a recurring cost.

- **Signals:**
  - Paid plan required above the free tier.
  - Estimated monthly cost > R$ {{TIER_PAID_THRESHOLD_BRL}}.
  - Significant vendor lock-in (data not exportable).
  - Auto-scale with a cost floor.
- **Typical trade-offs:** dev velocity vs recurring OPEX; data sovereignty vs convenience; cost predictability vs flexibility.

### 6. `irreversible` — Irreversible decision

**Mode in this tier:** `hard` (always)

Operation that destroys data or history in a non-recoverable way.

- **Signals:**
  - `DROP TABLE`, `TRUNCATE`, destructive schema migration (drop column with data).
  - `git push --force` on a shared branch.
  - Credential rotation without a grace window.
  - Hard-delete of records without prior soft-delete.
- **Typical trade-offs:** simplicity vs reversibility; space/perf vs auditability; now vs undo window.

### 7. `over_eng` — Over-engineering

**This workspace's tier:** `{{TIER}}`
**Mode applied:** `{{TIER_OVER_ENG_MODE}}`

Over-engineering signal in design.

- **Signals:**
  - 3+ new abstraction layers to solve 1 concrete problem.
  - Enterprise patterns (factories, mediators, brokers) without demonstrated need.
  - Preventive generalization without a second real use case.
  - Configurability with no second consumer.
- **Typical trade-offs:** future flexibility vs readability cost; YAGNI vs anticipatory reuse.

### 8. `pii` — PII / sensitive data

**This workspace's tier:** `{{TIER}}`
**Mode applied:** `{{TIER_PII_MODE}}`

Handling of personal or sensitive data.

- **Signals:**
  - Schema includes CPF, RG, e-mail, phone, health data.
  - Logs potentially leak PII in plain text.
  - Sharing between services without obfuscation/encryption.
  - Indefinite retention without a declared policy.
- **Typical trade-offs:** UX vs LGPD compliance; debug vs data minimization; perf vs encryption.

### 9. `prod_migration` — Production migration

**Mode in this tier:** `hard` (always)

Schema migration running against production data.

- **Signals:**
  - Migration touches a table with > 100k rows.
  - Blocking DDL in RDBMS (ALTER TABLE with rewrite).
  - Type/constraint change that invalidates existing rows.
  - No pre-agreed maintenance window.
- **Typical trade-offs:** zero-downtime vs simplicity; incremental backfill vs single shot; rollback plan vs forward-only.

### 10. `adr_drift` — ADR drift

**Mode in this tier:** `hard` (always)

Plan diverges from an existing ADR.

- **Signals:**
  - Approved ADR declares stack X, plan proposes Y.
  - Architectural decision touches a component with an active ADR.
  - Old ADR "Rationale" is still valid — but plan ignores it.
  - ADR has not been formally superseded.
- **Typical trade-offs:** keep ADR (cost of complying) vs supersede (cost of re-justifying) vs hybrid coexistence (cost of divergence).

### 11. `workspace_corrupt` — ICM workspace corrupted

**Mode in this tier:** `hard` (always)

L1/L2 inconsistent or critical state files damaged. Stops execution and requests recovery.

- **Signals:**
  - L1 YAML fails validation (`validate_state.py` exits 1).
  - L0 `icm_skill_version` missing or unparseable.
  - `profile_effective_hash` mismatch between L0 and L1.
  - Required stage output file missing while L1 says `COMPLETED`.
- **Typical trade-offs:** run Recovery Wizard (repair) vs abandon workspace vs spawn new workspace from last known good state.
- **Note:** always fires `hard` and invokes Recovery Wizard directly. No free A/B/C menu — wizard presents its own repair options.

### 12. `profile_mismatch` — Inconsistent profile/tier

**Mode in this tier:** `hard` (always)

Profile/tier chosen at bootstrap does not match the actual scope of the task in progress.

- **Signals:**
  - Tier `experimental` but plan includes production data.
  - Profile `technical_article` but task involves code running in CI.
  - `ml_project / tool` but plan requires formal peer-review.
  - Scope grew beyond what was declared in L0.
- **Typical trade-offs:** change profile/tier (regenerates matrix, re-validation cost) vs spawn a new workspace with the correct profile vs reduce the scope of the current task.

### 13. `ambiguous_feedback` — Low-confidence human visual feedback (v3.6.0)

**Mode in this tier:** `hard` (always)

Human feedback during preview loop is ambiguous — agent does NOT speculate and proceed.

- **Signals:**
  - Human says "it looks weird" or "something is off" without specifying what.
  - Multiple components referenced without clear target.
  - Feedback contradicts previous feedback from same session.
  - Response is a single word or emoji without technical content.
- **Typical trade-offs:** ask targeted clarifying question (A) vs revert last change and show before/after (B) vs skip this iteration and re-raise after next change (C).

### 14. `design_system_cascade` — Token change exceeds cascade threshold (v3.6.0)

**Mode in this tier:** `hard` (always)

A single design token change affects more than `design_cascade_threshold` components.

- **Signals:**
  - Color, spacing, or typography token change touches ≥ threshold components (default 5).
  - Preview shows widespread visual changes from a single token edit.
  - `git diff --stat` shows > threshold component files changed.
- **Typical trade-offs:** proceed with cascade (acknowledge and verify each) vs scope-limit the change to a subset vs redesign token architecture to reduce coupling.

### 15. `runtime_cleanup_failed` — Pre-exit stage 08 runtime cleanup (v3.7.0)

**Mode in this tier:** `hard` (always — strict universal, all tiers).

Applicable ONLY in stage 08 (exit A close, B restart, C spawn). Trigger:

- Runtime checklist (`scripts/runtime-status.py`) detects a non-clean category (live dev server, dirty branch, active container, etc.) and the human refuses to resolve now or cancels mid-confirmation.
- Cleanup command returns an error (port in use, branch protected, docker daemon down).
- Human abandons the checklist without completing all 6 categories.

Unlike other stop points: does NOT escalate architecture, escalates runtime state that requires human intervention outside ICM (kill process, manually delete branch, stop container). Session pauses, human resolves in terminal, resumes stage 08.

- **Signals:**
  - `runtime-status.py --exit-code` returns 1 (some category dirty).
  - `runtime-registry.py purge-dead` fails.
  - Human answers "n" in the runtime checklist mini-confirm.
- **Typical trade-offs:** resolve now (interrupt flow) vs defer cleanup (workspace becomes inconsistent; recovery wizard detects later) vs cancel stage 08 (status reverts to `COMPLETED_AWAITING_HUMAN`, resume when ready).
- **Specific A/B/C menu** (does not use the standard template §4):
  ```
  Runtime cleanup failed in category(ies): <list>

  [a] resolved manually, resume checklist
  [b] skip category + continue exit <A|B|C> (workspace becomes inconsistent; recovery detects later)
  [c] cancel stage 08 (status reverts to COMPLETED_AWAITING_HUMAN; resume when ready)
  ```

---

## 3. Severity modes

| Mode | Behavior |
|---|---|
| `warning` | Agent warns in prose in the session output, continues work with a note; **does not block**. Does not update L1 `status`. Optional append to `history` as `event: stop_point_warning`. |
| `hard` | Agent stops, writes A/B/C menu (template §4), updates L1 `status: BLOCKED_STOP_POINT`, waits for human response. |
| `hard+DPO` | `hard` + explicit recommendation "involve DPO/legal before proceeding" in the menu. Status same. |

---

## 4. Standard A/B/C menu template

Trigger: agent at any stage upon detecting a stop point with mode `hard` or `hard+DPO`.

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

Waiting for response. L1 updated: `status: BLOCKED_STOP_POINT`.
```

In `hard+DPO` mode, add an extra line right after the recommendation:

> **LGPD notice:** involve DPO/legal before proceeding. A technical decision does not replace legal validation.

---

## 5. L1 update upon trigger

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
4. Set `next_action: "waiting for human response to A/B/C menu"`.
5. Atomic commit (`workspace: stop_point <id> triggered`). Pre-commit hook validates L1↔outputs atomicity.

Status enum and schema come from `references/state-machine-schema.md` (in the skill).

---

## 6. Human response — resume protocol

Human replies in chat with `A`, `B`, `C`, or free text. Session:

1. Reads response.
2. Append to `history`:
   ```yaml
   - at: "<ISO 8601 UTC>"
     event: "stop_point_resolved"
     stop_point_id: "<id>"
     resolution: "A" | "B" | "C" | "custom"
     note: "<summary of human decision>"
   ```
3. Set `status: IN_PROGRESS`.
4. Updates `last_action`/`next_action` according to choice.
5. Continues work according to chosen option.
6. **ADR spawn:** if the choice implies an architectural decision (typical in stops 1, 2, 3, 6, 10), spawn `docs/decisions/NNNN-<slug>.md` — **only in stage 02 design**. In other stages, annotate in the `decisions-pending.md` of the next workspace's stage 02 or record as tech debt.

---

## 7. Custom stop points (this workspace)

{{CUSTOM_STOP_POINTS_BLOCK}}

---

## 8. Stages where stop points are expected

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
| 08 feedback_intake | n/a (stage 08 is analysis + A/B/C iteration decision; stops detected here roll over to the next workspace via exit C) |

The table is advisory. Any stage can trigger any stop if the signal appears — there is no enforced whitelist.
