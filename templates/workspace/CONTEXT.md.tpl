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
iteration: 0
stages_skipped: {{STAGES_SKIPPED}}
logs_root: {{LOGS_ROOT}}
llm_review_skipped_count: 0
last_action: "workspace bootstrapped"
last_action_at: "{{CREATED_AT}}"
next_action: "rodar reconnaissance estágio 00"
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

## Estado atual

| Campo | Valor |
|---|---|
| Estágio | `00` (Reconnaissance) |
| Sub-stage | `00_in_progress` |
| Status | `IN_PROGRESS` |
| Iteration | `0` |
| Stages skipped | `{{STAGES_SKIPPED}}` |
| Última ação | workspace bootstrapped em {{CREATED_AT}} |
| Próxima ação | rodar reconnaissance |

## Como esta máquina funciona

Toda sessão:

1. Lê este arquivo + L0 + L2 do `stage_atual`.
2. Lê `stages/<stage_atual>/_kickoff.md` (se existir — handoff da sessão anterior).
3. Trabalha conforme L2 instrui.
4. Ao transicionar (sub-stage ou stage): atualiza frontmatter + append em `history` + commit atômico.
5. Pre-commit hook valida atomicidade outputs ↔ frontmatter.

## Status canônicos

- `IN_PROGRESS` — sessão ativa.
- `COMPLETED_AWAITING_HUMAN` — aguarda gate humano.
- `BLOCKED_STOP_POINT` — menu A/B/C aguardando resposta.
- `BLOCKED_ERROR` — erro runtime; humano resolve.
- `COMPLETED` — workspace fechado.

Detalhes em `references/state-machine-schema.md` da skill.

## History

History é append-only. Sessões NUNCA editam itens existentes. Recovery Wizard pode prepend evento `recovery_applied` documentando reconstrução.
