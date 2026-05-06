# Feedback Intake — Stage 08

> **Version:** v4.0.0 · Three exits: A close, B restart stage X, C spawn new workspace.
> **Canonical source:** `templates/workspace/stages/08_feedback_intake/CONTEXT.md.tpl` — the L2 template is authoritative. This reference doc provides additional context.

---

## Purpose

Stage 08 is the **universal iteration gate** of the ICM cycle. Human triggers after real use of the workspace output (weeks/months after stage 04 last wave). Three exits: close workspace + record lessons, restart a stage with iteration++, or spawn a new workspace.

---

## When to run stage 08

- **Always optional, never automatic.** Human triggers after real use — weeks, months after stage 04 last wave approved.
- **Universal.** Any tier (`experimental` → `production`).
- **Trigger:** human opens new Claude Code session at project_root. L1 `stage_atual: "08"`, `sub_stage: 08_in_progress`.

### Stages skipped by profile

The `profile-matrix.md` declares `stages_skipped` per profile. v4.0: `experiment` lists `["02", "04", "08"]` (03/05/06/07 removed as stages).

---

## Pre-condition (v4.0)

Workspace must have `stage_atual: "08"`, `sub_stage: 08_in_progress`, `status: IN_PROGRESS`. Transition from stage 04 last wave via `BLOCKED` + `block_reason: human_gate` → human approval → `IN_PROGRESS`.

If `status: BLOCKED` with `block_reason: human_gate` → human already approved → set `status: IN_PROGRESS`, proceed.

If status undefined or inconsistent → stop point `workspace_corrupt` → Recovery Wizard.

---

## Mandatory runtime cleanup pre-exit (v3.7+)

BEFORE any Process action (pre-flight, collection, inference), session MUST run the Runtime Cleanup Checklist via `scripts/runtime-status.py`. Strict universal — all tiers go through the checklist without opt-out.

**9 explicit steps:**

1. Session reads L0 + L1 of the workspace (normal read order).
2. Session runs:
   ```
   python {SKILL_DIR}/scripts/runtime-status.py \
       --workspace-root <ws> --project-root <pr> --format text --exit-code
   ```
3. 6 categories verified: dev_servers, background_tasks, docker, wave_branches, working_tree, untracked.
4. For each non-clean category, session prints details (PIDs, branches, paths) + human menu `[y/n/edit]`.
5. Human resolves item (kill process, delete branch, commit dirt) and replies `[y]` to resume.
6. Session re-runs full checklist (idempotent).
7. Loop until **all categories clean** OR human cancels with `[n]` on any category.
8. Success → proceed to Process step 1 (pre-flight L1 validation).
9. Failure (human `[n]` or command errored after retry) → stop point #13 `runtime_cleanup_failed`. Status `BLOCKED (stop_point)`. Session pauses, writes specific A/B/C menu (resolved / skip / cancel).

**Output reported in `intake-report.md`:** section §"Runtime cleanup pre-exit" with final snapshot + confirmed categories + warnings (if any cleanup was skipped via stop point #13 menu B).

**Failure → BLOCKED_ERROR not used.** v3.7.0 introduced official stop point (#13). `BLOCKED_ERROR` is reserved for workspace-corrupt + hard IO failures.

Canonical doc: `references/runtime-cleanup-protocol.md`.

---

## What the stage 08 session does

### Pre-flight

Reads:

- L0 (`<workspace>/CLAUDE.md`) — absolute paths, profile, tier, `logs_root`.
- L1 (`<workspace>/CONTEXT.md`) — confirms `status: IN_PROGRESS` (v4.0), reads `iteration`, `history`, `prev_outputs`, `pending`.
- L2 (`<workspace>/stages/08_feedback_intake/CONTEXT.md`) — stage-specific instructions.
- Prior outputs: `stages/04_implementation_waves/output/*` — existence sample-check (audit).

Automatic validations:

1. `status == "IN_PROGRESS"` (v4.0 pre-condition).
2. Outputs from stages 01, 02, 04 exist (sample-check of at least 1 file per stage that ran — respecting `stages_skipped`).
3. Current `sub_stage` ∈ {`08_in_progress`, `08_decided_A`, `08_decided_B`, `08_decided_C`} or absent (first trigger).

Failure in any validation → abort with specific message + proposed action.

### Input collection

**1. System logs** (if `logs_root` declared in L0 and different from `null`)

Sample from last 30 days of `<logs_root>`. If `logs_root: null` (greenfield/text/skill), skip this step. If path does not exist or is empty, notes "logs empty/inaccessible" in the report and continues.

**2. Structured human feedback**

Session asks human in 4-block format:

```
## WHAT WORKED

(what actually delivered value)

## WHAT DIDN'T WORK

(what failed, caused friction, wasted time)

## WHAT PAIN PERSISTS

(what still hurts after this workspace)

## WHAT LESSON TO TAKE

(insight to capture in docs/lessons.md)
```

Human replies inline in the session. Session validates that each block has at least 1 substantive sentence (not empty or placeholder).

**3. Top-N error pattern analysis**

Groups logs + feedback into **≤5 patterns** with `frequency` (count or estimate) + `impact` (low/medium/high/critical) + `evidence` (log lines or feedback excerpt). If logs are empty and feedback is brief, there may be 0-2 patterns; that is acceptable.

### Output

Session writes `<workspace>/stages/08_feedback_intake/output/intake-report.md`:

```markdown
# Intake Report — Workspace NNN, iteration M

## Logs sample
(last 30 days from <logs_root>, or "n/a" if null)

## Human feedback
### WHAT WORKED
...
### WHAT DIDN'T WORK
...
### WHAT PAIN PERSISTS
...
### WHAT LESSON TO TAKE
...

## Top-N patterns
| # | Pattern | Frequency | Impact | Evidence |
|---|---|---|---|---|
| 1 | ... | ... | ... | ... |

## Recommendation
Suggested exit: A | B (stage X) | C
Rationale: ...
```

Pre-commit hook validates commit prefix `intake:` or `feedback:`.

---

## The 3 exits A/B/C

After `intake-report.md` is written, session triggers the A/B/C menu with the recommendation highlighted. Human chooses (may disagree with the recommendation). Session executes the corresponding transition.

### Exit A — Close workspace

**When:** tool works, lessons already captured, no additional action needed.

**Session executes:**

1. Append to `history`: `event: stage_transition`, `from: 08_in_progress`, `to: 08_decided_A`, `note: "<short reason>"`, `at: <ISO>`, `commit_sha: <to be filled post-commit>`.
2. Set `sub_stage: 08_decided_A`.
3. Set `status: COMPLETED`.
4. Append new lessons (extracted from the "WHAT LESSON TO TAKE" block of intake-report) to `{{PROJECT_ROOT}}/.icm-main/docs/lessons.md` via base-branch worktree, respecting strict frontmatter (id, date, tags, severity).
5. Atomic commit (pre-commit hook validates atomicity L1↔outputs↔lessons).
6. Human message: "Workspace NNN closed. M lessons added to .icm-main/docs/lessons.md."

**Concrete example — exit A:**

Message to human:
```
Workspace 042 closed with decision A (close).

3 lessons added to .icm-main/docs/lessons.md:
  #017 critical — race in large wave rebase
  #018 medium — on-demand peer review caught bug in critical path
  #019 low — wave-reviewer with 1 task adds noise (skip in future)

Final sub_stage: 08_decided_A. Status: COMPLETED.
```

YAML diff in L1:
```yaml
# before
sub_stage: "08_in_progress"
status: "IN_PROGRESS"
last_action: "stage 04 last wave merged, approved for feedback"

# after
sub_stage: "08_decided_A"
status: "COMPLETED"
last_action: "stage 08 exit A — close workspace"
last_action_at: "2026-04-25T16:00:00Z"
next_action: "n/a — workspace archived"
last_transition:
  from: "08_in_progress"
  to: "08_decided_A"
  at: "2026-04-25T16:00:00Z"
  commit_sha: "f1e2d3c4b5a6"
history:
  # ... prior entries preserved
  - at: "2026-04-25T15:30:00Z"
    event: "stage_transition"
    from: "04_wave_N_completed"
    to: "08_in_progress"
    commit_sha: "a1b2c3d4"
  - at: "2026-04-25T16:00:00Z"
    event: "stage_transition"
    from: "08_in_progress"
    to: "08_decided_A"
    commit_sha: "f1e2d3c4b5a6"
    note: "tool works, 3 lessons captured"
```

---

### Exit B — Restart stage X (iteration++)

**When:** new discovery requires partial redesign. Workspace returns to stage X with lessons from the intake applied.

**Constraint H1 (v4.0):** X ∈ {`01`, `02`, `04`}. Restart NOT permitted for:

- `00` (recon — to change `project_root` or project type, use exit C).
- `08` (current — restarting the gate itself makes no sense).

Validation in L2 of stage 08: human choosing B must declare valid X; session refuses X ∉ {01, 02, 04}.

**Session executes:**

1. Append to `history`: `event: iteration_increment`, `from: 08_in_progress`, `to: <XX>_in_progress`, `iteration_new: <N+1>`, `note: "restart stage X — <reason>"`, `at: <ISO>`.
2. Move old outputs: `stages/<XX>/output/` → `stages/<XX>/output-iteration-<N>/` (N = iteration BEFORE increment). Outputs preserved for audit. Internal schema identical to `output/`.
3. Set `iteration: N+1`.
4. Set `stage_atual: <XX>`.
5. Set `sub_stage: <XX>_in_progress`.
6. Set `status: IN_PROGRESS` (exits `COMPLETED`).
7. Set `last_action: "restart stage <XX> iteration N+1"`.
8. Set `next_action: "run stage <XX> with lessons from intake-report"`.
9. Atomic commit.
10. Human message: instruction to open new session.
11. Session exits. Next session reads L1 and naturally resumes stage XX.

**Concrete example — exit B (restart stage 02):**

Message to human:
```
Workspace 042 returned to stage 02 (design+plan), iteration 2.

Old outputs preserved in:
  stages/02_design/output-iteration-1/
  (plan.md, wave-plan.md, ambiguities-resolved.md)

New iteration 2 outputs go in stages/02_design/output/ (clean).

Open a new session at project_root to resume.
The session will read L1, see stage_atual=02 + iteration=2,
and pick up the lessons from intake-report when building the new plan.
```

YAML diff in L1:
```yaml
# before
stage_atual: "08"
sub_stage: "08_in_progress"
status: "IN_PROGRESS"
iteration: 1

# after
stage_atual: "02"
sub_stage: "02_in_progress"
status: "IN_PROGRESS"
iteration: 2
last_action: "restart stage 02 iteration 2"
last_action_at: "2026-04-25T16:00:00Z"
next_action: "run stage 02 with lessons from intake-report (DAG from wave 1 caused race in rebase, redesign)"
last_transition:
  from: "08_in_progress"
  to: "02_in_progress"
  at: "2026-04-25T16:00:00Z"
  commit_sha: "9a8b7c6d5e4f"
history:
  - at: "2026-04-25T16:00:00Z"
    event: "iteration_increment"
    from: "08_in_progress"
    to: "02_in_progress"
    iteration_new: 2
    note: "restart stage 02 — DAG from wave 1 caused race in rebase, redesign"
    commit_sha: "9a8b7c6d5e4f"
```

Filesystem move:
```
stages/02_design/output/plan.md               → stages/02_design/output-iteration-1/plan.md
stages/02_design/output/wave-plan.md           → stages/02_design/output-iteration-1/wave-plan.md
stages/02_design/output/ambiguities-resolved.md → stages/02_design/output-iteration-1/ambiguities-resolved.md
stages/02_design/output/                       → (empty, ready for iteration 2)
```

---

### Exit C — Spawn new workspace (inherits lessons + ADRs)

**When:** feedback indicates needing a new scope (major rewrite, evolution with distinct scope, or change of `project_root`). Workspace 042 stays closed; creates 043 inheriting context.

**UX H2:** stage 08 session does NOT bootstrap 043 automatically. Human opens a new session and pastes the explicit command. This preserves the separation "skill is a one-shot midwife, exits".

**Session executes:**

1. Append to `history`: `event: stage_transition`, `from: 08_in_progress`, `to: 08_decided_C`, `spawn_to: <new-slug>`, `note: "spawn new workspace — <reason>"`, `at: <ISO>`.
2. Set `sub_stage: 08_decided_C`.
3. Set `status: COMPLETED`.
4. Set `spawn_to: <new-workspace-slug>` (human suggests during session; default `043-<slug>` based on feedback scope).
5. Atomic commit.
6. Explicit human message with command to paste in new session.

**Bootstrap of 043 (happens in a SEPARATE session, not this one):**

- Reads `<project_root>/workspaces/042/CONTEXT.md` via `spawn_from=042` arg.
- Inherits `profile_base`, `tier`, `project_root` (human confirms each — may change).
- L1 of 043 receives `spawn_from: 042`.
- Initial recon-report of 043 includes section "Inherited from 042: applicable ADRs, critical lessons, motivating scope of spawn".
- L1 of 042 already had `spawn_to: 043` set; now it is a confirmed cross-reference.

**Concrete example — exit C:**

Message to human:
```
Workspace 042 closed with decision SPAWN.

042 L1 updated: spawn_to=043-feat-auth-v2, status=COMPLETED.

To create 043 inheriting context:

  1. Open new Claude Code session at the same project_root:
     C:/Users/guicr/projects/aura-luz-api

  2. Paste the command:
     /xp-icm-workflow project-root=C:/Users/guicr/projects/aura-luz-api spawn_from=042

  3. Bootstrap will:
     - Read CONTEXT.md of 042
     - Propose profile=app_web_backend and tier=development (from 042); you confirm
     - Create 043 with spawn_from=042 in recon-report
     - List inherited ADRs (0001-stack, 0003-auth-strategy) for you to confirm which apply
     - List critical lessons from 042 for initial context

This session ends here.
```

YAML diff in L1:
```yaml
# before
sub_stage: "08_in_progress"
status: "COMPLETED"
last_action: "stage 08 collected feedback + intake-report written"

# after
sub_stage: "08_decided_C"
status: "COMPLETED"
spawn_to: "043-feat-auth-v2"
last_action: "stage 08 exit C — spawn new workspace 043"
last_action_at: "2026-04-25T16:00:00Z"
next_action: "human opens new session + /xp-icm-workflow spawn_from=042"
last_transition:
  from: "08_in_progress"
  to: "08_decided_C"
  at: "2026-04-25T16:00:00Z"
  commit_sha: "5e4d3c2b1a09"
history:
  # ... prior entries preserved
  - at: "2026-04-25T16:00:00Z"
    event: "stage_transition"
    from: "08_in_progress"
    to: "08_decided_C"
    commit_sha: "5e4d3c2b1a09"
    spawn_to: "043-feat-auth-v2"
    note: "spawn new workspace — auth needs OAuth2 PKCE, scope does not fit in restart"
```

---

## Sub_stage enum stage 08 (recap state-machine-schema.md)

| Sub_stage | Meaning | Corresponding status |
|---|---|---|
| `08_in_progress` | session collecting logs + feedback + writing intake-report | `IN_PROGRESS` |
| `08_decided_A` | human chose A (close) | `COMPLETED` |
| `08_decided_B` | human chose B (restart stage X) | back to `IN_PROGRESS` in stage X |
| `08_decided_C` | human chose C (spawn) | `COMPLETED` + `spawn_to` set |

---

## Preserved iteration outputs (exit B)

In exit B, old outputs go to `stages/<XX>/output-iteration-<N>/` — **not deleted**. Full audit trail of the workspace evolution.

Schema:
- `output-iteration-<N>/` is a directory.
- Internal structure identical to `output/` (same filenames).
- New iteration writes to clean `stages/<XX>/output/`.
- Prior iterations (`output-iteration-1/`, `output-iteration-2/`, ...) coexist.

Pre-commit hook validates that `output-iteration-<N>/` is only created in commits with prefix `intake:` or `feedback:`.

---

## Constraints

- **Stage 08 does NOT write new code.** Only analyzes + decides + transitions state. Any new code is the responsibility of a new iteration (exit B) or new workspace (exit C).
- **Pre-commit hook validates transition** like any other (atomicity L1 ↔ outputs/lessons, prefix `feedback:` or `intake:`).
- **Stop points rare but possible:** item 11 `workspace_corrupt` if `intake-report.md` cannot be written (disk full, permission), or if human interrupts the session before deciding A/B/C (status stays `IN_PROGRESS` in `08_in_progress`; next session resumes).
- **New lessons only in exit A.** Exits B and C naturally reuse lessons (B via intake-report of iteration N+1; C via inheritance in recon-report of 043). Exit A is the only path for explicit append to `.icm-main/docs/lessons.md`.

---

## v3.3.0 — Triage classification (precedes A/B/C)

BEFORE A/B/C inference, classify feedback in **(category, state)**:

| Category | State | Exit |
|---|---|---|
| bug | ready-for-action | **B** restart stage X |
| enhancement | ready-for-action | **C** spawn new workspace |
| enhancement | wontfix | **A** close + append `_out-of-scope/` |
| any | needs-info | pause (status=BLOCKED (human_gate)) |
| none | all OK | **A** close |

Each item classified as B or C **generates an AGENT-BRIEF** (format:
`agent-brief-template.md`) which becomes input for the next session / spawn.

Enhancement rejected (wontfix) records in
`<workspace>/_out-of-scope/<concept>.md` (format: `out-of-scope-kb.md`).

CLAUDE.md root updated by handoff.py in all 3 exits (see
`session-handoff-protocol.md` §"Stage 08 exits A/B/C and CLAUDE.md root").

Canonical doc: `references/triage-state-machine.md`.
