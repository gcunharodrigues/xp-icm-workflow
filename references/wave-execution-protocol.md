# Wave Execution Protocol — Stage 04 (Canonical)

> Doc canônico do ciclo wave em stage 04. Consolida protocol disperso entre L2 template e references. Source of truth — outros docs apontam pra cá.

## Resumo (1 parágrafo)

Stage 04 = N waves sequenciais. Cada wave = 1 lead session. Lead spawna subagentes via `Agent(isolation: "worktree")`, um por task da wave (até cap por tier 2/3/5/5). Subagente trabalha em worktree efêmera isolada na branch `wave-<NNN>-<N>/<task-slug>`. Após COMPLETE de todos: wave-reviewer audita, lead merge sequencial em `BASE_BRANCH` (ordem do plan), CI global, cleanup, handoff. Mid-wave handoff automático; última wave gate humano.

## Atores

| Ator | Sessão | CWD | Branch | Função |
|------|--------|-----|--------|--------|
| Lead | 1 (toda a wave) | `{{PROJECT_ROOT}}` | `workspace/{{WORKSPACE}}` | Orquestra, gerencia state L1, faz merge |
| Subagente N | Spawnado pelo lead via Agent | Worktree efêmera | `wave-<NNN>-<N>/<task-slug>` | TDD 7 passos, escreve task report |
| Wave-reviewer | Spawnado pelo lead via Agent (sem worktree) | Lead CWD | `workspace/{{WORKSPACE}}` | Audita Auto-QA, files touched, acceptance |
| Humano | Async (gate inline) | — | — | Aprova última wave, resolve conflicts, responde stop points |

## Branches durante wave

```
main (= BASE_BRANCH)         ← estável, lead faz merge aqui
  └─ workspace/<NNN-slug>     ← lead trabalha (state files L1/L2, outputs)
       └─ wave-<NNN>-<N>/<slug-1>  ← subagente 1 (worktree efêmera)
       └─ wave-<NNN>-<N>/<slug-2>  ← subagente 2
       └─ ...
```

## Pipeline (12 passos)

1. **Pre-flight** — lead lê wave-plan.md, identifica wave atual, grava `pre_wave_sha` em L1 history.
2. **Spawn** — lead cria branches + invoca `Agent(isolation: "worktree")` paralelo (multi tool-use).
3. **Canal 2** — lead injeta ADR subset + lessons + design subset (se frontend) no prompt do Agent.
4. **TDD 7 passos** — subagente em worktree: RED → GREEN → CI 1ª → REFACTOR → CI 2ª → Auto-QA → COMPLETE.
5. **Stop points** — subagente detecta `new_dep`/`irreversible`/`over_eng`/`prod_migration`/`adr_drift` → menu A/B/C.
6. **Cap 3 voltas auto-QA** — `qa_loops_used` no task report; reviewer audita.
7. **Lead recebe** — Agent results bufferizados em `{task_slug: result}`; sort por plan order.
8. **Wave-reviewer** — Agent sem worktree, lê via `git show`/`git diff`; aprova ou flagra issues.
9. **Merge sequencial** — `git merge --no-ff` em `BASE_BRANCH`, ordem do plan; conflict → `conflict-resolution-protocol.md`.
10. **CI global** — verde → 11; vermelho → `ci-rollback-protocol.md`.
11. **Cleanup** — `git worktree remove` (decision matrix `--force`) + `git branch -d` (jamais `-D`); sync `.icm-main` condicional.
12. **Handoff** — mid-wave automático ou última wave gate humano (ver L2 § End of stage handoff).

## Status canônicos

- `IN_PROGRESS`
- `COMPLETED_AWAITING_HUMAN` (última wave)
- `BLOCKED_STOP_POINT`
- `BLOCKED_ERROR` (merge conflict, CI red, cap 3 voltas, cleanup unsafe)
- `BLOCKED_HITL` (wave mista, task HITL pendente)

## Cross-references

- Conflict de merge: `references/conflict-resolution-protocol.md`
- CI global vermelho: `references/ci-rollback-protocol.md`
- AGENT-BRIEF render: `references/agent-brief-template.md` + `scripts/agent-brief-render.py`
- Stop points: `references/stop-points-canonical.md`
- Diagnose: `references/diagnose-protocol.md`
- Handoff: `references/session-handoff-protocol.md`
- HITL: `references/task-types-hitl-afk.md`
- L2 stage 04 (instruções runtime): `templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl`

## Invariantes globais

- Lead sempre em `workspace/<NNN-slug>` durante wave inteira.
- Subagentes nunca leem outros workspaces.
- Branches wave nascem de `BASE_BRANCH`, NÃO de workspace branch.
- Merge sequencial usa ordem do plan, não ordem de retorno do Agent.
- `pre_wave_sha` capturado em L1 history pra rollback.
- Wave branches deletadas SÓ após merge bem-sucedido + CI verde + cleanup.
- Cleanup `--force` SÓ com `auto_qa_passed: true` no task report.
