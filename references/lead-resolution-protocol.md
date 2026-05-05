# Lead Resolution Protocol — Canonical (v3.9.0)

> **Version:** v3.9.0
> **Skill:** `xp-icm-workflow`
> **Consumer stage:** `04_implementation_waves` (step 9 — lead-resolution tier)
> **Purpose:** canonical document for the lead-resolution tier — 3 buckets (B1 REWRITE_SPEC, B3 DIRECT_IMPL, B4 VOID_TASK) activated when the per-task loop exhausts its cap (3 retries) OR convergence trip OR catastrophic detected. Lead = last resort "this is very bad".

## Summary (1 paragraph)

The standard per-task loop (writer subagent → L2 forensic+ → L3 critic → diagnose) has a cap of 3 retries. When it exhausts OR converges without a fix OR catastrophic is detected, control escalates to the **wave lead**. Lead reads `output/wave-N/task-<slug>-diagnose.md` (rendered by `scripts/lead-diagnose.py`) which recommends a bucket. Lead may override. 3 buckets available: **B1 REWRITE_SPEC** (lead rewrites the task spec to be more rigorous, 1 final writer spawn), **B3 DIRECT_IMPL** (lead writes code directly — passes L2+L3 identically), **B4 VOID_TASK** (declares the task void with rationale + plan update + wave-plan recalculate). Cap 1 attempt per bucket. Failure → `BLOCKED_ERROR`.

## Trigger conditions

The per-task loop enters lead-resolution tier when **any** of the 3 conditions is active:

| # | Condition | Detection | Bucket hint from diagnose |
|---|-----------|-----------|--------------------------|
| T1 | Cap 3 retries exhausted | `task_attempts >= 3` and last critic = REJECT | B1 (default) |
| T2 | Convergence trip | Jaccard(concerns_round_N, concerns_round_N-1) ≥ 0.7 (BLOCKING+MAJOR set) | B1 (ambiguous spec) or B3 (override) |
| T3 | Catastrophic detected | `lead-diagnose.py` pre-check: tests broken outside scope OR build globally broken OR scope creep > 5× OR repo CI red | B3 (default), B4 (override) |

Detection is deterministic in `scripts/lead-diagnose.py`. Lead **does not** decide the trigger — the script renders diagnose.md with condition + hint; lead only chooses the bucket (accepts hint OR overrides).

## Buckets

### B1 — REWRITE_SPEC

**Activation:** original spec is ambiguous/insufficient; loop converges because the writer lacks a clear anchor.

**Lead action:**
1. Reads critic concerns (triplets) accumulated across rounds 1-3 of the task.
2. Identifies the pattern: ambiguous acceptance criterion? Undeclared ADR conflict? Implicit edge case?
3. Rewrites the task in plan.md with:
   - More specific VALIDATION bullets (test names mandatory)
   - Additional OUT OF SCOPE bullets covering observed pitfalls
   - Prescriptive HOW bullets (required path/lib/pattern)
   - `Estimated lines` recalibrated if it was an underestimate
4. Commits plan update on the wave branch.
5. Spawns 1 final writer with the new brief (same model as round 3 OR upgrade to ceiling if tier allows).
6. Output passes L2 forensic+ + L3 critic identically to a normal writer. APPROVE → merge. REJECT → escalate B4 (no additional retry).

**Do not:**
- Lead **does not** write code in B1.
- Lead **does not** give inline hints to the writer (anti-sycophancy preserved).

### B3 — DIRECT_IMPL

**Activation:** lead assesses that the writer will not converge even with a better spec (catastrophic OR fine multi-file coordination OR subtle algorithm); or T3 trigger.

**Lead action:**
1. Reads critic concerns + diagnose.md.
2. Lead writes code directly (same vertical TDD cycle: tracer-first → 1 test → 1 impl → repeat).
3. Output **is NOT auto-approved** — passes L2 forensic+ + L3 critic identically.
4. APPROVE → merge. REJECT → escalate B4.

**Constraints:**
- Lead operates under the same `pick-model.py` ceiling for the tier (cannot run Opus in tier=experimental).
- Lead commits in a dedicated branch `wave-<NNN>-<N>/<slug>-lead-resolved` (suffix `-lead-resolved` distinguishes audit).
- L1 frontmatter gets `last_action: "wave_<N> task_<slug> bucket_B3 in_progress"`.

### B4 — VOID_TASK

**Activation:** task is unmergeable (B1+B3 failed OR catastrophic + real ADR conflict OR invalid scope discovered during implementation).

**Lead action:**
1. Reads critic concerns + diagnose.md.
2. Identifies concrete rationale (cite ADR conflict OR scope mismatch OR upstream blocker).
3. Rewrites task in plan.md with a new block:

```markdown
### VOIDED — wave <N> attempt <date>
- Reason: <ADR conflict | scope invalid | upstream blocker | other>
- Evidence: <file:line OR critic concern OR external constraint>
- Action proposed: <new task slug OR defer to v.NEXT OR remove from scope>
```

4. Commits plan update.
5. Triggers `wave-planner-script.py --recalculate` to re-derive the DAG without the voided task.
6. Wave continues with remaining tasks.
7. L1 history append: `event: task_voided, slug: <slug>, bucket: B4, reason: <text>`.

## Cap per bucket

**Hard cap: 1 attempt per bucket per task.**

| Sequence | Behavior |
|----------|----------|
| B1 fail | escalate B3 |
| B3 fail | escalate B4 |
| B4 declared | task voided — terminal, no retry |
| B1 → B3 → B4 all exhausted | `BLOCKED_ERROR error_type: lead_resolution_all_buckets_failed` |

Lead may skip buckets (skip B1 → start B3 directly if diagnose recommends it). Cannot revisit a used bucket (B3 → B1 is invalid — lead already has all necessary context; revisiting = infinite loop).

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

## Bucket recommendation
- bucket: <B1 | B3 | B4>
- rationale: <1-3 lines>

## Surgical brief (if B1)
<concise brief: top-3 concerns + acceptance delta vs original spec>
```

Lead may override the bucket — records the choice in `output/wave-N/task-<slug>-lead-decision.md`:

```markdown
# Lead decision — task <slug>

- diagnose_recommended: <B1|B3|B4>
- lead_chose: <B1|B3|B4>
- rationale: <why override OR why accept>
- bucket_attempt_started_at: <ISO 8601>
```

## Audit trail (consumed by stage 05)

Wave-summary.md gains a dedicated section:

```markdown
## Lead resolutions

| Task | Trigger | Bucket recommended | Bucket chosen | Result |
|------|---------|--------------------|---------------|--------|
| <slug> | T2 convergence | B1 | B1 | merged |
| <slug2> | T3 catastrophic | B3 | B3 | escalated B4 |
| <slug3> | T1 cap exhausted | B1 | B3 | merged |
```

Stage 05 audit (sub-step "audit lead resolutions") reads the table and applies meta-checks:

| Bucket | Meta-check | Fail action |
|--------|------------|-------------|
| B1 | Did spec rewrite tighten OR loosen constraints? Loosening without evidence = fail | `BLOCKED_ERROR error_type: lead_resolution_audit_failed` |
| B3 | Is lead diff coherent with critic concerns? Did lead resolve the real issue OR just silence the critic? | `BLOCKED_ERROR error_type: lead_resolution_audit_failed` |
| B4 | Does rationale cite a real ADR conflict OR concrete upstream blocker? Vague reason = fail | `BLOCKED_ERROR error_type: lead_resolution_audit_failed` |

Audit is deterministic regex + structure (zero LLM cost).

## L1 frontmatter during lead-resolution

New status: `LEAD_RESOLUTION_IN_PROGRESS`.

```yaml
status: LEAD_RESOLUTION_IN_PROGRESS
sub_stage: "04_wave_<N>_in_progress"  # keeps wave; resolution is a sub-state
last_action: "wave <N> task <slug> bucket <B1|B3|B4> in_progress"
```

History event when bucket starts:
```yaml
- at: <ISO 8601>
  event: lead_resolution_started
  slug: <task-slug>
  bucket: <B1|B3|B4>
  trigger: <T1|T2|T3>
```

## Catastrophic detector — signals

Pre-check in `scripts/lead-diagnose.py` before Jaccard:

| Signal | Trigger condition | Bucket hint |
|--------|-------------------|-------------|
| Tests broken outside task scope | `git diff --name-only` shows test files NOT declared in `files_touched` AND global suite is red | B3 |
| Build globally broken | `_config/profile-effective.yaml:build_command` exit ≠ 0 | B3 |
| Massive scope creep | forensic+ Check 2: `files_outside_declared > 5` | B3 default, B4 override |
| Repo CI completely red | `git log` shows commits that broke >50% of the global test suite | B3 |

Catastrophic detected → bypass cap 3, escalate to lead immediately (no surgical retry, no waiting for Jaccard).

## Edge cases

| EC | Scenario | Behavior |
|----|----------|----------|
| EC1 | Wave-planner DAG invalid after B4 (voided task was depended_by) | wave-planner re-derives DAG; dependent tasks treated as `BLOCKED_HITL` awaiting human OR cascade B4 |
| EC2 | Lead-resolution task → critic ABSTAIN | counts as REJECT, lead escalates to next bucket |
| EC3 | B3 lead writer crash (Agent tool fail) | retry 1×; 2nd failure → escalate B4 mandatory |
| EC4 | B1 spec rewrite reduces VALIDATION criteria | stage 05 audit detects loosen → `BLOCKED_ERROR` |
| EC5 | B4 without concrete rationale (rushed lead) | stage 05 audit detects vague reason → `BLOCKED_ERROR` |
| EC6 | Concurrent lead-resolution (wave has 2+ tasks in buckets) | OK — sequential per task; wave reviewer waits for all to resolve before merge |
| EC7 | Lead chose different bucket from recommendation but did not write lead-decision.md | wave-reviewer detects missing lead-decision.md → `BLOCKED_ERROR error_type: lead_decision_missing` |

## Cross-references

- Critic protocol: `references/critic-protocol.md`
- Forensic+ protocol: `references/forensic-plus-protocol.md`
- 14-step pipeline: `references/wave-execution-protocol.md` step 9-10
- Diagnose script: `scripts/lead-diagnose.py`
- Pick model: `scripts/pick-model.py`
- L2 runtime: `templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl`
- L2 stage 05 audit: `templates/workspace/stages/05_verification/CONTEXT.md.tpl`
- State machine: `references/state-machine-schema.md` (status `LEAD_RESOLUTION_IN_PROGRESS`; error_types `lead_resolution_audit_failed`, `lead_resolution_all_buckets_failed`, `lead_decision_missing`)
- Recovery wizard: `references/recovery-wizard.md` (type `LEAD_RESOLUTION_STALE`)
