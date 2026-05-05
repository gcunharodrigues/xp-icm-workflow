---
name: dispatching-parallel-agents-200tok
source_skill: superpowers:dispatching-parallel-agents
source_version: "5.0.0"
purpose: Dispatch concurrent agents when there are 2+ independent tasks with no shared state.
---

# Dispatching Parallel Agents — 200tok summary

## When to apply
- 2+ failures/tasks in independent domains (files, subsystems, distinct bugs).
- Each problem understandable without context from the others.
- No shared state — agents do not edit the same files or compete for resources.

## When NOT to use
- Related failures (fixing one may fix others) — investigate together.
- Exploratory debugging with no clear domain.
- Refactor that touches shared code.

## How to apply
1. Identify independent domains — group by "what is broken".
2. For each domain, compose a prompt with: **specific scope** (1 file/subsystem), **clear objective** (success criterion), **constraints** (e.g. "do not alter production code"), **expected output** (root cause summary + changes).
3. Dispatch in parallel in the same message (multiple simultaneous Task calls).
4. Integrate: read each summary, check for conflicts, run full suite, spot-check.

## Success signals
- Agents return independent summaries without editing the same files.
- Full suite green after integration; zero conflicts.
- Total time ≈ slowest agent's time (not sum).

## Common mistakes
- Vague prompt ("fix everything") → scope lost.
- No constraints → agent refactors beyond what is needed.
- No output specified → impossible to verify.

## Escape hatch
If domains turn out to be coupled or require orchestration → invoke full `superpowers:dispatching-parallel-agents`.
