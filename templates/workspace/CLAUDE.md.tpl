---
layer: L0
workspace: "{{WORKSPACE}}"
profile: "{{PROFILE}}"
tier: "{{TIER}}"
project_root: "{{PROJECT_ROOT}}"
base_branch: "{{BASE_BRANCH}}"
workspace_branch: "workspace/{{WORKSPACE}}"
profile_effective_hash: "{{PROFILE_EFFECTIVE_HASH}}"
logs_root: {{LOGS_ROOT}}
created_at: "{{CREATED_AT}}"
icm_skill_version: "{{SKILL_VERSION}}"
---

# Workspace {{WORKSPACE}} — L0 (identity)

## Purpose

L0 is the immutable constitution of this workspace. Every agent in every stage reads this file FIRST. It defines identity, absolute paths, and non-negotiable rules.

## Identity

| Field | Value |
|---|---|
| Workspace | `{{WORKSPACE}}` |
| Profile | `{{PROFILE}}` |
| Tier | `{{TIER}}` |
| Project root | `{{PROJECT_ROOT}}` (absolute path) |
| Base branch | `{{BASE_BRANCH}}` |
| Workspace branch | `workspace/{{WORKSPACE}}` |
| Logs root | `{{LOGS_ROOT}}` |
| Profile hash | `{{PROFILE_EFFECTIVE_HASH}}` |

## Absolute paths (source of truth)

| Resource | Path | Real branch |
|---|---|---|
| Workspace root | `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/` | workspace |
| L1 state | `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/CONTEXT.md` | workspace |
| Stages | `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/<NN>_*/` | workspace |
| Config | `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_config/` | workspace |
| Conventions | `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_config/xp-conventions.md` | workspace |
| Ubiquitous Language (L3) | `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_config/CONTEXT.md` | workspace |
| OUT-OF-SCOPE kb | `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_out-of-scope/` | workspace |
| Runtime refs | `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/runtime/` | workspace |
| Superpowers summaries | `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/superpowers-summary/` | workspace |
| Skill dir | `{{SKILL_DIR}}` | (global filesystem) |
| Project CLAUDE.md | `{{PROJECT_ROOT}}/CLAUDE.md` (external state dashboard; maintained by `handoff.py`) | workspace (migrates to base on exit A) |
| **Worktree base branch (`.icm-main/`)** | `{{PROJECT_ROOT}}/.icm-main/` | base (`{{BASE_BRANCH}}`) |
| Project ADRs | `{{PROJECT_ROOT}}/.icm-main/docs/decisions/` | base |
| Project lessons | `{{PROJECT_ROOT}}/.icm-main/docs/lessons.md` | base |
| Tech debt | `{{PROJECT_ROOT}}/.icm-main/docs/tech_debt.md` | base |
| Design System (profiles `app_web_frontend`, `fullstack`) | `{{PROJECT_ROOT}}/.icm-main/DESIGN.md` | base |
| Existing code (read-only cross-branch) | `{{PROJECT_ROOT}}/.icm-main/src/`, `{{PROJECT_ROOT}}/.icm-main/tests/` etc. | base |

**Rule:** ALL doc references resolve absolutely from `{{PROJECT_ROOT}}`. Skill scripts resolve absolutely from `{{SKILL_DIR}}/scripts/`. NEVER use relative `scripts/` (assumes wrong CWD). NEVER use relative `../../`. Path leakage = diagnose bug B2.

**Parallel worktree model (v3.4.0):** when the branch checked out at `{{PROJECT_ROOT}}` is `workspace/{{WORKSPACE}}`, paths like `{{PROJECT_ROOT}}/docs/decisions/` do NOT exist in the working tree (workspace branch has no `docs/`). To read/write those paths, use the linked worktree at `{{PROJECT_ROOT}}/.icm-main/` (always checked out at `{{BASE_BRANCH}}`). Canonical doc: `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/runtime/worktree-model.md`.

## Non-negotiable rules

### 1. Anti-bypass (B1)

NEVER use `git commit --no-verify` in this workspace. The pre-commit hook validates `outputs ↔ L1` atomicity and commit prefixes. If the hook blocks: investigate and fix the content, do not bypass the hook.

### 2. Agent CWD

Each session starts by reading its L2 (`stages/<NN>/CONTEXT.md`). The L2 declares the expected CWD:

- Sessions 00–03, 05–08: CWD = `{{PROJECT_ROOT}}` (workspace branch checkout).
- Session 04 (lead): CWD = `{{PROJECT_ROOT}}` (workspace branch).
- Subagent in wave: CWD = `{{PROJECT_ROOT}}` (branch `wave-{{WORKSPACE_NUM}}-<N>/<task-slug>`).

### 3. Branches + parallel worktree

Three types of ICM branches coexist via git worktree:

- `{{BASE_BRANCH}}` — real project code + ADRs + lessons + tech_debt + `CLAUDE.md` dashboard in idle state.
- `workspace/{{WORKSPACE}}` — only state files (`workspaces/{{WORKSPACE}}/*`) + active `CLAUDE.md` dashboard. NEVER touches `src/`, `tests/`, `docs/decisions/`, `docs/lessons.md`, `docs/tech_debt.md`.
- `wave-{{WORKSPACE_NUM}}-<N>/<task-slug>` — task code + tests. Created from `{{BASE_BRANCH}}`. Lead merges into `{{BASE_BRANCH}}` at end of wave.

Worktree:

- `{{PROJECT_ROOT}}/` (main worktree) — during ICM cycle, normally checked out at `workspace/{{WORKSPACE}}`.
- `{{PROJECT_ROOT}}/.icm-main/` (linked worktree) — always checked out at `{{BASE_BRANCH}}`. Created by bootstrap (`git worktree add .icm-main {{BASE_BRANCH}}`). Listed in `.gitignore` of all branches. Cleanup only on exit A of the last workspace.
- Subagents in stage 04 use `Agent(isolation: "worktree")` — tool creates an ephemeral worktree per subagent at `wave-{{WORKSPACE_NUM}}-<N>/<task-slug>`.

The pre-commit hook at `{{PROJECT_ROOT}}/` rejects commits on `workspace/*` that touch paths outside `workspaces/*`, `workspaces/.index.md`, `.gitignore`, `CLAUDE.md` (dashboard). ADRs / lessons / tech_debt are **not** in the hook whitelist — they must be committed via `cd .icm-main && git commit ...` (which operates on the base branch automatically).

Canonical model doc: `_references/runtime/worktree-model.md`.

### 4. Profile + Tier calibrate rigor

Profile = `{{PROFILE}}`. Tier = `{{TIER}}`. Canonical calibration in `_config/profile-matrix.md`. Defines:

- Skipped stages.
- Subagent cap per wave (2/3/5/5 by tier).
- TDD required vs optional.
- Security gate on/off.
- Calibrated stop points (5 paid service, 7 over-engineering, 8 PII).

Local override in `.icm-profile.local.yaml` (at `{{PROJECT_ROOT}}`). Hash recomputed on pre-flight.

### 5. Stop Points

15 canonical stop points in `_config/stop-points.md`. Trigger: agent pauses, writes A/B/C menu, updates L1 `status: BLOCKED_STOP_POINT`. Human responds, session resumes.

### 6. ADRs

ADRs created in stage 02 are nascent L4; after commit to `{{BASE_BRANCH}}` they become immutable L3. Editing an existing ADR = new version (`0001-stack-v2.md`) or superseding (`0042-supersedes-0001.md`). Direct edits prohibited by pre-commit hook.

Canonical stage 02 workflow (v3.4.0):

```
1. Write {{PROJECT_ROOT}}/.icm-main/docs/decisions/NNNN-<slug>.md
2. cd {{PROJECT_ROOT}}/.icm-main
3. git add docs/decisions/NNNN-*.md
4. git commit -m "docs(decisions): <slug> (workspace {{WORKSPACE}})"
5. cd {{PROJECT_ROOT}}
6. plan.md references filename relative to `.icm-main/docs/decisions/`
```

NEVER attempt `git add docs/decisions/...` directly from the main worktree on a workspace branch — pre-commit hook will reject it.

### 7. Language

Content in English. Code identifiers, paths, and commands in English.

### 8. Cross-branch reads via `.icm-main/`

Sessions in any stage that need to read content from the base branch
(active ADRs, inherited lessons, accumulated tech_debt, existing code
for diagnose) MUST read from `{{PROJECT_ROOT}}/.icm-main/<path>`. The Read tool
works directly — no `git show base:<path>` required.

Before the first cross-branch read of the session:

- Verify `.icm-main/` exists at `{{PROJECT_ROOT}}` (present since
  bootstrap; absent = recovery wizard).
- Optional sync: if the base branch has advanced since the last session,
  run `cd {{PROJECT_ROOT}}/.icm-main && git fetch && git pull --ff-only`
  (manually when relevant; stage 07 lead runs this after each merge).

### 9. Superpowers via summary, not Skill tool

Skills `superpowers:*` (brainstorming, executing-plans, test-driven-development, debugging, etc.) MUST NOT be invoked via the `Skill` tool during the ICM cycle.

- **Use:** summaries in `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/superpowers-summary/` (200tok each). Apply principles inline.
- **Escape hatch:** real invocation only with explicit human approval per turn (human writes "ok, invoke superpowers:X").
- **Why:** brainstorm/discovery lives in `stages/01_discovery/`. TDD/debug become instructions inside each L2. ICM governs the cycle via filesystem; superpowers as a parallel skill breaks L1↔outputs atomicity and bypasses governance.
- **Bootstrap pending with no args:** ask OR infer profile/tier. NEVER jump to free-flow superpowers.

### 10. Runtime side-effects = human responsibility (v3.7.0)

Runtime side-effects (dev servers, background tasks, docker containers, orphan wave branches, working tree dirt, untracked artifacts) are the **human's responsibility**, not the ICM skill's. The skill:

- **Detects** via `{{SKILL_DIR}}/scripts/runtime-status.py` run at stage 08 entry hook (exit A/B/C step 0 mandatory).
- **Prints** a 6-category checklist with detected items.
- **Waits** for human confirmation per category before transitioning (strict universal — all tiers).
- **NEVER kills a process, deletes a branch, or forces cleanup automatically.** Destructive actions require explicit human decision.

If human cancels checklist mid-confirmation or cleanup command fails:
- Status stays `BLOCKED_STOP_POINT` with stop point `runtime_cleanup_failed` (#15).
- Session pauses, writes A/B/C menu; human resolves outside ICM and resumes.

Canonical doc: `_references/runtime/runtime-cleanup-protocol.md`.
Helpers: `runtime-registry.py` (CRUD), `runtime-status.py` (checklist).

## Read order for any agent

1. `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/CLAUDE.md` (this file, L0)
2. `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/CONTEXT.md` (L1, state machine)
3. `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/<stage_atual>/CONTEXT.md` (L2, stage instructions)
4. `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/<stage_atual>/_kickoff.md` (L4-kickoff, handoff from previous session — conditional, may not exist in legacy workspaces or first session of a stage)
5. Paths declared in the L2 `Inputs` table (L3 + specific L4)

Layer Loading Protocol literal: the L2 `Inputs` table is the canonical source of what to read. The `Read Order` is a practical sequencing guide — items may be grouped or reordered for efficiency, but every Read Order item must map to an Inputs item. Refuse to read any path not listed in Inputs.

## Session header

Every session prints in its first message (R4.4):

```
Workspace {{WORKSPACE}} | Stage <NN> | Status <YY> | Profile {{PROFILE}}/{{TIER}} | Next: <next_action>
```
