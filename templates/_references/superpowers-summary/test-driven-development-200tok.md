---
name: test-driven-development-200tok
source_skill: superpowers:test-driven-development
source_version: "5.0.0"
purpose: Ensure all production code is born from a failing test first.
---

# Test-Driven Development — 200tok summary

## When to apply
- Every new feature, bugfix, refactor, or behavior change.
- Whenever there is production code to write.

## Iron law
No failing test first, no production code. Wrote code first? Delete it and start over. "Keep as reference" is rationalization.

## How to apply
Use the canonical TDD cycle already documented in this workspace at `references/4-block-contract-template.md` (RED → GREEN → CI → REFACTOR → CI → Auto-QA Akita 15-item → COMPLETE).

Essential summary:

1. **RED** — write a minimal test, clear name, one behavior only, real code (no mock if avoidable).
2. **Verify RED** — run the test and confirm it fails for the right reason (missing feature, not a typo).
3. **GREEN** — write the minimum code to make it pass. No YAGNI, no extra flags.
4. **Verify GREEN** — test passes, all other tests pass, output is clean.
5. **REFACTOR** — only after green; remove duplication, improve names, keep green.
6. **Next cycle.**

## Success signals
- Saw each test fail before implementation.
- Failed for the expected reason.
- Minimal code, no unrequested features.
- Pristine output, all other tests green.

## Red flags (stop and restart)
"I'll test later", "already tested manually", "deleting is wasteful", "TDD is dogmatic", "spirit not ritual" — all mean: delete the code and redo via TDD.

## Escape hatch
If the case is ambiguous (throwaway prototype, generated code, config) or complexity exceeds this summary → invoke formal `superpowers:test-driven-development`. For Auto-QA Akita 15-item, see `references/4-block-contract-template.md` (do not duplicate here).
