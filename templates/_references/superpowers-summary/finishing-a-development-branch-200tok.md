---
name: finishing-a-development-branch-200tok
source_skill: superpowers:finishing-a-development-branch
source_version: "5.0.0"
purpose: Decide how to integrate completed work — local merge, PR, or tag — after verification and review are green.
---

# Finishing a Development Branch — 200tok summary

## When to apply
- At stage 04 (implementation waves) of ICM, after the last wave completes and passes CI+E2E gates are APPROVED.
- When implementation is complete, tests pass, and you need to decide the branch destination.

## How to apply
1. **Verify tests** one more time on the branch (don't trust previous run). Failure → stop, return to stage 04.
2. **Determine base** with `git merge-base HEAD main` (or master).
3. **Present menu** to Guilherme — exactly 3 ICM-aware options:
   - **A) Direct local merge** — `git checkout <base> && git pull && git merge <feature>`, delete branch.
   - **B) Push + open PR** — `git push -u origin <branch>` + `gh pr create` with 2–3 bullet summary and test plan; keep branch until PR closes.
   - **C) Tag-only (keep as-is)** — create tag `icm/<stage>/<slug>` on HEAD, keep branch for later iteration.
4. **Execute choice**, record final SHA and tag/PR in stage's `merge-report.md`.
5. Delete branch only in A; in B await PR; in C preserve.

## Success signals
- `merge-report.md` records: option chosen, merge/PR SHA, tag (if any).
- Tests green after merge (post-integration run in A).
- Branch deleted **only** if merge confirmed.

## Red flags — STOP
- Tests failing → never proceed.
- Force-push without explicit request.
- Discard work without typed confirmation.
- Delete branch in B or C (loses state).

## Escape hatch
If Guilherme doesn't decide on the spot → option C (tag-only) preserves everything for future session, no cleanup needed.