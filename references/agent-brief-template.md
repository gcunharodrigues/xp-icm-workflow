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

## Template

```markdown
## Agent Brief

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

The existing 4-block from plan.md (`WHAT / HOW / OUT OF SCOPE / VALIDATION`)
maps to AGENT-BRIEF as follows:

| 4-block | AGENT-BRIEF |
|---|---|
| **WHAT** | Summary + Current/Desired behavior |
| **HOW** | Key interfaces (not procedural) |
| **OUT OF SCOPE** | Out of scope |
| **VALIDATION** | Acceptance criteria |

Stage 02 (design) writes plan.md in 4-block format. Stage 04 (lead session)
generates the AGENT-BRIEF from the task section in plan.md via
`scripts/agent-brief-render.py`.

## Before returning summary to lead

Subagent (AFK) MUST verify before declaring Status COMPLETE in the task report:

- [ ] `git log --oneline main..HEAD` shows ≥1 commit (≠ zero).
- [ ] working tree clean OR remaining files explicitly declared.
- [ ] task report written to absolute path.

Origin: sessao-recorrencia incident (workspace 001 wave 6) — subagent completed
TDD 7 steps without `git commit`, branch HEAD = main HEAD, working tree dirty.
Lead recovery had to save the work manually. Explicit gate prevents recurrence.

## Anti-patterns

- **Absolute file paths** (`src/triage/handler.ts:42`) — go stale.
- **Line numbers** — same reason.
- **Vagueness** ("the triage thing is broken", "fix it") — agent does not know what to do.
- **No acceptance criteria** — agent does not know when it is done.
- **No scope boundary** — agent gold-plates or modifies adjacent features.
- **Procedural** ("open file X, line Y, change Z") — breaks on the first refactor.
- **Unnecessary async pytest**: `Bash run_in_background=true + Monitor` for pytest <5min is overkill; use synchronous Bash. Reserve async for long builds/dev-servers.
