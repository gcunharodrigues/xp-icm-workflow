# xp-workflow ↔ xp-icm-workflow Integration

> **Version:** v3.0.0-beta5
> **Skill:** `xp-icm-workflow`
> **Purpose:** canonical doc of how `xp-icm-workflow` (this skill, workspace ICM midwife) relates to `xp-workflow` (sister skill in the plugin, direct task executor). Defines when to use each, invocation hierarchy, shared conventions and the "lift" flow from one to the other.

> **Decision origin:** §4.10 of plan + Q1 (skill = midwife), Q3 (batched sessions) + Aura project memory (xp-workflow is the everyday skill; xp-icm-workflow is only for formal projects).

---

## 1. When to use each

### 1.1 `/xp-workflow` directly

Use when the task is **trivial or cosmetic** and does not need ICM structure:

- 1 file, no architectural decisions.
- Simple bug fix (test reproduces, obvious fix, regression covered).
- Docstring refinement, rename, local refactor.
- Config adjustment, dependency bump without stack implications.
- Single session, ≤30min, ≤2k tok.

### 1.2 `/xp-icm-workflow`

Use when there is **structure, parallelism or non-trivial decisions**:

- New project (greenfield or existing) with multiple stages + human review between steps.
- Complex feature (discovery → design → impl → review → merge).
- Implementation that benefits from parallelism (subagents in stage 04).
- Want to see, edit and approve intermediate artifacts (L4 outputs per stage).
- Non-trivial architectural decisions needing A/B/C menu + formal ADR.
- Tier `development` or `production` with mandatory auditability.

### 1.3 Use **neither**

- Conceptual question ("how does X work").
- Exploratory conversation without concrete action.
- Pure research task (cites sources, does not write code).

---

## 2. Side-by-side comparison

| Dimension | `xp-workflow` | `xp-icm-workflow` |
|---|---|---|
| Type | Direct executor | One-shot bootstrap + filesystem-driven |
| Formal stages | Internal phases 0-10 (in skill's SKILL.md) | 9 stages materialized in folders (`stages/00..08`) |
| Typical sessions | 1 end-to-end session | N sessions (1 per stage or batch) |
| External state machine | n/a (skill is stateless per session) | L1 `<workspace>/CONTEXT.md` (yaml frontmatter + append-only history) |
| Parallelism | n/a (sequential single-agent) | subagents in stage 04 (cap 2/3/5/5 per tier, isolated branches) |
| Formal ADRs | Can write in `docs/decisions/` if task calls for it | Mandatory when stage 02 triggers architectural stop point |
| Profile/Tier | Implicit (inferred from task) | Explicit in L0 (`profile: app_web_backend`, `tier: development`) — calibrates rigor |
| Stop points | Yes (internal list from `xp-workflow`) | Yes (12 canonical in `references/stop-points-canonical.md`, calibrated by tier) |
| 4-block contract | Internal Phase 1 | Mandatory per task in `plan.md` (stage 02), consumed in stage 04 |
| Deterministic Wave Planner | n/a | Yes (`scripts/wave-planner-script.py`) + LLM review subagent |
| Recovery Wizard | n/a | Yes (6 inconsistencies detected in pre-flight) |
| Pre-commit hook | n/a | Installed by bootstrap; validates L1↔outputs atomicity |
| Git branches | Works in `main` or existing branch | Creates `workspace/NNN-slug` (state) + `wave-N/<task>` (code) |
| Feedback intake stage 08 | n/a | Yes — human triggers after real use, 3 exits A/B/C |
| Target token budget (session) | 2-8k | 1-6k per stage (more aggressive) |

---

## 3. Invocation hierarchy (priority order)

Defined in `SKILL.md` §Instruction Priority. Recap:

1. **User explicit instructions** (project's CLAUDE.md, AGENTS.md, direct messages) — always win.
2. **L0/L1/L2 of ICM workspace** — project/stage-specific instructions currently in progress (only when there is an active ICM workspace).
3. **`/xp-icm-workflow`** — only active during the one-shot bootstrap.
4. **Specialized skills** — `xp-workflow`, `superpowers:*` etc.
5. **Default system prompt** — loses to 1-4.

Practical implications:

- Session inside ICM workspace (active L1): L2 rules of the stage beat any specialized skill if there is a conflict.
- Session without ICM workspace: `xp-workflow` is the default for code tasks.
- Bootstrap of `xp-icm-workflow` runs once and exits; after that, it is the filesystem that governs.

---

## 4. Shared conventions

### 4.1 `xp-conventions.md` (single conventions file)

Defines standards applicable to the workspace's profile/tier. In v3, it is the **only** conventions file — contains both shared rules (naming, TDD, clean code) and ICM-specific rules (branches, commit prefixes, stop points).

Shared rules (derived from xp-workflow v3):
- TDD mandatory if `tier ∈ {development, production}`.
- Conventional Commits (`feat`, `fix`, `chore`, `refactor`, `docs`, `test`).
- Functions 4-20 lines, files <300/500, max nesting 2.
- Docstrings mandatory in public functions (4 elements).
- Clean Code gates per language (formatter, linter, type check, complexity, security, secrets, coverage).
- Post-cycle dirt check (duplication, naming, size).
- LGPD/PII handling baseline.
- Secrets policy (never commit, env var only).

ICM-specific rules:
- Commit prefixes by context: `workspace NNN:` on workspace branch (hook-validated), Conventional Commits on wave branches and base branch (no hook validation), `intake:`/`feedback:` on stage 08 (hook-validated).
- Branches by context (`workspace/NNN` for state, `wave-NNN-N/task` for code).
- Never `--no-verify` on workspace branch.
- Files touched discipline: each task declares its footprint.

**Current state (v3.0.0-beta5):** the file `xp-conventions.md` exists as `templates/workspace/_config/xp-conventions.md.tpl` and is rendered to `<workspace>/_config/xp-conventions.md` at bootstrap with filled placeholders.

---

## 5. "Lift" flow: from `xp-workflow` to `xp-icm-workflow`

Typical scenario: user starts with `/xp-workflow`, discovers the task grew (3+ parallel tasks, architectural decisions appearing, review between steps would be good). Can "promote" to `/xp-icm-workflow`.

### 5.1 Signals that promotion is warranted

- Task grew to 3+ files with potential files-conflict.
- A stack/db/dep decision appeared that deserves a formal ADR.
- User wants to see intermediate outputs before proceeding.
- Tier went up (from `tool` to `development`).
- Bug fix revealed that redesign is needed (will become a complex feature).

### 5.2 How to promote (new session)

The `xp-icm-workflow` skill is a **one-shot** midwife; it cannot be invoked from within `xp-workflow`. The user (or agent) opens a **new session** and runs:

```
/xp-icm-workflow profile=<X> tier=<Y> project-root=<absolute-path> workspace-name=<slug>
```

Bootstrap creates the ICM structure. Partial work done in `xp-workflow` is treated as **input for stage 00 recon** — agent reads the current branch, infers already-implicit ADRs, records in `recon-report.md`.

### 5.3 How **not** to promote

- Do not invoke `/xp-icm-workflow` inside an active `xp-workflow` session — breaks the one-shot separation.
- Do not try to "merge" workspaces: a new ICM workspace is born clean, inherits context via recon.
- Do not manually rename branches — bootstrap creates its own.

---

## 6. Coexistence (same project, both skills)

The same `project_root` may have:

- `workspaces/042-feat-auth/` (ICM cycle in progress).
- `main` or other active branches where `/xp-workflow` operates directly.
- Separate accounts: `workspace/042-feat-auth` touches ONLY state files; `main` (and its descendants) touches code.

**Non-interference rule:** `xp-workflow` session in `main` does **not** read `workspaces/NNN/` (not its input). `xp-icm-workflow` session in an active workspace respects L2 §"Does Not Read" (does not touch `src/` outside stage 04 branches).

---

## 7. Conceptual phase mapping (v3 ↔ v3)

Quick recap — `xp-workflow` v3 has internal phases 0-10; `xp-icm-workflow` v3 has 9 external stages materialized in folders.

| Phase `xp-workflow` | Stage `xp-icm-workflow` | Notes |
|---|---|---|
| 0 Reconnaissance | 00 recon | ICM materializes output in `stages/00_recon/output/baseline.md` |
| 1 4-block communication | Embedded in stage 02 (plan.md schema) | 4-block-contract-template.md formalizes |
| 2 Division of responsibilities | Embedded in `SKILL.md` §Division | L0/L1/L2/L3/L4 table covers |
| 3 Bootstrap or continuation | One-shot bootstrap (this skill) | Exits after — filesystem governs |
| 4 TDD cycles | 04 implementation_waves (each subagent runs the 7 steps) | See `4-block-contract-template.md` §3 |
| 5 Stop points | In any stage with a decision | 12 canonical in `stop-points-canonical.md` |
| 6 CI Gate | Steps 3 and 5 of TDD cycle + 05 verification | Double verification |
| 7 Pair check | Wave-reviewer (always) + peer-reviewer ad-hoc (critical path) | Details in `subagent-protocol.md` §5, §10 |
| 8 Post-deploy | 08 feedback_intake (universal all tiers) | 3 exits A/B/C |
| 9 Tech debt dashboard | `docs/tech_debt.md` maintained by stage 04 | Sample-check in 05/06 |
| 10 Self-revision | **Dropped** | ICM skill is a starter, not a runtime |

---

## 8. Documents shared between both skills

| Document | Path | Who writes | Who reads |
|---|---|---|---|
| `docs/decisions/NNNN-slug.md` | `<project_root>/docs/decisions/` | stage 02 design (ICM) or xp-workflow ad-hoc | any subsequent stage; xp-workflow consults |
| `docs/lessons.md` | `<project_root>/docs/lessons.md` | stage 08 exit A (ICM); xp-workflow ad-hoc | session resumption; pre-cooked by lead in stage 04 |
| `docs/tech_debt.md` | `<project_root>/docs/tech_debt.md` | subagent in stage 04 declaring debt | stages 04, 05, 06 |
| `xp-conventions.md` | `<workspace>/_config/xp-conventions.md` (ICM) or implicit (xp-workflow) | bootstrap renders `templates/_config/xp-conventions.md.tpl` | both skills |

---

## 9. Cross-references

| Doc | Content |
|---|---|
| `SKILL.md` §When to Use / §When NOT to Use | Canonical selection criteria |
| `SKILL.md` §Instruction Priority | Full hierarchy 1-5 |
| `references/stage-templates.md` | Mapping of the 9 ICM stages |
| `references/superpowers-mapping.md` | How ICM uses superpowers (200tok summaries) |
| `references/v2.4-snapshot/xp-workflow-integration.md` | Previous v2.4 version (historical reference) |
| Plugin `xp-workflow` SKILL.md | Internal phases 0-10 |
