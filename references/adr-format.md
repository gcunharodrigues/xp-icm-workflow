# ADR Format — canonical format (3-criteria gate)

Adapted from [mattpocock/skills/skills/engineering/grill-with-docs/ADR-FORMAT.md].

ADRs live in `<project_root>/docs/decisions/` and use sequential numbering:
`0001-slug.md`, `0002-slug.md`, etc.

## 3-criteria gate

**Create an ADR only if ALL 3 are true:**

1. **Hard to reverse** — the cost of changing your mind later is meaningful.
2. **Surprising without context** — a future reader will look at the code and ask
   "why on earth did they do it this way?"
3. **Result of a real trade-off** — there were genuine alternatives and you
   chose one for specific reasons.

If any of the 3 fails, **do NOT create an ADR**. The decision goes into `decisions.md` as
a note.

- Decision easy to reverse? It will be reversed without an ADR — skip.
- Not surprising? Nobody will ask — skip.
- No real alternative? Nothing to record — skip.

## Template

```md
# {Short title of the decision}

{1-3 sentences: what's the context, what did we decide, and why.}
```

This is the complete template. An ADR can be a single paragraph. The value lies in
recording **that** a decision was made and **why** — not in filling out sections.

## Optional sections

Include only when they add genuine value. Most ADRs will not need them.

- **Status** frontmatter (`proposed | accepted | deprecated | superseded by ADR-NNNN`) — useful when decisions are revisited
- **Considered Options** — only when rejected alternatives deserve to be remembered
- **Consequences** — only when non-obvious downstream effects need highlighting

## Numbering

Scan `docs/decisions/` for the highest existing number, increment by one.

## What qualifies as an ADR

- **Architectural shape.** "Monorepo." "Write model is event-sourced, read model
  projected in Postgres."
- **Integration patterns between contexts.** "Ordering and Billing communicate via
  domain events, not synchronous HTTP."
- **Tech choices that carry lock-in.** Database, message bus, auth provider,
  deployment target. Not every library — only those that would take a quarter to swap.
- **Boundary and scope decisions.** "Customer data is owned by the Customer context;
  other contexts reference by ID only." The explicit "no-s" are as valuable as
  the "yes-s".
- **Deliberate deviations from the obvious path.** "Manual SQL instead of ORM because X."
  Anything where a reasonable reader would assume the opposite.
- **Constraints not visible in code.** "We cannot use AWS due to compliance."
  "Response time must be <200ms per contract with partner API."
- **Rejected alternatives when rejection is non-obvious.** Considered GraphQL and
  picked REST for subtle reasons — record it, or someone will suggest GraphQL again
  in 6 months.

## What does NOT qualify

- Small style decisions (tab vs space)
- Small library choices (lodash vs ramda)
- Easily reversible decisions (choice of logging framework)
- Obvious decisions (no real alternative)
- Things self-evident from the code

## decisions.md vs individual ADRs

- `<workspace>/stages/02_design/output/decisions.md` — **index + short notes**
  for decisions that do NOT pass the gate (small decisions, brief reasoning).
- `<project_root>/docs/decisions/NNNN-slug.md` — individual ADRs for
  decisions that pass the gate.

decisions.md has sections: `## ADRs created (links)` + `## Notes (decisions that
did not become ADRs)`.
