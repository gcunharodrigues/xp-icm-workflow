# ICM Cleanup Protocol — saída A/C último ativo (v3.7.2)

> **Versão:** v3.7.2
> **Skill:** `xp-icm-workflow`
> **Disparado por:** stage 08 saídas A/C, opt-in com confirmação humano

## Propósito

Reverter estrutura ICM-effemeral (workspace branches, `.icm-main/` worktree, subagent worktrees) pra estado natural pós-projeto. Pós saída A (close último) ou C (spawn último), humano normalmente quer:

1. `<project_root>/` (raiz) refletir código produto, não workspace branch state.
2. Sem worktrees paralelos consumindo disco.
3. Sem branches stale acumulando.

Sem cleanup, humano vê:
- Raiz em `workspace/<NNN>-<slug>` branch (state efêmero).
- `.icm-main/` worktree paralela duplicada na mesma raiz.
- Subagent worktrees órfãs em `.git/worktrees/<task-slug>/`.
- Workspace branch deletável mas não deletada.

## Decisões de design

### D1 — Cleanup é opt-in com confirmação

Default: humano vê menu `[s/n/dry-run]` pós-`/init` em saída A/C. Razão: cleanup é destrutivo (deleta branch + worktrees). Automático sem confirm risca apagar trabalho não-commitado se humano esqueceu de stash.

Alternativa rejeitada: automático em tier=experimental. Complexity > value — opt-in unívoco mais previsível.

### D2 — Implementação em script Python dedicado

`scripts/icm-cleanup.py` ao invés de inline no template. Razões:
- Lógica complexa (pre-checks, ordem importa, fallback `--force`, dry-run).
- Testável determinística (`tests/unit/test_icm_cleanup.py`).
- Reusável fora do template (recovery wizard, manual humano).

### D3 — Pre-checks de segurança

Abort ANTES de qualquer mutação se:
- `project_root` não é git repo.
- Workspace branch tree dirty (uncommitted changes) — salvo `--force`.
- `.icm-main/` worktree dirty — salvo `--force`.

`--force` flag existe mas é destrutiva e marcada perigosa no help.

### D4 — Subagent worktrees stage 04

Worktrees criadas via `Agent(isolation: "worktree")` em wave execution. Path típico fora de `<project_root>` (gerado pelo Claude Code harness). Cleanup detecta via `git worktree list --porcelain`, filtra paths que NÃO são `<project_root>` nem `.icm-main/`. Remove com `--force` (assumindo que branch já foi mergeada ou descartada).

`git worktree prune` final limpa refs stale em `.git/worktrees/`.

### D5 — Saída A vs C vs B

| Saída | Cleanup oferecido? | Razão |
|---|---|---|
| **A** (close) | Sim, se exit 2 (último ativo) | Workspace fechado, sem follow-up — cleanup natural |
| **C** (spawn) | Sim, se exit 2 (último ativo) | Workspace novo será bootstrappado em sessão separada — bootstrap re-cria `.icm-main/` se ausente |
| **B** (restart) | NUNCA | Workspace continua ativo, cleanup destruiria estado em uso |

Em multi-workspace com remanescentes ativos pós saída A/C (exit `0`), cleanup também é skipado — outros workspaces dependem do `.icm-main/`.

## Algoritmo

Sequência (ordem importa):

```
1. Pre-checks (abort se falham)
   - project_root é git repo
   - workspace branch tree limpa
   - .icm-main/ tree limpa

2. Subagent worktrees órfãs
   for wt in git worktree list (≠ project_root, ≠ .icm-main):
       git worktree remove <wt> --force

3. Remove .icm-main worktree (libera base_branch)
   git worktree remove .icm-main
   (fallback: --force se falhou)

4. Checkout base_branch no project_root
   git checkout main
   (agora possível porque .icm-main saiu no step 3)

5. Deleta workspace branch
   git branch -D workspace/<NNN-slug>

6. Prune final
   git worktree prune
```

**Ordem crítica:** `.icm-main/` PRECISA sair antes do checkout no project_root, senão git rejeita "branch already checked out in another worktree".

## CLI

```bash
python scripts/icm-cleanup.py \
    --project-root <path> \
    --workspace <NNN-slug> \
    --base-branch main \
    [--dry-run]   # imprime comandos sem executar
    [--force]     # ignora uncommitted changes (perigoso)
```

Exit codes:
- `0` = sucesso (ou dry-run completo)
- `1` = aborto por pre-check
- `2` = erro de execução de git command

## Edge cases

| Edge case | Comportamento |
|---|---|
| `.icm-main/` ausente (legacy pre-v3.4.0) | Skip step 3, segue normalmente |
| Workspace branch já deletada | Warning + skip step 5 |
| Workspace branch tem commits não-mergeados (saída C — code pode ficar perdido) | Pre-check passa (commits existem), warning visível no print pós-cleanup |
| Project_root já em base_branch | Skip step 4, segue |
| Subagent worktrees ainda têm branches válidas | `--force` em `worktree remove` ignora; branch resta no repo (humano pode `git branch -D` manual) |
| Multi-workspace concorrente (humano abriu 2 sessões) | Cleanup só roda quando `--exit-2-if-last-active` retornou 2; race condition extrema = abort |

## Idempotência

Re-run no mesmo state limpo é no-op:
- Workspace branch ausente → warning + skip
- `.icm-main/` ausente → skip
- Project_root em main → skip checkout
- Sem subagents órfãs → skip
- `git worktree prune` é sempre seguro

Rodar 2× seguidas produz mesmo state final, exit code 0 ambas.

## Recovery wizard integration

Detector novo `STALE_ICM_MAIN_AFTER_CLOSE` (v3.7.2):
- Trigger: `workspaces/.index.md` zero workspaces ativos + `.icm-main/` presente.
- Plan A: oferece invocar `icm-cleanup.py` interativamente.
- Útil pra projetos pré-v3.7.2 que terminaram saída A/C antes do auto-trigger.

## Manual humano

Pós saída A/C, se humano disse `[n]` no menu (skip cleanup) e quer rodar depois:

```bash
python <skill-dir>/scripts/icm-cleanup.py \
    --project-root <project-root> \
    --workspace <NNN-slug> \
    --dry-run     # verifica primeiro
```

Confirma output, depois sem `--dry-run` pra executar.

## Doc relacionados

- `references/worktree-model.md` — modelo `.icm-main/` v3.4.0
- `references/recovery-wizard.md` — detectores + Plan A
- `templates/workspace/stages/08_feedback_intake/CONTEXT.md.tpl` — saídas A/C steps 6-7
- `templates/.claude/hooks/icm-session-check.sh` — SessionStart hook v3.7.1
