---
layer: L4-kickoff
stage_target: "03"
stage_target_name: "wave_planner"
generated_by: "session ending stage 02"
generated_at: "2026-04-26T14:30:00Z"
generator_commit_sha: "abc123def"
prev_stage: "02"
prev_outputs: 
  - path: "stages/02_design/output/plan.md"
    summary: "Plano com 8 tasks, 2 ADRs criados (0001 stack + 0004 auth)"
  - path: "stages/02_design/output/decisions.md"
    summary: "Index L4 dos ADRs"
prev_decisions_summary: |
  - Stack: Python 3.13 + FastAPI + Postgres
  - Auth: JWT com refresh tokens (ADR 0004)
pending_for_this_stage: ["Resolver ambiguidade: tasks user-model e user-routes tocam src/users/"]
---

# Kickoff — Stage 03 wave_planner (workspace 042-feat-auth)

## State delivered by previous session

Sessao anterior fechou design com 8 tasks plan + 2 ADRs.
Outputs em stages/02_design/output/.

## What this session must do

Particionar 8 tasks em waves respeitando DAG.
Resolver ambiguidades pendentes antes de freezar plan.

## KICKOFF block (verbal — copy-paste pro user)

```
Continuar workspace 042-feat-auth no estágio 03 (wave_planner).

Read order:
  workspaces/042-feat-auth/CLAUDE.md
  workspaces/042-feat-auth/CONTEXT.md
  workspaces/042-feat-auth/stages/03_wave_planner/CONTEXT.md
  workspaces/042-feat-auth/stages/03_wave_planner/_kickoff.md
```
