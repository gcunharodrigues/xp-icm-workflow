---
layer: L4-kickoff
stage_target: "{{STAGE_TARGET}}"
stage_target_name: "{{STAGE_TARGET_NAME}}"
generated_by: "session ending stage {{PREV_STAGE}}"
generated_at: "{{GENERATED_AT}}"
generator_commit_sha: "{{GENERATOR_COMMIT_SHA}}"
prev_stage: "{{PREV_STAGE}}"
prev_outputs: {{PREV_OUTPUTS_YAML}}
prev_decisions_summary: |
  {{PREV_DECISIONS_SUMMARY_INDENTED}}
pending_for_this_stage: {{PENDING_YAML}}
---

# Kickoff — Stage {{STAGE_TARGET}} {{STAGE_TARGET_NAME}} (workspace {{WORKSPACE}})

## State delivered by previous session

{{PREV_STATE_PROSE}}

## What this session must do

{{NEXT_TASKS_PROSE}}

## KICKOFF block (verbal — copy-paste pro user)

```
Continuar workspace {{WORKSPACE}} no estágio {{STAGE_TARGET}} ({{STAGE_TARGET_NAME}}).

Read order:
  workspaces/{{WORKSPACE}}/CLAUDE.md
  workspaces/{{WORKSPACE}}/CONTEXT.md
  workspaces/{{WORKSPACE}}/stages/{{STAGE_TARGET_DIR}}/CONTEXT.md
  workspaces/{{WORKSPACE}}/stages/{{STAGE_TARGET_DIR}}/_kickoff.md
```
