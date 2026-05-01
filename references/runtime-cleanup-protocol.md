# Runtime Cleanup Protocol — v3.7.0

> Protocolo canônico de cleanup de side-effects runtime ANTES de transição
> de saída fase 08 (A close, B restart, C spawn). Strict universal — todos
> tiers passam pelo checklist sem opt-out. Detector + decisão humana, NUNCA
> ação destrutiva automática.

---

## Por que existe

Pre-v3.7.0, side-effects órfãos eram problema recorrente: dev servers
continuavam rodando após workspace fechado, branches `wave-NNN-*`
permaneciam órfãs, containers Docker ficavam pendurados, `.icm-main/` ficava
dirty entre transições. Recovery wizard v3.6.0 introduziu `DEV_SERVER_ORPHAN`
+ `CDP_DISCONNECTED` mas eram detect-after-fact (próxima sessão pegava
estado inconsistente, não pré-transição).

v3.7.0 fecha lacuna: fase 08 saída A/B/C **bloqueia** transição até
checklist runtime confirmado clean (ou humano explicitar skip via stop point
#13 com consequências documentadas).

---

## Princípios

1. **Skill detecta, humano decide.** ICM nunca mata processo, deleta branch
   ou força cleanup automaticamente. Toda ação destrutiva requer decisão
   humana explícita per categoria.

2. **Strict universal.** Aplicável em todos tiers (`experimental` →
   `production`). Sem opt-out por tier — diferente de TDD (calibrado por
   tier).

3. **Per-categoria, não global.** Humano confirma cada categoria
   separadamente (não 1 confirm "tudo limpo?"). Reduz risco de skip
   acidental quando 1 categoria foi missada.

4. **Idempotente.** Re-rodar checklist = mesmo resultado. Items resolvidos
   não voltam à lista.

5. **Status reportado em intake-report.md.** Section §"Runtime cleanup
   pré-saída (v3.7+)" registra snapshot final + decisões humanas (skip
   explícito vs resolvido).

---

## 6 categorias canônicas

| # | Categoria | Detector | Cleanup default | Override humano |
|---|---|---|---|---|
| 1 | `dev_servers` | runtime-registry kind=dev_server alive | `kill <pid>` + unregister | skip = warning, deferido |
| 2 | `background_tasks` | kind=background_task alive | mesmo | mesmo |
| 3 | `docker` | `docker ps --filter label=icm-workspace=NNN` | `docker stop <id>` (humano roda) | skip = warning |
| 4 | `wave_branches` | `git branch --list wave-NNN-*` | `git branch -D <branch>` (humano roda) | skip = leftover histórico |
| 5 | `working_tree` | `git status --short` no project_root | humano commita ou stash | skip = não permitido |
| 6 | `untracked` | `.icm-main/` dirty + ls-files --others | humano commita ou ignora | skip = warning |

**Categoria 5 (working_tree) é especial:** dirt em working tree workspace
branch causa confusão pre-merge fase 07 (já resolvida) ou indica edits
não-rastreados. Skip não-permitido — humano DEVE commitar/stash antes de
fechar fase 08.

---

## Fluxo canônico

### Entry hook fase 08

```
[stage 08, sub_stage=08_in_progress, status=COMPLETED_AWAITING_HUMAN]

  Sessão sintetiza checklist:
  python <skill>/scripts/runtime-status.py \
      --workspace-root <ws> --project-root <pr> --format text

  Output exemplo:
  ✓ dev_servers: no dev servers
  ✗ background_tasks: 1 background task(s) alive
  ✓ docker: no containers
  ✗ wave_branches: 2 wave branch(es) órfãs
  ✓ working_tree: clean
  ✗ untracked: .icm-main dirty: 3 entry(ies)

  Per categoria não-clean:
    Imprime detalhes (PIDs, branches, paths).
    Aguarda humano: "[s] resolvi [n] cancela fase 08 [edit] descreva".

  Re-run até todas clean OU humano cancela (#13 stop point).
```

### Per-OS quirks

**Windows:**
- Kill processo: `taskkill /PID <pid> /F`
- Status processo: ctypes `OpenProcess` + `GetExitCodeProcess`
- Docker Desktop: requer service rodando; daemon down = "assumed clean".

**POSIX (Linux/macOS):**
- Kill processo: `kill <pid>` (SIGTERM) ou `kill -9 <pid>` (SIGKILL)
- Status processo: `os.kill(pid, 0)` (não envia sinal)
- Docker: `docker ps` requer daemon running; `docker stop --time 10`
  graceful shutdown.

`runtime-registry.py:_is_pid_alive` cobre ambos OSes via lazy detection.

---

## Recovery se cleanup falha mid-saída

Cenários e plano:

| Falha | Plan |
|---|---|
| `kill <pid>` retorna erro de permissão | sugere `kill -9` ou humano roda como root |
| Branch protected (push restriction) | sugere `git config branch.<name>.allowDeletion true` |
| Docker daemon down | warning "assumed clean", anota em intake-report |
| Comando timeout (>30s) | retry 1x, depois marca como skip + warning |
| Humano fecha terminal mid-checklist | sub_stage permanece `08_in_progress`; próxima sessão re-roda checklist (idempotente) |

Falhas técnicas vs cancelamento humano:
- **Falha técnica** (comando errou) → Plan A retry, depois stop point #13
- **Cancelamento humano** (responde [n]) → stop point #13 imediato
  + status `BLOCKED_STOP_POINT`

Stop point #13 menu A/B/C:
- `[a]` resolvi manualmente, retoma checklist
- `[b]` skip categoria + segue saída (workspace fica inconsistente; recovery
       wizard detecta depois)
- `[c]` cancela fase 08 (status volta `COMPLETED_AWAITING_HUMAN`)

---

## Integração com runtime-registry

Categorias 1-2 (dev_servers, background_tasks) consultam
`workspaces/<NNN>/_state/runtime-registry.json`. Entries com PID morto
NÃO marcam categoria como dirty (registry stale, sem side-effect ativo) —
mas geram entry pra cleanup de registry via
`runtime-registry.py purge-dead`.

Migração v3.6.0 → v3.7.0: workspaces antigos com `.icm-main/.dev-server.pid`
devem rodar `migrate-workspace.py --workspace-root <ws>` antes do primeiro
checklist (move PID file → registry, idempotente).

---

## Override em tier=experimental?

**Não.** Decisão de design (v3.7.0): strict universal aplicado a todos
tiers, incluindo `experimental`. Justificativa:

- Experimental = POC/spike, mas processos órfãos custam memória + portas
  conflict no próximo bootstrap.
- Atrito do checklist é baixo: 6 categorias, geralmente <30s humano.
- Override por tier abriria precedente complexo (quais tiers? quais
  categorias?). Strict universal mantém regra simples.

Quem realmente quer skip: usar `[b]` no menu stop point #13 (deferred
cleanup, aceita workspace inconsistente).

---

## Cross-refs

- Stage 08 L2 template: `templates/workspace/stages/08_feedback_intake/CONTEXT.md.tpl` §"Runtime Cleanup Checklist"
- Stop point #13: `templates/_config/stop-points.md` §"13. runtime_cleanup_failed"
- Recovery wizard: `references/recovery-wizard.md` (RUNTIME_REGISTRY_STALE detector)
- Runtime registry: `scripts/runtime-registry.py` (CRUD + legacy detect)
- Runtime status: `scripts/runtime-status.py` (checklist agregador)
- Migration: `scripts/migrate-workspace.py` (legacy PID → registry)
- L0 R10: `templates/workspace/CLAUDE.md.tpl` §"Runtime side-effects"
