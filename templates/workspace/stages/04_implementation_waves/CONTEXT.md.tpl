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
| 6 | {{PROJECT_ROOT}}/docs/decisions/ | L3 | condicional: ler SOMENTE ADRs listados em "ADRs aplicáveis" da task no plan.md |
| 7 | {{PROJECT_ROOT}}/docs/lessons.md | L3 | condicional: lessons-match.py pré-extrai lições relevantes; lead injeta via canal 2 |
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
- ADRs em {{PROJECT_ROOT}}/docs/decisions/ NÃO listados em "ADRs aplicáveis" da task corrente
- Outputs de outros estágios do mesmo workspace (00, 01, 05+) — apenas plan.md (02) e wave-plan.md (03)
- {{PROJECT_ROOT}}/docs/tech_debt.md diretamente — entra via canal 2 do lead se aplicável

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
11. **Lead escreve:** `output/wave-<N>/wave-summary.md` (tasks completadas, conflicts, decisões tomadas).
12. **Atualizar L1:** sub_stage `04_wave_<N>_completed`, append `history` evento `wave_completed`. Se houver mais waves: spawn próxima (`04_wave_<N+1>_in_progress`). Se foi a última: status `COMPLETED_AWAITING_HUMAN`, transição para estágio 05.

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

## End of stage handoff (1-stage-1-sessão)

**Stage 04 exception (wave-aware):** cada wave = 1 sessão lead. Lead encerra wave gerando kickoff para próxima wave (mesmo stage 04, sub_stage `04_wave_<N+1>_in_progress`) OU para stage 05 (após última wave). Sub-waves (subdivisões dentro de uma wave) NÃO disparam kickoff — lead persiste através das sub-waves dentro da mesma sessão.

Ao concluir esta wave (ou o estágio inteiro se for última wave), sessão deve:

1. **Atualizar L1** (`<workspace>/CONTEXT.md`):
   - `sub_stage = 04_wave_<N>_completed`
   - `status = COMPLETED_AWAITING_HUMAN` (ou `IN_PROGRESS` se transição automática pra próxima wave / stage)
   - `last_transition.from = 04_wave_<N>_completed`
   - `last_transition.to = 04_wave_<N+1>_in_progress` (se houver mais waves) **OU** `05_in_progress` (se última wave — conforme `next_stage` do frontmatter)
   - `last_transition.at = <ISO 8601 UTC now>`
   - `history` append: `{at, event: "stage_transition" | "wave_completed", from, to, commit_sha, note}`

2. **Renderizar `_kickoff.md`** no destino seguinte:
   - Próxima wave: `<workspace>/stages/04_implementation_waves/_kickoff.md` (overwrite — `stage_target = 04`, com `wave_target` no corpo apontando wave <N+1>)
   - Última wave → stage 05: `<workspace>/stages/05_verification/_kickoff.md`
   - Use `python {{SKILL_DIR}}/scripts/handoff.py render` ou função `render_kickoff` do `{{SKILL_DIR}}/scripts/handoff.py`
   - Frontmatter YAML L4-kickoff conforme schema em `references/session-handoff-protocol.md`
   - Corpo: prev_outputs com summary (task reports + wave-summary) + prev_decisions + pending pra próxima sessão (próxima wave ou stage 05)

3. **Commit atômico** (pre-commit hook valida outputs↔L1; commit-msg valida prefix):
   ```
   workspace <NNN>: wave <N> completa + kickoff wave <N+1>
   ```
   ou (última wave):
   ```
   workspace <NNN>: stage 04 completo + kickoff stage 05
   ```
   Files no commit: outputs da wave + L1 + `_kickoff.md` do próximo.

4. **Imprimir KICKOFF block verbal** pro user (copy-paste). Template (substitua placeholders — variante wave-em-andamento OU stage-completo):

   ```
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   ✅ Wave <N> COMPLETA (stage 04) — workspace <NNN-slug>
   (ou: ✅ Stage 04 COMPLETO — workspace <NNN-slug> — última wave)

   Workspace atualizado em commit <sha>:
     - L1: stage_atual=04, sub_stage=04_wave_<N+1>_in_progress
       (ou: stage_atual=05, sub_stage=05_in_progress)
     - Outputs: <task reports + wave-summary>
     - Kickoff: <path do _kickoff.md gerado>

   🔄 KICKOFF próxima sessão — copy/paste:
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Continuar workspace <NNN-slug> no estágio 04 (implementation_waves) — wave <N+1>.
   (ou: Continuar workspace <NNN-slug> no estágio 05 (verification).)

   Read order:
     workspaces/<NNN-slug>/CLAUDE.md
     workspaces/<NNN-slug>/CONTEXT.md
     workspaces/<NNN-slug>/stages/<stage-dir>/CONTEXT.md
     workspaces/<NNN-slug>/stages/<stage-dir>/_kickoff.md
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

   Encerre esta sessão (Ctrl+D ou /exit) e abra nova sessão Claude
   no project_root, depois cole o prompt acima.
   ```

5. **SAIR** da sessão. NÃO continuar pra próxima wave / próximo stage na mesma sessão.

Detalhes em `<skill_root>/references/session-handoff-protocol.md`.
