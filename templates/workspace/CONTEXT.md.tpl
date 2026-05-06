---
layer: L1
workspace: "{{WORKSPACE}}"
profile_base: "{{PROFILE}}"
profile_effective_hash: "{{PROFILE_EFFECTIVE_HASH}}"
tier: "{{TIER}}"
project_root: "{{PROJECT_ROOT}}"
base_branch: "{{BASE_BRANCH}}"
workspace_branch: "workspace/{{WORKSPACE}}"
stage_atual: "00"
sub_stage: "00_in_progress"
status: "IN_PROGRESS"
block_reason: null
iteration: 0
stages_skipped: {{STAGES_SKIPPED}}
logs_root: {{LOGS_ROOT}}
llm_review_skipped_count: 0
last_action: "workspace bootstrapped"
last_action_at: "{{CREATED_AT}}"
next_action: "run reconnaissance stage 00"
prev_outputs: []
pending: []
last_transition:
  from: "bootstrap"
  to: "00_in_progress"
  at: "{{CREATED_AT}}"
  commit_sha: "{{BOOTSTRAP_COMMIT_SHA}}"
history:
  - at: "{{CREATED_AT}}"
    event: "workspace_bootstrapped"
    note: "skill v{{SKILL_VERSION}} bootstrap, profile={{PROFILE}} tier={{TIER}}"
    commit_sha: "{{BOOTSTRAP_COMMIT_SHA}}"
---

# Workspace {{WORKSPACE}} — L1 (state machine)

## Current state

| Field | Value |
|---|---|
| Stage | `00` (Reconnaissance) |
| Sub-stage | `00_in_progress` |
| Status | `IN_PROGRESS` |
| Iteration | `0` |
| Stages skipped | `{{STAGES_SKIPPED}}` |
| Last action | workspace bootstrapped at {{CREATED_AT}} |
| Next action | run reconnaissance |

## How this state machine works

Every session:

1. Reads this file + L0 + L2 of `stage_atual`.
2. Reads `prev_outputs` and `pending` from L1 frontmatter (v4.0 handoff). Also reads `stages/<stage_atual>/_kickoff.md` if it exists (v3 legacy fallback — absent in v4 workspaces).
3. Works as L2 instructs.
4. On transition (sub-stage or stage): updates frontmatter + appends to `history` + atomic commit.
5. Pre-commit hook validates atomicity outputs ↔ frontmatter.

## Canonical statuses (v4.0)

- `IN_PROGRESS` — active session.
- `BLOCKED` — any blocking condition. `block_reason` field in frontmatter distinguishes: `human_gate`, `stop_point`, `error`, `hitl`, or `lead_resolution`.
- `COMPLETED` — workspace closed.

Details in `references/state-machine-schema.md` of the skill.

## History

History is append-only. Sessions NEVER edit existing items. Recovery Wizard may prepend a `recovery_applied` event documenting reconstruction.
