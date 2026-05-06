---
name: requesting-code-review-200tok
source_skill: superpowers:requesting-code-review
source_version: "5.0.0"
purpose: Lead requests review of subagent output before accepting merge — catches problems early, before they cascade.
---

# Requesting Code Review — 200tok summary

## When to apply
- In stage 04 (implementation waves) of ICM — the L3 critic provides orthogonal review, lead evaluates subagent output after stage 05 is green.
- After each task in subagent-driven development; before merge to main.
- Optional: when stuck (fresh perspective), before a large refactor.

## How to apply
1. Capture SHAs: `BASE_SHA=$(git rev-parse HEAD~1)` and `HEAD_SHA=$(git rev-parse HEAD)`.
2. Load the subagent's `references/4-block-contract-template.md` as the spec of what should have been delivered.
3. Run reviewer (subagent or structured self-review) covering 7 dimensions: correctness, tests, security, performance, readability, contract adherence, risks.
4. Record `review-report.md` in the stage workspace with:
   - Strengths (what is good)
   - Issues classified **P0** (blocks merge), **P1** (fix before proceeding), **P2** (important but not blocking), **P3** (note for later)
   - Verdict: APPROVED / FIX-LOOP / REJECTED
5. If P0/P1 exist → trigger fix loop (subagent returns to stage 04 with `review-report.md`).

## Success signals
- `review-report.md` references specific commits (SHA + lines).
- Each issue has severity, technical justification, and suggested fix.
- Explicit verdict; no ambiguity about "is it ready?".

## Escape hatch
Trivial change (typo, doc-only) → review may be inline in the commit message. But: if it touches production code, always go through formal review — do not skip because "it's simple".

See `references/subagent-protocol.md` for lead↔subagent handoff.
