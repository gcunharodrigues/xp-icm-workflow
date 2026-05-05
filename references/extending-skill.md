# Extending the Skill — xp-icm-workflow

Checklist for when a **new skill** is installed in the ecosystem or the user asks to incorporate a new capability into the workflow.

Apply the edit-source principle to the skill itself: if you keep updating the same files manually every time something changes, create a mechanism that ensures automatic consistency.

---

## When to read this file

Load on demand when:

1. A new skill is installed (e.g., `superpowers:ui-ux-design`, `superpowers:data-pipeline`).
2. User asks to "incorporate [capability] into the workflow".
3. Orchestrator detects a skill being invoked that does not appear in the mapping.
4. An existing skill changes name or scope.

---

## Classification questions (answer first)

Before updating files:

1. **Which stage does this skill affect?** → Determines which section of `SKILL.md` and which `CONTEXT.md` template to update.
2. **Does it replace or complement an existing skill?** → Replaces: remove the old one. Complements: add as auxiliary.
3. **Does the orchestrator need to read the output directly or delegate?** → Compact markdown (`discovery.md`, `plan.md`): orchestrator can read. Source code (`src/`, `tests/`): delegate to specialized subagents/skills.
4. **Does the skill introduce a new artifact type?** → If so, add it to the Inputs table of the stages that consume it. Example: wireframes (Stage 02) are input to Stage 03.
5. **Does the skill require a new stage?** → Distinct step with its own review gate → create a stage. Activity within an existing stage → add as auxiliary.

---

## Extensibility Checklist

For each new skill or change, update **all** relevant items:

| # | File | What to update | Example |
|---|---|---|---|
| 1 | `SKILL.md` — Division of Responsibilities | Add skill to table with Who and Decides/Does | `superpowers:ui-ux-design` → "Design: wireframes, prototypes, style guides" |
| 2 | `SKILL.md` — Workflow Overview (master table) | If creating new stage, add to flow. If complementing, add as auxiliary. | Stage 02.5: "UI/UX Design" with skill `ui-ux-design`, or Stage 03 with auxiliary skill |
| 3 | `SKILL.md` — Specific stage (lean Phase 1) | Update skill, key input, key output and gate of the affected stage | If UI/UX affects Stage 02: add wireframes as output |
| 4 | `references/stage-templates.md` | Update the affected stage template with new skill, inputs and outputs. If the new skill impacts workspace identity or routing, also update the root `CLAUDE.md` and `CONTEXT.md` templates in that same file. | Add `output/wireframes.md` to Stage 02 outputs; if skill adds new field (e.g., design system name) to workspace, update root `CLAUDE.md` template |
| 5 | `references/superpowers-mapping.md` | Add row to "Mapping by Stage" and/or "Transversal Situation" table | `02 Design & Planning` → `superpowers:ui-ux-design` |
| 6 | `references/xp-workflow-integration.md` | If it affects `/xp-workflow` phases, map it. If not, mark N/A. | Phase 1 of xp-workflow now includes UI/UX |
| 7 | `references/icm-paper-summary.md` | **DO NOT update** — paper summary, not skill summary | N/A |
| 8 | `SKILL.md` — Delegation Protocol (if applicable) | If skill reads source code or produces artifacts the orchestrator would consume, define whether it reads directly or via report | `ui-ux-design` produces wireframes (markdown) — orchestrator can read, no delegation needed |
| 9 | `references/changelog.md` | Record extension as a new minor version | v2.X.0 — Extension: [skill]. Stage(s): [...]. Files: [...] |

---

## Changelog entry format

```
## v2.X.0 — Extension: [skill name]
- Affected stage(s): [list]
- Updated files: [list]
- Reason for addition: [1 sentence]
- Orchestrator reads output directly? [yes/no + reason]
```

---

## Red flags

Signs that the extension is being done poorly:

- New skill appears in `SKILL.md` but not in `references/superpowers-mapping.md` (mapping out of sync).
- Stage template in `references/stage-templates.md` says "invoke X skill" but X is not listed in Division of Responsibilities.
- Orchestrator added direct read of `src/` — violates Delegation Principle.
- Stop points of `/xp-workflow` were not considered when a new artifact type was introduced.
- Changelog did not record the extension — future sessions have no traceability.

If any red flag is detected: stop, fix, only then proceed.
