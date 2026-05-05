# Superpowers Mapping — xp-icm-workflow v3.0.0-beta5

> **Version:** v3.0.0-beta5
> **Skill:** `xp-icm-workflow`
> **Purpose:** canonical document of how `xp-icm-workflow` v3 **uses** skills from the `superpowers` plugin. v3 inverts the v2.4 relationship: superpowers become **summarized references**, not runtime invocations. Formal skill only as an escape hatch.

> **Decision origin:** §4.7 of plan `reescrever-a-skill-zazzy-wirth.md` + §4.10 (v2.4 → v3 change table, row "Skills superpowers").

---

## 1. Philosophy (change vs v2.4)

| Aspect | v2.4 | v3.0.0-beta1 |
|---|---|---|
| Usage form | `Skill({skill: "superpowers:writing-plans"})` invoked at runtime | 200tok summary pre-copied to `<workspace>/_references/superpowers-summary/` |
| Who loads | Orchestrator (skill always active during cycle) | Bootstrap copies once at start; sessions read as stable L3 |
| Token cost per stage | ~3k SKILL.md + on-demand references | ~200tok summary (15× less) |
| Update | Always loads current upstream version | Snapshot copied; manual sync via Wave 8 (future) |
| Escape hatch | n/a (always invokes) | Session may `Skill({skill:"superpowers:<X>"})` if complexity warrants; logged in L1 history |

**Why it changed.** `xp-icm-workflow` v3 is a one-shot midwife, not an orchestrator. Filesystem governs the cycle via L0/L1/L2. Dynamically loaded skills conflict with the principle "session reads only what is declared in Inputs". 200tok summaries fit in stable L3; each stage references 1-2 summaries in L2 §11. Formal skill remains available, but is a conscious fallback.

---

## 2. Canonical stage ↔ skill ↔ summary mapping

Authoritative table. Mirror of the mapping in `references/stage-templates.md` §11. In case of divergence, `stage-templates.md` is the source of truth (the stage's L2 determines what the session reads).

| Stage | Slug | Main superpowers skill | 200tok summary |
|---|---|---|---|
| 00 | `recon` | `brainstorming` + `writing-plans` (light) | `brainstorming-200tok.md`, `writing-plans-200tok.md` |
| 01 | `discovery` | `brainstorming` | `brainstorming-200tok.md` |
| 02 | `design` | `writing-plans` | `writing-plans-200tok.md` |
| 03 | `wave_planner` | `dispatching-parallel-agents` | `dispatching-parallel-agents-200tok.md` |
| 04 | `implementation_waves` | `test-driven-development` + `subagent-driven-development` | `test-driven-development-200tok.md`, `subagent-driven-development-200tok.md` |
| 05 | `verification` | `verification-before-completion` | `verification-before-completion-200tok.md` |
| 06 | `review` | `requesting-code-review` + `receiving-code-review` | `requesting-code-review-200tok.md`, `receiving-code-review-200tok.md` |
| 07 | `merge` | `finishing-a-development-branch` | `finishing-a-development-branch-200tok.md` |
| 08 | `feedback_intake` | (none direct) | uses local `references/feedback-intake-stage08.md` |
| transversal | any stage with a bug | `systematic-debugging` | `systematic-debugging-200tok.md` |

### 2.1 Auxiliary skills (not mapped to a fixed stage)

| Skill | Where it appears | Summary |
|---|---|---|
| `using-git-worktrees` | outside the ICM cycle (replaced by Agent tool) | `using-git-worktrees-200tok.md` |
| `writing-skills` | outside the ICM cycle (Guilherme creating/editing skills) | n/a — not copied to workspace |

---

## 3. The 10 pre-copied 200tok summaries

Bootstrap copies to `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/superpowers-summary/`. Source of templates: `C:\Users\guicr\.claude\skills\xp-icm-workflow\templates\_references\superpowers-summary\`.

| # | File | Covers stage(s) |
|---|---|---|
| 1 | `brainstorming-200tok.md` | 00, 01 |
| 2 | `writing-plans-200tok.md` | 00 (light), 02 |
| 3 | `dispatching-parallel-agents-200tok.md` | 03 |
| 4 | `test-driven-development-200tok.md` | 04 |
| 5 | `subagent-driven-development-200tok.md` | 04 |
| 6 | `verification-before-completion-200tok.md` | 04 (CI gates), 05 |
| 7 | `requesting-code-review-200tok.md` | 06 |
| 8 | `receiving-code-review-200tok.md` | 06 |
| 9 | `finishing-a-development-branch-200tok.md` | 07 |
| 10 | `systematic-debugging-200tok.md` | transversal — any stage with a bug |
| 11 | `using-git-worktrees-200tok.md` | auxiliary (outside the ICM cycle) |

> Note: effective list has 11 files. Plan §7 lists 10 explicitly; the 11th (`using-git-worktrees`) remains as a generic git auxiliary, no longer required by the subagent protocol. Files materialized in `templates/_references/superpowers-summary/` and copied by bootstrap.

### 3.1 Mandatory summary schema

Every `<X>-200tok.md` has a standardized header:

```markdown
---
source_skill: superpowers:<X>
source_version: <upstream skill semver>
summarized_at: <ISO 8601 date>
target_tokens: 200
actual_tokens: <int>   # validated in CI ≤250
---

# <Skill X> — 200tok summary

## When to use
<1 paragraph>

## Canonical steps
1. ...
2. ...

## Signals for "invoke formal skill"
- <trigger 1>
- <trigger 2>
```

CI validates `actual_tokens ≤ 250` (25% margin above target).

---

## 4. Synchronization vs upstream

Summaries are **snapshots**. When the upstream skill changes in the `superpowers` plugin, the summary becomes outdated. Mitigation:

1. **`source_version` header:** every summary declares the version of the upstream skill from which it was summarized.
2. **Wave 8 of the rewrite (future):** reviewer agent reads diff between declared `source_version` and current version of the upstream skill; generates update task if there is a relevant semantic change.
3. **Drift policy:** summary with >2 version lag triggers a warning at bootstrap (`scripts/check-runtime.sh` checks via metadata from `~/.claude/plugins/superpowers/`).

The `xp-icm-workflow` skill does **not** synchronize automatically — sync is a manual maintainer decision.

---

## 5. Escape hatch — real formal skill invocation

When the 200tok summary is **insufficient** for the complexity of what the session is doing, the session may invoke the formal skill via `Skill({skill: "superpowers:<X>"})`. Typical cases:

- Discovery (stage 01) with an unprecedented domain — `brainstorming` summary does not cover problem nuance.
- Bug in stage 04 that the `systematic-debugging` summary does not unblock.
- Review (stage 06) with dense feedback where raw `receiving-code-review` helps more than the summary.

### 5.1 Mandatory protocol

A session that invokes a formal skill **MUST** record in L1 `history`:

```yaml
- at: "<ISO 8601 UTC>"
  event: "skill_escape_hatch"
  skill: "superpowers:<X>"
  stage: "<NN>"
  reason: "<1-2 sentences on why the summary was insufficient>"
  outcome: "resolved" | "escalated_to_human"
```

Without the record, the escape hatch is silent and breaks audit. Pre-commit hook validates that commits from sessions with `skill_escape_hatch` in the diff have prefix `workspace:` or `feedback:`.

### 5.2 Informal rate limit

If a workspace has ≥3 `skill_escape_hatch` for the **same skill**, it is a signal that the 200tok summary is poorly calibrated. Trigger a summary review task (Wave 8) or escalate to the `xp-icm-workflow` skill maintainer.

---

## 6. Superpowers ↔ ICM conflict resolution

When an instruction from the superpowers summary conflicts with an ICM rule (L0/L1/L2 of the workspace):

1. **L0/L1/L2 win.** Skill is layer 4 in the priority order of `SKILL.md` §Instruction Priority.
2. **Session records divergence** in a comment in the stage output (does not block).
3. **If conflict is structural** (e.g., skill says "read src/", L2 says "do not read src/"), open a summary review task — likely a translation bug.

---

## 7. Summary maintenance

To create/update a 200tok summary, see `references/extending-skill.md` §"Adding a superpower summary". Flow summary:

1. Read upstream skill in `~/.claude/plugins/superpowers/skills/<X>/SKILL.md`.
2. Summarize in ≤250 tokens with schema §3.1.
3. Update `source_version` to current version.
4. Add entry in `tests/unit/test_summary_format.py` (verifies schema + tokens).
5. Commit in the skill repo (not in the user workspace).

---

## 8. Cross-references

| Doc | Content |
|---|---|
| `references/stage-templates.md` §11 | Stage ↔ skill canonical mapping (authoritative) |
| `references/extending-skill.md` | How to add/update summaries |
| `references/changelog.md` | Version history of the mapping |
| `references/v2.4-snapshot/superpowers-mapping.md` | Previous version (historical reference) |
| `templates/_references/superpowers-summary/` | Templates of the 11 summaries |
| `SKILL.md` §Instruction Priority | Full priority order (1-5) |

---

## v3.3.0 — Diagnose 6-phase protocol mapping

Stage 05 (verification) activates the **Diagnose 6-phase** when CI fails OR coverage
fails. Stage 04 (subagent) may use it before declaring BLOCKED.

NOT a skill invocation via Skill tool (anti-superpowers). It is an inline
protocol with canonical reference in `_references/runtime/diagnose-protocol.md`.

Pipeline:
1. Build feedback loop (THE skill — without loop, no progress)
2. Reproduce — confirms exact symptom
3. Hypothesise — 3-5 ranked falsifiable
4. Instrument — tag logs `[DEBUG-xxxx]`, debugger > logs
5. Fix + regression test (if there is a correct seam)
6. Cleanup + post-mortem

Stage 05 output: `output/diagnose-report.md` with repro evidence,
hypotheses, root cause, fix, test path.

For HITL bugs: `_config/hitl-loop.template.sh` bash template.

Canonical doc: `references/diagnose-protocol.md`.
