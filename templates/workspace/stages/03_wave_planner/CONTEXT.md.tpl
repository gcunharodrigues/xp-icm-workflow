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

Roda o wave-planner determinístico em cima do `plan.md` da fase 02 design. Constrói DAG por dependências explícitas e file footprint, particiona tasks em waves topológicas respeitando o cap de subagentes por tier (2/3/5/5), e escreve `wave-plan.md` com lista de branches a criar para a fase 04. Estágio é determinístico: ciclos no plano viram `BLOCKED_ERROR`, não stop point.

## Inputs (lê SOMENTE estes, na ordem)

| # | Path | Layer | Obrigatório? |
|---|------|-------|--------------|
| 1 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/CLAUDE.md | L0 | sim |
| 2 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/CONTEXT.md | L1 | sim |
| 3 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/03_wave_planner/CONTEXT.md | L2 | sim |
| 4 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/02_design/output/plan.md | L4 | sim |
| 5 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_config/profile-effective.yaml | L3 | sim |
| 6 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/superpowers-summary/dispatching-parallel-agents-200tok.md | L3 | sim |
| 7 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/03_wave_planner/_kickoff.md | L4-kickoff | condicional: gerado pela sessão anterior. Ausente em workspaces beta1/beta2 (4B legacy) ou se for primeira sessão de stage. |
| 8 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/runtime/session-handoff-protocol.md | L3 | condicional: necessário no handoff final do estágio |
| 9 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/runtime/stop-points-canonical.md | L3 | condicional: catálogo canônico de IDs, complementar ao _config/stop-points.md de thresholds |

## Não Lê (negative constraint)

- {{PROJECT_ROOT}}/.icm-main/src/, {{PROJECT_ROOT}}/.icm-main/tests/
- {{PROJECT_ROOT}}/.icm-main/docs/decisions/ (ADRs já lidos pela fase 02; wave-planner só lê metadados em plan.md)
- Outputs de outros estágios além de `02_design/output/plan.md`
- {{PROJECT_ROOT}}/.icm-main/docs/lessons.md (lições serão injetadas pelo lead na fase 04)

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
6. Rodar LLM review (`python {{SKILL_DIR}}/scripts/wave-planner-llm-review.py`). CLI canônica:
   ```
   python {{SKILL_DIR}}/scripts/wave-planner-llm-review.py \
     --wave-plan {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/03_wave_planner/output/wave-plan.md \
     --plan {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/02_design/output/plan.md \
     --ambiguities {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/03_wave_planner/output/ambiguities-resolved.md \
     --output {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/03_wave_planner/output/llm-review-verdict.json \
     --update-wave-plan {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/03_wave_planner/output/wave-plan.md \
     --workspace-context {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/CONTEXT.md
   ```
   Se skip threshold bater (≤2 tasks ou ≤1 wave) → sai com `SKIPPED` no frontmatter. Se `--llm-response` fornecido → valida e aplica. Se nenhum response fornecido → script imprime prompt formatado (exit 2); humano/algoritmo externo roda LLM e repassa JSON via `--llm-response`. `--update-wave-plan` atualiza frontmatter do `wave-plan.md` com `llm_review: APPROVE|PROPOSE_CHANGES|SKIPPED` e incrementa `llm_review_iterations`.
7. **Handoff de fim de stage:** seguir protocolo gate-inline na seção `## End of stage handoff` deste L2 (Fase 1 WORK_DONE → gate humano → Fase 2 GATE_APPROVED).

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

## End of stage handoff (gate inline + 1-stage-1-sessão)

Handoff é split em DUAS fases dentro da MESMA sessão. Gate humano fica entre elas — `_kickoff.md` só é renderizado APÓS aprovação. Bug v3.4.2 corrigido: render+exit prematuros antes da aprovação criavam loop "kickoff → user aprova em sessão nova → kickoff de novo". Doc canônico: `<skill_root>/references/session-handoff-protocol.md`.

### Fase 1: WORK_DONE (após outputs prontos)

1. **Atualizar L1** (`<workspace>/CONTEXT.md`):
   - `sub_stage = 03_completed`
   - `status = COMPLETED_AWAITING_HUMAN`
   - `last_transition.from = 03_in_progress`
   - `last_transition.to = 03_completed`
   - `last_transition.at = <ISO 8601 UTC now>`
   - `history` append: `{at, event: "stage_transition", from: "03_in_progress", to: "03_completed", commit_sha, note: "work done, awaiting gate"}`

2. **Commit atômico 1/2** (outputs + L1; pre-commit hook valida atomicidade):
   ```
   workspace <NNN>: stage 03 work done, awaiting gate
   ```
   Files: outputs do stage atual + L1. **NÃO** inclui `_kickoff.md` (não renderizado ainda).

3. **Imprimir prompt de gate** pro humano. NÃO sair da sessão. NÃO renderizar `_kickoff.md`:

   ```
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   ✅ Stage 03 (wave_planner) trabalho COMPLETO — workspace <NNN-slug>

   Outputs prontos pra revisão:
     - <lista de paths>

   L1: sub_stage=03_completed, status=COMPLETED_AWAITING_HUMAN
   Commit 1/2: <sha>

   🛑 Gate humano: revise wave-plan.md (cap aplicado, ambiguidades resolvidas).
   Responda no chat:
     - "aprovado" / "ok prosseguir 04" → renderizo kickoff e saio
     - "ajustar X" → volto ao trabalho com seu pedido (status=IN_PROGRESS)
     - "abort" → marco workspace BLOCKED_ERROR
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   ```

4. **AGUARDAR resposta humana** na MESMA sessão.

### Fase 2: GATE_APPROVED (após humano responder "aprovado")

5. **Atualizar L1** (segunda transição — entrada em fase 04 começa pela wave 1):
   - `stage_atual = 04`
   - `sub_stage = 04_wave_1_in_progress`
   - `status = IN_PROGRESS`
   - `last_transition.from = 03_completed`
   - `last_transition.to = 04_wave_1_in_progress`
   - `last_transition.at = <ISO 8601 UTC now>`
   - `history` append: `{at, event: "stage_transition", from: "03_completed", to: "04_wave_1_in_progress", commit_sha, note: "gate approved by human"}`

6. **Renderizar `_kickoff.md`** no stage seguinte:
   - Path: `<workspace>/stages/04_implementation_waves/_kickoff.md`
   - Use `python {{SKILL_DIR}}/scripts/handoff.py render` ou função `render_kickoff` do `{{SKILL_DIR}}/scripts/handoff.py`
   - Frontmatter YAML L4-kickoff conforme schema em `references/session-handoff-protocol.md`
   - Corpo: prev_outputs + prev_decisions + pending pra próximo stage (incluindo wave 1 a executar)

7. **Commit atômico 2/2** (kickoff + L1):
   ```
   workspace <NNN>: gate aprovado, kickoff stage 04
   ```
   Files: `_kickoff.md` do próximo + L1 atualizado.

8. **Imprimir KICKOFF block verbal** pro user (copy-paste pra próxima sessão):

   ```
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   ✅ Stage 03 (wave_planner) GATE APROVADO — workspace <NNN-slug>

   Workspace atualizado em commit <sha>:
     - L1: stage_atual=04, sub_stage=04_wave_1_in_progress, status=IN_PROGRESS
     - Kickoff: stages/04_implementation_waves/_kickoff.md gerado

   🔄 KICKOFF próxima sessão — copy/paste:
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Continuar workspace <NNN-slug> no estágio 04 (implementation_waves) — wave 1.

   Read order:
     workspaces/<NNN-slug>/CLAUDE.md
     workspaces/<NNN-slug>/CONTEXT.md
     workspaces/<NNN-slug>/stages/04_implementation_waves/CONTEXT.md
     workspaces/<NNN-slug>/stages/04_implementation_waves/_kickoff.md
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

   Encerre esta sessão (Ctrl+D ou /exit) e abra nova sessão Claude
   no project_root, depois cole o prompt acima.
   ```

9. **SAIR** da sessão. NÃO continuar pro próximo stage na mesma sessão.

### Resposta "ajustar X" (gate rejeitado)

Se humano responder texto livre pedindo ajuste:
- Atualizar L1: `status = IN_PROGRESS`, append history `{event: "gate_rejected", note: "humano pediu ajuste: X"}`. Sub_stage permanece `03_completed` (volta a `03_in_progress` se mudança não-trivial).
- Voltar ao trabalho conforme pedido.
- Quando refizer outputs, voltar à Fase 1 (novo commit 1/2 + novo gate prompt).

### Resposta "abort"

Se humano responder "abort":
- Atualizar L1: `status = BLOCKED_ERROR`, append history `{event: "blocked_error", error_type: "human_abort", note: "humano abortou em gate"}`.
- Commit + sair. Workspace fica em BLOCKED_ERROR aguardando intervenção manual.

---

## v3.3.0 references aplicáveis a este stage

- **HITL/AFK respect (`_references/runtime/task-types-hitl-afk.md`):**
  wave-planner respeita campo `Type` por task. Tasks `HITL` ficam em
  **wave isolada com cap=1** (sub_stage `wave-N_hitl_pending`). Tasks
  `AFK` agrupadas normalmente respeitando cap por tier.
- **Output `wave-plan.md`:** adicionar coluna `Type` na tabela por sub-wave.
