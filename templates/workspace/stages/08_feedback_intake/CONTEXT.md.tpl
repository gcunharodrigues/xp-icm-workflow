---
layer: L2
stage: "08"
stage_name: "feedback_intake"
sub_stage_enum:
  - "08_in_progress"
  - "08_decided_A"
  - "08_decided_B"
  - "08_decided_C"
applicable_stop_points: []
output_files:
  - "output/intake-report.md"
next_stage: null
---

# Estágio 08 — feedback_intake (L2)

Gate de iteração universal do ciclo ICM. Disparado MANUAL pelo humano após uso real do output do workspace (semanas/meses após `07_completed`). Coleta logs (se `logs_root` declarado), feedback humano em 4 blocos e top-N error patterns. Resultado: menu A/B/C com 3 saídas — A) close workspace + lições em `docs/lessons.md`, B) restart fase X (X ∈ 01..07) com `iteration++`, C) spawn novo workspace via humano colando comando em sessão nova. NÃO faz código novo — apenas analisa e transiciona estado. Protocolo literal em `_references/runtime/feedback-intake-fase08.md`.

## Inputs (lê SOMENTE estes, na ordem)

| # | Path | Layer | Obrigatório? |
|---|------|-------|--------------|
| 1 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/CLAUDE.md | L0 | sim |
| 2 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/CONTEXT.md | L1 | sim |
| 3 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/08_feedback_intake/CONTEXT.md | L2 | sim |
| 4 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/01_discovery/output/ | L4 | condicional: existe se discovery rodou (profile não pulou 01) |
| 5 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/02_design/output/ | L4 | condicional: existe se design rodou |
| 6 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/03_wave_planner/output/ | L4 | condicional: existe se wave planner rodou |
| 7 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/04_implementation_waves/output/ | L4 | condicional: existe se implementação rodou |
| 8 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/05_verification/output/ | L4 | condicional: existe se verification rodou |
| 9 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/06_review/output/ | L4 | condicional: existe se review rodou |
| 10 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/07_merge/output/ | L4 | sim (sample-check pré-condição) |
| 11 | {{PROJECT_ROOT}}/docs/lessons.md | L3 | condicional: append apenas em saída A |
| 12 | {{LOGS_ROOT}} | L3 | condicional: opcional — sample dos últimos 30 dias se L0 declara `logs_root` ≠ null |
| 13 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/runtime/feedback-intake-fase08.md | L3 | sim (protocolo literal — cópia local da reference) |

**Nota sobre `{{LOGS_ROOT}}`:** placeholder resolvido pelo bootstrap a partir do campo `logs_root` do L0. Se `logs_root: null` (greenfield, texto, skill), bootstrap substitui por marcador inerte e o input é skipped no pre-flight. Se `logs_root` é path real, sessão samplea os últimos 30 dias.

## Não Lê (negative constraint)

- {{PROJECT_ROOT}}/src/, {{PROJECT_ROOT}}/tests/ — fase 08 não revisita código.
- Outros workspaces em {{PROJECT_ROOT}}/workspaces/<outro>/ — saída C (spawn) consulta CONTEXT.md de workspace antigo via `spawn_from`, mas isso é responsabilidade do NOVO workspace; o workspace atual não lê outros.
- {{PROJECT_ROOT}}/docs/decisions/ — ADRs não são editados na fase 08; herança em saída C é responsabilidade do novo workspace.
- {{PROJECT_ROOT}}/docs/tech_debt.md — não há append aqui (lições da fase 08 vão em `docs/lessons.md` somente em saída A).

## Read order

1. L0 — {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/CLAUDE.md
2. L1 — {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/CONTEXT.md (valida pré-condição `status: COMPLETED`)
3. L2 — este arquivo
4. {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/runtime/feedback-intake-fase08.md (protocolo literal)
5. Outputs anteriores (sample-check existência por estágio que rodou — respeita `stages_skipped` do profile)
6. {{LOGS_ROOT}} (sample 30 dias, se aplicável)
7. {{PROJECT_ROOT}}/docs/lessons.md (somente leitura aqui — append acontece em saída A)

## Process

1. **Pre-flight — pré-condição obrigatória:** L1 deve declarar `status: COMPLETED` (fase 07 já encerrou, ou fase 08 anterior decidiu A/C). Se status ∈ {`IN_PROGRESS`, `BLOCKED_*`, `COMPLETED_AWAITING_HUMAN`} → recusar com mensagem "workspace ainda não foi concluído (fase 07). Termine o ciclo principal antes de rodar feedback intake." Se status indefinido/inconsistente → stop point 11 `workspace_corrupt` (raro, mas possível).
2. **Setar sub_stage `08_in_progress`** + `status: IN_PROGRESS` no L1 (sai de `COMPLETED` enquanto a sessão decide). Append `history` evento `stage_transition` `from: 07_completed` (ou `08_decided_X` se reabertura) `to: 08_in_progress`.
3. **Coleta de logs** (somente se `logs_root` ≠ null em L0): sampleia últimos 30 dias de `{{LOGS_ROOT}}`. Se path inacessível/vazio, anota "logs vazios/inacessíveis" e segue.
4. **Coleta de feedback humano em 4 blocos** (sessão pergunta inline; valida que cada bloco tem ≥1 frase substantiva):
   - O QUE FUNCIONOU
   - O QUE NÃO FUNCIONOU
   - QUAL DOR PERSISTE
   - QUE LIÇÃO TIRAR
5. **Análise top-N error patterns:** agrupa logs + feedback em ≤5 padrões com `frequencia`, `impacto` (low/medium/high/critical) e `evidencia`. Aceita 0-2 padrões se logs vazios e feedback curto.
6. **Escrever `output/intake-report.md`** com seções fixas: Logs sample, Feedback humano (4 blocos), Top-N patterns (tabela), Recomendação (saída sugerida + justificativa).
7. **Menu A/B/C ao humano** (no chat, com recomendação destacada):
   - **A) Close workspace.** Append lições novas (extraídas de QUE LIÇÃO TIRAR) em `{{PROJECT_ROOT}}/docs/lessons.md` respeitando frontmatter strict (id, date, tags, severity). Set `sub_stage: 08_decided_A`, `status: COMPLETED`. Workspace arquivado.
   - **B) Restart fase X (`iteration++`).** Validar X ∈ {`01`, `02`, `03`, `04`, `05`, `06`, `07`} — recusar `00` (use saída C para mudar `project_root`/tipo) e `08` (não faz sentido restart no próprio gate). Mover outputs antigos: `stages/<XX>/output/` → `stages/<XX>/output-iteration-<N>/` (N = iteration ANTES do incremento). Set `iteration: N+1`, `stage_atual: <XX>`, `sub_stage: <XX>_in_progress`, `status: IN_PROGRESS`. Append `history` evento `iteration_increment`. Sessão sai; próxima sessão retoma na fase X com lições do intake-report.
   - **C) Spawn novo workspace.** UX: NÃO bootstrappa o novo automaticamente. Set `sub_stage: 08_decided_C`, `status: COMPLETED`, `spawn_to: <slug-novo-workspace>`. Imprime mensagem com comando para humano colar em sessão nova: `/xp-icm-workflow project-root={{PROJECT_ROOT}} spawn_from={{WORKSPACE}}`. Sessão atual termina. Bootstrap do novo acontece em sessão separada.
8. **Commit atômico** (pre-commit hook valida atomicidade L1 ↔ outputs ↔ lessons; prefixo `intake:` ou `feedback:`).

## Outputs

- `output/intake-report.md` — relatório de intake: logs sample (ou n/a), feedback humano em 4 blocos, top-N error patterns (tabela), recomendação de saída (A/B/C) com justificativa.

## Sub_stage transitions

Enum válido: `08_in_progress`, `08_decided_A`, `08_decided_B`, `08_decided_C`.

Transições:
- `08_in_progress → 08_decided_A`: humano escolhe A. `status: COMPLETED`. Lições appended em `docs/lessons.md`.
- `08_in_progress → <XX>_in_progress` (saída B): humano escolhe B com X ∈ 01..07. `iteration++`. `status: IN_PROGRESS`. Outputs antigos movidos para `output-iteration-<N>/`. Note: o sub_stage transita DIRETAMENTE para o estágio X — não há `08_decided_B` "estável" persistente; ele aparece apenas como evento em `history`. (Spec exige o enum `08_decided_B` por compatibilidade; sessões transicionam por ele e em seguida saem para `<XX>_in_progress`.)
- `08_in_progress → 08_decided_C`: humano escolhe C. `status: COMPLETED`. `spawn_to` set. Bootstrap do novo workspace é responsabilidade do humano em sessão separada.

`next_stage: null` — estágio 08 não tem próximo estágio determinístico. Saídas A e C terminam o workspace; saída B retorna a uma fase X via `last_transition`/`history`, não via `next_stage`.

**Validação saída B:** sessão recusa X ∉ {`01`, `02`, `03`, `04`, `05`, `06`, `07`}. Para mudar `project_root` ou tipo do projeto, use saída C.

**UX saída C:** sessão NÃO bootstrappa novo workspace. Apenas imprime comando explícito para humano colar em sessão nova. Preserva separação "skill é parteira one-shot, sai".

## Status canônicos disponíveis neste estágio

- `IN_PROGRESS` — coletando logs/feedback, escrevendo intake-report, ou aguardando escolha humana A/B/C. Também é o status final em saída B (no estágio X de retorno).
- `COMPLETED` — saída A (workspace fechado, lições appended) ou saída C (workspace fechado com `spawn_to` set).
- `BLOCKED_STOP_POINT` — raro; só dispara via stop point 11 `workspace_corrupt` se pré-condição falhar.
- `BLOCKED_ERROR` — `intake-report.md` não escreve (disco cheio, permissão), pre-commit hook rejeita, ou humano interrompe antes de decidir A/B/C (status fica `IN_PROGRESS` em `08_in_progress`; próxima sessão retoma).

## Stop points aplicáveis

`applicable_stop_points: []` — fase 08 NÃO dispara stop points por design. É análise + decisão direta A/B/C; não há trade-off arquitetural a escalar. Stops detectados durante o uso do output do workspace rolam para o próximo workspace via saída C (ou para o restart via saída B).

A única exceção é o stop point 11 `workspace_corrupt`, que pode aparecer no pre-flight se o estado do workspace está inconsistente — mas esse é tratado como erro de pré-condição, não como stop point regular do estágio.

## Skill superpowers de referência

Não há skill superpowers direta para a fase 08. O protocolo é literal e está em:

- `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/runtime/feedback-intake-fase08.md`

Esta é a cópia local (no workspace) da reference canônica `references/feedback-intake-fase08.md` da skill. Wave 4 da reescrita copia a reference para `_references/runtime/`.

## Gates

- **Humano:** dispara a fase 08 manualmente (nunca automático). Responde os 4 blocos de feedback inline. Escolhe A/B/C no menu (pode discordar da recomendação).
- **Automático (CI):** pre-commit hook valida atomicidade L1 ↔ outputs ↔ `docs/lessons.md` (em saída A). Pre-commit valida que `output-iteration-<N>/` (saída B) só é criado em commits com prefixo `intake:` ou `feedback:`.
- **Aprovação para transitar:** humano explicita escolha A/B/C; sub_stage transita conforme escolha no commit que registra a decisão. Saída A e C levam `status: COMPLETED`; saída B leva a fase X com `status: IN_PROGRESS` e `iteration: N+1`.
