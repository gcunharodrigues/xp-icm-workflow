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
7. **Handoff de fim de stage:** seguir protocolo gate-inline na seção `## End of stage handoff` deste L2 (Fase 1 WORK_DONE → gate humano sobre merge-report → Fase 2 GATE_APPROVED com auto-transição imediata 07→08). Stage 07 é especial: após gate aprovado, workspace transita imediatamente pra stage 08 com `status: COMPLETED_AWAITING_HUMAN` (workspace fica vivo aguardando feedback do mundo real). Workspace só fecha (`COMPLETED`) em stage 08 saída A.

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

## End of stage handoff (gate inline + auto-transição 07→08)

Stage 07 tem gate-inline + auto-transição pra 08 (sem segundo gate). Bug v3.4.2 corrigido: render+exit prematuros antes da aprovação do merge-report criavam loop. Stage 08 NÃO tem gate de saída próprio — `COMPLETED_AWAITING_HUMAN` em 08 significa "aguardando feedback do mundo real", não "aguardando approval de output". Doc canônico: `<skill_root>/references/session-handoff-protocol.md`.

### Fase 1: WORK_DONE (após merge executado + merge-report.md escrito)

1. **Atualizar L1** (`<workspace>/CONTEXT.md`):
   - `sub_stage = 07_completed`
   - `status = COMPLETED_AWAITING_HUMAN`
   - `last_transition.from = 07_in_progress`
   - `last_transition.to = 07_completed`
   - `last_transition.at = <ISO 8601 UTC now>`
   - `history` append: `{event: "stage_transition", from: "07_in_progress", to: "07_completed", commit_sha, note: "merge done, awaiting gate"}`

2. **Commit atômico 1/2** (outputs + L1; **NÃO** inclui `_kickoff.md`):
   ```
   workspace <NNN>: stage 07 merge done, awaiting gate
   ```
   Files: `output/merge-report.md` + L1.

3. **Imprimir prompt de gate** pro humano. NÃO sair. NÃO renderizar `_kickoff.md`:

   ```
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   ✅ Stage 07 (merge) trabalho COMPLETO — workspace <NNN-slug>
   Decisão A/B/C: <decisão executada>. commit_sha/PR/tag: <ref>.

   Outputs prontos pra revisão:
     - stages/07_merge/output/merge-report.md

   L1: sub_stage=07_completed, status=COMPLETED_AWAITING_HUMAN
   Commit 1/2: <sha>

   🛑 Gate humano: confirme merge-report.md.
   Responda no chat:
     - "aprovado" / "ok transita 08" → renderizo kickoff de 08 e saio
     - "ajustar X" → volto ao trabalho com seu pedido (status=IN_PROGRESS)
     - "abort" → marco workspace BLOCKED_ERROR
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   ```

4. **AGUARDAR resposta humana** na MESMA sessão.

### Fase 2: GATE_APPROVED (após humano confirmar) — auto-transição 07→08

Stage 07 é único: após gate aprovado, workspace TRANSITA imediatamente pra stage 08 com status `COMPLETED_AWAITING_HUMAN` (semântica diferente: workspace fica vivo aguardando feedback do mundo real, não review de output). Sem segundo gate.

5. **Atualizar L1** (segunda transição — auto-transit 07→08):
   - `stage_atual = 08`
   - `sub_stage = 08_in_progress`
   - `status = COMPLETED_AWAITING_HUMAN` (workspace ativo aguardando feedback humano após uso real)
   - `last_transition.from = 07_completed`
   - `last_transition.to = 08_in_progress`
   - `last_transition.at = <ISO 8601 UTC now>`
   - `history` append: `{event: "stage_transition", from: "07_completed", to: "08_in_progress", commit_sha, note: "gate approved, auto-transit 07→08 (workspace alive awaiting real-world feedback)"}`

6. **Renderizar `_kickoff.md`** em `<workspace>/stages/08_feedback_intake/_kickoff.md` via `python {{SKILL_DIR}}/scripts/handoff.py render`. Campos:
   - `prev_outputs`: `output/merge-report.md` (path + summary "merge feito A/B/C, commit_sha=X")
   - `prev_decisions_summary`: linha curta com decisão A/B/C + commit/tag/PR resultante
   - `pending_for_this_stage`: ["aguardar feedback humano após uso real do projeto", "interpretar intenção pra A/B/C"]

7. **Commit atômico 2/2** (kickoff + L1):
   ```
   workspace <NNN>: gate aprovado, auto-transita 07→08 (awaiting feedback)
   ```
   Files: L1 + `stages/08_feedback_intake/_kickoff.md`.

8. **Imprimir KICKOFF block verbal** pro user. Texto canônico (sem menu A/B/C — sessão 08 inferirá pela intenção do feedback):

   ```
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   ✅ Stage 07 (merge) GATE APROVADO — workspace <NNN-slug>

   Workspace transitou pra stage 08 (feedback intake) em status
   COMPLETED_AWAITING_HUMAN. Workspace fica vivo até você voltar
   com feedback após uso real do projeto.

   Workspace atualizado em commit <sha>:
     - L1: stage_atual=08, sub_stage=08_in_progress, status=COMPLETED_AWAITING_HUMAN
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

9. **SAIR** da sessão.

### Resposta "ajustar X" (gate rejeitado)

Se humano responder texto livre pedindo ajuste no merge-report (re-rodar merge com decisão diferente, refazer push, etc.):
- Atualizar L1: `status = IN_PROGRESS`, append history `{event: "gate_rejected", note: "humano pediu ajuste no merge: X"}`. Sub_stage permanece `07_completed`.
- Voltar ao trabalho conforme pedido. Pode envolver re-execução de Process step 5 (executar nova escolha A/B/C).
- Quando refizer outputs, voltar à Fase 1.

### Resposta "abort"

- Atualizar L1: `status = BLOCKED_ERROR`, append history `{event: "blocked_error", error_type: "human_abort"}`. Commit + sair.
