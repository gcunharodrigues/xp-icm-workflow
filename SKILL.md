---
name: xp-icm-workflow
description: One-shot bootstrap ICM (Interpretable Context Methodology) that creates the L0/L1/L2/L3 structure + git branch + hooks in a project and exits; subsequent sessions read L1+L2 from the current stage. Supports 9 stages (00 recon → 08 feedback intake), 11 profiles × 4 tiers (incl. fullstack), subagents via Agent Tool stage 04, deterministic Wave Planner, Recovery Wizard, AGENT-BRIEF protocol, ubiquitous language layer, ADR 3-criteria gate, diagnose protocol, triage state machine, OUT-OF-SCOPE knowledge base, DESIGN.md format for frontend/fullstack. Use when starting a new ICM workspace, multi-stage project with human review between steps, complex feature requiring discovery+design+implementation+review+merge, or implementation that benefits from parallelism via subagents. Skip when task is trivial (1 file), simple bug fix, cosmetic refinement, or continuing an existing workspace (fresh session reads L1+L2 on its own — do not re-invoke).
type: rigid
---

# xp-icm-workflow v3.12.1

> **Skill is a midwife, not an orchestrator.** One-shot bootstrap creates the structure. Filesystem governs the cycle. **1 stage = 1 session**: each stage ends with a dual handoff (verbal + `_kickoff.md` file) and the session exits. The next session starts fresh.

> **Theoretical basis:** Interpretable Context Methodology (VanClief & McDermott, 2025) — replaces framework orchestration with filesystem structure. Numbered folders represent stages; markdown files carry prompts and context. See `references/icm-paper-summary.md`.

---

## Instruction Priority

1. **User explicit instructions** (project CLAUDE.md, AGENTS.md, direct messages) — always win.
2. **L0/L1/L2 of the workspace** — project/stage-specific instructions in progress.
3. **This skill (`/xp-icm-workflow`)** — only active during one-shot bootstrap.
4. **Specialized skills (superpowers:*)** — summarized in workspace L3; real invocation only via escape hatch.
5. **Default system prompt** — loses to 1-4.

---

## When to Use

Invoke `/xp-icm-workflow` to **start** a new workspace. Typical cases:

- New project (greenfield or existing) with multiple stages + human review between steps.
- Complex feature (discovery → design → implementation → review → merge).
- Implementation that benefits from parallelism (subagents via Agent Tool in stage 04).
- Want to see, edit, and approve intermediate artifacts (L4 outputs per stage).
- Non-trivial architectural decisions that require an A/B/C menu.

## When NOT to Use

- Trivial code task (1 file, no decisions, no new tests) — use `/xp-workflow` directly.
- Simple bug fix — use `/xp-workflow` directly.
- Cosmetic refinement.
- Continuing an existing workspace — open a new session; it reads L1+L2 and proceeds on its own. Do NOT re-invoke the skill.

---

## What this skill does (one-shot bootstrap)

```
INPUT  →  Skill invoked with profile + tier + project_root
OUTPUT →  Workspace ready: folder structure + L0/L1 filled +
          L2 templates for the 9 stages + superpowers summaries + git
          branch created + pre-commit hook installed + initial commit
EXIT   →  Skill EXITS. New session resumes via L1+L2.
```

The skill **does not persist** during the cycle. It is not an orchestrator. It does not invoke other skills at project runtime. It is a short *project starter*.

**Anti-superpowers (non-negotiable rule):** during bootstrap, NEVER invoke `Skill` tool with `superpowers:*` (brainstorming, executing-plans, writing-plans, test-driven-development, debugging, requesting-code-review, etc.). Discovery/brainstorm belong to `stages/00_recon/` → `stages/01_discovery/` of the workspace. TDD/debug become inline instructions in each L2. Summaries (200tok each) live in `workspaces/NNN-slug/_references/superpowers-summary/` as reference. Escape hatch: real invocation only with explicit human approval per turn.

---

## Intent inference (prompt without args)

User can invoke `/xp-icm-workflow` with **free-form description** instead of args (e.g. "create skill that extracts design system from URL"). Protocol:

1. **Do NOT trigger `superpowers:*`** (see rule above). Discovery lives in the workspace.
2. **Infer profile/tier from prompt** (heuristics):

   | Signal in prompt | Inferred profile |
   |---|---|
   | "skill", "agent", "subagent", "LLM tool" | `agent_ia` |
   | "lib", "SDK", "framework", "package" | `framework_library` |
   | "CLI", "command", "command-line tool" | `cli_tool` |
   | "web page", "React/Vue component", "UI" | `app_web_frontend` |
   | "API", "backend", "endpoint", "microservice" | `app_web_backend` |
   | "dashboard", "BI", "analytics" | `dashboard` |
   | "EDA", "notebook", "data analysis" | `data_analysis` |
   | "train model", "ML pipeline", "fine-tune" | `ml_project` |
   | "article", "paper", "technical post" | `technical_article` |
   | "POC", "spike", "throwaway experiment" | `experiment` |

   **Default tier:** `development`. Adjust to `experimental` for POC/spike, `production` for an app already in production, `tool` for internal desktop use.

3. **Confirm with human** short menu:

   ```
   Inferred: profile=<X> tier=<Y> workspace-name=<slug>
   [a] confirm   [b] correct   [c] cancel
   ```

   Accepts OR corrects. Open discovery questions should be deferred to the next session; do **NOT** enter Q&A dialogue pre-bootstrap (that is the territory of `01_discovery`).

4. **Execute bootstrap** with confirmed args (`bash scripts/bootstrap.sh --profile X --tier Y --workspace-name slug`).

5. **Write initial seed** for the next session in `workspaces/NNN-slug/stages/00_recon/_seed.md`:

   ```markdown
   ---
   layer: L4-seed
   stage: 00_recon
   created_by: bootstrap
   created_at: <ISO8601>
   ---

   # Seed — pre-recon input

   ## User intent (literal)
   <original user prompt, quoted>

   ## Inference made at bootstrap
   - Profile: <X>  Why: <heuristic>
   - Tier: <Y>  Why: <heuristic>

   ## Decisions/context already captured (if any)
   - <Q1, Q2, ... raised during bootstrap dialogue, with choices and tradeoffs>

   ## External resources referenced
   - <repos, URLs, papers cited by user, with short summary if already fetched>

   ## Open items for 00_recon
   - <Qs still unanswered — e.g. output format, dependencies>
   ```

   This file is a declared input in the `Inputs` section of `stages/00_recon/CONTEXT.md` (L2). The next session reads it and starts from it rather than from scratch.

6. **Commit the seed** atomically with bootstrap (pre-commit hook validates prefix `workspace NNN: bootstrap seed`).

7. **EXIT.** Final summary includes: workspace path, branch, next steps, and the line **"Pre-recon seed at stages/00_recon/_seed.md"**.

**When NOT to infer:** if the prompt is ambiguous or the user wants to choose manually (signals: "help me choose", "what are the options", "explain the differences"), skip step 2 and go directly to the interactive menu of `bootstrap.sh` (step 3 with full table).

---

## Division of Responsibilities

| Who | Decides / Does |
|---|---|
| **Human** | Business scope, profile/tier, stage approval, editing intermediate outputs, recovery decisions |
| **Skill `/xp-icm-workflow`** | One-shot: creates ICM structure + git branch + hook + initial commit. Exits. |
| **L0** (`workspaces/NNN/CLAUDE.md`) | Immutable identity: absolute paths, profile/tier, non-negotiable rules |
| **L1** (`workspaces/NNN/CONTEXT.md`) | Single state machine: stage_atual, sub_stage, status, history append-only |
| **L2** (`workspaces/NNN/stages/<NN>/CONTEXT.md`) | Stage instructions: read order, expected outputs, gates |
| **L3** (stable) | Conventions, profile-matrix, canonical stop-points, superpowers summaries |
| **L4** (nascent outputs) | discovery.md, plan.md, ADRs, wave-plan.md, reports |

---

## CLI

```bash
/xp-icm-workflow profile=<X> tier=<Y> [project-root=<path>] [workspace-name=<slug>] [logs-root=<path>] [override=<yaml>]
```

**Args resolution (Q9 + L1):**

1. **CLI args** win everything (Q9-A''').
2. **`.icm-profile.local.yaml`** detected in project_root: human prompt "use this?".
3. **Interactive menu** if missing (Q9-A').

**Canonical profiles (11):** `app_web_backend`, `app_web_frontend`, `fullstack`, `dashboard`, `data_analysis`, `ml_project`, `agent_ia`, `cli_tool`, `framework_library`, `technical_article`, `experiment`.

**Tiers (4):** `experimental`, `tool`, `development`, `production`.

Details of the matrix in `templates/_config/profile-matrix.md` (11 × 4 = 44 combos).

---

## What gets created

```
<project_root>/
├── .git/
│   └── hooks/
│       └── pre-commit              [hook installed, R2.3+R3.3+R3.10+R5.4]
├── .gitignore                      [updated: .icm-profile.local.yaml]
├── workspaces/
│   ├── .index.md                   [registry of active/completed workspaces]
│   └── NNN-slug/                   [workspace root]
│       ├── CLAUDE.md               [L0 — immutable identity]
│       ├── CONTEXT.md              [L1 — single state machine]
│       ├── stages/
│       │   ├── 00_recon/           [L2 templates — Wave 3 of skill populates]
│       │   ├── 01_discovery/
│       │   ├── 02_design/
│       │   ├── 03_wave_planner/
│       │   ├── 04_implementation_waves/
│       │   ├── 05_verification/
│       │   ├── 06_review/
│       │   ├── 07_merge/
│       │   └── 08_feedback_intake/
│       ├── _config/
│       │   ├── profile-effective.yaml  [profile base + override + hash]
│       │   └── profile-matrix.md       [human reference 10×4]
│       └── _references/
│           ├── runtime/                [protocols: subagent, wave-planner, recovery, etc.]
│           └── superpowers-summary/    [10 summaries 200tok each]
```

**Branches created:**

- `<base_branch>` — real project code (usually `main`).
- `workspace/NNN-slug` — ONLY state files (`workspaces/NNN-slug/*` + `docs/decisions/*` via exception). NEVER touches `src/`.
- `wave-NNN-N/<task-slug>` — code + tests for the task. Created from `<base_branch>`. Lead merges into `<base_branch>` at the end of the wave.

---

## After bootstrap — 1 stage = 1 session (canonical)

The skill **exits**. Next steps follow the **1-stage-1-session** protocol (supersedes Q3 batched from plan v1; see `references/session-handoff-protocol.md`):

1. **User opens a new** Claude session in project_root.
2. Session automatically reads:
   - `workspaces/NNN-slug/CLAUDE.md` (L0, identity)
   - `workspaces/NNN-slug/CONTEXT.md` (L1, state machine)
   - `workspaces/NNN-slug/stages/<stage_atual>/CONTEXT.md` (L2, stage instructions)
   - `workspaces/NNN-slug/stages/<stage_atual>/_kickoff.md` if generated by the previous session
3. Session executes the stage per L2.
4. **End of stage:** session updates L1, generates `_kickoff.md` in the next stage, commits atomically, prints verbal KICKOFF block to user, **EXITS**.
5. User opens new session, pastes the KICKOFF prompt, repeats the cycle.

**Accepted trade-off:** each stage pays 1 cache miss (~2-3k tokens warm-up) in exchange for fresh context + total non-linear token spend that is lower overall. Empirical: batched B+D from beta1/beta2 grew context beyond the 2-8k per L2 target; 1-stage-1-session stays within it.

**Stage 04 exception (decision 2a):** each wave = 1 lead session (sub-waves within the same session). Lead generates kickoff between waves within stage 04 or to stage 05 at the end.

**Stage 07 → 08 automatic transition:** after confirmed merge, session immediately transitions to stage 08 with `status: COMPLETED_AWAITING_HUMAN`. Workspace stays alive waiting for the human to return with free-form feedback after real use (no deadline). Generates kickoff for 08.

**Stage 08 real terminal (exits inferred from feedback intent):** human pastes free-form feedback in session 08 (no raw A/B/C menu); session **infers** A/B/C autonomously via heuristics and mini-confirms before executing.
- **A close** → workspace `COMPLETED` + lessons in `docs/lessons.md` (signals: "all good", silence).
- **B restart stage X** → `iteration++`, kickoff to stage X (mapping: bug in tests → 05, code → 04, design → 02, etc.).
- **C spawn** → workspace closes + instruction for user to invoke `/xp-icm-workflow spawn_from=<NNN>` in a new session (signals: "pivot", "new project").

**Beta1/beta2 migration (decision 4B):** existing workspaces in batched mode continue batched; no forced conversion. Only workspaces created via `/xp-icm-workflow` post-beta3 use 1-stage-1-session.

**Recovery:** if a session crashes mid-stage → next session triggers `scripts/recovery-wizard.py` automatically via L2 pre-flight check. Detects 6 types of inconsistency (R2.7) and proposes actions.

**Stop points:** 12 canonical stop points in `_config/stop-points.md` calibrated by tier. Triggered: agent pauses, writes A/B/C menu, updates L1 `status: BLOCKED_STOP_POINT`. Human responds, session resumes.

**Subagents (stage 04):** parallelism waves via Agent tool. Cap by tier (2/3/5/5). Deterministic Wave Planner + LLM review subagent. Details in `_references/runtime/subagent-protocol.md`.

**Feedback intake (stage 08):** triggered manually by the human after real use. 3 exits: A) close workspace; B) restart stage X (iteration++); C) spawn new workspace inheriting lessons+ADRs.

---

## Pre-flight runtime check

Bootstrap runs `scripts/check-runtime.sh` before any action. Aborts cleanly if runtime fails:

- Python 3.11+ (tested on 3.13)
- PyYAML
- pytest (to run skill tests locally)
- git 2.30+
- bash POSIX (Linux/macOS native; Windows via Git Bash)
- bats (optional locally; CI runs via apt on Ubuntu runner)

Suggested permissions allowlist in `system-requirements.md`.

---

## Anti-patterns (do not use)

- `git commit --no-verify` in the workspace — pre-commit hook validates L1↔outputs atomicity and prefixes. Bypass breaks audit. Investigate and fix content, do NOT bypass the hook.
- Re-invoking `/xp-icm-workflow` in an existing workspace — only for creating new ones. To resume, open a new session; it reads L1.
- Editing L1 (`CONTEXT.md`) manually without understanding the schema — use `scripts/recovery-wizard.py` if you need to rebuild.
- Editing committed L4 outputs (decisions.md, ADRs) without a new version or superseding — see `_config/xp-conventions.md`.
- **Invoking `superpowers:*` skills during bootstrap** (brainstorming, writing-plans, executing-plans, test-driven-development, debugging, etc.). Brainstorm lives in `stages/01_discovery/`. TDD/debug become instructions inside each L2. Summaries in `_references/superpowers-summary/` (200tok each) serve as reference. Bypassing via Skill tool breaks L1↔outputs atomicity.
- **Q&A dialogue pre-bootstrap instead of bootstrapping.** When user invokes the skill with a free-form description, infer profile/tier (see "Intent inference"), confirm with short menu, bootstrap, and send open items to `_seed.md` of `00_recon`. Do NOT conduct full discovery before creating the workspace.

---

## References

| Doc | Content |
|---|---|
| `references/state-machine-schema.md` | Full L1 schema (yaml frontmatter + history append-only) |
| `references/session-handoff-protocol.md` | **1 stage = 1 session**: dual handoff, `_kickoff.md` schema, anti-patterns |
| `references/git-hooks.md` | Pre-commit + commit-msg hooks: rules, regex patterns, anti-bypass |
| `references/recovery-wizard.md` | 6 inconsistencies detected + A/B/C actions |
| `references/changelog.md` | Skill versions |
| `references/v2.4-snapshot/` | Snapshot of prior v2.4 (for historical reference) |
| `system-requirements.md` | Runtime + permissions allowlist |
| `templates/_config/profile-matrix.md` | Canonical matrix 11 profiles × 4 tiers |
| `templates/workspace/CLAUDE.md.tpl` | L0 template with placeholders |
| `templates/workspace/CONTEXT.md.tpl` | L1 template with placeholders |

**Algorithm references:**

- `references/wave-planner-algorithm.md` — DAG construction, sub-waves, LLM review subagent
- `references/subagent-protocol.md` — spawn via Agent tool, plan approval, mid-wave reduce
- `references/stop-points-canonical.md` — 12 stop points + thresholds by tier
- `references/4-block-contract-template.md` — WHAT / HOW / OUT OF SCOPE / VALIDATION
- `references/feedback-intake-stage08.md` — 3 exits A/B/C
- `references/profile-matrix.md` — calibration by profile/tier (skipped stages, etc.) — copy in `templates/_config/profile-matrix.md`
- `references/forensic-plus-protocol.md` — Forensic+ wave reviewer audit (7 checks v3.9.0: assertions count, files declared, scope creep, TODO, acceptance↔test, OUT OF SCOPE, ADR drift)
- `references/critic-protocol.md` — L3 LLM orthogonal critic (v3.9.0): fresh context, anti-sycophancy, triplet output, model = TIER_CEILING
- `references/lead-resolution-protocol.md` — buckets B1 REWRITE_SPEC / B3 DIRECT_IMPL / B4 VOID_TASK (v3.9.0) when per-task loop exhausts cap OR convergence trip OR catastrophic
- `references/mocking-guidelines.md` — boundaries only (HTTP/DB/time/randomness/env); never internals (v3.9.0, mattpocock alignment)
- `references/e2e-coverage-protocol.md` — E2E reinforcement (v3.10.0): wave-planner auto-flag user-facing tasks, forensic+ Check 8, L4 wave gate universal tier dev/prod, Stage 05 audit suite freshness
- `references/maintainer-checklist.md` — How to modify the skill itself (new script, doc, template, stage, version bump, drift detector)

**Test references:**

- `tests/run.sh` — orchestrator (pytest + bats)
- `tests/unit/` — unit + property-based via Hypothesis
- `tests/integration/` — bats integration (CI-only)
- `tests/e2e/` — bats e2e (CI-only)
- `.github/workflows/test-skill.yml` — CI GitHub Actions (Wave 6)
