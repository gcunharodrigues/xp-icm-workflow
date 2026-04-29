---
layer: L2
stage: "04"
stage_name: "implementation_waves"
sub_stage_enum:
  - "04_wave_<N>_in_progress"
  - "04_wave_<N>_completed"
sub_stage_pattern: "^04_wave_\\d+_(in_progress|completed)$"
applicable_stop_points:
  - "new_dep"
  - "irreversible"
  - "over_eng"
  - "prod_migration"
  - "adr_drift"
output_files:
  - "output/wave-<N>/task-<slug>.md"
  - "output/wave-<N>/wave-summary.md"
  - "output/wave-<N>/task-<slug>-blocked.md"
next_stage: "05"
---

# Estágio 04 — implementation_waves (L2)

Execução paralela em waves. Lead session orquestra subagentes via Agent tool respeitando o cap por tier (2/3/5/5). Cada subagente trabalha numa task em branch isolada `wave-{{WORKSPACE}}-<N>/<task-slug>` (a partir de `{{BASE_BRANCH}}`), segue o ciclo TDD 7 passos, valida via auto-QA Akita 15-itens. Subagentes comunicam resultados diretamente ao lead via Agent tool output. Wave-reviewer audita ao fim. Lead faz merge sequencial em `{{BASE_BRANCH}}`. Uma sub_stage por wave: `04_wave_<N>_in_progress` → `04_wave_<N>_completed`. Repete até esgotar `wave-plan.md`.

## Inputs (lê SOMENTE estes, na ordem)

| # | Path | Layer | Obrigatório? |
|---|------|-------|--------------|
| 1 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/CLAUDE.md | L0 | sim |
| 2 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/CONTEXT.md | L1 | sim |
| 3 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/04_implementation_waves/CONTEXT.md | L2 | sim |
| 4 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/03_wave_planner/output/wave-plan.md | L4 | sim |
| 5 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/02_design/output/plan.md | L4 | sim |
| 6 | {{PROJECT_ROOT}}/.icm-main/docs/decisions/ | L3 | condicional: ler SOMENTE ADRs listados em "ADRs aplicáveis" da task no plan.md |
| 7 | {{PROJECT_ROOT}}/.icm-main/docs/lessons.md | L3 | condicional: lessons-match.py pré-extrai lições relevantes; lead injeta via canal 2 |
| 8 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/superpowers-summary/test-driven-development-200tok.md | L3 | sim |
| 9 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/superpowers-summary/subagent-driven-development-200tok.md | L3 | sim |
| 10 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/runtime/4-block-contract-template.md | L3 | sim |
| 11 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_config/xp-conventions.md | L3 | sim |
| 12 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_config/stop-points.md | L3 | sim |
| 13 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/runtime/subagent-protocol.md | L3 | sim |
| 14 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/04_implementation_waves/_kickoff.md | L4-kickoff | condicional: gerado pela sessão anterior. Ausente em workspaces beta1/beta2 (4B legacy) ou se for primeira sessão de stage. |
| 15 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/runtime/session-handoff-protocol.md | L3 | condicional: necessário no handoff final do estágio |
| 16 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/runtime/stop-points-canonical.md | L3 | condicional: catálogo canônico de IDs, complementar ao _config/stop-points.md de thresholds |

## Não Lê (negative constraint)

- {{PROJECT_ROOT}}/workspaces/ (outros workspaces — isolamento por workspace)
- ADRs em {{PROJECT_ROOT}}/.icm-main/docs/decisions/ NÃO listados em "ADRs aplicáveis" da task corrente
- Outputs de outros estágios do mesmo workspace (00, 01, 05+) — apenas plan.md (02) e wave-plan.md (03)
- {{PROJECT_ROOT}}/.icm-main/docs/tech_debt.md diretamente — entra via canal 2 do lead se aplicável

## Process

Cada wave executa o pipeline abaixo. `<N>` = número da wave atual.

1. **Lead pre-flight:** lê wave-plan.md; identifica wave atual via L1 `waves.current`. Sub_stage transita para `04_wave_<N>_in_progress`.
2. **Lead spawn subagentes via Agent tool:** para cada task da wave (até cap), cria branch `wave-{{WORKSPACE}}-<N>/<task-slug>` a partir de `{{BASE_BRANCH}}` e invoca subagente via Agent tool com o contexto da task.
3. **Lead injeta canal 2:** injeta no prompt do subagente apenas o subset de ADRs + lições críticas + conventions extras declarados no plan.md daquela task. Subagente NÃO lê o `docs/` global do projeto.
4. **Subagente (CWD = project root, branch `wave-{{WORKSPACE}}-<N>/<task-slug>`):** executa ciclo TDD 7 passos do `4-block-contract-template.md`:
   1. RED — test que falha cobre VALIDAÇÃO da task.
   2. GREEN — implementação mínima.
   3. CI gate local 1ª — lint + type + tests verde.
   4. REFACTOR — limpa mantendo tests verde.
   5. CI gate local 2ª — garante refactor não quebrou.
   6. Auto-QA Akita 15-itens — `❌` força volta ao passo 4 ou 3 (cap 3 voltas).
   7. COMPLETE — escreve `output/wave-<N>/task-<slug>.md` com auto-QA registrado.
5. **Stop points dentro do ciclo:** se subagente detecta `new_dep`, `irreversible`, `over_eng`, `prod_migration` ou `adr_drift` → pausa estado atual, escreve menu A/B/C, retorna sinalização ao lead via Agent tool output, lead seta L1 `status: BLOCKED_STOP_POINT`. Humano responde, ciclo retoma do passo onde parou.
6. **Cap 3 voltas auto-QA:** subagente marca `status: BLOCKED_ERROR` no task-report e retorna ao lead via Agent tool; lead decide reduzir wave (ver subagent-protocol) ou escalar humano.
7. **Lead recebe resultado de cada subagente via Agent tool:** lead aguarda retorno COMPLETE de cada subagente da wave. Resultados chegam diretamente pelo Agent tool output — sem polling de diretório.
8. **Wave-reviewer:** subagente revisa Auto-QA Akita de cada task report + verifica que `Files touched` reais batem com declarado no plan.md.
9. **Merge sequencial:** lead faz merge de cada branch `wave-{{WORKSPACE}}-<N>/<task-slug>` em `{{BASE_BRANCH}}` na ordem do plan. Conflict de merge → `BLOCKED_ERROR`, humano resolve manualmente.
10. **CI gate global:** roda CI completo do projeto após todos os merges. Verde → wave concluída.
11. **Cleanup wave worktrees + branches (v3.4.3):** após merge bem-sucedido + CI verde, lead remove worktrees efêmeras criadas pelos subagentes E deleta branches já merged. Bug pre-v3.4.3: worktrees em `<project_root>/.icm-wave-*` (ou path retornado pelo Agent tool) ficavam orfãs após cada wave; branches `wave-<NNN>-<N>/<task-slug>` poluíam `git branch` listing.

   ```bash
   # Para cada task da wave (paths capturados dos Agent tool results):
   git worktree remove <path-do-worktree>           # remove worktree efemera
   git branch -d wave-{{WORKSPACE_NUM}}-<N>/<task-slug>   # safe: ja merged --no-ff

   # Fallback robusto (se path foi perdido — busca por pattern de branch):
   git worktree list --porcelain | awk '/^worktree /{p=$2} /^branch refs\/heads\/wave-{{WORKSPACE_NUM}}-<N>/{print p}' \
     | xargs -I {} git worktree remove {}
   ```

   Falha não-fatal: registrar warning em `wave-summary.md` (próximo passo). `git worktree remove` falha se working tree não-limpo → tentar `--force` apenas se Auto-QA Akita já passou (subagente garantiu commit limpo). `git branch -d` recusa se não-merged → não usar `-D` (forçar delete mascararia bugs do merge anterior).

12. **Lead escreve:** `output/wave-<N>/wave-summary.md` (tasks completadas, conflicts, decisões tomadas, **warnings de cleanup** se houve).
13. **Handoff de fim de wave/stage:** seguir protocolo na seção `## End of stage handoff` deste L2. Mid-wave (wave <N> → <N+1>): handoff automático sem gate humano (Caso A). Última wave → stage 05: gate-inline obrigatório (Caso B — Fase 1 WORK_DONE → gate humano → Fase 2 GATE_APPROVED).

CWD: lead em `{{PROJECT_ROOT}}` (workspace branch). Subagente em `{{PROJECT_ROOT}}` na branch `wave-{{WORKSPACE_NUM}}-<N>/<task-slug>`.

## Outputs

- `output/wave-<N>/task-<slug>.md` — task report do subagente (resumo, Auto-QA Akita 15-itens, ciclos consumidos).
- `output/wave-<N>/wave-summary.md` — síntese do lead pós wave-reviewer + merge.
- `output/wave-<N>/task-<slug>-blocked.md` — opcional, criado quando subagente dispara stop point ou estoura cap de 3 voltas.

## Sub_stage transitions

Enum válido: `04_wave_<N>_in_progress`, `04_wave_<N>_completed` (`<N>` inteiro positivo). Pattern: `^04_wave_\d+_(in_progress|completed)$`.

Transição `04_wave_<N>_in_progress` → `04_wave_<N>_completed` dispara quando:
- Todos os subagentes da wave entregaram `task-<slug>.md` COMPLETE.
- Wave-reviewer aprovou.
- Merge sequencial verde + CI global verde.
- `wave-summary.md` escrito.

Transição `04_wave_<N>_completed` → `04_wave_<N+1>_in_progress` (se houver mais waves) é interna ao estágio. Última wave → `next_stage: 05`.

## Status canônicos disponíveis neste estágio

- `IN_PROGRESS` — wave em execução (lead orquestrando, subagentes trabalhando).
- `COMPLETED_AWAITING_HUMAN` — última wave concluída, aguardando humano aprovar transição para 05.
- `BLOCKED_STOP_POINT` — subagente disparou menu A/B/C; humano responde.
- `BLOCKED_ERROR` — merge conflict, CI global vermelho, ou cap 3 voltas auto-QA estourado em alguma task.

## Stop points aplicáveis

Catálogo canônico em `references/stop-points-canonical.md`. IDs disparáveis em fase 04:

- `new_dep` — npm/pip/cargo nova adicionada durante implementação que não estava no plan.md.
- `irreversible` — `DROP TABLE`, `git push --force`, hard-delete sem soft-delete prévio.
- `over_eng` — 3+ camadas de abstração novas sem requisito (calibrado: warning experimental/tool, hard development/production).
- `prod_migration` — migration toca tabela com volume produção sem janela acordada.
- `adr_drift` — implementação diverge de ADR vigente sem superseding declarado.

## Skill superpowers de referência

Sumário TDD: `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/superpowers-summary/test-driven-development-200tok.md`

Sumário subagent: `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/superpowers-summary/subagent-driven-development-200tok.md`

Skill formal: `superpowers:test-driven-development` + `superpowers:subagent-driven-development` (escape hatch).

## Gates

- **Humano:** aprova transição da última wave para estágio 05; responde menu A/B/C de stop points; resolve conflict de merge quando ocorre.
- **Automático (CI):** commit-msg hook valida prefixo `workspace {{WORKSPACE_NUM}}:` em branch workspace (R6); wave branches e base branch usam Conventional Commits (`feat:`, `fix:`, etc.) sem validação de hook; CI global roda após merge de cada wave; auto-QA Akita validado por wave-reviewer.
- **Aprovação para transitar:** wave fecha automaticamente quando merge + CI global verde + wave-summary escrito. Última wave precisa de aprovação humana explícita para transitar para estágio 05.

## End of stage handoff (gate inline + 1-stage-1-sessão, wave-aware)

**Stage 04 exception (wave-aware):** cada wave = 1 sessão lead. Lead encerra wave gerando kickoff para próxima wave (mesmo stage 04, sub_stage `04_wave_<N+1>_in_progress`) OU para stage 05 (após última wave). Sub-waves (subdivisões dentro de uma wave) NÃO disparam kickoff — lead persiste através das sub-waves dentro da mesma sessão.

### Caso A: handoff mid-wave (wave <N> → wave <N+1>) — SEM gate humano

Mid-wave handoff é automático (sem gate) quando merge + CI global verde + wave-summary escrito. Bug v3.4.2 não afeta este caminho — wave intermediária não tem gate humano por design (gate só na transição para 05).

1. **Atualizar L1**:
   - `sub_stage = 04_wave_<N+1>_in_progress` (transição imediata, sem persistir `04_wave_<N>_completed` em status)
   - `status = IN_PROGRESS`
   - `last_transition.from = 04_wave_<N>_in_progress`
   - `last_transition.to = 04_wave_<N+1>_in_progress`
   - `history` append: 2 eventos (`wave_completed` + `stage_transition`)

2. **Renderizar `_kickoff.md`** em `<workspace>/stages/04_implementation_waves/_kickoff.md` (overwrite — `wave_target` no corpo aponta wave <N+1>).

3. **Commit atômico** (outputs + L1 + kickoff):
   ```
   workspace <NNN>: wave <N> completa + kickoff wave <N+1>
   ```

4. **Imprimir KICKOFF block verbal** pro user (copy-paste). SAIR da sessão.

### Caso B: handoff última wave → stage 05 — COM gate humano (gate inline)

Após última wave concluída, gate humano é OBRIGATÓRIO antes de transitar pra 05. Bug v3.4.2 corrigido aqui: render+exit prematuros antes da aprovação criavam loop "kickoff → user aprova em sessão nova → kickoff de novo". Doc canônico: `<skill_root>/references/session-handoff-protocol.md`.

#### Fase 1: WORK_DONE (após última wave merged + CI global verde)

1. **Atualizar L1**:
   - `sub_stage = 04_wave_<N>_completed` (N = última wave)
   - `status = COMPLETED_AWAITING_HUMAN`
   - `last_transition.from = 04_wave_<N>_in_progress`
   - `last_transition.to = 04_wave_<N>_completed`
   - `last_transition.at = <ISO 8601 UTC now>`
   - `history` append: `{event: "wave_completed", note: "última wave, awaiting gate"}`

2. **Commit atômico 1/2** (outputs da wave + L1; **NÃO** inclui `_kickoff.md`):
   ```
   workspace <NNN>: stage 04 work done (última wave), awaiting gate
   ```

3. **Imprimir prompt de gate** pro humano. NÃO sair. NÃO renderizar `_kickoff.md`:

   ```
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   ✅ Stage 04 (implementation_waves) trabalho COMPLETO — workspace <NNN-slug>
   Última wave (<N>) merged + CI global verde.

   Outputs prontos pra revisão:
     - <task reports + wave-summary>

   L1: sub_stage=04_wave_<N>_completed, status=COMPLETED_AWAITING_HUMAN
   Commit 1/2: <sha>

   🛑 Gate humano: revise wave-summary + task reports.
   Responda no chat:
     - "aprovado" / "ok prosseguir 05" → renderizo kickoff e saio
     - "ajustar X" → volto ao trabalho com seu pedido (status=IN_PROGRESS)
     - "abort" → marco workspace BLOCKED_ERROR
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   ```

4. **AGUARDAR resposta humana** na MESMA sessão.

#### Fase 2: GATE_APPROVED (após humano responder "aprovado")

5. **Atualizar L1** (segunda transição):
   - `stage_atual = 05`
   - `sub_stage = 05_in_progress`
   - `status = IN_PROGRESS`
   - `last_transition.from = 04_wave_<N>_completed`
   - `last_transition.to = 05_in_progress`
   - `last_transition.at = <ISO 8601 UTC now>`
   - `history` append: `{event: "stage_transition", from: "04_wave_<N>_completed", to: "05_in_progress", note: "gate approved by human"}`

6. **Renderizar `_kickoff.md`** em `<workspace>/stages/05_verification/_kickoff.md`.

7. **Commit atômico 2/2** (kickoff + L1):
   ```
   workspace <NNN>: gate aprovado, kickoff stage 05
   ```

8. **Imprimir KICKOFF block verbal** pro user (copy-paste pra próxima sessão):

   ```
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   ✅ Stage 04 (implementation_waves) GATE APROVADO — workspace <NNN-slug>

   Workspace atualizado em commit <sha>:
     - L1: stage_atual=05, sub_stage=05_in_progress, status=IN_PROGRESS
     - Kickoff: stages/05_verification/_kickoff.md gerado

   🔄 KICKOFF próxima sessão — copy/paste:
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Continuar workspace <NNN-slug> no estágio 05 (verification).

   Read order:
     workspaces/<NNN-slug>/CLAUDE.md
     workspaces/<NNN-slug>/CONTEXT.md
     workspaces/<NNN-slug>/stages/05_verification/CONTEXT.md
     workspaces/<NNN-slug>/stages/05_verification/_kickoff.md
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

   Encerre esta sessão (Ctrl+D ou /exit) e abra nova sessão Claude
   no project_root, depois cole o prompt acima.
   ```

9. **SAIR** da sessão.

#### Resposta "ajustar X" (gate rejeitado)

- Atualizar L1: `status = IN_PROGRESS`, append history `{event: "gate_rejected"}`. Sub_stage permanece `04_wave_<N>_completed`.
- Voltar ao trabalho conforme pedido. Pode envolver re-spawn de subagentes ou correção direta.
- Quando refizer outputs, voltar à Fase 1.

#### Resposta "abort"

- Atualizar L1: `status = BLOCKED_ERROR`, append history `{event: "blocked_error", error_type: "human_abort"}`. Commit + sair.

---

## v3.3.0 references aplicáveis a este stage

- **AGENT-BRIEF (`_references/runtime/agent-brief-template.md` +
  `<skill_root>/scripts/agent-brief-render.py`):** lead session gera brief
  estruturado por task ANTES de spawnar Agent tool. CLI:

  ```bash
  python {{SKILL_DIR}}/scripts/agent-brief-render.py \
      --task <slug> \
      --plan stages/02_design/output/plan.md \
      --adrs {{PROJECT_ROOT}}/.icm-main/docs/decisions
  ```

  Output (markdown) é injetado no prompt do Agent tool. Anti-patterns
  (paths absolutos, line numbers) gerados warnings.

- **Subagent worktree (v3.4.0):** lead spawna subagentes via
  `Agent(isolation: "worktree")` para wave branches `wave-{{WORKSPACE_NUM}}-<N>/<task-slug>`
  derivadas de `{{BASE_BRANCH}}`. Tool cria worktree efêmera; subagente
  trabalha nela isolado da worktree principal (que continua em
  `workspace/{{WORKSPACE}}`). Lead permanece no `{{PROJECT_ROOT}}/`
  workspace branch durante toda a wave. Após subagente terminar, lead
  inspeciona resultado do worktree retornado e merge a wave branch em
  `{{BASE_BRANCH}}` conforme protocol da fase 04. Após merge:
  `cd {{PROJECT_ROOT}}/.icm-main && git pull --ff-only` para sincronizar
  worktree linkada com novo HEAD da base.

- **HITL handling:** se wave é `Type: HITL`, lead session NÃO spawna
  subagent. Gera AGENT-BRIEF, exibe ao humano, atualiza L1 para
  `status=COMPLETED_AWAITING_HUMAN, sub_stage=04_wave_N_hitl_pending`,
  SAIR. Próxima sessão (após humano resolver) retoma wave seguinte.

- **Diagnose protocol nota (`_references/runtime/diagnose-protocol.md`):**
  subagent que detecta bug recorrente em sua task PODE ativar diagnose
  protocol (build feedback loop → reproduce → hypothesise → fix) antes
  de declarar BLOCKED. Reportar resultado em `task-<slug>.md`.
