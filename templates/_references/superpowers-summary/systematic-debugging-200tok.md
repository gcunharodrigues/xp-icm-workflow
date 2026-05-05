---
name: systematic-debugging-200tok
source_skill: superpowers:systematic-debugging
source_version: "5.0.0"
purpose: Find root cause before any fix; scientific method in four phases.
---

# Systematic Debugging — 200tok summary

## When to apply
- Any bug, failing test, unexpected behavior, build failure, integration problem.
- **Especially** under time pressure, when "a quick fix" seems obvious, or after multiple failed attempts.

## Iron law
No root-cause investigation, no fix. Symptom corrected without cause understood = failure.

## How to apply (4 phases, in order)

1. **Root cause**
   - Read error messages and full stack traces.
   - Reproduce consistently; if it doesn't reproduce, gather more data — do not guess.
   - Check recent changes (git diff, new deps, config).
   - In multi-component systems: instrument each boundary (log input/output/env) before proposing a fix. Identify which layer breaks.
   - Trace data backwards to the origin of the bad value. Fix at the source, not the symptom.

2. **Pattern**
   - Find a similar working example in the codebase.
   - Compare fully (no skimming) with the reference. List every difference.
   - Map dependencies/assumptions.

3. **Hypothesis**
   - Formulate a specific hypothesis in writing ("X is the cause because Y").
   - Test with the smallest possible change, one variable at a time.
   - Did it work? Phase 4. No? New hypothesis — do not stack fixes.

4. **Implementation**
   - Create a failing test that reproduces the issue (use TDD).
   - A single fix addressing the root cause. No "while I'm here".
   - Verify: test passes, nothing else broke.
   - **3+ fixes failed? Stop and question the architecture** with the human — do not attempt a 4th.

## Success signals
Cause explainable in one sentence, test reproducing the bug, minimal fix, remaining tests green.

## Red flags
"Quick fix for now", "it's probably X", multiple simultaneous changes, skipping the test, "one more attempt" after 2 failures.

## Escape hatch
If the case requires deep backward tracing, multi-layer defense-in-depth, or condition-based waiting → invoke formal `superpowers:systematic-debugging` (brings `root-cause-tracing.md`, `defense-in-depth.md`, `condition-based-waiting.md`).
