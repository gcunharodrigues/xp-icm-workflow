# xp-icm-workflow

Skill de orquestração de projetos via filesystem (ICM). v3.7.0 — runtime cleanup + spawn-pending handoff + drift hardening.

![tests](https://img.shields.io/badge/tests-781%20passed-brightgreen)
![coverage](https://img.shields.io/badge/coverage-83%25-brightgreen)
![python](https://img.shields.io/badge/python-3.11%2B-blue)
![version](https://img.shields.io/badge/version-v3.7.0-blue)

> Quando publicada como repo GitHub, substituir os badges acima por
> `[![tests](https://github.com/<user>/xp-icm-workflow/actions/workflows/test-skill.yml/badge.svg)](...)` etc.

## O que faz

Bootstrap one-shot que cria estrutura ICM (L0/L1/L2/L3) num projeto e SAI. A partir daí o filesystem governa o ciclo — sessões novas leem L0+L1+L2 do estágio atual e trabalham. 9 estágios (00 recon → 08 feedback intake), 11 profiles × 4 tiers calibrando rigor, subagentes via Agent Tool na fase 04 (paralelismo via `Agent(isolation: "worktree")` — worktree efêmera por task), Wave Planner determinístico + LLM review subagent, Recovery Wizard pra workspaces órfãos.

## Setup

```bash
pip install -r requirements.txt
bash scripts/check-runtime.sh
bash tests/run.sh
```

## Uso

```bash
# Em qualquer projeto:
/xp-icm-workflow profile=app_web_backend tier=development
```

Detalhes em `references/`. Walkthrough E2E em `references/example-run.md`.

## Documentos chave

| Doc | Conteúdo |
|---|---|
| `SKILL.md` | Entrada da skill |
| `references/state-machine-schema.md` | Schema L1 + sub_stage enum |
| `references/stage-templates.md` | Schema canônico dos 9 L2 templates |
| `references/stop-points-canonical.md` | 15 stop points + thresholds por tier |
| `references/runtime-cleanup-protocol.md` | Checklist 6 categorias pré-saída fase 08 (v3.7.0) |
| `references/spawn-handoff-protocol.md` | `.icm/spawn-pending.json` + `--spawn-from` arg (v3.7.0) |
| `references/preview-loop-protocol.md` | Build-iterate visual + dev server registry (v3.6.0/v3.7.0) |
| `references/design-system.md` | DESIGN.md format frontend/fullstack |
| `references/4-block-contract-template.md` | 4-block + ciclo TDD 7 passos + Akita 15-item |
| `references/wave-planner-algorithm.md` | DAG + LLM review subagent |
| `references/subagent-protocol.md` | Spawn via Agent tool + mid-wave reduce |
| `references/feedback-intake-fase08.md` | 3 saídas A/B/C |
| `references/recovery-wizard.md` | 6 inconsistências + reconstrução |
| `references/superpowers-mapping.md` | Estágio ↔ skill superpowers ↔ sumário 200tok |
| `references/xp-workflow-integration.md` | Quando usar /xp-workflow vs /xp-icm-workflow |
| `references/example-run.md` | E2E concreto 9 sessões |
| `references/smoke-manual-checklist.md` | 10 itens pré-release v3.0.0 |
| `references/changelog.md` | Versões |
| `references/git-hooks.md` | Pre-commit hook regras |
| `references/worktree-model.md` | Worktree paralelo `.icm-main/` (v3.4.0) — modelo cross-branch canônico |
| `system-requirements.md` | Runtime + permissions allowlist |

## Tests

```bash
bash tests/run.sh             # pytest + bats (se disponível)
bash tests/run.sh --ci        # coverage XML para CI
bash tests/run.sh --no-bats   # só pytest, skip bats
```

CI: `.github/workflows/test-skill.yml` — Ubuntu runner com Python 3.13 + bats.

## Arquitetura em camadas

| Camada | Conteúdo | Path típico |
|---|---|---|
| L0 | Identidade imutável do workspace | `workspaces/NNN/CLAUDE.md` |
| L1 | State machine (frontmatter YAML) | `workspaces/NNN/CONTEXT.md` |
| L2 | Instruções do estágio atual | `workspaces/NNN/stages/<NN>/CONTEXT.md` |
| L3 | Conventions, sumários superpowers, runtime refs | `workspaces/NNN/_config/`, `_references/` |
| L4 | Outputs nascentes (discovery.md, plan.md, etc.) | `workspaces/NNN/stages/<NN>/output/` |

## Versão

v3.7.0 — runtime cleanup obrigatório pré-saída fase 08 + spawn-pending handoff zero-friction + drift detector hardened + migration encadeada v3.3→v3.7. Versão canônica: `scripts/bootstrap.py:SKILL_VERSION`. Histórico completo em `references/changelog.md`.

## v3.7.0 — Runtime cleanup + spawn-pending handoff

10 mudanças concretas:

- **Runtime checklist obrigatório** (strict universal todos tiers) antes saída A/B/C fase 08. 6 categorias: dev_servers, background_tasks, docker, wave_branches, working_tree, untracked. Detector via `scripts/runtime-status.py`; humano confirma per categoria.
- **Runtime registry** (`scripts/runtime-registry.py`) substitui `.icm-main/.dev-server.pid` ad-hoc da v3.6.0 por JSON estruturado em `workspaces/<NNN>/_state/runtime-registry.json` (gitignored). Cross-platform PID liveness (POSIX `os.kill` / Windows `ctypes.OpenProcess`).
- **Spawn handoff via `.icm/spawn-pending.json`** (gitignored): saída C escreve schema completo (spawn_from, agent_brief estruturado 4 blocos, intake_report cross-branch path, proposed profile/tier/name, intake_commit_sha). Bootstrap próxima sessão auto-detecta + propõe + unlinka. Fallback explícito `--spawn-from <slug>` arg.
- **handoff.py outcome-aware idle render**: bug pre-v3.7.0 que hardcoded "Saída A" mesmo em saída C — agora `--outcome {A,C}` + `--spawn-to`.
- **Migration encadeada** (`scripts/migrate-workspace.py`): floor v3.3.0, encadeia v3.3→v3.4→v3.5→v3.6→v3.7. Trigger híbrido (COMPLETED auto-prompt; IN_PROGRESS warning-only). Backup automático.
- **Recovery wizard tipo novo** `RUNTIME_REGISTRY_STALE` (14º entry CANONICAL_ORDER): detecta entries com PID morto, sugere `purge-dead`.
- **Pre-commit hook block** `workspaces/*/_state/` (privacy guard: PID/port leak em commits/PRs públicos).
- **Stop point novo #15** (refs) / **#13** (template) `runtime_cleanup_failed` — strict universal, menu A/B/C específico (resolvi / skip + warning / cancela fase 08).
- **L0 R10 nova**: runtime side-effects = responsabilidade humana. Skill detecta + imprime checklist + aguarda confirmação. Nunca mata processo automaticamente.
- **Drift detector hardened**: `PROFILE_COUNT_PARENS_RE` + `PROFILE_COMBO_RE` pegam formatos missados pelo regex original. Sweep SKILL.md (10→11 profiles, 40→44 combos, +fullstack).

Tests: 781 passed (49 novos), zero regressão.

## v3.6.0 — Preview loop (build-iterate visual)

Profile `app_web_frontend` + `fullstack` ganham preview loop opt-in-by-default: dev server lifecycle automático, mock data tier-based, Chrome CDP live em `:9222`, preview pages em `preview/`, verificação tier-aware (`tsc` cada Edit, lint+Playwright wave-end), feedback combo livre (texto/screenshot/URL/HTML), design system cascade threshold 5 componentes, multi-tela sob pedido. Stop points novos `feedback_ambiguous` + `design_system_cascade`. Recovery types `DEV_SERVER_ORPHAN` + `CDP_DISCONNECTED` (legacy v3.6 — v3.7 migra dev server pra runtime-registry). Doc canônico: `references/preview-loop-protocol.md`.

## v3.5.0 — Stage 04 protocol gaps fix

10 gaps de protocolo wave execution (worktrees órfãs, merge order não-determinístico, conflict mid-wave sem retomada, HITL granularidade insuficiente). Drift detector introduzido em `tests/unit/test_no_drift.py`.

## v3.4.0 — Cross-branch worktree model

Workspace branch (`workspace/NNN-slug`) não tem `docs/`, `src/`, `tests/`
no working tree. v3.4.0 introduz worktree linkada permanente
`<project_root>/.icm-main/` (sempre checada na base branch, gitignored)
para resolver visibility cross-branch:

- Read tool funciona direto: `Read .icm-main/docs/decisions/0001-stack.md`.
- Write/commit cross-branch: `cd .icm-main && git add docs/... && git commit ...` cai na base branch atomicamente.
- Subagentes em fase 04 usam `Agent(isolation: "worktree")` para wave branches isoladas; lead permanece em workspace branch.

Doc canônico: `references/worktree-model.md`. Bootstrap automatiza setup.

## v3.3.0 — Patterns adopted from mattpocock/skills

8 patterns adotados (Tier 1 + Tier 2 + dependência) + Design It Twice (T3 promovido):

| Pattern | Doc canônico | Usado em |
|---|---|---|
| Project root CLAUDE.md | `references/project-root-claude-md.md` | bootstrap + handoff (cross-session signaling) |
| AGENT-BRIEF template | `references/agent-brief-template.md` | stage 04 (lead → subagent context injection) |
| Ubiquitous Language | `references/context-format.md` | stage 01 (grilling) → stages 02+ (consume) |
| ADR 3-criteria gate | `references/adr-format.md` | stage 02 (decisions) |
| Diagnose 6-fase | `references/diagnose-protocol.md` | stage 05 fallback (CI fail) |
| HITL/AFK | `references/task-types-hitl-afk.md` | stage 02 (plan) → stage 03 (waves) → stage 04 (lead) |
| Triage state machine | `references/triage-state-machine.md` | stage 08 (feedback intake) |
| OUT-OF-SCOPE kb | `references/out-of-scope-kb.md` | stage 02 (iter>0 check) + stage 08 (wontfix) |
| Design It Twice | `references/design-it-twice.md` | stage 02 (módulos core) |

Future work (Tier 3): Deep modules + deletion test, Git guardrails hook
(production tier), PreToolUse anti-/init durante workspace ativo.

Source: [github.com/mattpocock/skills](https://github.com/mattpocock/skills)
(engineering/triage, engineering/diagnose, engineering/grill-with-docs,
engineering/tdd, engineering/to-issues, engineering/improve-codebase-architecture).
