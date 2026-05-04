---
layer: L2
stage: "05"
stage_name: "verification"
sub_stage_enum:
  - "05_in_progress"
  - "05_completed"
applicable_stop_points: []
output_files:
  - "output/verification-report.md"
next_stage: "06"
---

# Estágio 05 — verification (L2)

Auditoria técnica do que foi entregue na fase 04. Sem código novo. Verifica que outputs declarados em `plan.md` e `wave-plan.md` existem no FS, roda CI global localmente (ou consulta status), e faz sample-check de 3 ADRs aleatórios — confere se foram citados em ≥1 task report. Falha CI vira `BLOCKED_ERROR` (não stop point — verification é determinística como o wave-planner).

## Inputs (lê SOMENTE estes, na ordem)

| # | Path | Layer | Obrigatório? |
|---|------|-------|--------------|
| 1 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/CLAUDE.md | L0 | sim |
| 2 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/CONTEXT.md | L1 | sim |
| 3 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/05_verification/CONTEXT.md | L2 | sim |
| 4 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/02_design/output/plan.md | L4 | sim |
| 5 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/03_wave_planner/output/wave-plan.md | L4 | sim |
| 6 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/04_implementation_waves/output/ | L4 | sim |
| 7 | {{PROJECT_ROOT}}/.icm-main/docs/decisions/ | L3 | sim — sample-check (3 ADRs aleatórios) |
| 8 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/superpowers-summary/verification-before-completion-200tok.md | L3 | sim |
| 9 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_config/xp-conventions.md | L3 | sim |
| 10 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/05_verification/_kickoff.md | L4-kickoff | condicional: gerado pela sessão anterior. Ausente em workspaces beta1/beta2 (4B legacy) ou se for primeira sessão de stage. |
| 11 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/runtime/session-handoff-protocol.md | L3 | condicional: necessário no handoff final do estágio |
| 12 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/runtime/stop-points-canonical.md | L3 | condicional: catálogo canônico de IDs, complementar ao _config/stop-points.md de thresholds |
| 13 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/runtime/lead-resolution-protocol.md | L3 | sim — meta-check de bucket audit (v3.9.0) |

## Não Lê (negative constraint)

- {{PROJECT_ROOT}}/.icm-main/src/ (código-fonte; CI já compilou/lint/type-checked)
- {{PROJECT_ROOT}}/.icm-main/tests/ — exceção: coverage report e lista de arquivos de teste existentes são verificados nos passos 4.5 e 4.6 abaixo via `git ls-files` + cobertura do CI, sem ler conteúdo de tests
- Outputs de estágios 00, 01, 06+ do mesmo workspace
- {{PROJECT_ROOT}}/.icm-main/docs/lessons.md, {{PROJECT_ROOT}}/.icm-main/docs/tech_debt.md (escopo do review fase 06)

## Process

1. Pre-flight: validar paths Inputs existem; sub_stage `05_in_progress`.
2. **Listar entregáveis declarados:** parseia plan.md por task → `Files touched` + outputs documentais. Junta com tasks executadas em wave-plan.md.
3. **Verificar existência FS:** para cada arquivo declarado, conferir `git ls-files` em `{{BASE_BRANCH}}` pós-merge das waves (ou em workspace branch + waves rebased). Diff entrega vs entregue.
4. **Rodar CI global localmente** OU consultar status do CI remoto se disponível. Captura: lint, type-check, tests, coverage.
4.5 **Auditar cobertura:** ler coverage report gerado pelo CI (arquivo `coverage.xml`, `.coverage`, `lcov.info`, `coverage/coverage-summary.json` ou equivalente — localização declarada em `plan.md §Test Strategy`). Extrair coverage % de linhas/branches. Comparar com `test_specs.coverage_threshold` do `_config/profile-effective.yaml`. Resultado:
   - ≥ threshold → PASS neste item.
   - < threshold AND tier ∈ {experimental, tool} → CONDITIONAL (warning no report, não bloqueia).
   - < threshold AND tier ∈ {development, production} → FAIL (bloqueia transição para stage 06; status `BLOCKED_ERROR`).
   - Coverage report ausente AND `tdd_required: true` → FAIL.
4.6 **Sample-check tipos de teste:** selecionar 3 tasks aleatórias do `wave-plan.md`. Para cada:
   - Verificar que os arquivos de teste declarados em `Files touched` do `plan.md` existem no FS via `git ls-files`.
   - Verificar que o tipo de teste (unit/integration/e2e/component/eval) bate com `test_specs.test_types_required` do profile efetivo.
   - Registrar no report: task slug, arquivo esperado, arquivo encontrado (✅/⚠️), tipo de teste declarado vs encontrado.
   - ≥2/3 tasks com arquivos corretos → PASS; 1/3 → CONDITIONAL; 0/3 → FAIL.
5. **Sample-check ADRs:** seleciona 3 ADRs aleatórios de `{{PROJECT_ROOT}}/.icm-main/docs/decisions/`. Para cada, faz `grep` no diretório `stages/04/output/` por menção (slug do ADR ou número). ≥1 menção = ok; 0 menções = warning no report.
5.5 **Audit lead resolutions (v3.9.0):** ler `stages/04/output/wave-*/wave-summary.md` e extrair seção `## Lead resolutions` (tabela com bucket aplicado per task voided/resolved). Para cada entry, aplicar meta-check determinístico:
   - **B1 (REWRITE_SPEC):** comparar plan.md task antes vs depois do rewrite. Spec rewrite deve TIGHTEN (mais bullets VALIDAÇÃO específicos OR mais NÃO QUERO bullets). LOOSEN (remover criteria) sem evidence em diagnose.md → FAIL.
   - **B3 (DIRECT_IMPL):** ler critic concerns acumulados em `task-<slug>-critic-round*.json`. Lead diff em branch `-lead-resolved` deve endereçar concerns reais (heurística: BLOCKING claims em concerns devem aparecer como files_modified OR test names em lead diff). Lead que apenas silenciou critic sem fix → FAIL.
   - **B4 (VOID_TASK):** ler bloco `### VOIDED` em plan.md. Rationale deve citar ADR conflict concreto OR upstream blocker concreto. Vague reason ("complexity too high", "out of scope") sem evidence → FAIL.

   Audit é regex+estrutura (zero LLM cost). FAIL → `BLOCKED_ERROR error_type: lead_resolution_audit_failed`. Doc canônico: `references/lead-resolution-protocol.md` § Audit trail (consumido stage 05).
6. **Escrever `output/verification-report.md`:** seções `Entregáveis (declarado vs entregue)`, `CI Status`, `Sample ADRs`, `Lead resolutions audit` (v3.9.0), `Sumário PASS/CONDITIONAL/FAIL`.
7. Se CI global falhou OU entregáveis ausentes → `status: BLOCKED_ERROR`, registrar em `history`. Humano resolve (volta fase 04 com `iteration++` ou corrige manualmente).
8. **Handoff de fim de stage:** seguir protocolo gate-inline na seção `## End of stage handoff` deste L2 (Fase 1 WORK_DONE → gate humano → Fase 2 GATE_APPROVED).

## Outputs

- `output/verification-report.md` — relatório técnico: entregáveis declarado-vs-entregue, status CI (lint/type/tests/coverage), **auditoria de cobertura** (% vs threshold do profile), **sample-check tipos de teste** (3 tasks × arquivo declarado vs entregue), sample-check ADRs, veredito PASS/CONDITIONAL/FAIL.

## Sub_stage transitions

Enum válido: `05_in_progress`, `05_completed`.

Transição IN_PROGRESS → COMPLETED dispara quando:
- `output/verification-report.md` existe.
- CI global verde (ou veredito CONDITIONAL aceito pelo humano).
- Sample-check ADRs concluído (mesmo que com warnings).
- Humano aprovou via gate (status `COMPLETED_AWAITING_HUMAN` → humano responde).

## Status canônicos disponíveis neste estágio

- `IN_PROGRESS` — auditando entregáveis e CI.
- `COMPLETED_AWAITING_HUMAN` — `verification-report.md` pronto, humano aprova transição para 06.
- `BLOCKED_ERROR` — CI global vermelho, entregáveis declarados ausentes no FS, inconsistência grave entre plan.md e wave outputs, OR lead resolutions audit failed (`error_type: lead_resolution_audit_failed`, v3.9.0).

## Stop points aplicáveis

Catálogo canônico em `references/stop-points-canonical.md`. **Nenhum stop point aplicável neste estágio** — verification é determinística. Falha CI = `BLOCKED_ERROR`, não stop point. Decisões arquiteturais detectadas tarde rolam para fase 06 (review) ou para próximo workspace via fase 08 saída C.

## Skill superpowers de referência

Sumário 200tok: `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/superpowers-summary/verification-before-completion-200tok.md`

Skill formal: `superpowers:verification-before-completion` (escape hatch).

## Gates

- **Humano:** revisa `verification-report.md`, aceita PASS ou CONDITIONAL, ou requisita volta à fase 04 se FAIL.
- **Automático (CI):** CI global roda + pre-commit hook valida atomicidade L1↔outputs e prefixo de commit `workspace/{{WORKSPACE}}`.
- **Aprovação para transitar:** humano aprova explicitamente; sub_stage vira `05_completed` no próximo commit.

## End of stage handoff (gate inline + 1-stage-1-sessão)

Handoff é split em DUAS fases dentro da MESMA sessão. Gate humano fica entre elas — `_kickoff.md` só é renderizado APÓS aprovação. Bug v3.4.2 corrigido: render+exit prematuros antes da aprovação criavam loop "kickoff → user aprova em sessão nova → kickoff de novo". Doc canônico: `<skill_root>/references/session-handoff-protocol.md`.

### Fase 1: WORK_DONE (após outputs prontos)

1. **Atualizar L1** (`<workspace>/CONTEXT.md`):
   - `sub_stage = 05_completed`
   - `status = COMPLETED_AWAITING_HUMAN`
   - `last_transition.from = 05_in_progress`
   - `last_transition.to = 05_completed`
   - `last_transition.at = <ISO 8601 UTC now>`
   - `history` append: `{at, event: "stage_transition", from: "05_in_progress", to: "05_completed", commit_sha, note: "work done, awaiting gate"}`

2. **Commit atômico 1/2** (outputs + L1; pre-commit hook valida atomicidade):
   ```
   workspace <NNN>: stage 05 work done, awaiting gate
   ```
   Files: outputs do stage atual + L1. **NÃO** inclui `_kickoff.md` (não renderizado ainda).

3. **Imprimir prompt de gate** pro humano. NÃO sair da sessão. NÃO renderizar `_kickoff.md`:

   ```
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   ✅ Stage 05 (verification) trabalho COMPLETO — workspace <NNN-slug>

   Outputs prontos pra revisão:
     - <lista de paths>

   L1: sub_stage=05_completed, status=COMPLETED_AWAITING_HUMAN
   Commit 1/2: <sha>

   🛑 Gate humano: revise verification-report.md (PASS/CONDITIONAL/FAIL).
   Responda no chat:
     - "aprovado" / "ok prosseguir 06" → renderizo kickoff e saio
     - "ajustar X" → volto ao trabalho com seu pedido (status=IN_PROGRESS)
     - "abort" → marco workspace BLOCKED_ERROR
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   ```

4. **AGUARDAR resposta humana** na MESMA sessão.

### Fase 2: GATE_APPROVED (após humano responder "aprovado")

5. **Atualizar L1** (segunda transição):
   - `stage_atual = 06`
   - `sub_stage = 06_in_progress`
   - `status = IN_PROGRESS`
   - `last_transition.from = 05_completed`
   - `last_transition.to = 06_in_progress`
   - `last_transition.at = <ISO 8601 UTC now>`
   - `history` append: `{at, event: "stage_transition", from: "05_completed", to: "06_in_progress", commit_sha, note: "gate approved by human"}`

6. **Renderizar `_kickoff.md`** no stage seguinte:
   - Path: `<workspace>/stages/06_review/_kickoff.md`
   - Use `python {{SKILL_DIR}}/scripts/handoff.py render` ou função `render_kickoff` do `{{SKILL_DIR}}/scripts/handoff.py`
   - Frontmatter YAML L4-kickoff conforme schema em `references/session-handoff-protocol.md`
   - Corpo: prev_outputs + prev_decisions + pending pra próximo stage

7. **Commit atômico 2/2** (kickoff + L1):
   ```
   workspace <NNN>: gate aprovado, kickoff stage 06
   ```
   Files: `_kickoff.md` do próximo + L1 atualizado.

8. **Imprimir KICKOFF block verbal** pro user (copy-paste pra próxima sessão):

   ```
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   ✅ Stage 05 (verification) GATE APROVADO — workspace <NNN-slug>

   Workspace atualizado em commit <sha>:
     - L1: stage_atual=06, sub_stage=06_in_progress, status=IN_PROGRESS
     - Kickoff: stages/06_review/_kickoff.md gerado

   🔄 KICKOFF próxima sessão — copy/paste:
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Continuar workspace <NNN-slug> no estágio 06 (review).

   Read order:
     workspaces/<NNN-slug>/CLAUDE.md
     workspaces/<NNN-slug>/CONTEXT.md
     workspaces/<NNN-slug>/stages/06_review/CONTEXT.md
     workspaces/<NNN-slug>/stages/06_review/_kickoff.md
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

   Encerre esta sessão (Ctrl+D ou /exit) e abra nova sessão Claude
   no project_root, depois cole o prompt acima.
   ```

9. **SAIR** da sessão. NÃO continuar pro próximo stage na mesma sessão.

### Resposta "ajustar X" (gate rejeitado)

Se humano responder texto livre pedindo ajuste:
- Atualizar L1: `status = IN_PROGRESS`, append history `{event: "gate_rejected", note: "humano pediu ajuste: X"}`. Sub_stage permanece `05_completed` (volta a `05_in_progress` se mudança não-trivial).
- Voltar ao trabalho conforme pedido.
- Quando refizer outputs, voltar à Fase 1 (novo commit 1/2 + novo gate prompt).

### Resposta "abort"

Se humano responder "abort":
- Atualizar L1: `status = BLOCKED_ERROR`, append history `{event: "blocked_error", error_type: "human_abort", note: "humano abortou em gate"}`.
- Commit + sair. Workspace fica em BLOCKED_ERROR aguardando intervenção manual.

---

## v3.3.0 references aplicáveis a este stage

- **Diagnose protocol fallback (`_references/runtime/diagnose-protocol.md`):**
  quando CI fail OU coverage fail, ativar diagnose 6-fase em vez de tentar
  fix ad-hoc. Phase 1 (build feedback loop) é THE skill — sem loop
  reproduzível, não avançar. Hipóteses 3-5 ranked falsifiable. Tag debug
  logs com `[DEBUG-xxxx]` para cleanup grep no fim.
- **Output adicional:** `output/diagnose-report.md` com repro evidence,
  ranked hypotheses, root cause, fix, regression test (path).
- **HITL loop (`_config/hitl-loop.template.sh`):** template bash para bugs
  que exigem interação manual humana. Customizar `REPRO_STEPS`,
  `OBSERVE_CMD`, `PASS_PATTERN`.
