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

Design técnico detalhado a partir do escopo refinado em discovery. Produz `plan.md` no schema 4-block + Files touched + ADRs por task (consumido pelo Wave Planner em 03). Cria ADRs novos em `{{PROJECT_ROOT}}/.icm-main/docs/decisions/` (worktree linkada da base branch — modelo v3.4.0) quando decisões arquiteturais surgem (stack, db, dependências, serviços pagos, migrações irreversíveis, etc.). Gate humano antes de transitar para 03.

## Inputs (lê SOMENTE estes, na ordem)

| # | Path | Layer | Obrigatório? |
|---|------|-------|--------------|
| 1 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/CLAUDE.md | L0 | sim |
| 2 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/CONTEXT.md | L1 | sim |
| 3 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/02_design/CONTEXT.md | L2 | sim |
| 4 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/01_discovery/output/discovery.md | L4 | sim |
| 5 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/00_recon/output/recon-report.md | L4 | sim |
| 6 | {{PROJECT_ROOT}}/.icm-main/docs/decisions/ | L3 | condicional: ler conteúdo dos ADRs vigentes listados no recon-report (filenames já indexados em 00). Lido via worktree `.icm-main/`. |
| 7 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_config/profile-effective.yaml | L3 | sim |
| 8 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_config/stop-points.md | L3 | sim |
| 9 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/runtime/4-block-contract-template.md | L3 | sim |
| 10 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/superpowers-summary/writing-plans-200tok.md | L3 | sim |
| 11 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_config/xp-conventions.md | L3 | sim |
| 12 | {{PROJECT_ROOT}}/.icm-main/docs/lessons.md | L3 | condicional: existe se herdou ou foi acumulada. Lido via worktree `.icm-main/`. |
| 13 | {{PROJECT_ROOT}}/.icm-main/docs/tech_debt.md | L3 | condicional: existe se há débito declarado em iterações anteriores. Lido via worktree `.icm-main/`. |
| 14 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/02_design/_kickoff.md | L4-kickoff | condicional: gerado pela sessão anterior. Ausente em workspaces beta1/beta2 (4B legacy) ou se for primeira sessão de stage. |
| 15 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/runtime/session-handoff-protocol.md | L3 | condicional: necessário no handoff final do estágio |
| 16 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/runtime/stop-points-canonical.md | L3 | condicional: catálogo canônico de IDs, complementar ao _config/stop-points.md de thresholds |
| 17 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/runtime/wave-planner-algorithm.md | L3 | condicional: referenciado no mapeamento discovery → tasks técnicas |
| 18 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/runtime/design-system.md | L3 | condicional: profile efetivo tem `design_system_required: True` (atualmente: `app_web_frontend`, `fullstack`) |
| 19 | {{PROJECT_ROOT}}/.icm-main/DESIGN.md | L3 | condicional: profile com `design_system_required: True` AND brownfield (arquivo já existe). Lido via worktree `.icm-main/`. |

## Não Lê (negative constraint)

- {{PROJECT_ROOT}}/.icm-main/src/ e {{PROJECT_ROOT}}/.icm-main/tests/ — design é output-driven a partir de discovery + ADRs; não inspeciona código existente. Se contexto de código for crítico, declarar dependência no plan.md (task com ADR de leitura) e revisitar 01.
- ADRs não-listados pelo recon-report — só lê os indexados em 00 ou criados nesta sessão.
- Outputs de estágios 03+ — não existem ainda.
- {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_config/xp-conventions.md — lido como Input #11; NÃO re-ler de outras fontes.
- Workspaces irmãos em {{PROJECT_ROOT}}/workspaces/<outro>/ — escopo é {{WORKSPACE}}.

## Process

1. **Pre-flight:** validar paths Inputs marcados `sim`; sub_stage `02_in_progress`. Se `discovery.md` ausente → status `BLOCKED_ERROR`.
2. **Ler 4-block-contract-template** para internalizar schema obrigatório de cada task em plan.md (O QUE / COMO / NÃO QUERO / VALIDAÇÃO + Files touched + ADRs aplicáveis + Lições críticas + Tech debt paydown + Requires_peer_review).
3. **Mapear discovery → tasks técnicas:** quebrar a opção macro escolhida em 01 numa lista de tasks discretas. Cada task encaixa em ≤1 wave do Wave Planner (ver `references/wave-planner-algorithm.md` — em construção, Wave 4 da skill).
4. **Para cada task, escrever 4-block + metadados** (Files touched, ADRs aplicáveis, Lições críticas se há match, etc.). Linguagem direta, evita over-engineering.
5. **Detectar stop points durante design:** stack/db/new_dep/paid_service/irreversible/over_eng/pii/adr_drift. Calibração por tier em `_config/stop-points.md`. Disparo: pausar, menu A/B/C, atualizar L1 `BLOCKED_STOP_POINT`, esperar resposta humana, retomar.
6. **Spawn ADRs novos** quando decisão arquitetural irreversível ou divergente do declarado: workflow canônico v3.4.0 via worktree `.icm-main/`:
   ```
   1. Write {{PROJECT_ROOT}}/.icm-main/docs/decisions/NNNN-<slug>.md
      (formato canônico — ver `_references/runtime/adr-format.md`)
   2. cd {{PROJECT_ROOT}}/.icm-main
   3. git add docs/decisions/NNNN-*.md
   4. git commit -m "docs(decisions): <slug> (workspace {{WORKSPACE}})"
   5. cd {{PROJECT_ROOT}}
   ```
   Numeração contínua a partir do maior NNNN existente em `.icm-main/docs/decisions/`. Validar 3-criteria gate antes (`adr-format.md`).
7. **Detectar adr_drift:** se proposta de design diverge de ADR vigente sem superseding declarado → stop point `adr_drift`. Resolução: superseding ADR (`NNNN-supersedes-MMMM.md`) OU revisão da proposta para alinhar.
7.5. **Design System (apenas profiles `app_web_frontend` + `fullstack`):** se profile efetivo tem `design_system_required: True` (lido em `_config/profile-effective.yaml`):
   - **Brownfield:** ler `{{PROJECT_ROOT}}/.icm-main/DESIGN.md` se existe; design respeita tokens declarados.
   - **Greenfield (arquivo ausente):** apresentar menu A/B/C ao humano:
     - **A) Criar do zero** — designer propõe tokens iniciais baseado em brand voice + audience capturados em discovery.md.
     - **B) Inspirar em exemplo** — escolha brand de referência da galeria [VoltAgent/awesome-design-md](https://github.com/VoltAgent/awesome-design-md) (airbnb, apple, claude, figma, framer, ferrari, etc.).
     - **C) Extrair de URL existente** — humano fornece URL e roda `npx designlang <url>` externamente. Designer adapta output base.
   - Após escolha, designer escreve/atualiza `<project_root>/.icm-main/DESIGN.md` seguindo schema canônico Google Stitch (YAML frontmatter + section order: Overview → Colors → Typography → Layout → Elevation & Depth → Shapes → Components → Do's and Don'ts).
   - Commit em base branch via worktree:
     ```
     cd {{PROJECT_ROOT}}/.icm-main
     git add DESIGN.md
     git commit -m "design: {{WORKSPACE}} — design system v<N>"
     cd {{PROJECT_ROOT}}
     ```
   - Plan.md cita componentes não-triviais com Component Spec table (Default/Hover/Active/Disabled) referenciando tokens declarados.
   - Tasks com files frontend ganham flag `requires_design_system: true` no metadata (consumido pelo lead na fase 04 — canal 2 inject).
   - Doc canônico: `_references/runtime/design-system.md`.
7.6. **Preview Loop — schema mock data + preview pages flag (v3.6.0):** se profile efetivo tem `preview_loop.preview_loop_enabled: true` (lido em `_config/profile-effective.yaml`):
   - **Mock data strategy** lida do efetivo (`preview_loop.mock_data_strategy`):
     - `fixtures` (experimental/tool): designer NÃO escreve schema formal; plan.md menciona apenas paths de `fixtures/*.json` esperados.
     - `msw_faker` (development): designer descreve em plan.md os endpoints `/api/*` esperados pelo frontend + shape do payload (em pseudo-TS), suficiente pra lead/subagente em fase 04 escrever `mocks/handlers.ts` usando MSW + Faker.
     - `msw_faker_zod` (production): designer escreve schema **Zod** completo em plan.md (bloco de código), salvo em `mocks/schema.ts` na fase 04. Schema é fonte de verdade do contrato API que o backend real implementará depois — refatorar mock → real = trocar handler MSW por chamada HTTP real, sem mexer em componente.
   - **Componentes reusáveis** ganham flag `requires_preview_page: true` no metadata da task. Indica ao subagente em fase 04 que junto com o componente deve escrever `preview/<component>/page.tsx` (Next.js app router) ou equivalente do build tool detectado, com ≥4 estados (Default/Hover/Active/Disabled). Path canônico em `preview_loop.preview_pages_path` (default `preview/`).
   - **Routes map (fallback CDP):** designer popula `output/routes.md` listando rotas planejadas + componente principal por rota + fixture/handler associado. Ativa fallback automático quando CDP indisponível em fase 04.
   - **Wireframe ASCII opcional:** plan.md task com layout não-trivial (ex: dashboard multi-grid) inclui wireframe ASCII no bloco `COMO`. Stage 04 lead injeta wireframe no canal 2 do subagente. Wireframe NÃO substitui DESIGN.md tokens; é aux pra layout coords.
   - Doc canônico: `_references/runtime/preview-loop-protocol.md`.
8. **Definir Test Strategy global do workspace** (uma vez no plan.md, não por task). Ler `test_specs` do `_config/profile-effective.yaml` para calibrar. Seção obrigatória com:
   - **Framework**: linguagem → framework principal (ex: Python → pytest + httpx; TS → vitest + @testing-library/react)
   - **Test pyramid**: proporção unit/integration/e2e justificada pelo profile
   - **Coverage threshold**: de `test_specs.coverage_threshold` do profile efetivo (mínimo 80% development, 90% production em linhas/branches)
   - **Path crítico 100%**: código de autenticação, pagamento, PII deve ter 100% unit obrigatório
   - **Test file location**: convenção de onde ficam os arquivos de teste (co-located vs `tests/`)
   - Se profile == `agent_ia`: incluir **Eval Strategy** (golden_output, eval_threshold, determinism seed)
   - Se profile == `ml_project`: incluir **Model Regression** (dataset fixtures, performance baseline)
9. **Escrever `output/plan.md`** com seções: Visão geral (5-10 linhas); **Test Strategy** (seção 8 acima); Tasks (lista, cada uma com 4-block + metadados); ADRs criados nesta sessão; Stop points disparados (se houve); Tech debt herdado (se houve); Métricas de aceite (vinculam a discovery.md).
10. **Handoff de fim de stage:** seguir protocolo gate-inline na seção `## End of stage handoff` deste L2 (Fase 1 WORK_DONE → gate humano → Fase 2 GATE_APPROVED).

## Outputs

- `output/plan.md` — design técnico com **Test Strategy global** + lista de tasks no schema 4-block (cada task com ≥1 arquivo de teste em `Files touched`), consumido pelo Wave Planner em 03. ADRs vivem em `{{PROJECT_ROOT}}/.icm-main/docs/decisions/` (worktree base branch) — plan.md cita os filenames criados como path relativo a `.icm-main/`.

## Sub_stage transitions

Enum válido: `02_in_progress`, `02_completed`.

Transição IN_PROGRESS → COMPLETED dispara quando:
- `output/plan.md` existe com pelo menos 1 task no schema 4-block + metadados completos.
- `output/plan.md` contém seção **Test Strategy** preenchida com framework, pyramid, coverage threshold e test file location.
- Toda task com código funcional tem ≥1 arquivo de teste em `Files touched`.
- Stop points disparados durante a sessão estão resolvidos (status volta a `IN_PROGRESS` antes do completar).
- ADRs novos commitados em base branch via `{{PROJECT_ROOT}}/.icm-main/docs/decisions/` (se houve decisão arquitetural).
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

Disparo: agente pausa, escreve menu A/B/C no output, atualiza L1 `status: BLOCKED_STOP_POINT`. Humano responde, sessão retoma com `IN_PROGRESS`. Decisões arquiteturais resolvidas viram ADRs em `{{PROJECT_ROOT}}/.icm-main/docs/decisions/`.

## Skill superpowers de referência

Sumário 200tok: `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/superpowers-summary/writing-plans-200tok.md`

Skill formal: `superpowers:writing-plans` (escape hatch — invocação real só se design demanda planejamento estruturado profundo além do sumário).

## Gates

- **Humano:** revisa `output/plan.md` e ADRs criados; aprova ou requisita ajustes. Pode editar plan.md diretamente se discordar.
- **Automático (CI):** pre-commit hook valida atomicidade L1↔outputs e prefixo de commit `workspace/{{WORKSPACE}}`. ADRs commitam via `cd {{PROJECT_ROOT}}/.icm-main && git commit ...` — esses commits caem em base_branch automaticamente (worktree linkada).
- **Aprovação para transitar:** humano explicitamente aprova; sub_stage vira `02_completed` no commit que registra a aprovação. Stop points pendentes bloqueiam transição.

## End of stage handoff (gate inline + 1-stage-1-sessão)

Handoff é split em DUAS fases dentro da MESMA sessão. Gate humano fica entre elas — `_kickoff.md` só é renderizado APÓS aprovação. Bug v3.4.2 corrigido: render+exit prematuros antes da aprovação criavam loop "kickoff → user aprova em sessão nova → kickoff de novo". Doc canônico: `<skill_root>/references/session-handoff-protocol.md`.

### Fase 1: WORK_DONE (após outputs prontos)

1. **Atualizar L1** (`<workspace>/CONTEXT.md`):
   - `sub_stage = 02_completed`
   - `status = COMPLETED_AWAITING_HUMAN`
   - `last_transition.from = 02_in_progress`
   - `last_transition.to = 02_completed`
   - `last_transition.at = <ISO 8601 UTC now>`
   - `history` append: `{at, event: "stage_transition", from: "02_in_progress", to: "02_completed", commit_sha, note: "work done, awaiting gate"}`

2. **Commit atômico 1/2** (outputs + L1; pre-commit hook valida atomicidade):
   ```
   workspace <NNN>: stage 02 work done, awaiting gate
   ```
   Files: outputs do stage atual + L1. **NÃO** inclui `_kickoff.md` (não renderizado ainda).

3. **Imprimir prompt de gate** pro humano. NÃO sair da sessão. NÃO renderizar `_kickoff.md`:

   ```
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   ✅ Stage 02 (design) trabalho COMPLETO — workspace <NNN-slug>

   Outputs prontos pra revisão:
     - <lista de paths>

   L1: sub_stage=02_completed, status=COMPLETED_AWAITING_HUMAN
   Commit 1/2: <sha>

   🛑 Gate humano: revise os outputs acima.
   Responda no chat:
     - "aprovado" / "ok prosseguir 03" → renderizo kickoff e saio
     - "ajustar X" → volto ao trabalho com seu pedido (status=IN_PROGRESS)
     - "abort" → marco workspace BLOCKED_ERROR
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   ```

4. **AGUARDAR resposta humana** na MESMA sessão.

### Fase 2: GATE_APPROVED (após humano responder "aprovado")

5. **Atualizar L1** (segunda transição):
   - `stage_atual = 03`
   - `sub_stage = 03_in_progress`
   - `status = IN_PROGRESS`
   - `last_transition.from = 02_completed`
   - `last_transition.to = 03_in_progress`
   - `last_transition.at = <ISO 8601 UTC now>`
   - `history` append: `{at, event: "stage_transition", from: "02_completed", to: "03_in_progress", commit_sha, note: "gate approved by human"}`

6. **Renderizar `_kickoff.md`** no stage seguinte:
   - Path: `<workspace>/stages/03_wave_planner/_kickoff.md`
   - Use `python {{SKILL_DIR}}/scripts/handoff.py render` ou função `render_kickoff` do `{{SKILL_DIR}}/scripts/handoff.py`
   - Frontmatter YAML L4-kickoff conforme schema em `references/session-handoff-protocol.md`
   - Corpo: prev_outputs + prev_decisions + pending pra próximo stage

7. **Commit atômico 2/2** (kickoff + L1):
   ```
   workspace <NNN>: gate aprovado, kickoff stage 03
   ```
   Files: `_kickoff.md` do próximo + L1 atualizado.

8. **Imprimir KICKOFF block verbal** pro user (copy-paste pra próxima sessão):

   ```
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   ✅ Stage 02 (design) GATE APROVADO — workspace <NNN-slug>

   Workspace atualizado em commit <sha>:
     - L1: stage_atual=03, sub_stage=03_in_progress, status=IN_PROGRESS
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

9. **SAIR** da sessão. NÃO continuar pro próximo stage na mesma sessão.

### Resposta "ajustar X" (gate rejeitado)

Se humano responder texto livre pedindo ajuste:
- Atualizar L1: `status = IN_PROGRESS`, append history `{event: "gate_rejected", note: "humano pediu ajuste: X"}`. Sub_stage permanece `02_completed` (volta a `02_in_progress` se mudança não-trivial).
- Voltar ao trabalho conforme pedido.
- Quando refizer outputs, voltar à Fase 1 (novo commit 1/2 + novo gate prompt).

### Resposta "abort"

Se humano responder "abort":
- Atualizar L1: `status = BLOCKED_ERROR`, append history `{event: "blocked_error", error_type: "human_abort", note: "humano abortou em gate"}`.
- Commit + sair. Workspace fica em BLOCKED_ERROR aguardando intervenção manual.

---

## v3.3.0 references aplicáveis a este stage

- **ADR 3-critérios gate (`_references/runtime/adr-format.md`):** antes de
  spawnar ADR, validar TODOS os 3 critérios: (1) hard to reverse, (2)
  surprising without context, (3) result of real trade-off. Falha em qualquer
  → vai para `decisions.md` como nota, NÃO ADR.
- **OUT-OF-SCOPE check (`_references/runtime/out-of-scope-kb.md`):** se
  `iteration > 0` no L1, ler `<workspace>/_out-of-scope/*.md` antes de
  propor design. Match com rejeição prior → surface ao humano antes de
  re-propor.
- **HITL/AFK no plan.md (`_references/runtime/task-types-hitl-afk.md`):**
  cada task no plan.md ganha campo `**Type:** HITL|AFK`. AFK é default.
  HITL exige justificativa em campo `**Reason:**`.
- **AGENT-BRIEF compatibility (`_references/runtime/agent-brief-template.md`):**
  4-block (O QUE / COMO / NÃO QUERO / VALIDAÇÃO) por task DEVE ser parseável
  pelo `agent-brief-render.py` na fase 04. Mapping: O QUE→Summary+Desired,
  COMO→Key interfaces (sem paths absolutos!), NÃO QUERO→Out of scope,
  VALIDAÇÃO→Acceptance criteria.
- **Design It Twice (`_references/runtime/design-it-twice.md`):** módulos
  marcados `core: true` no plan.md acionam Design It Twice. Spawnar 3+
  Agent tool calls em paralelo com constraints distintos (minimize
  interface / maximize flexibility / optimize common caller). Output em
  `output/design-alternatives-<module>.md` + decisão final em decisions.md.
- **Deep modules (`_references/runtime/deep-modules.md`, v3.4.1):** para
  cada módulo novo introduzido pelo design, validar checklist de 5 itens:
  interface mínima (≤5 métodos), information hiding (API não expõe estado),
  single responsibility (nome sem and/or), deletion test (blast radius
  <30% callers precisarem adaptar lógica), alternativa considerada em ADR.
  ≥2 itens falhando = voltar à prancheta. Skip para bug fix puro ou módulo
  trivial single-function.

## Ubiquitous Language

Inputs: `_config/CONTEXT.md` (L3, populado em stage 01) é obrigatório.
Vocabulário do glossário deve ser usado consistentemente em plan.md, ADRs,
e output/. Auto-QA Akita valida consistência.

## v3.4.0 — Worktree paralelo

Pré-flight do estágio inclui validar `.icm-main/` worktree existe em
`{{PROJECT_ROOT}}/`. Ausente = `BLOCKED_ERROR`; recovery wizard sugere
`git worktree add .icm-main {{BASE_BRANCH}}`. Doc canônico:
`_references/runtime/worktree-model.md`.
