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
next_stage: null
---

# Estágio 07 — merge (L2)

Finaliza o ciclo: integra a `workspace_branch` rebased em `base_branch` (geralmente `main`), opcionalmente abre PR ou cria tag de release. Decisão "merge direto / PR / tag-only" é menu humano. Após executar, workspace transita para `status: COMPLETED` — fim do ciclo principal. A fase 08 (feedback intake) é disparada manualmente pelo humano semanas/meses depois, com workspace já fechado.

## Inputs (lê SOMENTE estes, na ordem)

| # | Path | Layer | Obrigatório? |
|---|------|-------|--------------|
| 1 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/CLAUDE.md | L0 | sim |
| 2 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/CONTEXT.md | L1 | sim |
| 3 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/07_merge/CONTEXT.md | L2 | sim |
| 4 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/06_review/output/review-report.md | L4 | sim |
| 5 | {{PROJECT_ROOT}}/.git/config | L3 | sim (read-only — qual remote, qual base_branch) |
| 6 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/superpowers-summary/finishing-branch-200tok.md | L3 | sim |
| 7 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/07_merge/_kickoff.md | L4-kickoff | condicional: gerado pela sessão anterior. Ausente em workspaces beta1/beta2 (4B legacy) ou se for primeira sessão de stage. |

## Não Lê (negative constraint)

- {{PROJECT_ROOT}}/src/, {{PROJECT_ROOT}}/tests/ — merge não inspeciona código (review e verification já validaram).
- Outputs de estágios 00–05 — review-report já consolida o que importa para a decisão de merge.
- {{PROJECT_ROOT}}/docs/decisions/ na íntegra — ADRs já foram aplicados nas fases 02/04/06.
- Workspaces irmãos.

## Read order

1. L0 — {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/CLAUDE.md
2. L1 — {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/CONTEXT.md
3. L2 — este arquivo
4. review-report.md (confirma sem P0/P1, aprovação humana registrada)
5. .git/config (remotes, base_branch)
6. Sumário finishing-branch-200tok

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
7. **Atualizar L1:** `sub_stage: "07_completed"`, `status: COMPLETED`. Append `history` evento `stage_transition` `from: 06_completed` `to: 07_completed` com `commit_sha` do merge/tag/PR. Commit atômico.
8. **Gate humano final:** humano confirma o merge-report. Workspace fica em `status: COMPLETED` e arquivado. Fase 08 só roda se humano disparar manualmente depois.

## Outputs

- `output/merge-report.md` — relatório do merge: decisão A/B/C, comandos executados, commit_sha resultante (merge commit / PR URL / tag), estado do CI pós-merge.

## Sub_stage transitions

Enum válido: `07_in_progress`, `07_completed`.

Transição IN_PROGRESS → COMPLETED dispara quando:
- `output/merge-report.md` existe.
- Decisão humana A/B/C executada com sucesso (commit_sha registrado em merge-report).
- Humano confirmou via gate.

`next_stage: null` — estágio 07 é o último estágio do ciclo principal. Não há transição automática para 08; a fase 08 é disparada manualmente pelo humano em sessão futura.

## Status canônicos disponíveis neste estágio

- `IN_PROGRESS` — preparando merge, aguardando escolha humana A/B/C.
- `COMPLETED_AWAITING_HUMAN` — merge-report escrito, humano confirma fechamento do workspace.
- `BLOCKED_STOP_POINT` — `irreversible` ou `prod_migration` disparou; menu A/B/C aguardando resposta.
- `BLOCKED_ERROR` — review-report indicava P0/P1, working tree sujo, rebase falhou, ou push rejeitado.
- `COMPLETED` — workspace fechado; ciclo principal encerrado.

## Stop points aplicáveis

Catálogo canônico em `references/stop-points-canonical.md`. IDs disparáveis no estágio 07 merge:

- `irreversible` — operação destrutiva (force-push em branch compartilhada, drop em prod, rotação de credencial sem grace-window). Sempre `hard`.
- `prod_migration` — migration de schema com dados em produção (DDL bloqueante, mudança de tipo invalidando linhas existentes). Sempre `hard`.

Disparo: agente pausa, escreve menu A/B/C no output, atualiza L1 `status: BLOCKED_STOP_POINT`. Humano responde, sessão retoma com `IN_PROGRESS`.

## Skill superpowers de referência

Sumário 200tok (consulta obrigatória):

- `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/superpowers-summary/finishing-branch-200tok.md`

Skill formal (escape hatch): `superpowers:finishing-a-development-branch`.

## Gates

- **Humano:** escolhe A/B/C no menu de merge; confirma o merge-report ao final.
- **Automático (CI):** pre-commit hook valida atomicidade L1↔outputs e prefixo de commit `workspace/{{WORKSPACE}}`. Pós-merge, CI da `base_branch` valida o estado integrado.
- **Aprovação para transitar:** humano confirma merge-report; sub_stage vira `07_completed` e `status: COMPLETED` no commit que registra a confirmação.

## End of stage handoff (1-stage-1-sessão)

**Stage 07 terminal:** NÃO gera `_kickoff.md` para stage 08. Stage 08 (feedback intake) é manual: humano dispara depois de uso real, não automaticamente.

Final do stage 07:
- L1: `status = COMPLETED`, `sub_stage = 07_completed`
  - `last_transition.from = 07_in_progress`
  - `last_transition.to = 07_completed`
  - `last_transition.at = <ISO 8601 UTC now>`
  - `history` append: `{at, event: "stage_transition", from, to, commit_sha, note}`
- Commit atômico (pre-commit hook valida outputs↔L1; commit-msg valida prefix):
  ```
  workspace <NNN>: stage 07 completo (workspace COMPLETED)
  ```
  Files no commit: `output/merge-report.md` + L1.
- Print pro user:
  ```
  ✅ Workspace <NNN-slug> COMPLETED.

  Próximos passos opcionais:
  - Após uso real, dispare manualmente: /xp-icm-workflow feedback <NNN>
    (cria sessão stage 08 feedback intake)
  - Caso contrário, workspace fica em estado COMPLETED.
  ```
- Branch workspace pode ser arquivada (vide R3.4 do plan).
- SAIR da sessão.

Detalhes em `<skill_root>/references/session-handoff-protocol.md`.
