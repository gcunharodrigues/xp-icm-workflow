---
name: subagent-driven-development-200tok
source_skill: superpowers:subagent-driven-development
source_version: "5.0.0"
purpose: Execute plan with a fresh subagent per task and two-step review (spec then quality).
---

# Subagent-Driven Development — 200tok summary

## When to apply
- There is a written implementation plan, independent tasks, execution in the same session.
- Fits stage 04 `implementation_waves` when the Wave Planner has released subagents. See `references/subagent-protocol.md` for local rules (Agent tool, isolation, 4-block contracts).

## Principle
Fresh subagent per task + two-step review (spec compliance → code quality) = high quality, fast iteration.

## How to apply
1. Read the plan once, extract the full text of each task + context, create TodoWrite.
2. For each task:
   a. Dispatch **implementer subagent** with full text + context. Answer questions before it starts.
   b. Implementer does TDD, tests, commits, self-review, returns status (DONE / DONE_WITH_CONCERNS / NEEDS_CONTEXT / BLOCKED).
   c. Dispatch **spec reviewer** — confirms code matches the spec, nothing missing or extra. Loop until OK.
   d. Dispatch **code quality reviewer** — only after spec OK. Loop until approved.
   e. Mark task as complete.
3. After all tasks, dispatch **final reviewer** over the entire implementation.

## Model selection
Use the cheapest model that handles the role: mechanical → cheap; integration → standard; architecture/review → more capable.

## Success signals
- Each task went through separate spec review and quality review.
- Review loops closed (no "close enough").
- No parallel implementation subagents on the same task.

## Red flags
Skipping review, running code quality before spec OK, having the subagent read the plan (pass full text), accepting open issues to the next task.

## Escape hatch
If complexity exceeds this summary (non-trivial multi-agent coordination, branch conflicts, ambiguous plan) → invoke formal `superpowers:subagent-driven-development`.
