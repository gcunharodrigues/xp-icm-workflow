---
layer: L2
stage: "07"
stage_name: "merge"
sub_stage_enum:
  - "07_in_progress"
  - "07_completed"
applicable_stop_points:
  - "irreversible"
  - "prod_migration"
output_files:
  - "output/merge-report.md"
next_stage: "08"
---

# Estágio 07 — merge (L2)

Finaliza ciclo de implementação: integra a `workspace_branch` rebased em `base_branch` (geralmente `main`), opcionalmente abre PR ou cria tag de release. Decisão "merge direto / PR / tag-only" é menu humano. Após executar, workspace transita automaticamente para **stage 08 (feedback intake)** com `status: COMPLETED_AWAITING_HUMAN` — workspace fica "vivo" aguardando o humano voltar com feedback após uso real do projeto. Workspace SÓ fecha (status `COMPLETED`) quando stage 08 decide saída A (close).

## Inputs (lê SOMENTE estes, na ordem)

| # | Path | Layer | Obrigatório? |
|---|------|-------|--------------|
| 1 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/CLAUDE.md | L0 | sim |
| 2 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/CONTEXT.md | L1 | sim |
| 3 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/07_merge/CONTEXT.md | L2 | sim |
| 4 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/06_review/output/review-report.md | L4 | sim |
| 5 | {{PROJECT_ROOT}}/.git/config | L3 | sim (read-only — qual remote, qual base_branch) |
| 6 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/superpowers-summary/finishing-a-development-branch-200tok.md | L3 | sim |
| 7 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_config/stop-points.md | L3 | sim |
| 8 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/07_merge/_kickoff.md | L4-kickoff | condicional: gerado pela sessão anterior. Ausente em workspaces beta1/beta2 (4B legacy) ou se for primeira sessão de stage. |
| 9 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/runtime/session-handoff-protocol.md | L3 | condicional: necessário no handoff final do estágio |
| 10 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/runtime/stop-points-canonical.md | L3 | condicional: catálogo canônico de IDs, complementar ao _config/stop-points.md de thresholds |

## Não Lê (negative constraint)

- {{PROJECT_ROOT}}/.icm-main/src/, {{PROJECT_ROOT}}/.icm-main/tests/ — merge não inspeciona código (review e verification já validaram).
- Outputs de estágios 00–05 — review-report já consolida o que importa para a decisão de merge.
- {{PROJECT_ROOT}}/.icm-main/docs/decisions/ na íntegra — ADRs já foram aplicados nas fases 02/04/06.
- Workspaces irmãos.

## Process

1. **Pre-flight:** validar paths Inputs; sub_stage `07_in_progress`. review-report.md AUSENTE ou indicando P0/P1 → `BLOCKED_ERROR` (não deveria estar em 07 nesse caso).
2. **Verificar estado git:** `workspace_branch` existe, está rebased em `base_branch`, working tree limpo. Se não — `BLOCKED_ERROR` com mensagem específica.
3. **Detectar stop points:**
   - Operações irreversíveis no merge (force-push, drop) → `irreversible` (sempre `hard`).
   - Migration de schema com dados em produção → `prod_migration` (sempre `hard`).
4. **Menu humano A/B/C** (escrito no chat, não em arquivo):
   - **A) Merge direto** em `base_branch` (`git merge --no-ff` ou `--squash`, conforme convenção do projeto declarada em xp-conventions ou git config).
   - **B) Abrir PR** via `gh pr create` (ou equivalente), aguarda revisão humana externa antes de merge final.
   - **C) Tag-only** — cria tag de release sem merge automatizado (usado para entregas que vão atrás de gate de deploy externo).
5. **Executar a escolha humana:**
   - A: rebase final + merge + push em `base_branch`.
   - B: push da branch + `gh pr create` com link para review-report.
   - C: `git tag -a v<X>.<Y>.<Z>` + push de tag.
6. **Escrever `output/merge-report.md`:** decisão tomada (A/B/C), comandos executados, commit_sha resultante (merge commit, PR URL, ou tag), status do CI pós-merge se aplicável.
7. **Atualizar L1:** `sub_stage: "07_completed"`, depois transita imediatamente `stage_atual: "08"`, `sub_stage: "08_in_progress"`, `status: COMPLETED_AWAITING_HUMAN` (workspace ativo aguardando feedback humano). Append `history` 2 eventos: `stage_transition from:07_in_progress to:07_completed` + `stage_transition from:07_completed to:08_in_progress`. Commit atômico.
8. **Render `_kickoff.md` em stage 08** com prev_outputs (merge-report) + prev_decisions_summary (merge feito + commit_sha). Próxima sessão (disparada quando user voltar com feedback) lê este kickoff.
9. **Gate humano final do merge:** humano confirma merge-report. Workspace transita pra 08 (não fecha como COMPLETED — fechamento só em stage 08-A).

## Outputs

- `output/merge-report.md` — relatório do merge: decisão A/B/C, comandos executados, commit_sha resultante (merge commit / PR URL / tag), estado do CI pós-merge.

## Sub_stage transitions

Enum válido: `07_in_progress`, `07_completed`.

Transição IN_PROGRESS → 07_completed dispara quando:
- `output/merge-report.md` existe.
- Decisão humana A/B/C executada com sucesso (commit_sha registrado em merge-report).
- Humano confirmou via gate.

Imediatamente após `07_completed`, sessão TRANSITA para stage 08 (`stage_atual: "08"`, `sub_stage: "08_in_progress"`, `status: COMPLETED_AWAITING_HUMAN`). Workspace fica vivo aguardando feedback humano após uso real. Workspace só fecha (`status: COMPLETED`) quando stage 08 saída A (close) é decidida.

`next_stage: "08"` — estágio 07 transita automaticamente para 08 (feedback intake).

## Status canônicos disponíveis neste estágio

- `IN_PROGRESS` — preparando merge, aguardando escolha humana A/B/C.
- `COMPLETED_AWAITING_HUMAN` — merge feito, sessão transitou pra stage 08; workspace aguardando feedback humano após uso real.
- `BLOCKED_STOP_POINT` — `irreversible` ou `prod_migration` disparou; menu A/B/C aguardando resposta.
- `BLOCKED_ERROR` — review-report indicava P0/P1, working tree sujo, rebase falhou, ou push rejeitado.

`COMPLETED` NÃO é setado neste stage — fechamento definitivo só ocorre em stage 08 saída A (close).

## Stop points aplicáveis

Catálogo canônico em `references/stop-points-canonical.md`. IDs disparáveis no estágio 07 merge:

- `irreversible` — operação destrutiva (force-push em branch compartilhada, drop em prod, rotação de credencial sem grace-window). Sempre `hard`.
- `prod_migration` — migration de schema com dados em produção (DDL bloqueante, mudança de tipo invalidando linhas existentes). Sempre `hard`.

Disparo: agente pausa, escreve menu A/B/C no output, atualiza L1 `status: BLOCKED_STOP_POINT`. Humano responde, sessão retoma com `IN_PROGRESS`.

## Skill superpowers de referência

Sumário 200tok (consulta obrigatória):

- `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/superpowers-summary/finishing-a-development-branch-200tok.md`

Skill formal (escape hatch): `superpowers:finishing-a-development-branch`.

## Gates

- **Humano:** escolhe A/B/C no menu de merge; confirma o merge-report ao final.
- **Automático (CI):** pre-commit hook valida atomicidade L1↔outputs e prefixo de commit `workspace/{{WORKSPACE}}`. Pós-merge, CI da `base_branch` valida o estado integrado.
- **Aprovação para transitar:** humano confirma merge-report; sub_stage vira `07_completed` e status transita imediatamente para `COMPLETED_AWAITING_HUMAN` (stage 08). `COMPLETED` NÃO é setado neste stage — fechamento definitivo só em stage 08 saída A.

## End of stage handoff (1-stage-1-sessão)

Ao concluir este estágio, sessão deve:

1. **Atualizar L1** (`<workspace>/CONTEXT.md`):
   - Primeira transição: `sub_stage = 07_completed`
   - Segunda transição imediata: `stage_atual = "08"`, `sub_stage = 08_in_progress`, `status = COMPLETED_AWAITING_HUMAN`
   - `last_transition.from = 07_completed`
   - `last_transition.to = 08_in_progress`
   - `last_transition.at = <ISO 8601 UTC now>`
   - `history` append 2 eventos: `stage_transition 07_in_progress→07_completed` + `stage_transition 07_completed→08_in_progress`

2. **Renderizar `_kickoff.md` em `stages/08_feedback_intake/_kickoff.md`** via `python {{SKILL_DIR}}/scripts/handoff.py render`. Campos:
   - `prev_outputs`: `output/merge-report.md` (path + summary "merge feito A/B/C, commit_sha=X")
   - `prev_decisions_summary`: linha curta com decisão A/B/C + commit/tag/PR resultante
   - `pending_for_this_stage`: ["aguardar feedback humano após uso real do projeto", "interpretar intenção pra A/B/C"]

3. **Commit atômico** (pre-commit hook valida outputs↔L1; commit-msg valida prefix):
   ```
   workspace <NNN>: stage 07 completo + transita pra 08 (awaiting feedback)
   ```
   Files no commit: `output/merge-report.md` + L1 + `stages/08_feedback_intake/_kickoff.md`.

4. **Imprimir KICKOFF block verbal** pro user. Texto canônico (sem menu A/B/C — sessão 08 inferirá pela intenção do feedback):

   ```
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   ✅ Stage 07 (merge) COMPLETO — workspace <NNN-slug>

   Workspace transitou pra stage 08 (feedback intake) em status
   COMPLETED_AWAITING_HUMAN. Workspace fica vivo até você voltar
   com feedback após uso real do projeto.

   Workspace atualizado em commit <sha>:
     - L1: stage_atual=08, sub_stage=08_in_progress
     - Outputs: stages/07_merge/output/merge-report.md
     - Kickoff: stages/08_feedback_intake/_kickoff.md gerado

   🔄 KICKOFF próxima sessão (DEPOIS de uso real, sem prazo):
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Continuar workspace <NNN-slug> no estágio 08 (feedback_intake).

   Read order:
     workspaces/<NNN-slug>/CLAUDE.md
     workspaces/<NNN-slug>/CONTEXT.md
     workspaces/<NNN-slug>/stages/08_feedback_intake/CONTEXT.md
     workspaces/<NNN-slug>/stages/08_feedback_intake/_kickoff.md

   Cole o feedback livre — sessão 08 lê outputs, infere intenção
   (bug fix → restart fase X, feature nova → spawn workspace,
   tudo OK → close), confirma com você antes de executar.
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   ```

5. **SAIR** da sessão.

Detalhes em `<skill_root>/references/session-handoff-protocol.md`.
