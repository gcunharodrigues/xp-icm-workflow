# CONTEXT.md (Ubiquitous Language) — canonical format

Adapted from [mattpocock/skills/skills/engineering/grill-with-docs/CONTEXT-FORMAT.md].

## Structure

```markdown
---
layer: L3
scope: ubiquitous_language
workspace: "{{WORKSPACE}}"
---

# Ubiquitous Language — workspace {{WORKSPACE}}

## Language

**Order**:
A request from a Customer to fulfill goods/services.
_Avoid_: Purchase, transaction

**Invoice**:
A request for payment sent to a customer after delivery.
_Avoid_: Bill, payment request

**Customer**:
A person or organization that places orders.
_Avoid_: Client, buyer, account

## Relationships

- An **Order** produces one or more **Invoices**
- An **Invoice** belongs to exactly one **Customer**

## Example dialogue

> **Dev:** "When a **Customer** places an **Order**, do we create the **Invoice** immediately?"
> **Domain expert:** "No — an **Invoice** is only generated once a **Fulfillment** is confirmed."

## Flagged ambiguities

- "account" was used to mean both **Customer** and **User** — resolved: these are distinct concepts.
```

## Rules

- **Be opinionated.** When multiple words exist for the same concept,
  pick the best one and list others as aliases to avoid.
- **Flag conflicts explicitly.** If a term is used ambiguously, call it out
  in "Flagged ambiguities" with a clear resolution.
- **Keep definitions tight.** One sentence max. Define what it IS, not what it does.
- **Show relationships.** Use bold term names and express cardinality when obvious.
- **Only include domain-specific terms.** Generic programming concepts
  (timeouts, error types, utility patterns) do NOT belong here even if the
  project uses them extensively. Before adding a term, ask: is this a concept
  unique to this domain, or a generic programming concept?
  Only the former belongs.
- **Group terms under subheadings** when natural clusters emerge.
- **Write an example dialogue.** A conversation between dev and domain expert that
  demonstrates how the terms interact naturally and clarifies boundaries
  between related concepts.

## When to update

- **Stage 01 (discovery):** the session is a grilling session. Each resolved term
  → update `<workspace>/_config/CONTEXT.md` **inline** (do not batch at the end).
- **Stage 02+ (design, waves, etc):** consume the glossary when writing
  outputs. If a new term emerges or an existing term is refined,
  update inline and reference it in the commit message.
- **Stage 04 subagent context-injection:** lead injects `_config/CONTEXT.md`
  as mandatory L3. Subagent uses the vocabulary when writing code + tests.

## Single-context vs multi-context

**Single context (majority of workspaces):** a single `<workspace>/_config/CONTEXT.md`.

**Multiple contexts (workspace covers multiple distinct bounded contexts):**
a `_config/CONTEXT-MAP.md` lists the contexts and where they live. Each subpath has
its own `CONTEXT.md`. Infer the structure — if the workspace is cohesive, single
context; otherwise, create the map.

## Anti-patterns

- Listing generic terms (`http`, `cache`, `event-loop`) — they are not domain concepts.
- Long, verbose definitions — one sentence is enough.
- Multiple words for the same concept without resolving which is canonical.
- Batched update at the end of the stage — loses context of the resolution.
