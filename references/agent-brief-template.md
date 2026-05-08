# AGENT-BRIEF Template — canonical format

Adapted from [mattpocock/skills/skills/engineering/triage/AGENT-BRIEF.md].

## Principles

### 1. Durability over precision
A subagent may run minutes or days after the brief was written. The codebase may change.
The brief must remain useful even with renames/refactors.
- **Do:** describe interfaces, types, behavioral contracts.
- **Do not:** reference absolute paths, line numbers, or the current internal structure.

### 2. Behavioral, not procedural
Describe **what** the system should do, not **how** to implement it.
- **Good:** "When `/triage` runs with no args, shows a summary of issues needing attention"
- **Bad:** "Add switch statement on line 42 of handler.ts"

### 3. Complete acceptance criteria
The subagent needs to know when it is done. Criteria must be concrete, testable,
and independently verifiable.
- **Good:** "`gh issue list --label needs-triage` returns issues that passed initial classification"
- **Bad:** "Triage should work correctly"

### 4. Explicit scope boundaries
Explicitly state what is out of scope. Prevents gold-plating and
assumptions about adjacent features.

## HARD GATES — canonical (v4.0.x)

Every AGENT-BRIEF rendered by `scripts/agent-brief-render.py` must include the
following 3 gates at the TOP, before Summary. Subagent MUST execute them in order.
Skip any = task BLOCKED.

**GATE 1 — Branch verification (first action after spawn):**
```bash
git branch --show-current
```
Must show `wave-<NNN>-<N>/<task-slug>`. Wrong → STOP, report `Status: BLOCKED`.
Do NOT run `git checkout`. Do NOT create a branch.

**GATE 2 — Synchronous-first (every test/lint/typecheck):**
Use `Bash: "<command>"` — synchronous, blocks, returns exit code.
NEVER `Bash(run_in_background=true)` + `Monitor` for commands under 5 minutes.

**GATE 3 — Commit verify (before declaring COMPLETE):**
```bash
git log --oneline <BASE_BRANCH>..HEAD  # ≥1 commit required
git status --short                      # must be clean
```
Zero commits → return to TDD loop. Dirty tree → commit or stash.

## Isolation rules — canonical (v4.0.x)

All subagents use manual worktrees in `.claude/worktrees/icm-wave-<NNN>-<N>-<slug>/`
on branch `wave-<NNN>-<N>-<slug>`. Single isolation mode — no Path A / Path B branching.

- [ ] Your CWD is `.claude/worktrees/icm-wave-<NNN>-<N>-<slug>/` — a git worktree on branch `wave-<NNN>-<N>-<slug>`. Run `pwd` to confirm. NOT the project root.
- [ ] Write code ONLY in this worktree. NEVER write via absolute paths to the project.
- [ ] NEVER write to `<PROJECT_ROOT>/.icm-main/` or any path under it. It is the base-branch linked worktree — read-only for docs.
- [ ] NEVER run `git checkout`, `git switch`, `git rebase`, or `git push`. Branch is pre-created.
- [ ] Read base-branch docs (ADRs, lessons, tech_debt) from `<PROJECT_ROOT>/.icm-main/<path>`.
- [ ] Verify on startup: `git branch --show-current` MUST show correct branch. `git status --short` MUST be clean. Wrong → STOP, report `Status: BLOCKED`.
- [ ] Workspace state (L0/L1/L2) is injected into the brief by the lead. Do NOT read separately.
- [ ] Return results in Agent tool output. Lead writes all workspace state files. MUST NOT write to workspace branch paths.

## Template

```markdown
### HARD GATES — execute in order. Skip any = task BLOCKED.

**GATE 1 — Branch verification:**
...(rendered by agent-brief-render.py)

**GATE 2 — Synchronous-first:**
...(rendered by agent-brief-render.py)

**GATE 3 — Commit verify:**
...(rendered by agent-brief-render.py)

### Isolation rules (MANDATORY)
...(rendered by agent-brief-render.py)

**Category:** bug / enhancement
**Summary:** one-line description of what needs to happen

**Current behavior:**
What happens now. Bugs: broken behavior. Enhancements: status quo.

**Desired behavior:**
What should happen after agent's work is complete. Be specific about edge
cases and error conditions.

**Key interfaces:**
- `TypeName` — what needs to change and why
- `functionName()` return type — what it currently returns vs what it should return
- Config shape — any new configuration options needed

**Acceptance criteria:**
- [ ] Specific, testable criterion 1
- [ ] Specific, testable criterion 2
- [ ] Specific, testable criterion 3
- [ ] `git log --oneline main..HEAD` ≥1 commit (branch persists the work — do not return Status COMPLETE with zero commits).

**Out of scope:**
- Thing that should NOT be changed or addressed in this issue
- Adjacent feature that might seem related but is separate
```

## Mapping to 4-block in plan.md

| 4-block | AGENT-BRIEF |
|---|---|
| **WHAT** | Summary + Current/Desired behavior |
| **HOW** | Key interfaces (not procedural) |
| **OUT OF SCOPE** | Out of scope |
| **VALIDATION** | Acceptance criteria |

## Anti-patterns

- **Absolute file paths** — go stale after first refactor.
- **Line numbers** — same reason.
- **Vagueness** — "the triage thing is broken" — agent does not know what to do.
- **No acceptance criteria** — agent does not know when it is done.
- **No scope boundary** — agent gold-plates or modifies adjacent features.
- **Procedural** — "open file X, line Y, change Z" — breaks on first refactor.
- **Unnecessary async** — `Bash run_in_background=true + Monitor` for pytest <5min is overkill; use synchronous Bash.
