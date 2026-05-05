# OUT-OF-SCOPE — workspace {{WORKSPACE}}

> Knowledge base of rejected feature requests. 1 file per concept,
> NOT per issue. Multiple requests for the same concept are grouped.
>
> Canonical format: `_references/runtime/out-of-scope-kb.md`.

## Convention

```
_out-of-scope/
├── README.md            (this file)
├── <concept-1>.md
├── <concept-2>.md
└── ...
```

Each `<concept>.md` contains:

```markdown
# {Concept Name}

Short description of what the concept is + decision not to implement.

## Why it is out of scope

Durable reason: project scope/philosophy, technical constraint, or strategic
decision. Not a temporary reason ("too busy right now").

## Prior requests

- session NNN stage XX — "summary"
- session NNN stage XX — "summary"
```

## When to consult

- **Stage 02 (design):** if `iteration > 0`, read all files before
  proposing design. Surface matches to the human.
- **Stage 08 (feedback intake):** during triage of new feedback, check
  for matches before classifying.

## When to update

- **wontfix of enhancement:** append to existing file OR create new one.
- **Reconsideration:** delete file, issue proceeds through normal triage.
