# Design It Twice — parallel interface design

Adapted from [mattpocock/skills/skills/engineering/improve-codebase-architecture/INTERFACE-DESIGN.md].

For core modules in stage 02 (design), spawn **3+ subagents in parallel**
with distinct constraints. Compare before committing to an interface. Based on
"Design It Twice" (Ousterhout, *A Philosophy of Software Design*) — the first
idea is rarely the best.

## When to apply

- Module marked `core: true` in plan.md (meaningful architectural decision)
- Interface will have multiple callers / public surface
- High lock-in (refactoring later costs a quarter+)
- Not applicable: trivial modules, single-caller, glue code

## Process

### 1. Frame the problem space

Before spawning, write a user-facing explanation of the problem space:
- Constraints that any interface would satisfy
- Dependencies (categorize: in-process / local-substitutable / remote-owned / true-external)
- Illustrative code sketch (not a proposal — just grounding constraints)

Show to the user, then proceed to Step 2 (user reads while subagents work).

### 2. Spawn 3+ subagents in parallel

Use the `Agent` tool with 3+ parallel calls. Each subagent has a **different
constraint** (separate briefs, but all reference CONTEXT.md + ADRs):

- **Agent 1:** "Minimize interface — 1-3 entry points max. Maximize leverage per entry point."
- **Agent 2:** "Maximize flexibility — support many use cases + extension."
- **Agent 3:** "Optimize common caller — default case trivial."
- **Agent 4 (if applicable):** "Design around ports & adapters for cross-seam dependencies."

Each subagent returns:
1. Interface (types, methods, params + invariants, ordering, error modes)
2. Usage example showing how callers use it
3. What the implementation hides behind the seam
4. Dependency strategy + adapters
5. Trade-offs — where leverage is high, where it is thin

### 3. Present and compare

Present designs sequentially so the user can absorb each one. Compare in
prose by:
- **Depth** — leverage at the interface (deep = high leverage)
- **Locality** — where change concentrates
- **Seam placement** — where behavior can be altered

After the comparison, give an **opinionated recommendation**: which design is strongest
and why. If elements from different designs combine well, propose a hybrid.

User wants a strong read, not a menu.

## Output in stage 02

`stages/02_design/output/design-alternatives-<module>.md`:

```markdown
# Design Alternatives — <module name>

## Problem space
<constraints, dependencies, code sketch>

## Alternative 1 — Minimal interface
<interface, usage, hidden complexity, trade-offs>

## Alternative 2 — Maximum flexibility
<...>

## Alternative 3 — Optimize common caller
<...>

## Comparison
| Aspect | Alt 1 | Alt 2 | Alt 3 |
|---|---|---|---|
| Depth | high | medium | medium |
| Locality | tight | spread | tight |
| Seam | external | internal | external |

## Recommendation
<opinionated pick, or hybrid proposal, with reasons>
```

`decisions.md` lists the final decision (with link). May become an ADR if it passes
the 3-criteria gate (see `references/adr-format.md`).

## Anti-patterns

- Spawning 3 subagents with the same prompt — will not produce diversity.
- Applying to EVERY module — overhead. Reserve for core decisions.
- Using it as a menu (user's choice) — the agent must have an opinion.
- Skipping Step 1 (problem space) — subagents work with different constraints than the user.
