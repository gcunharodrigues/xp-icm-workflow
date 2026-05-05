---
name: brainstorming-200tok
source_skill: superpowers:brainstorming
source_version: "5.0.0"
purpose: Transform raw idea into approved design before any implementation.
---

# Brainstorming — 200tok summary

## When to apply
- Before creating feature, component, or changing behavior — always, even in "simple" projects.
- When spec doesn't exist yet or requirements are vague.
- Hard-gate: Do NOT write code or invoke implementation skill until design is approved.

## How to apply
1. Explore project context (files, docs, recent commits).
2. If scope covers independent subsystems, decompose before detailing.
3. Ask clarification questions **one at a time**, multiple-choice when possible. Focus: purpose, constraints, success criteria.
4. Propose 2–3 approaches with trade-offs and explicit recommendation.
5. Present design in sections (architecture, components, data flow, error handling, tests); incremental approval per section.
6. Save spec to `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` and commit.
7. Transition **only** to `writing-plans` (never directly to implementation).

## Success signals
- Design document has units with clear boundaries and well-defined interfaces.
- User approved each section; YAGNI applied (no speculative features).
- Spec committed before any line of code.

## Escape hatch
If design requires visual mockups, multiple subsystems, or formal review loop → invoke full `superpowers:brainstorming`.
