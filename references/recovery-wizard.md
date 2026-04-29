# Recovery Wizard

> Detecção e reconstrução de workspaces ICM em estado inconsistente. Disparado em pre-flight check de sessão NOVA (humano explicitamente retomando), nunca por timer/cron.

> **Path resolution:** todos os caminhos `scripts/` neste documento referem-se ao diretório `<SKILL_DIR>/scripts/`, onde `SKILL_DIR` está definido em L0 (`CLAUDE.md`). Em contexto de workspace, use o path absoluto `${SKILL_DIR}/scripts/<script>`.

## Quando dispara

`<SKILL_DIR>/scripts/recovery-wizard.py` é invocado:

1. **Bootstrap** detecta `<project_root>/workspaces/NNN-slug/` JÁ existente — pode ser retomada legítima ou estado órfão.
2. **Pre-flight de cada sessão** (Q1.1) — antes de carregar L2, valida L1 via `${SKILL_DIR}/scripts/validate-state.sh`. Heurísticas R2.7 → dispara wizard.

NUNCA dispara: cron, timer, agente em loop, sessão mid-flight.

## Inconsistências detectadas (R2.7 + R4.5 + R6.6 + G5)

| Code | Severidade | Causa | Detecção |
|---|---|---|---|
| `HASH_MISMATCH` | warning | `_config/profile-effective.yaml` editado fora do bootstrap | sha256 recomputado vs `profile_effective_hash` em L0 |
| `MISSING_OUTPUT` | warning | output declarado em `history` ausente no FS | regex `stages/\d{2}\w*/output/.+\.md` em items de history; check existe |
| `STALE_IN_PROGRESS` | warning | sessão crashou ou foi abandonada | `status: IN_PROGRESS` E sem commit em `workspaces/NNN/*` últimas 24h |
| `MISSING_COMMIT` | critical | merge/force push eliminou o commit referenciado | `git cat-file -e <last_transition.commit_sha>` falha |
| `BRANCH_MISSING` | critical | humano deletou `workspace/NNN-slug` | `git branch --list workspace/NNN-slug` vazio |
| `BOOTSTRAP_PARTIAL` | critical | bootstrap crashou entre scaffold commit e hook install | workspace dir existe E scaffold commitado E hooks ausentes em `.git/hooks/` |
| `CLAUDE_MD_ROOT_STALE` | warning | sessão crashou sem chamar `handoff.update_project_claude_md` | bloco do workspace em `<project_root>/CLAUDE.md` (região ICM) tem `stage_atual` ≠ `L1.stage_atual` |
| `CLAUDE_MD_ROOT_MISSING` | warning | bloco removido manualmente, ou bootstrap pre-v3.1 | `L1.status=IN_PROGRESS` mas comentário `<!-- ICM-WORKSPACE:NNN-slug -->` ausente |
| `WORKTREE_MISSING` (v3.4.0) | critical | `.icm-main/` worktree linkada removida ou não criada | `<project_root>/.icm-main/` ausente |
| `WORKTREE_WRONG_BRANCH` (v3.4.0) | warning | worktree foi switched para outra branch manualmente | `git rev-parse --abbrev-ref HEAD` em `.icm-main/` ≠ `base_branch` |
| `WRONG_BRANCH_CHECKOUT` (v3.4.0) | warning | humano abriu sessão sem ativar workspace branch | `<project_root>` checkado em branch ≠ `workspace_branch` enquanto status ≠ COMPLETED |
| `KICKOFF_WITHOUT_GATE` (v3.4.2) | warning | sintoma do bug pre-v3.4.2 — sessão renderizou kickoff sem aguardar gate | `_kickoff.md` em `stages/<NN+1>/_kickoff.md` existe AND L1 declara `stage_atual=NN, status=COMPLETED_AWAITING_HUMAN, sub_stage=NN_completed` |

## Ações por inconsistência

| Code | A (preserve) | B (rollback) | C (escalate) |
|---|---|---|---|
| `HASH_MISMATCH` | recompute hash + atualiza L0/L1 | restaura `_config/profile-effective.yaml` do último commit | mark `BLOCKED_ERROR` |
| `MISSING_OUTPUT` | append `recovery_warning` em history (preserva append-only) | rollback ao `last_transition` antes do output sumir | mark `BLOCKED_ERROR` |
| `STALE_IN_PROGRESS` | append `recovery_applied` em history + status `COMPLETED_AWAITING_HUMAN` | mesmo que A | mark `BLOCKED_ERROR` |
| `MISSING_COMMIT` | rollback `last_transition` pro penúltimo válido em history | mesmo que A | mark `BLOCKED_ERROR` |
| `BRANCH_MISSING` | append `recovery_warning` com sugestão `git reflog \| grep workspace/NNN` | mesmo que A | mark `BLOCKED_ERROR` (manual) |
| `BOOTSTRAP_PARTIAL` | instalar hooks via `git-hook-installer.sh` + `context-check.sh` | rollback: `git reset --soft HEAD~1` e re-executar bootstrap | mark `BLOCKED_ERROR` |
| `CLAUDE_MD_ROOT_STALE` / `CLAUDE_MD_ROOT_MISSING` | regerar bloco a partir de L1 (chama `handoff.update_project_claude_md`) | mesmo que A | mark `BLOCKED_ERROR` |
| `WORKTREE_MISSING` (v3.4.0) | rodar `git worktree add .icm-main <base_branch>` | n/a (sempre A) | mark `BLOCKED_ERROR` |
| `WORKTREE_WRONG_BRANCH` (v3.4.0) | `cd .icm-main && git checkout <base_branch>` | n/a | mark `BLOCKED_ERROR` |
| `WRONG_BRANCH_CHECKOUT` (v3.4.0) | `git -C <project_root> checkout <workspace_branch>` | n/a | mark `BLOCKED_ERROR` |
| `KICKOFF_WITHOUT_GATE` (v3.4.2) | aprovar gate retroativamente: transita L1 pra `stage_atual=NN+1`, mantém kickoff já gerado | deleta `_kickoff.md` + volta `sub_stage=NN_in_progress` (workspace continua trabalhando no stage NN) | mark `BLOCKED_ERROR` |

**Múltiplas inconsistências:** wizard agrupa por código e aplica em batch na ordem canônica:

```
HASH → BOOTSTRAP_PARTIAL → MISSING_COMMIT → MISSING_OUTPUT → STALE → BRANCH_MISSING
```

Cada apply faz append em `history`:

```yaml
- at: "<now ISO 8601>"
  event: "recovery_applied"
  note: "wizard fix: <codes>"
  context:
    plan: "A"
    inconsistencies_found: ["HASH_MISMATCH", "STALE_IN_PROGRESS"]
```

## CLI

```bash
# Audit only (sem modificar)
python <SKILL_DIR>/scripts/recovery-wizard.py --workspace <path> --dry-run

# Interactive: imprime plano, lê stdin pra escolha A/B/C
python <SKILL_DIR>/scripts/recovery-wizard.py --workspace <path>

# Não-interactive: aplica plan direto
python <SKILL_DIR>/scripts/recovery-wizard.py --workspace <path> --apply A
```

**Exit codes:**

- `0` — workspace consistente OU recovery aplicado com sucesso OU dry-run completo (mesmo com inconsistências).
- `1` — workspace path inválido OU recovery falhou OU choice inválido (`--apply Q`).

## UX exemplo (interactive)

```
$ python <SKILL_DIR>/scripts/recovery-wizard.py --workspace ~/projects/aura/workspaces/042-feat-auth

🔍 Workspace: 042-feat-auth
🔍 Inconsistências detectadas: 2

  [warning] HASH_MISMATCH
    Mensagem: profile_effective.yaml editado fora do bootstrap.
              hash em L0 (9f3a8b2c...) ≠ hash recomputado (7c4e1d09...).
    Ação A: recompute hash + atualiza L0/L1
    Ação B: restaura _config/profile-effective.yaml do último commit
    Ação C: mark BLOCKED_ERROR + escala humano

  [warning] STALE_IN_PROGRESS
    Mensagem: status=IN_PROGRESS sem commit em workspaces/042-feat-auth/*
              nas últimas 24h (último: 2026-04-23T14:30:00Z).
    Ação A: append recovery_applied + status=COMPLETED_AWAITING_HUMAN
    Ação B: mesmo que A
    Ação C: mark BLOCKED_ERROR

Escolha plano (A/B/C): A
✅ Aplicado plan A em 2 inconsistências.
   - HASH_MISMATCH: hash atualizado em L0 (9f3a... → 7c4e...)
   - STALE_IN_PROGRESS: status=COMPLETED_AWAITING_HUMAN
   history append: recovery_applied (codes=[HASH_MISMATCH, STALE_IN_PROGRESS])

Próximo: revisar L1 e prosseguir ou abrir issue se algo parecer errado.
```

## Anti-patterns documentados

### Reflog retention (R5.5)

`git reflog` mantém referências ~90 dias por default. Workspace branch deletada > 90 dias = state perdido permanente. **Sem workaround built-in.**

Se humano deletou `workspace/NNN-slug` mas reflog ainda tem:

```bash
git reflog | grep workspace/NNN-slug
# achou: a1b2c3d HEAD@{42}: branch: deleted workspace/042-feat-auth
git branch workspace/042-feat-auth a1b2c3d
```

Wizard NÃO faz isso automaticamente — risco de mascarar perda intencional. Sugere comando, humano executa.

### Não bypass o pre-commit hook

Wizard sempre commita via flow normal. NUNCA `git commit --no-verify`. Se hook bloqueia o recovery commit, wizard reporta erro pra humano resolver — não bypass.

### Não recria branch automaticamente

`BRANCH_MISSING` plan A só sugere reflog comando. Auto-recreate poderia mascarar:
- Branch deletada intencionalmente porque workspace é lixo.
- Reflog inconsistente entre máquinas (push/clone perde reflog local).
- Nova branch criada do sha errado (sem entender history original).

Humano decide.

## Schema da resposta `Inconsistency`

```python
@dataclass(frozen=True)
class Inconsistency:
    code: str        # "HASH_MISMATCH" | "MISSING_OUTPUT" | "STALE_IN_PROGRESS"
                     # | "MISSING_COMMIT" | "BRANCH_MISSING" | "BOOTSTRAP_PARTIAL"
    message: str     # mensagem humana específica
    proposed_action: str  # ação A sugerida em prosa curta
    severity: str    # "critical" | "warning"
    context: dict    # campos auxiliares: paths, shas, timestamps, etc.
```

## Integration com outros componentes

| Componente | Como interage |
|---|---|
| `<SKILL_DIR>/scripts/validate-state.sh` | Pre-flight call. Falha → dispara wizard. |
| `<SKILL_DIR>/scripts/bootstrap.sh` | Detecta workspace dir existente → invoca wizard antes de criar novo. |
| Pre-commit hook | Wizard NÃO bypass. Recovery commits passam pelo hook normal. |
| L1 history | Wizard SEMPRE append `recovery_applied` ou `recovery_warning`. |
| `references/state-machine-schema.md` | Wizard respeita schema canônico em qualquer modificação. |

## Edge cases

| Caso | Comportamento |
|---|---|
| Workspace consistente + `--dry-run` | exit 0 + "workspace consistent" |
| Workspace consistente + `--apply A` | no-op silencioso + exit 0 |
| Path workspace inexistente | exit 1 + mensagem `workspace not found at <path>` |
| L1 yaml malformado | exit 1 + mensagem específica do `validate-state.sh` |
| Múltiplos inconsistências + `--apply A` | aplica todos em batch ordem canônica |
| `--apply Q` (choice inválido) | exit code != 0 (argparse reject) |

## Tests

- Unit: `tests/unit/test_recovery_wizard.py` — 28 tests cobrindo detect + apply + CLI determinístico
- E2E: `tests/e2e/recovery_orphan.bats` — fixture + apply + verify (CI-only)
- Fixture: `tests/fixtures/workspace_orphan/` — L1 stale + outputs + missing commit

Coverage atual: 73% (caminhos B menos exercitados; aceito como design — humano raramente escolhe rollback).
