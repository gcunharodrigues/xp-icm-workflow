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
  - "feedback_ambiguous"
  - "design_system_cascade"
output_files:
  - "output/wave-<N>/task-<slug>.md"
  - "output/wave-<N>/wave-summary.md"
  - "output/wave-<N>/task-<slug>-blocked.md"
  - "output/wave-<N>/task-<slug>-critic-round<R>.json"
  - "output/wave-<N>/task-<slug>-diagnose.md"
  - "output/wave-<N>/task-<slug>-lead-decision.md"
next_stage: "05"
---

# Estágio 04 — implementation_waves (L2)

Execução paralela em waves. Lead session orquestra subagentes via Agent tool respeitando o cap por tier (2/3/5/5). Cada subagente trabalha numa task em branch isolada `wave-{{WORKSPACE}}-<N>/<task-slug>` (a partir de `{{BASE_BRANCH}}`), segue ciclo TDD vertical (tracer-first + RED→GREEN→CI scope→REFACTOR loop). Loop per-task tem cap 3 attempts, validado por L2 forensic+ extended (7 checks deterministic) + L3 critic ortogonal (Agent fresh context, anti-sycophancy, model = tier ceiling). Quando cap esgota OR convergence trip OR catastrophic detected → lead-resolution tier (3 buckets B1 REWRITE_SPEC / B3 DIRECT_IMPL / B4 VOID_TASK). Lead faz merge sequencial em `{{BASE_BRANCH}}` após approve. Uma sub_stage por wave: `04_wave_<N>_in_progress` → `04_wave_<N>_completed`. Repete até esgotar `wave-plan.md`.

**Docs canônicos consolidados:**
- `references/wave-execution-protocol.md` — pipeline 12-passos
- `references/critic-protocol.md` — L3 critic (v3.9.0)
- `references/lead-resolution-protocol.md` — buckets B1/B3/B4 (v3.9.0)
- `references/forensic-plus-protocol.md` — 7 checks (extended v3.9.0)
- `references/4-block-contract-template.md` — TDD vertical + tracer-first (v3.9.0)
- `references/mocking-guidelines.md` — boundaries only (v3.9.0)

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
| 17 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/runtime/critic-protocol.md | L3 | sim — L3 critic ortogonal (v3.9.0) |
| 18 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/runtime/lead-resolution-protocol.md | L3 | sim — buckets B1/B3/B4 (v3.9.0) |
| 19 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/runtime/forensic-plus-protocol.md | L3 | sim — 7 checks extended (v3.9.0) |
| 20 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/runtime/mocking-guidelines.md | L3 | sim — boundaries only (v3.9.0) |

## Não Lê (negative constraint)

- {{PROJECT_ROOT}}/workspaces/ (outros workspaces — isolamento por workspace)
- ADRs em {{PROJECT_ROOT}}/.icm-main/docs/decisions/ NÃO listados em "ADRs aplicáveis" da task corrente
- Outputs de outros estágios do mesmo workspace (00, 01, 05+) — apenas plan.md (02) e wave-plan.md (03)
- {{PROJECT_ROOT}}/.icm-main/docs/tech_debt.md diretamente — entra via canal 2 do lead se aplicável

## Process

Cada wave executa o pipeline abaixo. `<N>` = número da wave atual.

1. **Lead pre-flight:** lê wave-plan.md; identifica wave atual via L1 `waves.current`. Sub_stage transita para `04_wave_<N>_in_progress`. Lead grava em L1 history evento `{event: "wave_started", wave: <N>, pre_wave_sha: <git rev-parse {{BASE_BRANCH}}>}` — usado por ci-rollback-protocol.md como ponto de reset.
2. **Lead spawn subagentes via Agent tool:** para cada task da wave (até cap):
   1. Lead cria branch ANTES do spawn: `git branch wave-{{WORKSPACE_NUM}}-<N>/<task-slug> {{BASE_BRANCH}}`. Lead permanece em workspace branch (sem checkout). Branch órfã (caso Agent falhe pré-checkout) é detectável via `git branch --merged {{BASE_BRANCH}}` e limpa no passo 11.
   2. Lead invoca `Agent(isolation: "worktree", subagent_type: "general-purpose", description: "wave <N> task <slug>", prompt: <AGENT-BRIEF + canal-2>)`. Harness faz `git worktree add` apontando pra branch já existente — NÃO cria branch novo. Path do worktree retornado no Agent tool result; lead persiste em estrutura local pra cleanup posterior.
   3. Tasks paralelas: múltiplos `Agent` calls em UMA mensagem (multi tool-use). Tasks sequenciais (HITL ou dependentes): chamadas sequenciais.
3. **Lead injeta canal 2:** injeta no prompt do subagente apenas o subset de ADRs + lições críticas + conventions extras declarados no plan.md daquela task. Subagente NÃO lê o `docs/` global do projeto. **Se task tem flag `requires_design_system: true`** (profile `app_web_frontend` ou `fullstack`): lead também injeta subset relevante do DESIGN.md (tokens aplicáveis + components section da task) — subagente lê via `Read {{PROJECT_ROOT}}/.icm-main/DESIGN.md` se precisar de detalhe extra. Doc: `_references/runtime/design-system.md`.
4. **Subagente (CWD = project root, branch `wave-{{WORKSPACE}}-<N>/<task-slug>`):** executa ciclo TDD vertical (`references/4-block-contract-template.md` § 3):
   1. **Tracer-first** — escreve 1 test E2E golden path (mínimo viável, espera-se vermelho). Commit como primeiro da task.
   2. **Loop per feature unit** (cada iteração = 1 commit):
      - RED → 1 test (1 acceptance bullet OR edge case)
      - GREEN → minimal impl pra test passar
      - CI scope → tests + types + lint nos files touched (fast feedback)
      - REFACTOR → opcional, só se redução de complexity óbvia
   3. **Anti-horizontal slicing** — proibido escrever todos tests de uma vez OR todo impl de uma vez. Forensic+ Check 5 detecta acceptance bullets sem test mapping; se diff > 100 LOC sem novo test → stop e re-pace.
   4. **Commit verify gate** — antes de COMPLETE, confirma `git log --oneline {{BASE_BRANCH}}..HEAD` mostra ≥1 commit. Zero = volta ao loop.
   5. **COMPLETE** — escreve `output/wave-<N>/task-<slug>.md` minimalista (resumo, files modificados, tests, ADRs aplicados — SEM checklist Akita inline, QA delegada a L2/L3).
5. **Stop points dentro do ciclo:** se subagente detecta `new_dep`, `irreversible`, `over_eng`, `prod_migration` ou `adr_drift` → pausa estado atual, escreve menu A/B/C, retorna sinalização ao lead via Agent tool output, lead seta L1 `status: BLOCKED_STOP_POINT`. Humano responde, ciclo retoma do passo onde parou.
6. **Per-task QA loop** (cap 3 attempts):
   1. **L2 forensic+ extended** roda primeiro (passo 8b). HARD ≥ 1 → skip L3, surgical brief retry (não desperdiça tokens em código rejeitado por gate barato).
   2. **L3 critic ortogonal** (passo 8c) sempre roda quando L2 passou. REJECT → diagnose (passo 8d) decide surgical retry OR escalate.
   3. **Cap 3 attempts** total. Esgotado → lead-resolution tier (passo 9).
   4. **Convergence trip** (Jaccard ≥ 0.7 entre rounds N e N-1) → escalate imediato sem aguardar cap.
   5. **Catastrophic detected** (tests broken outside scope, build globally broken, scope creep > 5×) → escalate imediato bypass cap.
7. **Lead recebe resultado de cada subagente via Agent tool:** lead aguarda retorno COMPLETE de cada subagente da wave. Resultados chegam diretamente pelo Agent tool output — sem polling de diretório. Ordem de retorno é não-determinística (paralelismo). Lead bufferiza resultados em estrutura `{task_slug: agent_result}`. Antes do passo 9 (merge sequencial), lead ordena tasks por índice no `plan.md > tasks[]` da wave atual — merge order = plan order, NÃO retorno order. Auditável: `wave-summary.md` lista tasks na ordem do plan.
8. **Wave-reviewer L2 + L3 (Agent sem worktree, sub-steps 8a-8e):**

   8a. **Pre-audit:** files_touched real (`git diff --name-only`) capturado pra todas tasks AFK. Skip cross-task audit em wave 1-task (flag `skip_cross_task_audit: true` no wave-plan.md).

   8b. **L2 Forensic+ extended (7 checks, deterministic, 0 token):** pra cada task AFK da wave (skip `type: HITL`), reviewer Agent invoca:
       ```bash
       python {{SKILL_DIR}}/scripts/forensic-plus.py \
           --workspace-num {{WORKSPACE_NUM}} --wave <N> --task-slug <slug> \
           --base-branch {{BASE_BRANCH}} --tier <T> \
           --plan {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/02_design/output/plan.md \
           --output json
       ```
       Parse JSON. Grava em `output/wave-<N>/task-<slug>.md` frontmatter campos `forensic_violations`, `forensic_passed`, `forensic_max_severity`, `forensic_respawn_count`. Doc canônico: `references/forensic-plus-protocol.md`. Crash do script (exit 1) → reviewer emit `forensic_error` + treat como HARD; lead → `BLOCKED_ERROR error_type: forensic_script_crash`.

       - HARD em ≥1 check → skip 8c (não roda L3 em código rejeitado por gate barato), brief surgical pra retry (cap 3 attempts da task).

   8c. **L3 Critic ortogonal (sempre, todos tiers — v3.9.0):** pra cada task AFK que passou 8b, reviewer (lead OR Agent) invoca critic via Agent tool com fresh context:
       ```python
       Agent(
           description="L3 critic ortogonal task <slug>",
           subagent_type="general-purpose",
           model=<critic_model_from_pick_model_py>,  # = TIER_CEILING[tier]
           prompt=render_critic_prompt(<slug>, <wave>),  # templates/critic-prompt.md
       )
       ```
       Critic output JSON triplet (claim, evidence file:line, counterexample, severity BLOCKING|MAJOR|MINOR; decision APPROVE|REJECT|ABSTAIN). Doc canônico: `references/critic-protocol.md`. Critic JSON salvo em `output/wave-<N>/task-<slug>-critic-round<R>.json` (R = attempt number 1-3).

       - REJECT (≥1 BLOCKING ou ≥2 MAJOR) → 8d diagnose.
       - ABSTAIN → trata como REJECT; 2 ABSTAIN consecutivos → `BLOCKED_ERROR error_type: critic_abstain_loop`.
       - APPROVE → task PASS, prossegue passo 10 merge.

   8d. **Diagnose (deterministic, 0 token):** quando 8b HARD OR 8c REJECT, lead invoca:
       ```bash
       python {{SKILL_DIR}}/scripts/lead-diagnose.py \
           --task-slug <slug> --wave <N> --workspace-num {{WORKSPACE_NUM}} \
           --base-branch {{BASE_BRANCH}} \
           --critic-rounds output/wave-<N>/task-<slug>-critic-round1.json[,round2.json,...] \
           --files-touched <comma-sep> \
           --forensic-files-outside <int from 8b Check 2> \
           --output output/wave-<N>/task-<slug>-diagnose.md
       ```
       Renderiza diagnose.md com trigger condition (T1/T2/T3) + Jaccard table + catastrophic signals + bucket recommendation (B1/B3/B4) + surgical brief (se B1).

   8e. **Decision per task:**
       - **Cap não esgotado AND não convergence AND não catastrophic** → surgical retry: lead re-spawn writer com brief enxuto (top-3 concerns + acceptance delta from critic triplets). Volta ao passo 4. Attempt counter ++.
       - **Cap 3 esgotado OR convergence trip OR catastrophic** → escalate lead-resolution tier (passo 9).
       - **Apenas SOFT em 8b + APPROVE em 8c** → `approved_pending_ci: true`, warnings log em `wave-summary.md` § L2/L3 summary. Merge prossegue (passo 10).

9. **Lead-resolution tier (B1/B3/B4) — quando passo 8 escalou:**
   Lead lê `output/wave-<N>/task-<slug>-diagnose.md` recommend bucket. Lead pode override (registra escolha em `output/wave-<N>/task-<slug>-lead-decision.md`). L1 status: `LEAD_RESOLUTION_IN_PROGRESS`. Doc canônico: `references/lead-resolution-protocol.md`.

   - **B1 REWRITE_SPEC:** lead reescreve task no plan.md (VALIDAÇÃO mais específico, NÃO QUERO adicional, COMO prescritivo). Commit plan update. 1 final spawn writer com brief novo. Output passa L2+L3 (volta passo 8). APPROVE → merge. REJECT → escalate B3.
   - **B3 DIRECT_IMPL:** lead escreve código direto em branch `wave-<NNN>-<N>/<slug>-lead-resolved`. Mesmo cycle TDD vertical. Output passa L2+L3 igual a writer normal (volta passo 8). APPROVE → merge. REJECT → escalate B4.
   - **B4 VOID_TASK:** lead reescreve task com bloco `### VOIDED — wave <N> attempt <date>` (rationale concreto: ADR conflict / scope inválido / upstream blocker). Commit plan update. Trigger `wave-planner-script.py --recalculate` re-deriva DAG sem task. Wave continua com tasks restantes. L1 history append `event: task_voided`.

   Cap: 1 attempt per bucket per task. Sequence B1→B3→B4. Pular bucket OK; revisitar bucket usado proibido. Todos exhausted → `BLOCKED_ERROR error_type: lead_resolution_all_buckets_failed`.

10. **Merge sequencial:** lead faz merge de cada branch `wave-{{WORKSPACE_NUM}}-<N>/<task-slug>` (OR `-lead-resolved` quando B3) em `{{BASE_BRANCH}}` usando ordem buferizada do passo 7 (= ordem do plan). Comando: `git checkout {{BASE_BRANCH}} && git merge --no-ff <branch>` por task. `--no-ff` preserva grupo de commits (auditável). Conflict de merge → `references/conflict-resolution-protocol.md`.
11. **L4 wave gate (CI global):** roda CI completo do projeto após todos os merges. Verde → wave concluída, segue passo 12. Vermelho → `references/ci-rollback-protocol.md`. Production tier + ≥2 tasks com shared file/API change → cross-task coherence check (subagent fresh context, optional v3.9.0).
12. **Cleanup wave worktrees + branches (v3.4.3):** após merge bem-sucedido + CI verde, lead remove worktrees efêmeras criadas pelos subagentes E deleta branches já merged. Bug pre-v3.4.3: worktrees em `<project_root>/.icm-wave-*` (ou path retornado pelo Agent tool) ficavam orfãs após cada wave; branches `wave-<NNN>-<N>/<task-slug>` poluíam `git branch` listing.

   ```bash
   # Para cada task da wave (paths capturados dos Agent tool results):
   git worktree remove <path-do-worktree>           # remove worktree efemera
   git branch -d wave-{{WORKSPACE_NUM}}-<N>/<task-slug>   # safe: ja merged --no-ff

   # Fallback robusto (se path foi perdido — busca por pattern de branch):
   git worktree list --porcelain | awk '/^worktree /{p=$2} /^branch refs\/heads\/wave-{{WORKSPACE_NUM}}-<N>/{print p}' \
     | xargs -I {} git worktree remove {}
   ```

   **Decision matrix `--force`:**
   - `git worktree remove <path>` falha se working tree não-limpo → lead lê task report `output/wave-<N>/task-<slug>.md`:
     - L2 + L3 PASS no frontmatter (`forensic_passed: true` AND `critic_decision: APPROVE`) → safe usar `git worktree remove --force <path>` (lock file órfão é a única causa restante).
     - Caso contrário → NÃO força. Set `status: BLOCKED_ERROR`, registrar em `wave-summary.md`, humano inspeciona manualmente.
   - `git branch -d` recusa se não-merged → JAMAIS usar `-D`. Branch não-merged pós-merge step indica bug no merge sequencial; investigar antes.
   - Falha cleanup não-fatal (após force válido): registrar warning em `wave-summary.md` (próximo passo).

13. **Lead escreve:** `output/wave-<N>/wave-summary.md` (tasks completadas, conflicts, decisões tomadas, **warnings de cleanup** se houve, **§ L2/L3 summary** com violations SOFT + critic concerns MINOR, **§ Lead resolutions** com tabela buckets aplicados se houve).
14. **Handoff de fim de wave/stage:** seguir protocolo na seção `## End of stage handoff` deste L2. Mid-wave (wave <N> → <N+1>): handoff automático sem gate humano (Caso A). Última wave → stage 05: gate-inline obrigatório (Caso B — Fase 1 WORK_DONE → gate humano → Fase 2 GATE_APPROVED).

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
- `BLOCKED_ERROR` — merge conflict, CI global vermelho, cap 3 attempts esgotado + B1+B3+B4 todos falharam, critic abstain loop, OR cleanup --force unsafe.
- `BLOCKED_HITL` — wave mista com 1+ task `type: HITL` aguardando humano (não é falha; espera externa).
- `LEAD_RESOLUTION_IN_PROGRESS` (v3.9.0) — per-task loop esgotou trigger condition (cap 3 / convergence trip / catastrophic); lead executando bucket B1/B3/B4. Sub_stage permanece `04_wave_<N>_in_progress`.

## Stop points aplicáveis

Catálogo canônico em `references/stop-points-canonical.md`. IDs disparáveis em fase 04:

- `new_dep` — npm/pip/cargo nova adicionada durante implementação que não estava no plan.md.
- `irreversible` — `DROP TABLE`, `git push --force`, hard-delete sem soft-delete prévio.
- `over_eng` — 3+ camadas de abstração novas sem requisito (calibrado: warning experimental/tool, hard development/production).
- `prod_migration` — migration toca tabela com volume produção sem janela acordada.
- `adr_drift` — implementação diverge de ADR vigente sem superseding declarado.
- `feedback_ambiguous` — (preview loop v3.6.0) feedback visual humano com baixa confidence: descrição vaga, screenshot sem anotação clara, contradição entre texto e visual. Sempre `hard`.
- `design_system_cascade` — (preview loop v3.6.0) mudança em token afeta > `preview_loop.design_cascade_threshold` componentes. Sempre `hard`.

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
  `{{BASE_BRANCH}}` conforme protocol da fase 04.

  **Sync `.icm-main` (condicional v3.5.0):** após merge, lead checa se
  `{{PROJECT_ROOT}}/.icm-main` existe E é worktree linkada:
  ```bash
  if git worktree list --porcelain | grep -q "worktree {{PROJECT_ROOT}}/.icm-main"; then
      cd {{PROJECT_ROOT}}/.icm-main && git pull --ff-only
  fi
  ```
  Se ausente: skip silencioso (`.icm-main` é convenção opcional setup
  por recovery wizard / bootstrap em alguns workspaces). Falha do
  `pull --ff-only` (ex: divergence): warning não-fatal em
  `wave-summary.md`, lead segue.

- **HITL handling (task-level granularity):**
  - **Wave-level HITL** (todas tasks da wave têm `type: HITL`, ou
    wave-planner isolou tasks HITL em sub-wave cap=1): lead NÃO spawna
    Agent para nenhuma task. Gera AGENT-BRIEF de cada, exibe ao humano,
    atualiza L1 `status=COMPLETED_AWAITING_HUMAN,
    sub_stage=04_wave_N_hitl_pending`, SAIR. Próxima sessão (após humano
    resolver) lê task reports preenchidos pelo humano e prossegue.
  - **Task-level HITL** (wave mista — algumas tasks `type: HITL`, outras
    não): lead spawna Agents para tasks não-HITL EM PARALELO; para cada
    task HITL gera AGENT-BRIEF + escreve `output/wave-<N>/task-<slug>.md`
    com frontmatter `status: AWAITING_HITL` + brief inline. Lead aguarda
    Agents não-HITL retornarem. Após retorno: se ainda há tasks
    AWAITING_HITL, lead atualiza L1 `status=BLOCKED_HITL,
    sub_stage=04_wave_N_partial_hitl_pending`, SAIR. Próxima sessão
    valida que tasks HITL viraram `status: COMPLETE` (humano editou) e
    retoma passo 8 (wave-reviewer) com a wave inteira.
  - Status canônico novo: `BLOCKED_HITL` (distinto de `BLOCKED_ERROR` —
    não é falha, é espera externa).

- **Diagnose protocol nota (`_references/runtime/diagnose-protocol.md`):**
  subagent que detecta bug recorrente em sua task PODE ativar diagnose
  protocol (build feedback loop → reproduce → hypothesise → fix) antes
  de declarar BLOCKED. Reportar resultado em `task-<slug>.md`.

## Preview Loop entry/exit hooks (v3.6.0)

Aplica APENAS quando profile efetivo tem
`preview_loop.preview_loop_enabled: true` (lido em
`_config/profile-effective.yaml`). Doc canônico:
`_references/runtime/preview-loop-protocol.md`.

### Entry hook (1ª sessão da wave 1, OU sessão fresca de wave>1)

Lead executa ANTES do passo 1 (pre-flight) acima:

1. **Detectar package manager** via lockfile em `{{PROJECT_ROOT}}`:
   - `bun.lockb` ou `bun.lock` → `bun dev`
   - `pnpm-lock.yaml` → `pnpm dev`
   - `yarn.lock` → `yarn dev`
   - `package-lock.json` → `npm run dev`
   - Múltiplos: prioridade `bun > pnpm > yarn > npm`.
   - Nenhum: stop point `BLOCKED_ERROR` — falta scaffold inicial (deve
     ter sido criado em wave 1 task 1).

2. **Verificar runtime registry** (v3.7.0):
   ```bash
   python {{SKILL_DIR}}/scripts/runtime-registry.py list \
       --workspace-root {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}} \
       --kind dev_server
   ```
   - Entry com PID alive → reutiliza, skip start.
   - Entry com PID morto → unregister (registry stale; auto-recovery via
     `recovery-wizard.py` `RUNTIME_REGISTRY_STALE`).
   - Sem entries → start novo (passo 3).

   **Legacy (v3.6.0):** se workspace foi criado pré-v3.7.0 e tem
   `.icm-main/.dev-server.pid` no lugar do registry, rodar
   `migrate-workspace.py --workspace-root <ws>` ANTES de prosseguir.

3. **Start dev server em background + register:**
   ```bash
   cd {{PROJECT_ROOT}}
   <pm> run dev > .icm-main/.dev-server.log 2>&1 &
   PID=$!
   python {{SKILL_DIR}}/scripts/runtime-registry.py register \
       --workspace-root {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}} \
       --kind dev_server --pid $PID --port <PORT> --command "<pm> run dev"
   ```
   Aguardar 3-5s pra Vite/Next bootear (lê stderr do log até ver
   "ready" ou "Local:"). Falha = `BLOCKED_ERROR`.

   **Custom dev server** (não-default): registre kind apropriado
   (`background_task` se daemon worker, etc.) com `--metadata` extra. Doc:
   `_references/runtime/runtime-cleanup-protocol.md`.

4. **Imprimir kickoff priming** ao humano:

   ```
   🎨 Preview loop ativo — workspace {{WORKSPACE}}

   Dev server: http://localhost:3000 (PID <pid>)
   Chrome CDP helper: scripts/launch-chrome-cdp.{bat,sh}
   Preview pages: localhost:3000/preview/<component>

   Pra dar feedback visual, qualquer combo funciona:
     - Texto: "botão direita, mais padding"
     - Print anotado (Win+Shift+S Snipping ou ShareX): cola PNG
     - URL: "/checkout, header torto"
     - HTML: cola outerHTML do elemento problemático

   Se ambíguo, eu pergunto antes de mexer (stop point feedback_ambiguous).
   ```

### Verificação tier-aware durante implementação

Substituem/complementam Auto-QA Akita do passo 4.6:

- **Cada Edit** em arquivo `.ts/.tsx/.vue/.svelte` → subagente roda
  `tsc --noEmit` (~1s). Falha = NÃO declara task done, fix imediato.
- **Wave end** (após passo 9 merge) → lead roda lint completo + Playwright
  headless sample-check (1 click em cada componente novo da wave, valida
  render sem crash).
- **Sob pedido humano** ("ok testa" / "valida") → lead roda full suite +
  e2e relevantes.
- **Sempre ativo:** Vite/Next overlay nativo mostra erros de compile na
  tela do humano direto.

### Stop point novo: `feedback_ambiguous`

Disparável durante a wave quando humano dá feedback visual de baixa
confidence (descrição vaga, screenshot sem anotação clara, contradição
entre texto e visual). Lead/subagente NÃO mexe especulando: pausa,
escreve menu A/B/C com interpretações candidatas, atualiza L1
`status: BLOCKED_STOP_POINT`. Calibração: sempre `hard` (qualquer tier).

### Stop point novo: `design_system_cascade`

Disparável quando mudança de token afeta > `preview_loop.design_cascade_threshold`
(default 5) componentes. Menu A/B/C: cascata global / limita escopo /
cancela. Sempre `hard`.

### Exit hook (handoff final stage 04 — Caso B Fase 2 GATE_APPROVED)

Lead executa APÓS commit 2/2 do gate aprovado (passo 7 do Caso B), antes
de imprimir KICKOFF block.

**v3.7.0 (registry-based):**

1. **Listar entries dev_server** do registry:
   ```bash
   python {{SKILL_DIR}}/scripts/runtime-registry.py list \
       --workspace-root {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}} \
       --kind dev_server --format json
   ```
2. **Pra cada entry com PID alive**, matar processo:
   - POSIX: `kill <pid>` (ou `kill -9 <pid>` se não responde).
   - Windows: `taskkill /PID <pid> /F`.
   Falha silenciosa OK (processo já morto).
3. **Unregister entries** (independente de PID alive/morto):
   ```bash
   python {{SKILL_DIR}}/scripts/runtime-registry.py unregister \
       --workspace-root {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}} \
       --id <entry_id>
   ```
   Ou batch via `purge-dead` se todos PIDs já mortos.
4. **Apagar `.dev-server.log`** (housekeeping).
5. **NÃO apaga** `.icm-chrome-profile/` — humano pode querer manter
   abas abertas pra próximo workspace; recovery wizard limpa quando
   detecta orphan persistente.

Stage 05 (verification) NÃO depende do dev server. Stage 06+ idem.

**Legacy (v3.6.0):** workspaces pre-v3.7.0 ainda usam
`.icm-main/.dev-server.pid` direto. Migration via
`migrate-workspace.py` move pra registry. Após migration, este exit hook
funciona uniformemente.
