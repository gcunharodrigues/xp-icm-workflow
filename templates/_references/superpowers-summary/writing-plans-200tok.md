---
name: writing-plans-200tok
source_skill: superpowers:writing-plans
source_version: "5.0.0"
purpose: Convert approved spec into bite-sized implementation plan executable by context-free agent.
---

# Writing Plans — 200tok summary

## When to apply
- After spec approved in brainstorming, before touching code.
- Multi-step task to be executed by another agent/session.
- Target engineer can code but doesn't know our codebase or domain.

## How to apply
1. Scope check: if spec covers independent subsystems, suggest breaking into separate plans (1 plan = 1 testable unit).
2. Map file structure before tasks: each file with single responsibility, clear boundaries.
3. Structure mandatory header: Goal (1 sentence), Architecture (2–3 sentences), Tech Stack.
4. Decompose into bite-sized tasks (2–5 min each): Write failing test → Run (expect FAIL) → Implement minimum → Run (expect PASS) → Commit.
5. Each task lists: exact files (Create/Modify with line ranges/Test), complete code in plan (not "add validation"), exact commands with expected output.
6. Save to `docs/superpowers/plans/YYYY-MM-DD-<feature>.md`.
7. Review loop by chunks (≤1000 lines) with plan-document-reviewer until approved.

## Success signals
- TDD, DRY, YAGNI respected; frequent commits.
- Absolute paths, copy-paste commands, embedded code — zero ambiguity.

## Escape hatch
If plan exceeds 1 chunk or requires formal subagent review → invoke full `superpowers:writing-plans`.
