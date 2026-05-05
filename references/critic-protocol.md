# Critic Protocol — Canonical (v3.9.0)

> **Version:** v3.9.0
> **Skill:** `xp-icm-workflow`
> **Consumer stage:** `04_implementation_waves` (step 8c — L3 critic, always, all tiers)
> **Purpose:** canonical document for the L3 orthogonal LLM critic — fresh-context, anti-sycophancy, triplet-output. Runs on every AFK task after forensic+ extended pass (L2). Binary output APPROVE/REJECT consumed by lead-diagnose.

## Summary (1 paragraph)

L3 critic is a second opinion from a distinct model (intra-Claude — Sonnet ↔ Opus mix), spawned by the lead via Agent tool with fresh context (zero session memory from the writer). Runs **always**, on all tiers, after forensic+ extended (L2) has approved. Receives a lean brief: task spec (4-block) + full diff + acceptance criteria. Output is a binary decision (APPROVE | REJECT) accompanied by triplets `(claim, file:line, counterexample)` when REJECT. Critic model = `TIER_CEILING[tier]` always. Expected token budget ~3-8k input + 0.5-2k output per task; cost amortized against the forensic+ deterministic gate (zero tokens).

## Why an orthogonal critic

Self-grading by the same writer model suffers documented bias:
- Huang et al. ICLR 2024 — sycophancy bias ~88% Claude Code autonomous (auto-approval)
- arxiv 2510.11822 — asymmetric agreeableness (models yield more when challenged)
- arxiv 2509.16533 — sycophancy under rebuttal (88% flip rate Claude)

Forensic+ (L2) is deterministic regex git-only — immune to sycophancy but only catches structural fraud (assertion count, declared files, scope creep, TODO). It does not catch:
- Wrong logic with tests passing coincidentally
- ADR violation via a disguised import
- Absent edge case coinciding with a test lacking coverage
- Refactor that changes contract without updating callers

L3 intra-Claude critic (writer = Sonnet, critic = Opus tier ceiling) covers the residual semantic gap. Accepts ~5-10% family blindspot (same family) — stage 06 human review + stage 08 feedback compensate downstream.

## Spawn — who invokes

Wave lead invokes via Agent tool:

```python
Agent(
    description="L3 orthogonal critic task <slug>",
    subagent_type="general-purpose",
    model="<critic_model_from_pick_model_py>",
    isolation="worktree",  # optional; may reuse writer worktree for read-only
    prompt=render_critic_prompt(task_slug, wave_num),
)
```

No Python script wrapper — Agent tool is the scaffold. Canonical prompt template at `templates/critic-prompt.md` (rendered with slug + wave + diff + spec).

## Anti-sycophancy prompt — principles

Critic prompt is **hardcoded** (does not derive from plan.md, no room for the writer to "convince" it). Critic does not see retry history, writer arguments, or previous diagnose output. It sees only:

1. Original task spec (4-block + acceptance criteria + applicable ADRs + lessons)
2. Full task diff (`git diff BASE...wave-<NNN>-<N>/<slug> -- <files_touched>`)
3. Test results (raw test runner output, not a summary)

Hardcoded clauses in the prompt template:

```
You are an independent auditor. You do not know who wrote the code.
Your role is to REJECT changes that do not meet acceptance criteria or
violate documented constraints. APPROVE is the exceptional path;
REJECT is the default when in doubt.

Do NOT ask for clarification. Do NOT offer constructive alternatives.
Do NOT assume good faith in the code. Every claim must point to a
file:line + concrete counterexample.

If you cannot identify 3+ problems, still review every modified file
line by line — you probably missed something.

Output ONLY the triplet schema. No preamble. No apologies.
No "great work, but...". Direct critique only.
```

## Triplet output schema

Critic output is strict JSON (parseable) — lead-diagnose.py consumes it and clusters it for Jaccard.

```json
{
  "task_slug": "<slug>",
  "wave": <N>,
  "decision": "APPROVE" | "REJECT" | "ABSTAIN",
  "concerns": [
    {
      "claim": "<short 1-line assertion>",
      "evidence": "<file>:<line-start>[-<line-end>]",
      "counterexample": "<input/scenario that breaks the claim>",
      "severity": "BLOCKING" | "MAJOR" | "MINOR"
    }
  ],
  "model": "<claude-haiku-4-5|claude-sonnet-4-6|claude-opus-4-7>",
  "tokens_used": { "input": <int>, "output": <int> }
}
```

| Decision | When | Lead action |
|----------|------|-------------|
| `APPROVE` | no BLOCKING/MAJOR; only MINOR or no concerns | task PASS, proceed to merge |
| `REJECT` | ≥1 BLOCKING or ≥2 MAJOR | lead-diagnose.py → surgical retry OR escalate |
| `ABSTAIN` | critic could not evaluate (truncated diff, insufficient context, infra fail) | lead treats as REJECT — forces retry; 2 consecutive ABSTAINs → `BLOCKED_ERROR error_type: critic_abstain_loop` |

## Severity levels

| Severity | Criterion | Example |
|----------|-----------|---------|
| BLOCKING | violates explicit acceptance criterion OR breaks contract OR security hole | "validate_token accepts invalid signature when exp is absent" |
| MAJOR | relevant edge case not covered OR ADR drift OR perf regression >2× | "O(N²) loop in declared hot path" |
| MINOR | style nit, missing comment, suboptimal naming | "func name `processData` is ambiguous" |

Lead-diagnose only counts BLOCKING + MAJOR for Jaccard convergence trip. MINOR is discarded (noise).

## Tier ceiling — always

Critic model = `TIER_CEILING[tier]` regardless of writer complexity score. Rationale: critic needs capability ≥ writer to be useful; downgrading the critic invalidates the gate.

| Tier | Critic model |
|------|--------------|
| experimental | claude-haiku-4-5 |
| tool | claude-sonnet-4-6 |
| development | claude-opus-4-7 |
| production | claude-opus-4-7 |

`pick-model.py:pick_models(score, tier)` returns `(writer, critic)` tuple; critic always = ceiling. Caps writer ceiling.

## When L3 does NOT run

| Case | Behavior |
|------|----------|
| Task `type: HITL` | skip (human resolves manually) |
| L2 forensic+ HARD violation | skip — diagnose directly (no wasted tokens on code rejected by cheap gate) |
| Task `Conventions extras: doc-only` | skip (nothing to audit semantically in markdown) |
| Wave with 1 task with `skip_cross_task_audit: true` | L3 still runs on the task — flag affects L4 cross-task only |
| Stage 04 sub_stage `04_wave_<N>_lead_resolution_in_progress` | skip during lead bucket B3 retry; L3 runs 1× on lead output |

## Edge cases

| EC | Scenario | Behavior |
|----|----------|----------|
| EC1 | Critic crash (Agent tool fail / quota exhausted) | lead retries 1× with same prompt; 2nd failure → `BLOCKED_ERROR error_type: critic_unavailable` |
| EC2 | Critic JSON malformed | lead parser returns parsing error; critic re-spawned 1×; 2nd failure → treated as ABSTAIN |
| EC3 | Critic disagrees on interpretation of an ambiguous spec | this is the critic's function — REJECT is default. Surgical retry brief must clarify spec |
| EC4 | Diff > 200 LOC | critic still runs; prompt template paginates (50-LOC chunks) with summary header |
| EC5 | Critic agrees with writer (rare "all clear" signal) | APPROVE is legitimate; lead proceeds. Not a red flag if forensic+ passed |
| EC6 | Lead bucket B3 (DIRECT_IMPL) — critic of the lead | same critic protocol; lead writes code, orthogonal critic validates identically to subagent |
| EC7 | Tests passing but critic identifies a bug | REJECT prevails — tests may be insufficient. Triplet evidence + counterexample mandates adding a test on retry |

## Invocation — render_critic_prompt

Render via `templates/critic-prompt.md` with placeholders:

| Placeholder | Source |
|-------------|--------|
| `{{TASK_SLUG}}` | Agent call param |
| `{{WAVE_NUM}}` | param |
| `{{TASK_4BLOCK}}` | parsed from plan.md |
| `{{ACCEPTANCE_CRITERIA}}` | VALIDATION block of the task |
| `{{ADRS_APPLICABLE}}` | metadata `Applicable ADRs` |
| `{{DIFF_COMPLETE}}` | `git diff BASE...wave-<NNN>-<N>/<slug>` |
| `{{TEST_OUTPUT_RAW}}` | stdout from the test runner (last task run) |
| `{{TIER}}` | L1 frontmatter |

## Cross-references

- Lead-resolution canonical: `references/lead-resolution-protocol.md`
- Forensic+ canonical: `references/forensic-plus-protocol.md`
- 12-step pipeline: `references/wave-execution-protocol.md` step 8c
- Pick-model heuristic: `scripts/pick-model.py`
- L2 runtime: `templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl`
- State machine: `references/state-machine-schema.md` (`error_type: critic_unavailable|critic_abstain_loop`)
- Renderable prompt template: `templates/critic-prompt.md`
