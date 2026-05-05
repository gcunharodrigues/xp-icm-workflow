---
name: receiving-code-review-200tok
source_skill: superpowers:receiving-code-review
source_version: "5.0.0"
purpose: Subagent receives reviewer feedback with technical rigor, not performative agreement.
---

# Receiving Code Review — 200tok summary

## When to apply
- When fix loop triggers: P0/P1 in `review-report.md` requires return to stage 04.
- When receiving any review, especially if feedback seems confusing or technically questionable.
- Before implementing suggestion — verify before changing.

## How to apply
1. **READ** entire feedback without reacting.
2. **UNDERSTAND** restate each item in your own words; if you can't, ask for clarification **before** implementing any item (items may be related).
3. **VERIFY** against codebase reality: does the suggestion break something? is there a reason for current implementation? works on all platforms?
4. **EVALUATE** YAGNI: grep for real usage before "implement properly".
5. **RESPOND** with technical reasoning or grounded pushback — never "You're absolutely right!", "Great point!", "Thanks for catching that!".
6. **IMPLEMENT** one item at a time, test each, no regressions.
7. Note fixes in the same `review-report.md` (subsection "fixes applied") and re-run verification before returning to reviewer.

## Success signals
- Each P0/P1 item has fix with commit SHA referenced.
- Pushback (when applicable) cites code/test proving your position.
- Zero performative language; code speaks for the work.

## Red flags — STOP
- "You're right!" or any gratitude before verifying.
- Implement in batch without testing between items.
- Accept suggestion that breaks existing functionality without questioning.
- Conflict with Guilherme's previous decision → pause and ask.

## Escape hatch
If you can't verify (e.g., needs specific environment) → declare limitation in report, ask for direction. Never implement blind.
