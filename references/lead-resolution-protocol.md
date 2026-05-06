# Lead Resolution Protocol — Canonical (v4.0)

> **Version:** v4.0
> **Skill:** `xp-icm-workflow`
> **Consumer stage:** `04_implementation_waves` (step 9 — lead-resolution tier)
> **Purpose:** canonical document for the lead-resolution tier — 2 options (RETRY or VOID) activated when the per-task loop exhausts its cap (3 retries) OR convergence trip OR catastrophic detected.

## Summary (1 paragraph)

The standard per-task loop (writer subagent → L2 forensic+ → L3 critic → diagnose) has a cap of 3 retries. When it exhausts OR converges without a fix OR catastrophic is detected, control escalates to the **wave lead**. Lead reads `output/wave-N/task-<slug>-diagnose.md` (rendered by `scripts/lead-diagnose.py`) which recommends RETRY or VOID. Lead may override. 1 attempt per option. RETRY fail → VOID. VOID is terminal.

## Trigger conditions

The per-task loop enters lead-resolution tier when **any** of the 3 conditions is active:

| # | Condition | Detection | Action hint from diagnose |
|---|-----------|-----------|--------------------------|
| T1 | Cap 3 retries exhausted | `task_attempts >= 3` and last critic = REJECT | RETRY (default) |
| T2 | Convergence trip | Jaccard(concerns_round_N, concerns_round_N-1) ≥ 0.7 (BLOCKING+MAJOR set) | RETRY or VOID |
| T3 | Catastrophic detected | `lead-diagnose.py` pre-check: tests broken outside scope OR build globally broken OR scope creep > 5× OR repo CI red | VOID (default) |

Detection is deterministic in `scripts/lead-diagnose.py`. Lead **does not** decide the trigger — the script renders diagnose.md with condition + action hint; lead only chooses RETRY or VOID (accepts hint OR overrides).

## Actions

### RETRY

**Activation:** spec is ambiguous/insufficient; writer can succeed with better guidance.

**Lead action:**
1. Reads critic concerns (triplets) accumulated across rounds 1-3 of the task.
2. Identifies the pattern: ambiguous acceptance criterion? Undeclared ADR conflict? Implicit edge case?
3. Rewrites task in plan.md with specific VALIDATION bullets, additional OUT OF SCOPE, prescriptive HOW.
4. Commits plan update on workspace branch.
5. Spawns 1 final writer with new brief (same model as round 3, or upgrade if tier allows).
6. Output passes L2 forensic+ + L3 critic identically to normal writer.
7. APPROVE → merge. REJECT → VOID (no additional retry).

**Do not:** lead does NOT write code inline. No hints to writer (anti-sycophancy preserved).

### VOID

**Activation:** task is unmergeable — spec invalid, ADR conflict, upstream blocker, or RETRY failed.

**Lead action:**
1. Reads critic concerns + diagnose.md.
2. Identifies concrete rationale (cite ADR conflict OR scope mismatch OR upstream blocker).
3. Rewrites task in plan.md with VOIDED block:

```markdown
### VOIDED — wave <N> attempt <date>
- Reason: <ADR conflict | scope invalid | upstream blocker | other>
- Evidence: <file:line OR critic concern OR external constraint>
- Action proposed: <new task slug OR defer to v.NEXT OR remove from scope>
```

4. Commits plan update.
5. Re-runs `wave-planner-script.py` with updated plan.md to re-derive DAG without voided task.
6. Wave continues with remaining tasks.
7. L1 history append: `event: task_voided, slug: <slug>, reason: <text>`.

## Cap

**Hard cap: 1 RETRY → VOID (terminal).**

| Sequence | Behavior |
|----------|----------|
| RETRY | Spawn 1 final writer with revised spec |
| RETRY fail → VOID | Task voided — terminal, no further retry |
| RETRY + VOID both exhausted | `BLOCKED_ERROR error_type: lead_resolution_failed` |

Lead may skip RETRY and go directly to VOID if diagnose recommends it.

## diagnose.md schema

`scripts/lead-diagnose.py` renders `output/wave-N/task-<slug>-diagnose.md` each time a trigger condition activates:

```markdown
# Diagnose — task <slug> (wave <N>)

## Trigger
- condition: <T1_cap_exhausted | T2_convergence_trip | T3_catastrophic>
- detected_at: <ISO 8601>
- attempts_so_far: <int>

## Critic concerns clustered (rounds 1-N)
| Round | BLOCKING | MAJOR | Jaccard vs prev |
|-------|----------|-------|-----------------|
| 1 | <count> | <count> | n/a |
| 2 | <count> | <count> | <0.0-1.0> |
| 3 | <count> | <count> | <0.0-1.0> |

## Recurring claims (Jaccard ≥ 0.5 across rounds)
- <claim text> — appeared rounds: <list>, evidence: <files>

## Catastrophic signals (if T3)
- <signal name>: <evidence>

## Action recommendation
- action: <RETRY | VOID>
- rationale: <1-3 lines>

## Surgical brief (if RETRY)
<concise brief: top-3 concerns + acceptance delta vs original spec>
```

Lead may override — records choice in `output/wave-N/task-<slug>-lead-decision.md`:

```markdown
# Lead decision — task <slug>

- diagnose_recommended: <RETRY|VOID>
- lead_chose: <RETRY|VOID>
- rationale: <why override OR why accept>
```

## Audit trail (consumed by stage 05)

Wave-summary.md gains a dedicated section:

```markdown
## Lead resolutions

| Task | Trigger | Action | Result |
|------|---------|--------|--------|
| <slug> | T2 convergence | RETRY | merged |
| <slug2> | T3 catastrophic | VOID | voided |
```
