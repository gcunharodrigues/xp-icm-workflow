# Design System — DESIGN.md format (v3.11.0)

> **Version:** v3.11.0
> **Skill:** `xp-icm-workflow`
> **Applies when:** effective profile has `design_system_required: True`
> (currently: `app_web_frontend` and `fullstack`).
> **Canonical path:** `<project_root>/.icm-main/DESIGN.md` (base branch,
> persistent cross-iteration via worktree v3.4.0).
> **Complements:** `references/preview-loop-protocol.md` — DESIGN.md provides
> tokens; preview loop provides the build-iterate visual cycle that consumes those
> tokens in real screens with hot-reload.

## Why DESIGN.md and not another format

ICM adopts the **DESIGN.md** format defined by the
[Google Stitch spec](https://stitch.withgoogle.com/docs/design-md/overview/).
Reasons:

1. **Plain markdown + YAML frontmatter** — the LLM reads it directly, no special
   tooling needed. Subagent in stage 04 reads via `Read tool`, zero ceremony.
2. **Open spec + community** — 69 ready-made examples at
   [VoltAgent/awesome-design-md](https://github.com/VoltAgent/awesome-design-md)
   (airbnb, apple, claude, figma, framer, ferrari, etc.).
3. **File-based ≡ ICM philosophy** — lives alongside ADRs in
   `<project_root>/.icm-main/`. Same authoring pattern (worktree-mediated
   commits on base branch).
4. **Schema converts trivially** to `tokens.json` (W3C DTCG), Figma
   variables, Tailwind theme config, shadcn/ui theme.

## Canonical file structure

```markdown
---
version: alpha
name: <Brand name>
description: <optional, 1-2 sentences>

colors:
  primary: "#1A1C1E"
  secondary: "#6C7278"
  tertiary: "#B8422E"
  neutral: "#F7F5F2"
  # Optional semantic states:
  # surface, on-surface, error, on-error, etc.

typography:
  display-lg:
    fontFamily: <font>
    fontSize: <Dimension>
    fontWeight: <number>
    lineHeight: <Dimension|number>
    letterSpacing: <Dimension>
  headline-lg: { ... }
  body-md: { ... }
  label-sm: { ... }
  # Usually 9-15 named levels (display/headline/body/label/caption × sm/md/lg)

rounded:
  sm: 4px
  md: 8px
  lg: 16px
  full: 9999px

spacing:
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px

components:
  # Composite tokens with cross-token refs via {path.to.token}
  button:
    bg: "{colors.primary}"
    fg: "#ffffff"
    rounded: "{rounded.md}"
    padding: "{spacing.md}"
---

## Overview
<Brand personality, target audience, emotional response. Foundational
context for the agent to make high-level decisions when a specific token
does not apply.>

## Colors
<Palette + rationale per color, mapping palette description → semantic role>

## Typography
<Scale with 9-15 levels and a declared role per level>

## Layout
<Grid system, breakpoints, container max-widths>

## Elevation & Depth
<Shadow scale, z-index layers>

## Shapes
<Border radius, shape language (sharp / rounded / pill / organic)>

## Components
<Anatomy per key component: button, input, card, modal, navbar, etc.>

## Do's and Don'ts
<Patterns to use vs anti-patterns to avoid>
```

Section order is canonical: omitting a section is OK; reordering is not.

## 3-layer token architecture (canonical principle)

Stage 02 designer structures tokens in three hierarchical layers:

```
Primitive (raw values) — colors.gray-900, colors.blue-600, spacing.16
       ↓
Semantic (purpose aliases) — colors.primary, colors.text-default, spacing.md
       ↓
Component (component-specific) — button.bg, card.padding, input.border
```

Resulting CSS example:

```css
/* Primitive */
--color-blue-600: #2563EB;
--spacing-16: 16px;

/* Semantic — references primitive via {colors.blue-600} */
--color-primary: var(--color-blue-600);
--spacing-md: var(--spacing-16);

/* Component — references semantic */
--button-bg: var(--color-primary);
--button-padding: var(--spacing-md);
```

Token reference syntax in DESIGN.md: `"{colors.primary}"`. Conversion to
CSS variables, Tailwind config, or Figma variables is deterministic.

## Component spec table (template)

Stage 02 plan.md includes a spec per non-trivial component using this
template. Covers 4 visual states + allows identifying design gaps.

| Property | Default | Hover | Active | Disabled |
|----------|---------|-------|--------|----------|
| Background | `{colors.primary}` | `{colors.primary-dark}` | `{colors.primary-darker}` | `{colors.muted}` |
| Text | `#ffffff` | `#ffffff` | `#ffffff` | `{colors.muted-fg}` |
| Border | none | none | none | `{colors.muted-border}` |
| Shadow | `{elevation.sm}` | `{elevation.md}` | none | none |

Subagent in stage 04 validates that the implementation covers all 4 states when
writing component tests.

## Flow per ICM stage

| Stage | Action |
|---|---|
| **00 recon** | Detects whether DESIGN.md already exists in `.icm-main/`. Reports presence/absence in `recon-report.md`. If it exists: stage 02 updates incrementally. If absent: stage 02 creates from scratch. |
| **01 discovery** | Brand voice, target audience, emotional tone emerge from human clarification. Does not write DESIGN.md yet — only captures inputs in `discovery.md` that stage 02 will use to fill the `## Overview` section. |
| **02 design** | **Stage where DESIGN.md is created/updated.** New process step (only profiles `app_web_frontend` + `fullstack`). See "Stage 02 process" below. |
| **03 wave_planner** | Tasks with frontend files get the flag `requires_design_system: true` in plan.md (consumed by the lead in stage 04). |
| **04 implementation_waves** | Lead injects DESIGN.md into channel 2 of the subagent prompt when the task has the `requires_design_system` flag. Subagent reads tokens + writes code respecting refs. |
| **05 verification** | `visual_regression` (production tier) audits adherence. Sample-check: 3 implemented components match the tokens declared in DESIGN.md. |
| **06 review** | `conventions` dimension audits adherence to tokens (no hardcoded values when a token exists). |
| **07 merge** | Changes to DESIGN.md go along in the merge (commit on base via `.icm-main/`). |
| **08 feedback intake** | New iteration reads current DESIGN.md before proposing visual changes. |

## Stage 02 process — create/update DESIGN.md

After reading the desired `## Overview` section (from discovery.md) and
existing tokens (if brownfield), the stage 02 designer presents a menu A/B/C
to the human:

```
## Design System — choose starting point

A) **Create from scratch** — designer proposes initial tokens based on
   brand voice + audience captured in discovery. Human iteration will
   refine afterwards.

B) **Inspire from example** — choose a reference brand from the
   awesome-design-md gallery (airbnb, apple, claude, figma, framer, etc).
   Designer adapts tokens for the new project preserving the vibe.

C) **Extract from existing URL** — human provides a reference site URL.
   Designer instructs running `npx designlang <url>`
   externally and pastes the relevant base output. Designer adapts.

Awaiting human response.
```

After the choice:

1. Designer writes/updates `<project_root>/.icm-main/DESIGN.md`
   following the canonical schema (YAML frontmatter + section order).
2. Commit on base branch via worktree:
   ```bash
   cd <project_root>/.icm-main
   git add DESIGN.md
   git commit -m "design: <workspace-slug> — design system v<N>"
   cd <project_root>
   ```
3. Plan.md cites non-trivial components with a component spec table
   (Default/Hover/Active/Disabled) — refs to the tokens declared in DESIGN.md.
4. Stage 02 wave_planner will consume the flag `requires_design_system: true`
   in tasks with frontend files.

## Stage 04 channel 2 — DESIGN.md in the subagent prompt

Lead in stage 04, when spawning a subagent for a frontend task, injects in channel 2:

```
## Design System (DESIGN.md source of truth)

Read BEFORE writing code:
  Read <project_root>/.icm-main/DESIGN.md

Available tokens (sections relevant to this task):
- colors.primary, colors.secondary, colors.tertiary
- typography.body-md, typography.label-sm
- spacing.md, spacing.lg
- components.button (if applicable)

Rule:
- DO NOT use hardcoded values when a token exists.
- Use refs `{colors.primary}` instead of `#1A1C1E` literal.
- For new components, propose an entry in the `components` section of DESIGN.md
  via stop point `design_system_drift`.
```

Lead pre-processes — subagent does NOT read DESIGN.md raw in full; it receives
a relevant subset (tokens + components section related to the task).

## Reference gallery

[VoltAgent/awesome-design-md](https://github.com/VoltAgent/awesome-design-md):
69 DESIGN.md files extracted from popular sites. Stage 02 designer can
suggest them as a starting point (Case B of the menu).

Available brands include: airbnb, airtable, apple, bmw, cal, claude,
clay, clickhouse, cohere, coinbase, composio, cursor, elevenlabs, expo,
ferrari, figma, framer, hashicorp, ibm, intercom, and more.

## Optional external tool — designlang

For Case C (extract from URL), the human runs externally:

```bash
npx designlang <url>           # generates 17 output files
npx designlang <url> --dark    # also captures dark mode
npx designlang <url> --depth 3 # multi-page crawl for consistency
```

Output in `./design-extract-output/` includes:
- `*-design-language.md` — 19-section markdown ready for LLM
- `*-design-tokens.json` — DTCG W3C format
- `*-tailwind.config.js`, `*-shadcn-theme.css`

ICM designer reads the generated markdown, extracts relevant tokens, adapts to
the project's DESIGN.md. designlang is **not a dependency** of the skill — it is an
optional external tool the human runs when useful.

Doc: https://github.com/Manavarya09/design-extract

## Escape hatch — ui-ux-pro-max-skill

For cases where ICM design needs more depth beyond the DESIGN.md
spec, the human can invoke the parallel skill `ui-ux-pro-max:ui-ux-pro-max`
manually. Covers:

- 161 reasoning rules + 99 UX guidelines
- 67 UI styles (glassmorphism, claymorphism, minimalism, brutalism,
  neumorphism, bento grid, etc.)
- 161 color palettes + 57 font pairings
- 25 chart types
- 10 stacks (React, Next.js, Vue, Svelte, SwiftUI, RN, Flutter,
  Tailwind, shadcn/ui, HTML/CSS)

**When to invoke:**

- Greenfield with no prior visual reference (before stage 02 populates DESIGN.md)
- Slides/decks/banners — out of ICM scope; ui-ux-pro-max has a `slides`
  sub-skill with 8 CSVs of strategy
- Stuck on a design decision in stage 02 — ICM menu A/B/C is limited;
  ui-ux-pro-max expands the decision framework
- Brand exploration before bootstrapping a workspace

**When NOT to invoke:**

- Mid stage 04 (implementation). Lead reading 161 rules during TDD = noise.
  Subagents receive DESIGN.md (canonical for the project) in channel 2, not
  ui-ux-pro-max.
- Refinement of tokens already in DESIGN.md — ICM stage 02 handles that.
- Stage 06 review — ICM's `conventions` dimension already validates adherence.

**Boundary:** ICM governs the project cycle. ui-ux-pro-max is a parallel
consultive tool. Explicit human invocation ("ok, launch
ui-ux-pro-max"), never auto-invocation inside an ICM stage. Same pattern as
`superpowers:*` that ICM already adopted in v3.3.0.

## Conversion to other representations

DESIGN.md frontmatter converts deterministically:

| Target | Conversion |
|---|---|
| W3C DTCG `tokens.json` | `colors`, `typography`, etc. → `$value`/`$type` schema |
| Figma variables | YAML keys → variables with the same name |
| Tailwind `theme.extend` | `colors`, `spacing`, `borderRadius`, `fontFamily`, etc. |
| shadcn/ui CSS vars | `colors` → `--primary`, `--secondary`, etc. via `oklch()` or hex |
| CSS custom properties | Direct mapping with `--<token-path>` |

If the project requires dual-source (DESIGN.md + tokens.json synchronized),
document in an ADR and choose the primary source. Recommendation: **DESIGN.md
is the source of truth**; other formats are generated.

## Anti-patterns

### Hardcoded values when a token exists

```diff
- background: #1A1C1E;
+ background: var(--color-primary);
```

Code review (stage 06) flags this. Subagent in stage 04 is already instructed
in channel 2.

### Non-standard DESIGN.md

Section order, YAML schema keys, token reference syntax `{path.to.token}`
strictly follow the Google spec. Custom keys → breaks interop with
awesome-design-md examples and tools (Figma, Tailwind generators).

### Components only in code, not in DESIGN.md

Every reusable component deserves an entry in the `## Components` section of
DESIGN.md with anatomy + states (Default/Hover/Active/Disabled). Without
this, onboarding new devs loses context.

### Designer modifying code directly

Stage 02 designer ONLY writes to DESIGN.md (and plan.md). Does NOT touch
`src/`, `tests/` — that is stage 04. The workspace branch pre-commit hook
rejects it.

## Build-iterate visual loop (v3.6.0)

DESIGN.md tokens cover the declarative source of truth. But frontend is NOT
built mockup-first in an external canvas (Figma/Penpot require manual work in a
GUI or a paid plan). Instead, ICM v3.6.0 adopts a **code-first** loop:
agent generates UI with mock data, human inspects in a real browser,
gives verbal/visual/screenshot feedback, agent iterates via hot-reload.

Canonical doc: `references/preview-loop-protocol.md`. Covers:

- Dev server lifecycle (start at stage 04 entry, kill at exit).
- Tier-based mock data (fixtures → MSW+Faker → MSW+Faker+Zod).
- Chrome CDP live integration (`--remote-debugging-port=9222`).
- Uniform verification (`tsc` each edit + lint/Playwright wave-end).
- Preview pages (`preview/<component>` instead of Storybook).
- Free-form feedback (text, annotated screenshot, URL, HTML).
- Visual iteration without cap (human closes when OK).
- Design system cascade threshold (≤5 cascade directly, >5 stop point).
- Multi-screen replay on demand + auto-detect keywords.
- Recovery wizard types `DEV_SERVER_ORPHAN` + `CDP_DISCONNECTED`.

DESIGN.md remains the canonical source of tokens. The preview loop is the
execution cycle that consumes those tokens in real screens. The two docs work
together: design-system.md = O QUÊ; preview-loop-protocol.md = COMO ITERAR.

## Cross-references

- [DESIGN.md spec (Google Stitch)](https://stitch.withgoogle.com/docs/design-md/overview/)
- [VoltAgent/awesome-design-md](https://github.com/VoltAgent/awesome-design-md) — 69 examples
- [Manavarya09/design-extract (designlang)](https://github.com/Manavarya09/design-extract) — URL extraction
- [W3C Design Token JSON spec](https://www.designtokens.org/tr/2025.10/format/)
- `references/preview-loop-protocol.md` — build-iterate visual cycle (v3.6.0)
- `references/worktree-model.md` — model for writes on base branch via `.icm-main/`
- `templates/_config/profile-matrix.md` — `design_system_required` per profile
- `references/4-block-contract-template.md` — task schema in plan.md
