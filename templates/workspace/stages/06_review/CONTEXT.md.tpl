---
layer: L2
stage: "06"
stage_name: "review"
sub_stage_enum:
  - "06_in_progress"
  - "06_completed"
applicable_stop_points:
  - "over_eng"
  - "pii"
  - "adr_drift"
output_files:
  - "output/review-report.md"
  - "output/p0-p1-issues.md"  # condicional: somente se houver P0/P1
next_stage: "07"
---

# Estágio 06 — review (L2)

Code review nas 7 dimensões (correctness, security, performance, complexity, tests, docs, conventions) sobre o que a fase 04 entregou e a fase 05 verificou. Issues P0/P1 disparam fix loop (loopback ao estágio 04 — nova wave ou regeneração de wave existente). Issues P2/P3 viram tech debt registrado em `{{PROJECT_ROOT}}/docs/tech_debt.md` e o ciclo segue para o merge (07).

## Inputs (lê SOMENTE estes, na ordem)

| # | Path | Layer | Obrigatório? |
|---|------|-------|--------------|
| 1 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/CLAUDE.md | L0 | sim |
| 2 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/CONTEXT.md | L1 | sim |
| 3 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/06_review/CONTEXT.md | L2 | sim |
| 4 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/05_verification/output/verification-report.md | L4 | sim |
| 5 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/02_design/output/plan.md | L4 | sim |
| 6 | {{PROJECT_ROOT}}/docs/decisions/ | L3 | condicional: ler ADRs referenciados em plan.md (sample-check, não conteúdo total) |
| 7 | {{PROJECT_ROOT}}/docs/tech_debt.md | L3 | condicional: existe se tier ≠ experimental — append novos P2/P3 aqui |
| 8 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_config/xp-conventions.md | L3 | sim |
| 9 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_config/stop-points.md | L3 | sim |
| 10 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/superpowers-summary/requesting-code-review-200tok.md | L3 | sim |
| 11 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/superpowers-summary/receiving-code-review-200tok.md | L3 | sim |
| 12 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/06_review/_kickoff.md | L4-kickoff | condicional: gerado pela sessão anterior. Ausente em workspaces beta1/beta2 (4B legacy) ou se for primeira sessão de stage. |
| 13 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/runtime/session-handoff-protocol.md | L3 | condicional: necessário no handoff final do estágio |
| 14 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/runtime/stop-points-canonical.md | L3 | condicional: catálogo canônico de IDs, complementar ao _config/stop-points.md de thresholds |

## Não Lê (negative constraint)

- {{PROJECT_ROOT}}/src/ na íntegra — review focado nos arquivos `Files touched` declarados em cada task do plan.md.
- Outputs dos estágios 00, 01, 03, 04, 07, 08 — não relevantes para o review (verification-report já consolida o que importa de 04+05).
- ADRs em {{PROJECT_ROOT}}/docs/decisions/ NÃO referenciados no plan.md.
- {{PROJECT_ROOT}}/docs/lessons.md (lições já vêm pré-injetadas no fluxo da fase 04, não relevantes ao review).

## Process

1. **Pre-flight:** validar paths Inputs obrigatórios; sub_stage `06_in_progress`. verification-report.md AUSENTE → `BLOCKED_ERROR`.
2. **Spawn reviewer subagent:** subagent independente lê verification-report + plan.md + arquivos do `Files touched`. Não confunde com author. Consulta sumários requesting/receiving 200tok.
3. **Review nas 7 dimensões** (uma passada por dimensão, registrando achados):
   - **correctness** — comportamento bate com o 4-block contract da task?
   - **security** — input validation, secrets, authz, injection, PII vazando?
   - **performance** — hot path com complexidade indevida, N+1, leak?
   - **complexity** — over-engineering, abstrações desnecessárias, código morto?
   - **tests** — cobrem caminhos críticos? testam contrato, não implementação?
   - **docs** — docstrings, README, ADR aplicado, comentários onde não-óbvio?
   - **conventions** — bate com xp-conventions.md (naming, imports, formatting)?
4. **Classificar issues** em P0/P1/P2/P3:
   - **P0** — bug que afeta funcionalidade declarada no plan, vulnerabilidade ativa, regressão.
   - **P1** — risco alto não-imediato (race rara, perf gap, edge case sem teste).
   - **P2** — tech debt relevante (refactor desejável, cobertura baixa).
   - **P3** — cosmético (naming, comentário, import order).
5. **Detectar stop points** durante o review:
   - 3+ camadas de abstração novas sem requisito → `over_eng` (calibrado por tier).
   - Logs/schema com PII em texto claro → `pii` (calibrado por tier).
   - Implementação diverge de ADR vigente sem superseding declarado → `adr_drift`.
6. **Se P0/P1 existem (fix loop — loopback ao estágio 04):**
   - Escrever `output/p0-p1-issues.md` com cada issue: arquivo, linha, descrição, recomendação.
   - Atualizar L1: `stage_atual: "04"`, `sub_stage: "04_wave_<N+1>_in_progress"` (nova wave de fix) OU regenerar a wave atual conforme severidade. Append `history` evento `stage_transition` `from: 06_in_progress` `to: 04_wave_<N+1>_in_progress` com `note: "fix loop — P0/P1 issues do review"`.
   - status: `IN_PROGRESS`. Sessão termina; próxima sessão retoma na fase 04.
   - Commit atômico (pre-commit hook valida atomicidade L1↔outputs).
7. **Se nenhum P0/P1:**
   - Append P2/P3 em `{{PROJECT_ROOT}}/docs/tech_debt.md` (cada item com workspace+task de origem).
   - Escrever `output/review-report.md`: 7 dimensões, lista de issues classificada P0-P3, stops detectados, recomendação final ("OK para 07" / "fix loop").
   - Atualizar L1: `sub_stage: "06_completed"`, `status: COMPLETED_AWAITING_HUMAN`. Append `history` evento `stage_transition`.
   - Commit atômico.
8. **Gate humano:** humano lê review-report. Aprova → próxima sessão entra em estágio 07.

## Outputs

- `output/review-report.md` — relatório das 7 dimensões + lista de issues classificada P0-P3 + stops detectados + recomendação ("merge" ou "fix loop").
- `output/p0-p1-issues.md` — somente se houver P0/P1; descreve cada issue com arquivo, linha, descrição e ação proposta para a wave de fix.

## Sub_stage transitions

Enum válido: `06_in_progress`, `06_completed`.

Transição IN_PROGRESS → COMPLETED dispara quando:
- `output/review-report.md` existe.
- Sem P0/P1 (caso contrário, há loopback para 04 — sub_stage volta a `04_wave_<N+1>_in_progress` e a fase 06 será revisitada após).
- P2/P3 (se houver) appended em `tech_debt.md`.
- Humano aprovou via gate (status `COMPLETED_AWAITING_HUMAN` → resposta humana).

**Loopback to 04 if P0/P1:** quando o reviewer classifica ≥1 issue como P0/P1, a sub_stage NÃO transita para `06_completed`. Em vez disso, L1 é atualizado para `stage_atual: "04"` e `sub_stage: "04_wave_<N+1>_in_progress"` (ou regeneração da wave corrente). A fase 06 é revisitada depois que a nova wave passa pela 05 verification — agora com fix do issue.

## Status canônicos disponíveis neste estágio

- `IN_PROGRESS` — review ativo, reviewer subagent rodando.
- `COMPLETED_AWAITING_HUMAN` — review-report pronto sem P0/P1, humano aprova antes de 07.
- `BLOCKED_STOP_POINT` — `over_eng`, `pii` ou `adr_drift` disparou; menu A/B/C aguardando resposta.
- `BLOCKED_ERROR` — verification-report ausente, hook rejeitou commit, ou reviewer subagent falhou.

## Stop points aplicáveis

Catálogo canônico em `references/stop-points-canonical.md`. IDs disparáveis no estágio 06 review:

- `over_eng` — 3+ camadas de abstração novas sem requisito (warning experimental/tool, hard development/production).
- `pii` — schema/logs com PII em claro (warning experimental, hard tool/development, hard+DPO production).
- `adr_drift` — código entregue diverge de ADR vigente sem superseding declarado.

Disparo: agente pausa, escreve menu A/B/C no output, atualiza L1 `status: BLOCKED_STOP_POINT`. Humano responde, sessão retoma com `IN_PROGRESS`.

## Skill superpowers de referência

Sumários 200tok (consulta obrigatória pelo reviewer subagent):

- `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/superpowers-summary/requesting-code-review-200tok.md`
- `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/superpowers-summary/receiving-code-review-200tok.md`

Skills formais (escape hatch): `superpowers:requesting-code-review`, `superpowers:receiving-code-review`.

## Gates

- **Humano:** revisa `output/review-report.md`. Se sem P0/P1, aprova "OK para 07?". Se P0/P1, aprova fix loop (transição automática a 04).
- **Automático (CI):** pre-commit hook valida atomicidade L1↔outputs e prefixo de commit `workspace/{{WORKSPACE}}`.
- **Aprovação para transitar:** humano aprova explicitamente; sub_stage vira `06_completed` no commit que registra a aprovação. Loopback ao 04 não exige gate humano formal — basta o reviewer ter classificado P0/P1, o L1 transita automaticamente.

## End of stage handoff (1-stage-1-sessão)

Ao concluir este estágio, sessão deve:

1. **Atualizar L1** (`<workspace>/CONTEXT.md`):
   - `sub_stage = 06_completed` (ou `04_wave_<N+1>_in_progress` se loopback por P0/P1 — nesse caso `stage_atual = 04` também)
   - `status = COMPLETED_AWAITING_HUMAN` (sem P0/P1) ou `IN_PROGRESS` (loopback ao 04)
   - `last_transition.from = 06_completed` (ou `06_in_progress` se loopback)
   - `last_transition.to = 07_in_progress` (sem P0/P1, conforme `next_stage`) **OU** `04_wave_<N+1>_in_progress` (loopback)
   - `last_transition.at = <ISO 8601 UTC now>`
   - `history` append: `{at, event: "stage_transition", from, to, commit_sha, note}`

2. **Renderizar `_kickoff.md`** no destino seguinte:
   - Sem P0/P1: `<workspace>/stages/07_merge/_kickoff.md`
   - Loopback (P0/P1): `<workspace>/stages/04_implementation_waves/_kickoff.md` (com `prev_outputs` incluindo `p0-p1-issues.md` + nota de fix loop em `pending_for_this_stage`)
   - Use `python {{SKILL_DIR}}/scripts/handoff.py render` ou função `render_kickoff` do `{{SKILL_DIR}}/scripts/handoff.py`
   - Frontmatter YAML L4-kickoff conforme schema em `references/session-handoff-protocol.md`
   - Corpo: prev_outputs com summary + prev_decisions + pending pra próxima sessão

3. **Commit atômico** (pre-commit hook valida outputs↔L1; commit-msg valida prefix):
   ```
   workspace <NNN>: stage 06 completo + kickoff stage 07
   ```
   ou (loopback):
   ```
   workspace <NNN>: stage 06 fix loop + kickoff wave <N+1>
   ```
   Files no commit: outputs do stage atual + L1 + `_kickoff.md` do próximo.

4. **Imprimir KICKOFF block verbal** pro user (copy-paste). Template (substitua placeholders — variante sem P0/P1 OU variante loopback):

   ```
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   ✅ Stage 06 (review) COMPLETO — workspace <NNN-slug>
   (ou: 🔁 Stage 06 LOOPBACK ao 04 — P0/P1 detectados)

   Workspace atualizado em commit <sha>:
     - L1: stage_atual=07, sub_stage=07_in_progress
       (ou: stage_atual=04, sub_stage=04_wave_<N+1>_in_progress)
     - Outputs: <lista>
     - Kickoff: <path do _kickoff.md gerado>

   🔄 KICKOFF próxima sessão — copy/paste:
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Continuar workspace <NNN-slug> no estágio 07 (merge).
   (ou: Continuar workspace <NNN-slug> no estágio 04 (implementation_waves) — wave <N+1> de fix.)

   Read order:
     workspaces/<NNN-slug>/CLAUDE.md
     workspaces/<NNN-slug>/CONTEXT.md
     workspaces/<NNN-slug>/stages/<stage-dir>/CONTEXT.md
     workspaces/<NNN-slug>/stages/<stage-dir>/_kickoff.md
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

   Encerre esta sessão (Ctrl+D ou /exit) e abra nova sessão Claude
   no project_root, depois cole o prompt acima.
   ```

5. **SAIR** da sessão. NÃO continuar pro próximo stage na mesma sessão.

Detalhes em `<skill_root>/references/session-handoff-protocol.md`.
