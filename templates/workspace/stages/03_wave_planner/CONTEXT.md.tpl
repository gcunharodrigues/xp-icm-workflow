---
layer: L2
stage: "03"
stage_name: "wave_planner"
sub_stage_enum:
  - "03_in_progress"
  - "03_completed"
applicable_stop_points: []
output_files:
  - "output/wave-plan.md"
next_stage: "04"
---

# Estágio 03 — wave_planner (L2)

Roda o wave-planner determinístico em cima do `plan.md` da fase 02 design. Constrói DAG por dependências explícitas e file footprint, particiona tasks em waves topológicas respeitando o cap de teammates por tier (2/3/5/5), e escreve `wave-plan.md` com lista de branches a criar para a fase 04. Estágio é determinístico: ciclos no plano viram `BLOCKED_ERROR`, não stop point.

## Inputs (lê SOMENTE estes, na ordem)

| # | Path | Layer | Obrigatório? |
|---|------|-------|--------------|
| 1 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/CLAUDE.md | L0 | sim |
| 2 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/CONTEXT.md | L1 | sim |
| 3 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/03_wave_planner/CONTEXT.md | L2 | sim |
| 4 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/02_design/output/plan.md | L4 | sim |
| 5 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_config/profile-effective.yaml | L3 | sim |
| 6 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/superpowers-summary/dispatching-parallel-agents-200tok.md | L3 | sim |

## Não Lê (negative constraint)

- {{PROJECT_ROOT}}/src/, {{PROJECT_ROOT}}/tests/
- {{PROJECT_ROOT}}/docs/decisions/ (ADRs já lidos pela fase 02; wave-planner só lê metadados em plan.md)
- Outputs de outros estágios além de `02_design/output/plan.md`
- {{PROJECT_ROOT}}/docs/lessons.md (lições serão injetadas pelo lead na fase 04)

## Read order

1. L0 — {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/CLAUDE.md
2. L1 — {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/CONTEXT.md
3. L2 — este arquivo
4. plan.md (entrada principal — schema 4-block + Files touched + Depends on)
5. profile-effective.yaml (cap por tier/profile)
6. dispatching-parallel-agents-200tok.md (sumário superpowers)

## Process

1. Pre-flight: validar paths Inputs existem; sub_stage `03_in_progress`.
2. Ler `profile-effective.yaml` para extrair `tier` e `profile` efetivos (cap = `min(tier_cap, profile_override)`).
3. Rodar wave-planner determinístico (CLI canônica, paths absolutos resolvidos):
   ```
   python {{SKILL_DIR}}/scripts/wave-planner-script.py \
     --plan {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/02_design/output/plan.md \
     --tier <tier> \
     --profile <profile> \
     --workspace {{WORKSPACE}} \
     --output {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/03_wave_planner/output/wave-plan.md
   ```
4. Se script saiu com exit ≠ 0 (ciclo, slug duplicado, dep desconhecida, schema inválido) → setar `status: BLOCKED_ERROR`, registrar erro em `history` e parar. NÃO disparar stop point — `applicable_stop_points: []`.
5. Stdout do script reporta `total_tasks`, `total_waves`, `total_sub_waves`, `ambiguities`. Anexar como nota em `last_action`.
6. (Placeholder) LLM review subagent — Wave 4 da skill instalará. Por enquanto, na v3.0.0-beta1, este passo é no-op: `wave-plan.md` sai com `llm_review: PENDING` no frontmatter; humano revisa manualmente no gate.
7. Atualizar L1: sub_stage `03_completed`, status `COMPLETED_AWAITING_HUMAN`, append `history`. Commit atômico.

## Outputs

- `output/wave-plan.md` — frontmatter (cap, total_tasks, total_waves, llm_review status) + tabela por sub-wave (slug, files touched, depends on, branch a criar) + audit (file conflicts serializados, ambiguidades).

## Sub_stage transitions

Enum válido: `03_in_progress`, `03_completed`.

Transição IN_PROGRESS → COMPLETED dispara quando:
- `output/wave-plan.md` existe.
- Wave-planner saiu com exit 0 (sem ciclo, sem schema inválido).
- Humano aprovou via gate (status `COMPLETED_AWAITING_HUMAN` → humano responde).

## Status canônicos disponíveis neste estágio

- `IN_PROGRESS` — rodando wave-planner.
- `COMPLETED_AWAITING_HUMAN` — `wave-plan.md` pronto, humano revisa cap/ambiguidades.
- `BLOCKED_ERROR` — wave-planner falhou (ciclo, slug duplicado, dep desconhecida, schema inválido em plan.md).

## Stop points aplicáveis

Catálogo canônico em `references/stop-points-canonical.md`. **Nenhum stop point aplicável neste estágio** — wave-planner é determinístico. Falhas (ciclo, ambiguidade não-resolvível) viram `BLOCKED_ERROR`, humano corrige `plan.md` e re-roda.

## Skill superpowers de referência

Sumário 200tok: `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/superpowers-summary/dispatching-parallel-agents-200tok.md`

Skill formal: `superpowers:dispatching-parallel-agents` (escape hatch — só se humano pedir explicação detalhada de paralelismo).

## Gates

- **Humano:** revisa `output/wave-plan.md`, valida cap aplicado, examina ambiguidades, aprova ou pede ajuste em `plan.md` (volta à fase 02).
- **Automático (CI):** pre-commit hook valida atomicidade L1↔outputs e prefixo de commit `workspace/{{WORKSPACE}}`.
- **Aprovação para transitar:** humano aprova explicitamente; sub_stage vira `03_completed` no próximo commit.
