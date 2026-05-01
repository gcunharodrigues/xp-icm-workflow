---
layer: L2
stage: "08"
stage_name: "feedback_intake"
sub_stage_enum:
  - "08_in_progress"
  - "08_decided_A"
  - "08_decided_B"
  - "08_decided_C"
applicable_stop_points:
  - "runtime_cleanup_failed"  # v3.7.0 — strict universal, todos tiers
output_files:
  - "output/intake-report.md"
next_stage: null
---

# Estágio 08 — feedback_intake (L2)

Gate de iteração universal do ciclo ICM. Workspace transita pra cá automaticamente após stage 07 e fica em `COMPLETED_AWAITING_HUMAN` aguardando humano voltar com feedback livre após uso real do projeto (semanas/meses sem prazo). Quando humano abre nova sessão e cola feedback livre (texto solto, sem menu), sessão **infere intenção** e mapeia pra uma das 3 saídas: A) close workspace + lições em `docs/lessons.md`, B) restart fase X (X ∈ 01..07) com `iteration++`, C) spawn novo workspace via humano colando comando em sessão nova. Sessão confirma a inferência com humano antes de executar (mini-menu s/n/ajusta). Coleta logs (se `logs_root` declarado), extrai 4 blocos do feedback livre, calcula top-N error patterns. NÃO faz código novo — apenas analisa, infere e transita estado. Protocolo literal em `_references/runtime/feedback-intake-fase08.md`.

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
| 11 | {{PROJECT_ROOT}}/.icm-main/docs/lessons.md | L3 | condicional: append apenas em saída A |
| 12 | {{LOGS_ROOT}} | L3 | condicional: opcional — sample dos últimos 30 dias se L0 declara `logs_root` ≠ null |
| 13 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/runtime/feedback-intake-fase08.md | L3 | sim (protocolo literal — cópia local da reference) |
| 14 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/08_feedback_intake/_kickoff.md | L4-kickoff | condicional: gerado pela sessão anterior. Ausente em workspaces beta1/beta2 (4B legacy) ou se for primeira sessão de stage. Em stage 08 normalmente AUSENTE — humano dispara manualmente após uso real, não há sessão anterior automática. |
| 15 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/runtime/session-handoff-protocol.md | L3 | condicional: necessário no handoff final do estágio (saída B gera kickoff) |
| 16 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/runtime/recovery-wizard.md | L3 | condicional: referenciado no pre-flight se workspace inconsistente |

**Nota sobre `{{LOGS_ROOT}}`:** placeholder resolvido pelo bootstrap a partir do campo `logs_root` do L0. Se `logs_root: null` (greenfield, texto, skill), bootstrap substitui por marcador inerte e o input é skipped no pre-flight. Se `logs_root` é path real, sessão samplea os últimos 30 dias.

## Não Lê (negative constraint)

- {{PROJECT_ROOT}}/.icm-main/src/, {{PROJECT_ROOT}}/.icm-main/tests/ — fase 08 não revisita código.
- Outros workspaces em {{PROJECT_ROOT}}/workspaces/<outro>/ — saída C (spawn) consulta CONTEXT.md de workspace antigo via `spawn_from`, mas isso é responsabilidade do NOVO workspace; o workspace atual não lê outros.
- {{PROJECT_ROOT}}/.icm-main/docs/decisions/ — ADRs não são editados na fase 08; herança em saída C é responsabilidade do novo workspace.

**v3.7.0:** `{{PROJECT_ROOT}}/.icm-main/docs/tech_debt.md` PODE ser **escrito** (append) em saídas A/B se feedback livre revela débito técnico durável (não-lição). Diferença lessons vs tech_debt: lição = aprendizado pra próximo workspace; débito técnico = item rastreável que precisa ser endereçado em código futuro. Ambos coexistem em saída A; B append apenas se feedback explicitamente cita débito.

## Runtime Cleanup Checklist (v3.7.0 — pré-Process obrigatório)

ANTES de qualquer step do Process, executar checklist runtime cleanup. Strict universal — todos tiers (`experimental` → `production`) passam pelo checklist sem opt-out.

**Comando:**

```bash
python {{SKILL_DIR}}/scripts/runtime-status.py \
    --workspace-root {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}} \
    --project-root {{PROJECT_ROOT}} \
    --format text
```

**6 categorias verificadas:**

| # | Categoria | Detecta |
|---|---|---|
| 1 | `dev_servers` | Entries kind=dev_server alive em runtime-registry |
| 2 | `background_tasks` | Entries kind=background_task alive |
| 3 | `docker` | Containers com label `icm-workspace={{WORKSPACE}}` |
| 4 | `wave_branches` | Git branches `wave-<workspace_num>-*` órfãs |
| 5 | `working_tree` | `git status --short` no project_root (workspace branch) |
| 6 | `untracked` | `.icm-main/` dirty (worktree base) |

**Comportamento por categoria detectada não-clean:**

```
✗ dev_servers: 1 dev server(s) alive: pid=12345

[s] resolvi (dev server matado / unregistered), retoma checklist
[n] cancela fase 08 (status volta COMPLETED_AWAITING_HUMAN)
[edit] descreva ajuste
```

**Fluxo:**

1. Sessão roda checklist completo (todas 6 categorias).
2. Pra cada categoria não-clean, sessão imprime confirm humano (per categoria, não 1 confirm global — strict universal).
3. Humano resolve (kill processo, deletar branch, etc.) e responde `[s]` pra retomar checklist.
4. Re-run checklist até **todas categorias clean**.
5. Falha persistente / cancelamento humano → stop point #13 `runtime_cleanup_failed`. Status `BLOCKED_STOP_POINT`.
6. Sucesso → prosseguir pra Process step 1.

**Output reportado em `output/intake-report.md`:** seção §"Runtime cleanup pré-saída (v3.7+)" com snapshot do checklist final + categorias resolvidas + warnings (se algum cleanup foi skipado via menu C com humano explícito).

Doc canônico: `_references/runtime/runtime-cleanup-protocol.md`.

## Process

1. **Pre-flight — pré-condição obrigatória:** L1 deve declarar `stage_atual: "08"` com `sub_stage: 08_in_progress` (transição automática vinda de stage 07) e `status: COMPLETED_AWAITING_HUMAN`. Se status ∈ {`IN_PROGRESS`, `BLOCKED_*`} → workspace inconsistente (recovery wizard). Se `stage_atual ≠ 08` → recusar com "workspace ainda não chegou em 08 (termine 07 primeiro)". Se status indefinido → stop point 11 `workspace_corrupt`.

   **Step 0 (v3.7.0 — strict universal):** rodar Runtime Cleanup Checklist (§acima) ANTES de step 1. Bloqueia transição se alguma categoria não-clean e humano não confirmou cleanup. Status pode disparar stop point #13 `runtime_cleanup_failed` se humano cancela.
2. **Setar `status: IN_PROGRESS`** no L1 (sai de `COMPLETED_AWAITING_HUMAN` enquanto sessão trabalha). Append `history` evento `feedback_session_started`.
3. **Coleta de logs** (somente se `logs_root` ≠ null em L0): sampleia últimos 30 dias de `{{LOGS_ROOT}}`. Se path inacessível/vazio, anota "logs vazios/inacessíveis" e segue.
4. **Receber feedback livre do humano:** humano cola feedback como texto solto (não menu, não 4 blocos guiados). Sessão valida ≥1 frase substantiva. Em silêncio prolongado / mensagem vazia explicíta tipo "tudo certo, encerra" → considera intenção A close.
5. **Inferência de intenção (sessão decide A/B/C autonomamente):** aplicar heurísticas abaixo. Se múltiplas categorias matcham, prioridade: B > C > A (correção pontual ganha de pivô; pivô ganha de close). Se ambíguo, sessão pergunta clarificação curta antes de prosseguir.

   | Sinal no feedback livre | Saída inferida | Detalhamento |
   |---|---|---|
   | "bug em X", "quebra", "erro", "não funciona", "regressão", "fail", "crashou" | **B** restart | Mapeia stage do bug: testes/CI → 05, código → 04, design errado → 02, requisitos errados → 01, review missou → 06, merge → 07 |
   | "tudo ok", "funcionando", "encerrar", "fechar projeto", "concluído", "sem feedback", silêncio | **A** close | Workspace arquivado + lições |
   | "novo projeto", "pivotar", "mudar direção", "feature grande nova", "outro workspace", "começar do zero com X aprendido" | **C** spawn | Workspace fecha + spawn instruction |
   | "extensão pequena", "iterar mais", "voltar a fase Y", explícita menção a stage por número/nome | **B** com X explícito | Stage extraído da menção |
   | Mistura "bug + feature nova" | preferir **B** primeiro (corrige bug); user pode disparar 08 de novo depois pra C | |

6. **Mini-confirm com humano** (1 menu único, sem A/B/C cru):
   ```
   Entendi: <saída inferida em prosa>
   Ex: "restart fase 02 design pra revisar contrato API"
   Ex: "spawn workspace novo pra feature billing"
   Ex: "close workspace, tudo ok"

   [s] confirma   [n] cancela e pergunta de novo   [edit] descreva o que ajusta
   ```
7. **Análise top-N error patterns:** agrupa logs + feedback em ≤5 padrões com `frequencia`, `impacto` (low/medium/high/critical) e `evidencia`. Aceita 0-2 padrões se logs vazios e feedback curto.
8. **Extrair 4 blocos do feedback livre** (parsing pra audit, não pergunta inline): O QUE FUNCIONOU / O QUE NÃO FUNCIONOU / QUAL DOR PERSISTE / QUE LIÇÃO TIRAR. Aceita blocos vazios (não força preenchimento).
9. **Escrever `output/intake-report.md`** com seções fixas: Logs sample, Feedback livre (literal), 4 blocos extraídos, Top-N patterns (tabela), Inferência (saída + heurística disparada + confiança), Decisão final (após mini-confirm).
10. **Executar saída confirmada** conforme seções "Saída A/B/C" abaixo.
11. **Commit atômico** (pre-commit hook valida atomicidade L1 ↔ outputs ↔ lessons; prefixo `intake:` ou `feedback:`).

## Outputs

- `output/intake-report.md` — relatório de intake: logs sample (ou n/a), feedback livre (literal), 4 blocos extraídos, top-N error patterns (tabela), inferência (heurística disparada + confiança), decisão final pós-confirm humano.

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
- `BLOCKED_ERROR` — `workspace_corrupt` detectado no pre-flight, `intake-report.md` não escreve (disco cheio, permissão), pre-commit hook rejeita, ou humano interrompe antes de decidir A/B/C (status fica `IN_PROGRESS` em `08_in_progress`; próxima sessão retoma).

## Stop points aplicáveis

`applicable_stop_points: []` — fase 08 NÃO dispara stop points por design. É análise + inferência + decisão direta A/B/C; não há trade-off arquitetural a escalar. Stops detectados durante o uso do output do workspace rolam para o próximo workspace via saída C (ou para o restart via saída B).

A única exceção é o stop point 11 `workspace_corrupt`, que pode aparecer no pre-flight se o estado do workspace está inconsistente — mas esse é tratado como erro de pré-condição, não como stop point regular do estágio.

## Inferência de intenção (heurísticas canônicas)

Mapping detalhado feedback livre → saída A/B/C. Ordem de prioridade quando múltiplos matches: **B > C > A**.

### Saída B (restart fase X) — sinais

- Palavras-chave: "bug", "quebra", "erro", "fail", "regressão", "crashou", "não funciona", "errado", "missed", "passou batido"
- Frases: "preciso corrigir X", "voltar a Y", "refazer Z"
- Menção explícita de stage/fase por número (`fase 02`, `stage 4`) ou nome (`design`, `review`, `verification`, etc.)

**Mapping bug → stage X:**

| Tipo de bug | X inferido |
|---|---|
| Falha em testes / CI / regressão automatizada | 05 verification |
| Bug em runtime / código quebrado / lógica errada | 04 implementation_waves |
| Code smell, design ruim que passou no review, dimensão 7-fold faltou | 06 review |
| Plano errado / arquitetura inadequada / ADR equivocado | 02 design |
| Wave plan errada / DAG ruim / dependências mal mapeadas | 03 wave_planner |
| Requisitos faltando / discovery superficial / faltou pergunta | 01 discovery |
| Merge com problema / push em branch errada / tag errada | 07 merge |
| Reconhecimento incompleto (raro — geralmente prefere C) | NÃO permite restart de 00; se intenção é mudar tipo/project_root, vira C |

### Saída C (spawn novo workspace) — sinais

- Palavras-chave: "pivotar", "mudar direção", "novo projeto", "outro workspace", "feature grande nova", "começar do zero", "este aprendizado vai pra outro"
- Frases: "esse projeto serviu pra X mas agora preciso Y diferente", "evolução para fora do escopo"
- Mudança de profile/tier/project_root → sempre C

### Saída A (close) — sinais

- Palavras-chave: "tudo ok", "funcionando", "encerrar", "fechar", "concluído", "sem feedback", "nada a relatar"
- Silêncio do humano após pergunta direta
- Mensagem curta neutra tipo "ok"

### Confidence score

Sessão computa `confidence` (0.0-1.0) baseado em:
- Quantidade de sinais matchados (mais sinais → maior confiança)
- Especificidade (`fase 02` > `tem bug`)
- Univocidade (sem mistura de categorias)

Se `confidence < 0.6`, sessão pergunta clarificação curta. Se `≥ 0.6`, segue pra mini-confirm.

### Mini-confirm template

```
Entendi: <saída inferida em prosa, 1-2 frases>

Exemplos:
  - "Restart fase 02 design pra revisar contrato API (bug em endpoints)"
  - "Spawn workspace novo pra feature billing (escopo fora do atual)"
  - "Close workspace — tudo ok, lições registradas"

[s] confirma e executa
[n] cancela, pergunta de novo
[edit] descreva o ajuste (ex: "na verdade restart fase 03, não 02")
```

## Skill superpowers de referência

Não há skill superpowers direta para a fase 08. O protocolo é literal e está em:

- `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/runtime/feedback-intake-fase08.md`

Esta é a cópia local (no workspace) da reference canônica `references/feedback-intake-fase08.md` da skill. Wave 4 da reescrita copia a reference para `_references/runtime/`.

## Gates

- **Humano:** dispara a fase 08 manualmente (nunca automático). Responde os 4 blocos de feedback inline. Escolhe A/B/C no menu (pode discordar da recomendação).
- **Automático (CI):** pre-commit hook valida atomicidade L1 ↔ outputs ↔ `docs/lessons.md` (em saída A). Pre-commit valida que `output-iteration-<N>/` (saída B) só é criado em commits com prefixo `intake:` ou `feedback:`.
- **Aprovação para transitar:** humano explicita escolha A/B/C; sub_stage transita conforme escolha no commit que registra a decisão. Saída A e C levam `status: COMPLETED`; saída B leva a fase X com `status: IN_PROGRESS` e `iteration: N+1`.

## End of stage handoff (1-stage-1-sessão)

**Stage 08 saídas (Q12 do plan):**

- **A — Close:** workspace `COMPLETED`. Sessão sai SEM gerar kickoff.
- **B — Restart phase X:** L1 `iteration++`, `stage_atual=X`, `sub_stage=X_in_progress`. GERAR kickoff em `stages/<X>_<name>/_kickoff.md` herdando outputs anteriores em `prev_outputs` + history append. Imprime KICKOFF verbal pra próxima sessão.
- **C — Spawn novo workspace:** NÃO gera kickoff (workspace novo é outro). Imprime instrução pro user invocar `/xp-icm-workflow` novo (skill nova faz bootstrap herdando lessons+ADRs do parent via `--spawn-from <NNN>`).

Detalhamento por saída:

### Saída A — Close

1. **Atualizar L1**:
   - `sub_stage = 08_decided_A`
   - `status = COMPLETED`
   - `last_transition.from = 08_in_progress`
   - `last_transition.to = 08_decided_A`
   - `last_transition.at = <ISO 8601 UTC now>`
   - `history` append: `{at, event: "stage_transition", from, to, commit_sha, note: "saida A close"}`
2. Append lições novas (de "QUE LIÇÃO TIRAR") em `{{PROJECT_ROOT}}/.icm-main/docs/lessons.md` respeitando frontmatter strict.
3. **(v3.7.0) Append tech debt durante intake — opcional:** se feedback livre revela débito técnico durável (não-lição), append em `{{PROJECT_ROOT}}/.icm-main/docs/tech_debt.md` respeitando frontmatter strict. Diferença: **lição** = aprendizado meta para próximo workspace; **tech debt** = item rastreável que precisa endereçar em código futuro (ex: "refator do módulo X adiado", "validação Y temporariamente flexível"). Se feedback não cita débito explícito, skip step (lessons-only).
4. Commit atômico (pre-commit valida atomicidade L1↔outputs↔lessons; commit-msg prefix `intake:` ou `feedback:`). Tech debt append (se houve) deve commitar via `cd .icm-main && git commit ...` (workflow ADR-style — ver L0 R6):
   ```
   intake: workspace <NNN> close (saida A) + lessons + tech_debt append
   ```
5. Print pro user: `✅ Workspace <NNN-slug> CLOSED (saída A). Lições registradas em docs/lessons.md.` (+ "Tech debt registrado em docs/tech_debt.md." se step 3 executou).
6. **CLAUDE.md root:** rodar `python {{SKILL_DIR}}/scripts/handoff.py remove-block --project-root {{PROJECT_ROOT}} --workspace {{WORKSPACE}} --skill-dir {{SKILL_DIR}} --closed-at <ISO> --outcome A`.
7. **NÃO gerar `_kickoff.md`.** SAIR da sessão.

### Saída B — Restart phase X

1. Validar `X ∈ {01, 02, 03, 04, 05, 06, 07}` (recusar `00` e `08`).
2. Mover outputs antigos: `stages/<XX>/output/` → `stages/<XX>/output-iteration-<N>/` (N = iteration ANTES do incremento).
3. **Atualizar L1**:
   - `iteration = N+1`
   - `stage_atual = <XX>`
   - `sub_stage = <XX>_in_progress` (ou `04_wave_1_in_progress` se X=04)
   - `status = IN_PROGRESS`
   - `last_transition.from = 08_in_progress`
   - `last_transition.to = <XX>_in_progress`
   - `last_transition.at = <ISO 8601 UTC now>`
   - `history` append: `{at, event: "iteration_increment", from: "08_in_progress", to: "<XX>_in_progress", commit_sha, note: "saida B restart fase X"}`
4. **Renderizar `_kickoff.md`** em `<workspace>/stages/<XX>_<name>/_kickoff.md`:
   - `prev_outputs` herda do `intake-report.md` (sumário das lições + 4 blocos de feedback)
   - `pending_for_this_stage`: pontos do feedback que motivaram o restart
   - Use `python {{SKILL_DIR}}/scripts/handoff.py render`
5. Commit atômico (prefix `intake:` ou `feedback:`):
   ```
   intake: workspace <NNN> restart fase <XX> (saida B, iteration <N+1>) + kickoff
   ```
   Files no commit: `intake-report.md` + L1 + outputs movidos pra `output-iteration-<N>/` + `_kickoff.md` do stage X.
6. **Imprimir KICKOFF block verbal** pro user (copy-paste):

   ```
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   🔁 Stage 08 SAÍDA B — restart fase <XX> — workspace <NNN-slug>

   Workspace atualizado em commit <sha>:
     - L1: stage_atual=<XX>, sub_stage=<XX>_in_progress, iteration=<N+1>
     - Outputs antigos movidos: stages/<XX>/output-iteration-<N>/
     - Kickoff: stages/<XX>_<name>/_kickoff.md gerado

   🔄 KICKOFF próxima sessão — copy/paste:
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Continuar workspace <NNN-slug> no estágio <XX> (<name>) — iteração <N+1>.

   Read order:
     workspaces/<NNN-slug>/CLAUDE.md
     workspaces/<NNN-slug>/CONTEXT.md
     workspaces/<NNN-slug>/stages/<XX>_<name>/CONTEXT.md
     workspaces/<NNN-slug>/stages/<XX>_<name>/_kickoff.md
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

   Encerre esta sessão (Ctrl+D ou /exit) e abra nova sessão Claude
   no project_root, depois cole o prompt acima.
   ```
7. SAIR da sessão.

### Saída C — Spawn novo workspace

1. **Atualizar L1**:
   - `sub_stage = 08_decided_C`
   - `status = COMPLETED`
   - `spawn_to = <slug-novo-workspace>`
   - `last_transition.from = 08_in_progress`
   - `last_transition.to = 08_decided_C`
   - `last_transition.at = <ISO 8601 UTC now>`
   - `history` append: `{at, event: "stage_transition", from, to, commit_sha, note: "saida C spawn"}`
2. Commit atômico:
   ```
   intake: workspace <NNN> close + spawn <slug-novo> (saida C)
   ```
3. **(v3.7.0) Renderizar `.icm/spawn-pending.json`** em `{{PROJECT_ROOT}}/.icm/spawn-pending.json` (gitignored). Schema:
   ```json
   {
     "spawn_from": "{{WORKSPACE}}",
     "intake_report_path": "workspaces/{{WORKSPACE}}/stages/08_feedback_intake/output/intake-report.md",
     "intake_report_branch": "workspace/{{WORKSPACE}}",
     "proposed_workspace_name": "<slug-novo-workspace>",
     "proposed_profile": "<profile sugerido baseado escopo>",
     "proposed_tier": "<tier sugerido>",
     "intake_commit_sha": "<sha do commit step 2>",
     "agent_brief": {
       "por_que_spawn": "...",
       "escopo_motivador": "...",
       "heranca_aplicavel": "...",
       "nao_quero": "...",
       "notes_livre": ""
     },
     "created_at": "<ISO 8601>"
   }
   ```
   `agent_brief` consumível pelo recon-report do workspace novo (stage 00 lê + cita herança). Bootstrap próxima sessão auto-detecta arquivo (`bootstrap.detect_spawn_pending`), propõe valores, unlinka pós-sucesso.
4. **NÃO gerar `_kickoff.md`** (workspace novo é outro; bootstrap acontece em sessão separada).
5. **CLAUDE.md root:** `python {{SKILL_DIR}}/scripts/handoff.py remove-block --project-root {{PROJECT_ROOT}} --workspace {{WORKSPACE}} --skill-dir {{SKILL_DIR}} --closed-at <ISO> --outcome C --spawn-to <slug-novo>`.
6. Print pro user — instrução explícita pra próxima sessão:

   ```
   ✅ Workspace <NNN-slug> CLOSED + SPAWN registrado (saída C).

   Próximo passo (humano, sessão nova):

     /xp-icm-workflow project-root={{PROJECT_ROOT}}

   Bootstrap auto-detecta .icm/spawn-pending.json e propõe:
     - profile=<profile sugerido>
     - tier=<tier sugerido>
     - workspace-name=<slug-novo>
     - spawn_from={{WORKSPACE}}

   Você confirma ou ajusta no menu interativo.
   (Fallback explícito: --spawn-from={{WORKSPACE}} arg sobre arquivo.)
   ```
7. SAIR da sessão.

Detalhes em `<skill_root>/references/session-handoff-protocol.md`.

---

## v3.3.0 references aplicáveis a este stage

- **Triage state machine (`_references/runtime/triage-state-machine.md`):**
  ANTES da inferência A/B/C, classificar feedback em (category, state):
  - bug → Saída B (restart fase X)
  - enhancement aceito → Saída C (spawn novo workspace)
  - enhancement rejeitado → wontfix → append em `_out-of-scope/` + Saída A
  - tudo OK → Saída A
  Cada item B/C produz AGENT-BRIEF (formato:
  `_references/runtime/agent-brief-template.md`).

- **OUT-OF-SCOPE wontfix (`_references/runtime/out-of-scope-kb.md`):**
  enhancement rejeitada → criar/atualizar `<workspace>/_out-of-scope/<conceito-kebab>.md`
  com decision + reason durável + prior requests.

- **CLAUDE.md root atualização:**
  - **Saída A:** `python {{SKILL_DIR}}/scripts/handoff.py remove-block --project-root {{PROJECT_ROOT}} --workspace {{WORKSPACE}} --skill-dir {{SKILL_DIR}} --closed-at <ISO8601>`. Se era o último ativo, ativa região idle automaticamente.
  - **Saída B:** `python {{SKILL_DIR}}/scripts/handoff.py update-project-md --project-root {{PROJECT_ROOT}} --workspace {{WORKSPACE}} --profile {{PROFILE}} --tier {{TIER}} --stage-atual <X> --stage-dir <X_name> --sub-stage <X>_in_progress --iteration <N+1> --status IN_PROGRESS --skill-dir {{SKILL_DIR}}`.
  - **Saída C:** `remove-block` (workspace dono vira COMPLETED). Bootstrap em sessão B adiciona bloco do novo workspace.
