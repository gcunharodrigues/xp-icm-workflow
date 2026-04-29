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

Code review nas 7 dimensões (correctness, security, performance, complexity, tests, docs, conventions) sobre o que a fase 04 entregou e a fase 05 verificou. Issues P0/P1 disparam fix loop (loopback ao estágio 04 — nova wave ou regeneração de wave existente). Issues P2/P3 viram tech debt registrado em `{{PROJECT_ROOT}}/.icm-main/docs/tech_debt.md` e o ciclo segue para o merge (07).

## Inputs (lê SOMENTE estes, na ordem)

| # | Path | Layer | Obrigatório? |
|---|------|-------|--------------|
| 1 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/CLAUDE.md | L0 | sim |
| 2 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/CONTEXT.md | L1 | sim |
| 3 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/06_review/CONTEXT.md | L2 | sim |
| 4 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/05_verification/output/verification-report.md | L4 | sim |
| 5 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/02_design/output/plan.md | L4 | sim |
| 6 | {{PROJECT_ROOT}}/.icm-main/docs/decisions/ | L3 | condicional: ler ADRs referenciados em plan.md (sample-check, não conteúdo total) |
| 7 | {{PROJECT_ROOT}}/.icm-main/docs/tech_debt.md | L3 | condicional: existe se tier ≠ experimental — append novos P2/P3 aqui |
| 8 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_config/xp-conventions.md | L3 | sim |
| 9 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_config/stop-points.md | L3 | sim |
| 10 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/superpowers-summary/requesting-code-review-200tok.md | L3 | sim |
| 11 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/superpowers-summary/receiving-code-review-200tok.md | L3 | sim |
| 12 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/06_review/_kickoff.md | L4-kickoff | condicional: gerado pela sessão anterior. Ausente em workspaces beta1/beta2 (4B legacy) ou se for primeira sessão de stage. |
| 13 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/runtime/session-handoff-protocol.md | L3 | condicional: necessário no handoff final do estágio |
| 14 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/runtime/stop-points-canonical.md | L3 | condicional: catálogo canônico de IDs, complementar ao _config/stop-points.md de thresholds |

## Não Lê (negative constraint)

- {{PROJECT_ROOT}}/.icm-main/src/ na íntegra — review focado nos arquivos `Files touched` declarados em cada task do plan.md.
- Outputs dos estágios 00, 01, 03, 04, 07, 08 — não relevantes para o review (verification-report já consolida o que importa de 04+05).
- ADRs em {{PROJECT_ROOT}}/.icm-main/docs/decisions/ NÃO referenciados no plan.md.
- {{PROJECT_ROOT}}/.icm-main/docs/lessons.md (lições já vêm pré-injetadas no fluxo da fase 04, não relevantes ao review).

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
6. **Se P0/P1 existem (fix loop — loopback ao estágio 04, SEM gate humano):**
   - Escrever `output/p0-p1-issues.md` com cada issue: arquivo, linha, descrição, recomendação.
   - Seguir Caso B (loopback) na seção `## End of stage handoff` deste L2 — auto-transição L1 pra `stage_atual: "04"` + render kickoff em `04_implementation_waves/_kickoff.md` + commit atômico + KICKOFF block + SAIR.
7. **Se nenhum P0/P1:**
   - Append P2/P3 em `{{PROJECT_ROOT}}/.icm-main/docs/tech_debt.md` (cada item com workspace+task de origem).
   - Escrever `output/review-report.md`: 7 dimensões, lista de issues classificada P0-P3, stops detectados, recomendação final ("OK para 07" / "fix loop").
   - Seguir Caso A (gate-inline) na seção `## End of stage handoff` deste L2 (Fase 1 WORK_DONE → gate humano → Fase 2 GATE_APPROVED).

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

## End of stage handoff (gate inline + 1-stage-1-sessão)

Stage 06 tem dois caminhos: loopback ao 04 (auto, sem gate) e transição pra 07 (com gate-inline). Bug v3.4.2 corrigido apenas no Caso A (transição pra 07) — render+exit prematuros antes da aprovação criavam loop. Doc canônico: `<skill_root>/references/session-handoff-protocol.md`.

### Caso A: handoff 06 → 07 (sem P0/P1) — COM gate humano (gate inline)

#### Fase 1: WORK_DONE (após review-report.md escrito)

1. **Atualizar L1**:
   - `sub_stage = 06_completed`
   - `status = COMPLETED_AWAITING_HUMAN`
   - `last_transition.from = 06_in_progress`
   - `last_transition.to = 06_completed`
   - `last_transition.at = <ISO 8601 UTC now>`
   - `history` append: `{event: "stage_transition", from: "06_in_progress", to: "06_completed", note: "work done, awaiting gate"}`

2. **Commit atômico 1/2** (outputs + L1; **NÃO** inclui `_kickoff.md`):
   ```
   workspace <NNN>: stage 06 work done, awaiting gate
   ```

3. **Imprimir prompt de gate** pro humano. NÃO sair. NÃO renderizar `_kickoff.md`:

   ```
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   ✅ Stage 06 (review) trabalho COMPLETO — workspace <NNN-slug>
   Sem P0/P1 detectado. Recomendação: OK para 07.

   Outputs prontos pra revisão:
     - <lista de paths>

   L1: sub_stage=06_completed, status=COMPLETED_AWAITING_HUMAN
   Commit 1/2: <sha>

   🛑 Gate humano: revise review-report.md (7 dimensões + P2/P3 em tech_debt).
   Responda no chat:
     - "aprovado" / "ok prosseguir 07" → renderizo kickoff e saio
     - "ajustar X" → volto ao trabalho com seu pedido (status=IN_PROGRESS)
     - "abort" → marco workspace BLOCKED_ERROR
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   ```

4. **AGUARDAR resposta humana** na MESMA sessão.

#### Fase 2: GATE_APPROVED (após humano responder "aprovado")

5. **Atualizar L1** (segunda transição):
   - `stage_atual = 07`
   - `sub_stage = 07_in_progress`
   - `status = IN_PROGRESS`
   - `last_transition.from = 06_completed`
   - `last_transition.to = 07_in_progress`
   - `history` append: `{event: "stage_transition", from: "06_completed", to: "07_in_progress", note: "gate approved by human"}`

6. **Renderizar `_kickoff.md`** em `<workspace>/stages/07_merge/_kickoff.md`.

7. **Commit atômico 2/2** (kickoff + L1):
   ```
   workspace <NNN>: gate aprovado, kickoff stage 07
   ```

8. **Imprimir KICKOFF block verbal** pro user:

   ```
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   ✅ Stage 06 (review) GATE APROVADO — workspace <NNN-slug>

   Workspace atualizado em commit <sha>:
     - L1: stage_atual=07, sub_stage=07_in_progress, status=IN_PROGRESS
     - Kickoff: stages/07_merge/_kickoff.md gerado

   🔄 KICKOFF próxima sessão — copy/paste:
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Continuar workspace <NNN-slug> no estágio 07 (merge).

   Read order:
     workspaces/<NNN-slug>/CLAUDE.md
     workspaces/<NNN-slug>/CONTEXT.md
     workspaces/<NNN-slug>/stages/07_merge/CONTEXT.md
     workspaces/<NNN-slug>/stages/07_merge/_kickoff.md
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

   Encerre esta sessão (Ctrl+D ou /exit) e abra nova sessão Claude
   no project_root, depois cole o prompt acima.
   ```

9. **SAIR** da sessão.

#### Resposta "ajustar X" / "abort"

- "ajustar X": L1 status=IN_PROGRESS, history `gate_rejected`, voltar ao review com pedido. Refazer Fase 1 quando outputs prontos novamente.
- "abort": L1 status=BLOCKED_ERROR, history `human_abort`. Commit + sair.

### Caso B: loopback 06 → 04 (P0/P1 detectado) — SEM gate humano

Loopback é auto-transição (per Gates section): reviewer classificou P0/P1 → L1 transita pra 04 sem gate humano formal.

1. **Atualizar L1**:
   - `stage_atual = 04`
   - `sub_stage = 04_wave_<N+1>_in_progress` (nova wave de fix) OU regeneração da wave corrente conforme severidade
   - `status = IN_PROGRESS`
   - `last_transition.from = 06_in_progress`
   - `last_transition.to = 04_wave_<N+1>_in_progress`
   - `history` append: `{event: "stage_transition", from: "06_in_progress", to: "04_wave_<N+1>_in_progress", note: "fix loop — P0/P1 issues do review"}`

2. **Renderizar `_kickoff.md`** em `<workspace>/stages/04_implementation_waves/_kickoff.md` (com `prev_outputs` incluindo `p0-p1-issues.md` + nota de fix loop em `pending_for_this_stage`).

3. **Commit atômico** (outputs + L1 + kickoff):
   ```
   workspace <NNN>: stage 06 fix loop + kickoff wave <N+1>
   ```

4. **Imprimir KICKOFF block verbal** + SAIR:

   ```
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   🔁 Stage 06 LOOPBACK ao 04 — P0/P1 detectados — workspace <NNN-slug>
   Workspace atualizado em commit <sha>:
     - L1: stage_atual=04, sub_stage=04_wave_<N+1>_in_progress, status=IN_PROGRESS
     - Kickoff: stages/04_implementation_waves/_kickoff.md gerado

   🔄 KICKOFF próxima sessão — copy/paste:
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Continuar workspace <NNN-slug> no estágio 04 (implementation_waves) — wave <N+1> de fix.

   Read order:
     workspaces/<NNN-slug>/CLAUDE.md
     workspaces/<NNN-slug>/CONTEXT.md
     workspaces/<NNN-slug>/stages/04_implementation_waves/CONTEXT.md
     workspaces/<NNN-slug>/stages/04_implementation_waves/_kickoff.md
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

   Encerre esta sessão (Ctrl+D ou /exit) e abra nova sessão Claude
   no project_root, depois cole o prompt acima.
   ```
