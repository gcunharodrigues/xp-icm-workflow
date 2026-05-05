# OUT-OF-SCOPE Knowledge Base

Adapted from [mattpocock/skills/skills/engineering/triage/OUT-OF-SCOPE.md].

`<workspace>/_out-of-scope/` stores persistent records of rejected feature
requests. Two purposes:

1. **Institutional memory** — why a feature was rejected, rationale
   preserved when the issue closes.
2. **Deduplication** — when a new issue matches a prior rejection, the skill
   surfaces the previous decision instead of re-litigating.

## Structure

```
<workspace>/_out-of-scope/
├── README.md            (template explaining the convention)
├── dark-mode.md
├── plugin-system.md
└── graphql-api.md
```

**1 file per concept**, NOT per issue. Multiple issues requesting the same
thing are grouped under 1 file.

## Format

Relaxed/readable style — short design doc, not a database entry.

```markdown
# Dark Mode

This project does not support dark mode or theming.

## Why it is out of scope

The rendering pipeline assumes a single color palette in `ThemeConfig`. Supporting
multiple themes would require:
- Theme context provider wrapping the component tree
- Per-component theme-aware style resolution
- Persistence layer for user theme preference

Significant architectural change that does not align with the focus on content authoring.
Theming is a downstream concern — embed/redistribute output.

```ts
interface ThemeConfig {
  colors: ColorPalette;  // single palette, build-time
  fonts: FontStack;
}
```

## Prior requests

- session 042 stage 08 — "Add dark mode support"
- session 087 stage 02 — "Night theme accessibility"
- session 134 stage 01 — "Dark theme option"
```

## Naming

- Short, descriptive kebab-case: `dark-mode.md`, `plugin-system.md`,
  `graphql-api.md`.
- Descriptive enough — someone browsing the directory understands what was
  rejected without opening the file.

## Reason must be substantive

Not "we don't want this" but **why**. Good reasons reference:

- Project scope/philosophy ("Focus on X; theming is a downstream concern")
- Technical constraints ("Supporting this would require Y, conflicting with Z")
- Strategic decisions ("We chose A over B because...")

The reason must be **durable**. Avoid temporary circumstances ("too busy
right now") — that is a deferral, not a real rejection.

## When to consult `_out-of-scope/`

**Stage 02 (design):** if the workspace has `iteration > 0`, read all
`_out-of-scope/*.md` files. If the proposed design matches a prior rejection, surface it to
the human:
> "This proposal is similar to `_out-of-scope/dark-mode.md` — we rejected it before
> because [reason]. Do you still agree?"

The human may:
- **Confirm** — new issue added to "Prior requests", workspace
  proceeds without including the item in the design.
- **Reconsider** — file deleted/updated, design proceeds normally.
- **Disagree** — related but distinct issues, proceed.

**Stage 08 (feedback intake):** during triage, before classifying new feedback,
check for a match with `_out-of-scope/` files.

## When to write to `_out-of-scope/`

Only when an **enhancement** (not a bug) is rejected as `wontfix`:

1. Maintainer/agent decides the feature is out of scope.
2. Check whether the corresponding file already exists.
3. If yes: append a new entry to "Prior requests".
4. If no: create a new file with concept name + decision + reason + first prior request.
5. Post a message in the log explaining the decision + mentioning the file.
6. Workspace closes with Output A (close), L1 status=COMPLETED.

## When to update/remove

If the decision changes (it is no longer out of scope):
- Delete the `_out-of-scope/<concept>.md` file.
- The skill does not need to reopen old issues — they are historical records.
- The new issue that triggered the reconsideration proceeds through normal triage.

## Concept match (not keyword)

"Night theme" matches `dark-mode.md` because of concept similarity. Mechanism:
agent reads all files in the kb, compares the semantics of the new feedback against each
concept. If match: surface to human.

Not strict keyword matching — identical terms are not required.
