# Spawn Handoff Protocol — v3.7.0

> Doc canônico do handoff fase 08 saída C → bootstrap próximo workspace.
> Substitui UX H2 da v3.0+ (humano colava comando longo) por arquivo
> `.icm/spawn-pending.json` auto-detectado pelo bootstrap.

---

## Por que existe

Pre-v3.7.0, fase 08 saída C imprimia comando explícito tipo:

```
/xp-icm-workflow project-root=<long-path> spawn_from=NNN-old-slug
```

Humano copiava manualmente. Atrito alto: comando longo, fácil errar
slug, perdia contexto se sessão fechava entre kickoff e bootstrap.

v3.7.0: fase 08 saída C escreve `<project_root>/.icm/spawn-pending.json`
estruturado. Bootstrap próxima sessão **auto-detecta** + propõe valores
+ unlinka pós-sucesso. Zero comando manual no caso comum.

Fallback explícito: `--spawn-from <slug>` arg ainda aceito pra re-spawn
manual ou caso edge sem arquivo pendente.

---

## Schema canônico

`<project_root>/.icm/spawn-pending.json`:

```json
{
  "spawn_from": "001-001-saas-psicologo-mvp",
  "intake_report_path": "workspaces/001-001-saas-psicologo-mvp/stages/08_feedback_intake/output/intake-report.md",
  "intake_report_branch": "workspace/001-001-saas-psicologo-mvp",
  "proposed_workspace_name": "002-e2e-playwright-suite",
  "proposed_profile": "app_web_frontend",
  "proposed_tier": "tool",
  "intake_commit_sha": "abc1234",
  "agent_brief": {
    "por_que_spawn": "Suite E2E precisa cobertura Playwright completa.",
    "escopo_motivador": "Cobrir fluxos críticos: booking, payment, cancel.",
    "heranca_aplicavel": "ADRs 0001-0003 (stack), lessons sobre auth.",
    "nao_quero": "Tests unitários (já cobertos no parent).",
    "notes_livre": ""
  },
  "created_at": "2026-05-01T12:00:00Z"
}
```

### Campos obrigatórios

| Campo | Tipo | Descrição |
|---|---|---|
| `spawn_from` | string | slug workspace parent (NNN-NNN-slug) |
| `intake_report_path` | string | path relativo project_root pro intake-report.md |
| `intake_report_branch` | string | branch git onde reside intake-report |
| `proposed_workspace_name` | string | slug sugerido pro novo workspace |
| `proposed_profile` | string | profile inferido do escopo motivador |
| `proposed_tier` | string | tier inferido |
| `intake_commit_sha` | string | sha do commit fase 08 saída C |
| `agent_brief` | object | brief estruturado (4 campos + notes) |
| `created_at` | string | ISO 8601 UTC |

### `agent_brief` estruturado

| Campo | Conteúdo |
|---|---|
| `por_que_spawn` | Razão do spawn vs restart B (pivot, escopo distinto) |
| `escopo_motivador` | O que o novo workspace deve cobrir |
| `heranca_aplicavel` | ADRs/lessons do parent que se aplicam |
| `nao_quero` | Out-of-scope explícito (evita sobreposição) |
| `notes_livre` | Contexto extra opcional |

Workspace novo (stage 00 recon) consome `agent_brief` no recon-report seed.

---

## Cross-branch read do intake-report

Workspace novo NNN-2 está checked em `workspace/NNN-2`. Diretório
`workspaces/NNN-1/` NÃO existe nessa branch (cada workspace branch só
tem próprio dir). Intake-report mora em branch
`workspace/NNN-1/workspaces/NNN-1/stages/08_feedback_intake/output/intake-report.md`.

Read pattern (documentado em L2 stage 00 do workspace novo):

```bash
git show <intake_report_branch>:<intake_report_path>
```

Exemplo:

```bash
git show workspace/001-001-saas-psicologo-mvp:workspaces/001-001-saas-psicologo-mvp/stages/08_feedback_intake/output/intake-report.md
```

Zero overhead — pattern já usado pra cross-branch reads via `.icm-main/`
em outros stages.

---

## Bootstrap detection flow

```
[bootstrap.py main]

  1. detect_spawn_pending(project_root)
     → lê .icm/spawn-pending.json
     → valida schema (9 campos obrigatórios)
     → retorna dict ou None

  2. resolve_spawn_source(project_root, spawn_from_arg)
     → consolida arquivo + CLI arg:
       - source="none" — nem arquivo nem arg → fluxo normal
       - source="arg"  — só arg → bootstrap usa arg
       - source="file" — só arquivo OU arg matcha → arquivo wins
       - source="conflict" — arquivo+arg de workspaces diferentes

  3. Se source="conflict":
     menu humano [a] usar arquivo (NNN-X) [b] usar arg (NNN-Y) [c] cancela

  4. Se source ∈ {file, arg}:
     - Se file: payload pré-popula --profile, --tier, --workspace-name
     - Humano confirma OU ajusta no menu interativo
     - Bootstrap procede com valores resolvidos

  5. Pós-bootstrap successful:
     consume_spawn_pending(project_root)
     → unlink .icm/spawn-pending.json
     → idempotente (no-op se ausente)
```

---

## Edge cases

### Arquivo presente mas workspace já fechado/aberto

`spawn_from` aponta workspace que já completou ciclo (status COMPLETED).
OK — bootstrap só lê metadados, não modifica parent. Padrão esperado:
parent fechou via fase 08 saída C, escreveu spawn-pending.

### Arquivo presente mas workspace destino já existe

`proposed_workspace_name` já criado em workspaces/NNN-NNN-slug/.
Bootstrap detecta colisão no validate_slug step → menu humano:
- `[a]` cancela bootstrap (resolve manualmente)
- `[b]` propor próximo NNN livre
- `[c]` aceita override (perigo: data loss potencial)

### Arquivo presente entre 2+ máquinas (clone)

`.icm/spawn-pending.json` é gitignored (v3.7.0 GITIGNORE_LINES) —
não viaja entre clones. Trade-off aceito: skill é local-first; humano
em outra máquina precisa disparar fluxo manual `--spawn-from <slug>`.

### Arquivo corrompido (JSON inválido)

`detect_spawn_pending` raise `BootstrapError`. Bootstrap aborta antes de
fluxo principal — humano resolve (deletar arquivo se obsoleto, ou
recriar via fase 08 re-execute).

### Múltiplos arquivos pendentes (impossível por design)

Schema permite só 1 spawn pendente por project_root. Fase 08 saída C
sobrescreve `.icm/spawn-pending.json` se já existe (último wins). Esse
comportamento é intencional: 2 workspaces fechando saída C
sequencialmente, último spawn-pending vence; humano escolhe qual
bootstrap rodar.

---

## Pre-commit hook implications

`.icm/spawn-pending.json` está no `GITIGNORE_LINES` v3.7.0
(`bootstrap.py:67`). Pre-commit hook nunca vê arquivo no staged set —
zero risco de commit acidental.

Caso humano `git add -f` força:
- Path `.icm/...` está fora do whitelist do hook → rejeitado.
- Mensagem orienta: "diretório .icm/ é local-only (handoff transitório)".

---

## Cross-refs

- Bootstrap helpers: `scripts/bootstrap.py` (`detect_spawn_pending`,
  `resolve_spawn_source`, `consume_spawn_pending`,
  `SPAWN_PENDING_REQUIRED_FIELDS`)
- Stage 08 L2: `templates/workspace/stages/08_feedback_intake/CONTEXT.md.tpl` §"Saída C"
- Feedback intake: `references/feedback-intake-fase08.md` §"Saída C — Spawn novo workspace"
- Stage 00 L2 (target consumer): `templates/workspace/stages/00_recon/CONTEXT.md.tpl` §"Registrar herança"
- GITIGNORE_LINES: `scripts/bootstrap.py:67` (`.icm/spawn-pending.json`)
