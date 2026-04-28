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
| 7 | {{PROJECT_ROOT}}/docs/decisions/ | L3 | sim — sample-check (3 ADRs aleatórios) |
| 8 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/superpowers-summary/verification-before-completion-200tok.md | L3 | sim |
| 9 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_config/xp-conventions.md | L3 | sim |
| 10 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/05_verification/_kickoff.md | L4-kickoff | condicional: gerado pela sessão anterior. Ausente em workspaces beta1/beta2 (4B legacy) ou se for primeira sessão de stage. |

## Não Lê (negative constraint)

- {{PROJECT_ROOT}}/src/, {{PROJECT_ROOT}}/tests/ (CI já testou; verification consulta resultado, não relê fonte)
- Outputs de estágios 00, 01, 06+ do mesmo workspace
- {{PROJECT_ROOT}}/docs/lessons.md, {{PROJECT_ROOT}}/docs/tech_debt.md (escopo do review fase 06)

## Read order

1. L0 — {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/CLAUDE.md
2. L1 — {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/CONTEXT.md
3. L2 — este arquivo
4. plan.md — entregáveis declarados por task
5. wave-plan.md — waves executadas e branches geradas
6. stages/04/output/ — task reports + wave summaries
7. ADRs sample (3 aleatórios) — verificar citação em ≥1 task report
8. verification-before-completion-200tok.md (sumário)
9. xp-conventions.md — naming, file limits, docstrings (baseline para verification)
10. {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/05_verification/_kickoff.md (se existe — handoff do estágio 04)

## Process

1. Pre-flight: validar paths Inputs existem; sub_stage `05_in_progress`.
2. **Listar entregáveis declarados:** parseia plan.md por task → `Files touched` + outputs documentais. Junta com tasks executadas em wave-plan.md.
3. **Verificar existência FS:** para cada arquivo declarado, conferir `git ls-files` em `{{BASE_BRANCH}}` pós-merge das waves (ou em workspace branch + waves rebased). Diff entrega vs entregue.
4. **Rodar CI global localmente** OU consultar status do CI remoto se disponível. Captura: lint, type-check, tests, coverage.
5. **Sample-check ADRs:** seleciona 3 ADRs aleatórios de `{{PROJECT_ROOT}}/docs/decisions/`. Para cada, faz `grep` no diretório `stages/04/output/` por menção (slug do ADR ou número). ≥1 menção = ok; 0 menções = warning no report.
6. **Escrever `output/verification-report.md`:** seções `Entregáveis (declarado vs entregue)`, `CI Status`, `Sample ADRs`, `Sumário PASS/CONDITIONAL/FAIL`.
7. Se CI global falhou OU entregáveis ausentes → `status: BLOCKED_ERROR`, registrar em `history`. Humano resolve (volta fase 04 com `iteration++` ou corrige manualmente).
8. Atualizar L1: sub_stage `05_completed`, status `COMPLETED_AWAITING_HUMAN`. Commit atômico.

## Outputs

- `output/verification-report.md` — relatório técnico: entregáveis declarado-vs-entregue, status CI (lint/type/tests/coverage), sample-check ADRs, veredito PASS/CONDITIONAL/FAIL.

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
- `BLOCKED_ERROR` — CI global vermelho, entregáveis declarados ausentes no FS, ou inconsistência grave entre plan.md e wave outputs.

## Stop points aplicáveis

Catálogo canônico em `references/stop-points-canonical.md`. **Nenhum stop point aplicável neste estágio** — verification é determinística. Falha CI = `BLOCKED_ERROR`, não stop point. Decisões arquiteturais detectadas tarde rolam para fase 06 (review) ou para próximo workspace via fase 08 saída C.

## Skill superpowers de referência

Sumário 200tok: `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/superpowers-summary/verification-before-completion-200tok.md`

Skill formal: `superpowers:verification-before-completion` (escape hatch).

## Gates

- **Humano:** revisa `verification-report.md`, aceita PASS ou CONDITIONAL, ou requisita volta à fase 04 se FAIL.
- **Automático (CI):** CI global roda + pre-commit hook valida atomicidade L1↔outputs e prefixo de commit `workspace/{{WORKSPACE}}`.
- **Aprovação para transitar:** humano aprova explicitamente; sub_stage vira `05_completed` no próximo commit.

## End of stage handoff (1-stage-1-sessão)

Ao concluir este estágio, sessão deve:

1. **Atualizar L1** (`<workspace>/CONTEXT.md`):
   - `sub_stage = 05_completed`
   - `status = COMPLETED_AWAITING_HUMAN` (ou `IN_PROGRESS` se transição automática pro próximo stage)
   - `last_transition.from = 05_completed`
   - `last_transition.to = 06_in_progress` (ou conforme `next_stage` do frontmatter)
   - `last_transition.at = <ISO 8601 UTC now>`
   - `history` append: `{at, event: "stage_transition", from, to, commit_sha, note}`

2. **Renderizar `_kickoff.md`** no stage seguinte:
   - Path: `<workspace>/stages/06_review/_kickoff.md`
   - Use `python {{SKILL_DIR}}/scripts/handoff.py render` ou função `render_kickoff` do `{{SKILL_DIR}}/scripts/handoff.py`
   - Frontmatter YAML L4-kickoff conforme schema em `references/session-handoff-protocol.md`
   - Corpo: prev_outputs com summary + prev_decisions + pending pra próximo stage

3. **Commit atômico** (pre-commit hook valida outputs↔L1; commit-msg valida prefix):
   ```
   workspace <NNN>: stage 05 completo + kickoff stage 06
   ```
   Files no commit: outputs do stage atual + L1 + `_kickoff.md` do próximo.

4. **Imprimir KICKOFF block verbal** pro user (copy-paste). Template (substitua placeholders):

   ```
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   ✅ Stage 05 (verification) COMPLETO — workspace <NNN-slug>

   Workspace atualizado em commit <sha>:
     - L1: stage_atual=06, sub_stage=06_in_progress
     - Outputs: <lista>
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

5. **SAIR** da sessão. NÃO continuar pro próximo stage na mesma sessão.

Detalhes em `<skill_root>/references/session-handoff-protocol.md`.
