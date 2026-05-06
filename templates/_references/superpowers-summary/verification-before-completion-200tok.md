---
name: verification-before-completion-200tok
source_skill: superpowers:verification-before-completion
source_version: "5.0.0"
purpose: Prove work is complete with fresh evidence before any success claim.
---

# Verification Before Completion — 200tok summary

## When to apply
- Before any claim of "done", "passes", "works", "fixed".
- Before commit, PR, merge, or marking task complete.
- At stage 04 (implementation waves) of ICM — verification runs as inline CI+E2E gates after each wave — generates `verification-report.md` in stage workspace.
- When receiving subagent success report — verify diff, don't trust reports.

## How to apply
1. **IDENTIFY** command that proves the claim (test suite, build, lint, smoke).
2. **RUN** command complete and fresh this turn (don't reuse previous output).
3. **READ** entire output: exit code, failure count, warnings.
4. **VERIFY** if output confirms the claim — if not, report actual status.
5. **RECORD** evidence in `verification-report.md` (command + output + verdict).
6. Regression test requires TDD red-green cycle: revert fix, see fail, restore, see pass.

## Success signals
- `verification-report.md` cites exact command and literal output (not paraphrased).
- Exit code 0 confirmed for each gate (test, build, lint).
- Plan requirements checked line-by-line; gaps explicit when they exist.

## Red flags — STOP
- Words "should", "probably", "seems to", "should pass".
- Expression of satisfaction ("Great!", "Perfect!") without running command.
- Trust "agent reported success" without checking diff/VCS.
- "Linter passed" used as proof of build (linter doesn't compile).

## Escape hatch
If gate has no automated command (e.g., visual UX review) → document in `verification-report.md` the manual method used and who validated. Never skip recording.
