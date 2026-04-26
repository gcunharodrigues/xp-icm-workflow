---
layer: L2
stage: "02"
stage_name: "design"
sub_stage_enum:
  - "02_in_progress"
  - "02_completed"
applicable_stop_points:
  - "stack"
  - "db"
  - "new_dep"
  - "paid_service"
  - "irreversible"
  - "over_eng"
  - "pii"
  - "adr_drift"
output_files:
  - "output/plan.md"
next_stage: "03"
---

# Estágio 02 — design (L2)

Design técnico detalhado a partir do escopo refinado em discovery. Produz `plan.md` no schema 4-block + Files touched + ADRs por task (consumido pelo Wave Planner em 03). Cria ADRs novos em `{{PROJECT_ROOT}}/docs/decisions/` quando decisões arquiteturais surgem (stack, db, dependências, serviços pagos, migrações irreversíveis, etc.). Gate humano antes de transitar para 03.

## Inputs (lê SOMENTE estes, na ordem)

| # | Path | Layer | Obrigatório? |
|---|------|-------|--------------|
| 1 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/CLAUDE.md | L0 | sim |
| 2 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/CONTEXT.md | L1 | sim |
| 3 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/02_design/CONTEXT.md | L2 | sim |
| 4 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/01_discovery/output/discovery.md | L4 | sim |
| 5 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/00_recon/output/recon-report.md | L4 | sim |
| 6 | {{PROJECT_ROOT}}/docs/decisions/ | L3 | condicional: ler conteúdo dos ADRs vigentes listados no recon-report (filenames já indexados em 00) |
| 7 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_config/profile-effective.yaml | L3 | sim |
| 8 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_config/stop-points.md | L3 | sim |
| 9 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/runtime/4-block-contract-template.md | L3 | sim |
| 10 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/superpowers-summary/writing-plans-200tok.md | L3 | sim |
| 11 | {{PROJECT_ROOT}}/docs/lessons.md | L3 | condicional: existe se herdou ou foi acumulada |
| 12 | {{PROJECT_ROOT}}/docs/tech_debt.md | L3 | condicional: existe se há débito declarado em iterações anteriores |
| 13 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/02_design/_kickoff.md | L4-kickoff | condicional: gerado pela sessão anterior. Ausente em workspaces beta1/beta2 (4B legacy) ou se for primeira sessão de stage. |

## Não Lê (negative constraint)

- {{PROJECT_ROOT}}/src/ e {{PROJECT_ROOT}}/tests/ — design é output-driven a partir de discovery + ADRs; não inspeciona código existente. Se contexto de código for crítico, declarar dependência no plan.md (task com ADR de leitura) e revisitar 01.
- ADRs não-listados pelo recon-report — só lê os indexados em 00 ou criados nesta sessão.
- Outputs de estágios 03+ — não existem ainda.
- Workspaces irmãos em {{PROJECT_ROOT}}/workspaces/<outro>/ — escopo é {{WORKSPACE}}.

## Read order

1. L0 — {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/CLAUDE.md
2. L1 — {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/CONTEXT.md
3. L2 — este arquivo
4. {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/01_discovery/output/discovery.md (entrada principal)
5. {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/00_recon/output/recon-report.md (índice de ADRs + tipo de workspace)
6. {{PROJECT_ROOT}}/docs/decisions/*.md (ADRs vigentes — só os listados pelo recon-report)
7. {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_config/profile-effective.yaml + stop-points.md
8. {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/runtime/4-block-contract-template.md (schema obrigatório das tasks)
9. Sumário superpowers writing-plans-200tok
10. {{PROJECT_ROOT}}/docs/lessons.md + tech_debt.md (se existem)

## Process

1. **Pre-flight:** validar paths Inputs marcados `sim`; sub_stage `02_in_progress`. Se `discovery.md` ausente → status `BLOCKED_ERROR`.
2. **Ler 4-block-contract-template** para internalizar schema obrigatório de cada task em plan.md (O QUE / COMO / NÃO QUERO / VALIDAÇÃO + Files touched + ADRs aplicáveis + Lições críticas + Tech debt paydown + Requires_peer_review).
3. **Mapear discovery → tasks técnicas:** quebrar a opção macro escolhida em 01 numa lista de tasks discretas. Cada task encaixa em ≤1 wave do Wave Planner (ver `references/wave-planner-algorithm.md` — em construção, Wave 4 da skill).
4. **Para cada task, escrever 4-block + metadados** (Files touched, ADRs aplicáveis, Lições críticas se há match, etc.). Linguagem direta, evita over-engineering.
5. **Detectar stop points durante design:** stack/db/new_dep/paid_service/irreversible/over_eng/pii/adr_drift. Calibração por tier em `_config/stop-points.md`. Disparo: pausar, menu A/B/C, atualizar L1 `BLOCKED_STOP_POINT`, esperar resposta humana, retomar.
6. **Spawn ADRs novos** quando decisão arquitetural irreversível ou divergente do declarado: criar `{{PROJECT_ROOT}}/docs/decisions/NNNN-<slug>.md` com formato canônico (Context / Decision / Consequences / Status). Numeração contínua a partir do maior NNNN existente.
7. **Detectar adr_drift:** se proposta de design diverge de ADR vigente sem superseding declarado → stop point `adr_drift`. Resolução: superseding ADR (`NNNN-supersedes-MMMM.md`) OU revisão da proposta para alinhar.
8. **Escrever `output/plan.md`** com seções: Visão geral (5-10 linhas); Tasks (lista, cada uma com 4-block + metadados); ADRs criados nesta sessão; Stop points disparados (se houve); Tech debt herdado (se houve); Métricas de aceite (vinculam a discovery.md).
9. **Atualizar L1:** sub_stage `02_completed`, status `COMPLETED_AWAITING_HUMAN`, append `history` evento `stage_transition`. Commit atômico (hook valida).

## Outputs

- `output/plan.md` — design técnico com lista de tasks no schema 4-block, consumido pelo Wave Planner em 03. ADRs vivem em `{{PROJECT_ROOT}}/docs/decisions/` (fora do workspace) — plan.md cita os filenames criados.

## Sub_stage transitions

Enum válido: `02_in_progress`, `02_completed`.

Transição IN_PROGRESS → COMPLETED dispara quando:
- `output/plan.md` existe com pelo menos 1 task no schema 4-block + metadados completos.
- Stop points disparados durante a sessão estão resolvidos (status volta a `IN_PROGRESS` antes do completar).
- ADRs novos commitados em `{{PROJECT_ROOT}}/docs/decisions/` (se houve decisão arquitetural).
- Humano aprovou via gate (status `COMPLETED_AWAITING_HUMAN` → humano responde "aprovado, prosseguir 03").

## Status canônicos disponíveis neste estágio

- `IN_PROGRESS` — design ativo, escrevendo plan.md e ADRs.
- `COMPLETED_AWAITING_HUMAN` — plan.md pronto, humano revisa/edita antes de transitar.
- `BLOCKED_STOP_POINT` — menu A/B/C aguardando resposta (qualquer um dos 8 IDs aplicáveis).
- `BLOCKED_ERROR` — discovery.md ausente, ADR superseding malformado, ou hook rejeitou commit.

## Stop points aplicáveis

Catálogo canônico em `references/stop-points-canonical.md`. IDs disparáveis no estágio 02 design:

- `stack` — proposta troca de linguagem/framework/runtime vs ADR vigente. Sempre `hard`.
- `db` — engine ou schema design novo. Sempre `hard`.
- `new_dep` — npm/pip/cargo nova no manifesto (license/maintenance/size). Sempre `hard`.
- `paid_service` — SaaS recorrente (calibrado por tier: warning R$50 / hard R$200/500/1000).
- `irreversible` — drop table, migração destrutiva, schema sem volta. Sempre `hard`.
- `over_eng` — 3+ camadas de abstração novas sem requisito (warning experimental/tool, hard development/production).
- `pii` — LGPD, dados sensíveis (warning experimental, hard tool/development, hard+DPO production).
- `adr_drift` — proposta diverge de ADR existente sem superseding declarado. Sempre `hard`.

Disparo: agente pausa, escreve menu A/B/C no output, atualiza L1 `status: BLOCKED_STOP_POINT`. Humano responde, sessão retoma com `IN_PROGRESS`. Decisões arquiteturais resolvidas viram ADRs em `{{PROJECT_ROOT}}/docs/decisions/`.

## Skill superpowers de referência

Sumário 200tok: `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/superpowers-summary/writing-plans-200tok.md`

Skill formal: `superpowers:writing-plans` (escape hatch — invocação real só se design demanda planejamento estruturado profundo além do sumário).

## Gates

- **Humano:** revisa `output/plan.md` e ADRs criados; aprova ou requisita ajustes. Pode editar plan.md diretamente se discordar.
- **Automático (CI):** pre-commit hook valida atomicidade L1↔outputs e prefixo de commit `workspace/{{WORKSPACE}}`. ADRs em `{{PROJECT_ROOT}}/docs/decisions/` commitam em base_branch (não no workspace branch).
- **Aprovação para transitar:** humano explicitamente aprova; sub_stage vira `02_completed` no commit que registra a aprovação. Stop points pendentes bloqueiam transição.

## End of stage handoff (1-stage-1-sessão)

Ao concluir este estágio, sessão deve:

1. **Atualizar L1** (`<workspace>/CONTEXT.md`):
   - `sub_stage = 02_completed`
   - `status = COMPLETED_AWAITING_HUMAN` (ou `IN_PROGRESS` se transição automática pro próximo stage)
   - `last_transition.from = 02_completed`
   - `last_transition.to = 03_in_progress` (ou conforme `next_stage` do frontmatter)
   - `last_transition.at = <ISO 8601 UTC now>`
   - `history` append: `{at, event: "stage_transition", from, to, commit_sha, note}`

2. **Renderizar `_kickoff.md`** no stage seguinte:
   - Path: `<workspace>/stages/03_wave_planner/_kickoff.md`
   - Use `python scripts/handoff.py render` ou função `render_kickoff` do `scripts/handoff.py`
   - Frontmatter YAML L4-kickoff conforme schema em `references/session-handoff-protocol.md`
   - Corpo: prev_outputs com summary + prev_decisions + pending pra próximo stage

3. **Commit atômico** (pre-commit hook valida outputs↔L1; commit-msg valida prefix):
   ```
   workspace <NNN>: stage 02 completo + kickoff stage 03
   ```
   Files no commit: outputs do stage atual + L1 + `_kickoff.md` do próximo.

4. **Imprimir KICKOFF block verbal** pro user (copy-paste). Template (substitua placeholders):

   ```
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   ✅ Stage 02 (design) COMPLETO — workspace <NNN-slug>

   Workspace atualizado em commit <sha>:
     - L1: stage_atual=03, sub_stage=03_in_progress
     - Outputs: <lista>
     - Kickoff: stages/03_wave_planner/_kickoff.md gerado

   🔄 KICKOFF próxima sessão — copy/paste:
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Continuar workspace <NNN-slug> no estágio 03 (wave_planner).

   Read order:
     workspaces/<NNN-slug>/CLAUDE.md
     workspaces/<NNN-slug>/CONTEXT.md
     workspaces/<NNN-slug>/stages/03_wave_planner/CONTEXT.md
     workspaces/<NNN-slug>/stages/03_wave_planner/_kickoff.md
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

   Encerre esta sessão (Ctrl+D ou /exit) e abra nova sessão Claude
   no project_root, depois cole o prompt acima.
   ```

5. **SAIR** da sessão. NÃO continuar pro próximo stage na mesma sessão.

Detalhes em `<skill_root>/references/session-handoff-protocol.md`.
