# Task Types — HITL vs AFK

Adapted from [mattpocock/skills/skills/engineering/to-issues/SKILL.md].

## Definitions

**HITL (Human-In-The-Loop):** task that **requires human interaction** during
execution. A subagent cannot complete it autonomously.

Examples:
- Architectural decision with non-obvious trade-off (choosing between 2 frameworks)
- Design review (mockup requires approval)
- Manual UX/QA testing (clicking buttons, validating visuals)
- Access to credentials/vaults
- Production deploy gate
- External stakeholder sign-off

**AFK (Away-From-Keyboard):** task that **a subagent can complete
autonomously** given the brief. Lead spawns via Agent tool, subagent runs
the 7-step TDD cycle, returns report.

Examples:
- Implement REST endpoint with schema defined in plan.md
- Add column to schema + migration
- Refactor internal function preserving contract
- Add test coverage to existing module
- Fix bug with clear repro test

## Default

`AFK` is the default. Mark as `HITL` only with **explicit justification** in
the plan.md column.

## Schema in plan.md

```markdown
### Task: implementar-jwt-refresh

**Type:** AFK
**Files touched:** src/auth/jwt.{ts,test.ts}, src/api/refresh.ts
**Depends on:** none

**O QUE:** ...
**COMO:** ...
**NÃO QUERO:** ...
**VALIDAÇÃO:** ...
```

```markdown
### Task: choose-orm

**Type:** HITL
**Reason:** Architectural decision — Prisma vs Drizzle vs raw SQL. Significant
lock-in; team must approve.
**Files touched:** docs/decisions/0007-orm-choice.md
**Depends on:** none

**O QUE:** ...
```

## Wave planner consequence

- **AFK tasks:** grouped into topological waves respecting cap per tier
  (experimental: 2, tool: 3, development: 5, production: 5).
- **HITL tasks:** each becomes an **isolated wave with cap=1**. Lead session
  pauses upon reaching that wave, generates an AGENT-BRIEF (but does NOT spawn a subagent),
  displays it to the human and waits for input. Status: `wave-N_hitl_pending`.

## Lead session on a HITL wave

```
1. Detect wave type=HITL
2. Generate AGENT-BRIEF from the task
3. Print to human:
   "Wave N (HITL): <task summary>
    Brief generated at stages/04/output/wave-N/hitl-brief.md
    Action required: <reason>
    After resolving, resume the session and set sub_stage=04_wave_N_completed."
4. Update L1: status=COMPLETED_AWAITING_HUMAN, sub_stage=04_wave_N_hitl_pending
5. EXIT the session.
```

Next session (after human resolves) resumes at the following wave.

## Classification criteria

**Mark HITL when:**
- Decision is hard to reverse + has real alternatives (corresponds to the ADR gate)
- Subagent lacks sufficient information (requires external input)
- Explicit stakeholder sign-off required
- Manual testing requires human eyes (UX, design)
- Credentials/secrets involved

**Mark AFK when:**
- Brief has testable acceptance criteria
- Technical path is clear (even if multi-step)
- Tests can confirm correctness automatically
- No external human dependencies

## Task-level HITL granularity (v3.5.0)

Before v3.5.0: the entire wave paused if 1+ tasks were HITL (lead exited, next session resumed). Result: non-HITL tasks in the same wave waited unnecessarily.

From v3.5.0 onward:
- **Pure HITL wave** (all tasks `type: HITL`, or wave-planner isolated them into a sub-wave with cap=1): legacy behavior preserved. Lead does not spawn Agent, generates AGENT-BRIEFs, exits with `BLOCKED_HITL`.
- **Mixed wave** (HITL + non-HITL tasks): lead spawns Agents only for non-HITL tasks IN PARALLEL. HITL tasks: inline AGENT-BRIEF in `task-<slug>.md` + `status: AWAITING_HITL`. Lead waits for Agents to return. If `AWAITING_HITL` tasks remain: L1 `status: BLOCKED_HITL`, exit. Next session validates that HITL tasks became COMPLETE (human edited them) and resumes the wave-reviewer.

### Canonical associated status

`BLOCKED_HITL` (distinct from `BLOCKED_ERROR` — not a failure, it is an external wait). Listed in `references/state-machine-schema.md`.

### Cross-ref

- Detailed pipeline: `references/wave-execution-protocol.md`
- L2 runtime: `templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl` § HITL handling
