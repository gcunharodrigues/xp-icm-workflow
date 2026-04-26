---
name: xp-icm-workflow
description: Bootstrap one-shot que cria estrutura ICM (L0/L1/L2/L3) num projeto e SAI. A partir daí o filesystem governa o ciclo — sessões novas leem L0+L1+L2 do estágio atual e trabalham. Suporta 9 estágios (00 recon → 08 feedback intake), 10 profiles × 4 tiers calibrando rigor, Agent Teams na fase 04 (paralelismo via git worktrees), Wave Planner determinístico + LLM review, e Recovery Wizard pra workspaces órfãos.
type: rigid
---

# xp-icm-workflow v3.0.0-beta1

> **Skill é parteira, não orquestradora.** Bootstrap one-shot cria a estrutura. Filesystem governa o ciclo. Sessões novas leem L0+L1+L2 e trabalham.

> **Base teórica:** Interpretable Context Methodology (VanClief & McDermott, 2025) — substitui orquestração por framework por estrutura de sistema de arquivos. Pastas numeradas representam estágios; arquivos markdown carregam prompts e contexto. Ver `references/icm-paper-summary.md`.

---

## Instruction Priority

1. **User explicit instructions** (CLAUDE.md do projeto, AGENTS.md, mensagens diretas) — sempre vencem.
2. **L0/L1/L2 do workspace** — instruções específicas do projeto/estágio em curso.
3. **Esta skill (`/xp-icm-workflow`)** — só ativa no bootstrap one-shot.
4. **Skills especializadas (superpowers:*)** — sumarizadas em L3 do workspace; invocação real só por escape hatch.
5. **Default system prompt** — perde para 1-4.

---

## When to Use

Invoque `/xp-icm-workflow` para **iniciar** um workspace novo. Casos típicos:

- Projeto novo (greenfield ou existente) com múltiplos estágios + revisão humana entre passos.
- Feature complexa (discovery → design → implementação → review → merge).
- Implementação que se beneficia de paralelismo (Agent Teams na fase 04).
- Quer ver, editar e aprovar artefatos intermediários (L4 outputs por estágio).
- Decisões arquiteturais não-triviais que precisam de menu A/B/C.

## When NOT to Use

- Tarefa trivial de código (1 arquivo, sem decisões, sem testes novos) — use `/xp-workflow` direto.
- Bug fix simples — use `/xp-workflow` direto.
- Refinamento cosmético.
- Continuar workspace existente — abra sessão nova; ela lê L1+L2 e procede sozinha. NÃO re-invoque a skill.

---

## What this skill does (one-shot bootstrap)

```
INPUT  →  Skill invocada com profile + tier + project_root
OUTPUT →  Workspace pronto: estrutura de pastas + L0/L1 preenchidos +
          templates de L2 dos 9 estágios + sumários superpowers + git
          branch criada + pre-commit hook instalado + commit inicial
EXIT   →  Skill SAI. Sessão nova retoma via L1+L2.
```

A skill **não persiste** durante o ciclo. Não é orquestradora. Não invoca outras skills no runtime do projeto. É um *project starter* curto.

---

## Division of Responsibilities

| Quem | Decide / Faz |
|---|---|
| **Humano** | Negócio, escopo, profile/tier inicial, aprovação entre estágios, edição de outputs intermediários, recovery decisions |
| **Skill `/xp-icm-workflow`** | One-shot: cria estrutura ICM + git branch + hook + commit inicial. Sai. |
| **L0** (`workspaces/NNN/CLAUDE.md`) | Identidade imutável: paths absolutos, profile/tier, regras inegociáveis |
| **L1** (`workspaces/NNN/CONTEXT.md`) | State machine única: stage_atual, sub_stage, status, history append-only |
| **L2** (`workspaces/NNN/stages/<NN>/CONTEXT.md`) | Instruções do estágio: read order, outputs esperados, gates |
| **L3** (estável) | Conventions, profile-matrix, stop-points canônicos, sumários superpowers |
| **L4** (outputs nascentes) | discovery.md, plan.md, ADRs, wave-plan.md, reports |

---

## CLI

```bash
/xp-icm-workflow profile=<X> tier=<Y> [project-root=<path>] [workspace-name=<slug>] [logs-root=<path>] [override=<yaml>]
```

**Args resolution (Q9 + L1):**

1. **CLI args** vencem tudo (Q9-A''').
2. **`.icm-profile.local.yaml`** detectado em project_root: prompt humano "usar este?".
3. **Pergunta interativa** menu PT (Q9-A') se faltar.

**Profiles canônicos (10):** `app_web_backend`, `app_web_frontend`, `dashboard`, `data_analysis`, `ml_project`, `agent_ia`, `cli_tool`, `framework_library`, `technical_article`, `experiment`.

**Tiers (4):** `experimental`, `tool`, `development`, `production`.

Detalhes da matriz em `templates/_config/profile-matrix.md` (10 × 4 = 40 combos).

---

## What gets created

```
<project_root>/
├── .git/
│   └── hooks/
│       └── pre-commit              [hook instalado, R2.3+R3.3+R3.10+R5.4]
├── .gitignore                      [updated: .worktrees/ + .icm-profile.local.yaml]
├── workspaces/
│   ├── .index.md                   [registry de workspaces ativos/completados]
│   └── NNN-slug/                   [workspace root]
│       ├── CLAUDE.md               [L0 — identidade imutável]
│       ├── CONTEXT.md              [L1 — state machine única]
│       ├── stages/
│       │   ├── 00_recon/           [L2 templates — Wave 3 da skill popula]
│       │   ├── 01_discovery/
│       │   ├── 02_design/
│       │   ├── 03_wave_planner/
│       │   ├── 04_implementation_waves/
│       │   ├── 05_verification/
│       │   ├── 06_review/
│       │   ├── 07_merge/
│       │   └── 08_feedback_intake/
│       ├── _config/
│       │   ├── profile-effective.yaml  [profile base + override + hash]
│       │   └── profile-matrix.md       [referência humana 10×4]
│       └── _references/
│           ├── runtime/                [protocolos: agent-team, wave-planner, recovery, etc.]
│           └── superpowers-summary/    [10 sumários 200tok cada]
└── .worktrees/                         [criado on-demand pela fase 04]
    └── workspace-NNN/
        └── wave-N/
            └── task-slug/              [git worktree por teammate]
```

**Branches criadas:**

- `<base_branch>` — código real do projeto (geralmente `main`).
- `workspace/NNN-slug` — APENAS state files (`workspaces/NNN-slug/*` + `docs/decisions/*` via exceção). NUNCA toca `src/`.
- `wave-NNN-N/<task-slug>` — código + tests da task. Criada de `<base_branch>`. Lead rebase em `<base_branch>` ao fim da wave.

---

## After bootstrap — what happens next

A skill **sai**. Próximos passos são responsabilidade do humano:

1. **Abrir sessão nova** com Claude no project_root.
2. Sessão lê automaticamente:
   - `workspaces/NNN-slug/CLAUDE.md` (L0, identidade)
   - `workspaces/NNN-slug/CONTEXT.md` (L1, state machine)
   - `workspaces/NNN-slug/stages/<stage_atual>/CONTEXT.md` (L2, instruções do estágio)
3. Sessão executa o estágio conforme L2 instrui.
4. Ao transicionar: atualiza L1 + commit atômico (pre-commit hook valida).
5. Próxima sessão repete o ciclo.

**Recovery:** se sessão crashar mid-estágio → próxima sessão dispara `scripts/recovery-wizard.py` automaticamente via pre-flight check do L2. Detecta 6 tipos de inconsistência (R2.7) e propõe ações.

**Stop points:** 12 stop points canônicos em `_config/stop-points.md` calibrados por tier. Disparo: agente pausa, escreve menu A/B/C, atualiza L1 `status: BLOCKED_STOP_POINT`. Humano responde, sessão retoma.

**Agent Teams (fase 04):** waves de paralelismo via git worktrees. Cap por tier (2/3/5/5). Wave Planner determinístico + LLM review subagent. Detalhes em `_references/runtime/agent-team-protocol.md`.

**Feedback intake (fase 08):** disparada manualmente pelo humano após uso real. 3 saídas: A) close workspace; B) restart fase X (iteration++); C) spawn novo workspace herdando lessons+ADRs.

---

## Pre-flight runtime check

Bootstrap roda `scripts/check-runtime.sh` antes de qualquer ação. Aborta limpo se runtime falha:

- Python 3.11+ (testado em 3.13)
- PyYAML
- pytest (pra rodar testes da skill localmente)
- git 2.30+
- bash POSIX (Linux/macOS nativo; Windows via Git Bash)
- bats (opcional local; CI rodará via apt no Ubuntu runner)

Permissions allowlist sugerida em `system-requirements.md`.

---

## Anti-patterns (não use)

- `git commit --no-verify` no workspace — pre-commit hook valida atomicidade L1↔outputs e prefixos. Bypass quebra audit. Investigue e corrija conteúdo, NÃO bypass o hook.
- Re-invocar `/xp-icm-workflow` em workspace existente — só pra criar novos. Para retomar, abra sessão nova; ela lê L1.
- Editar L1 (`CONTEXT.md`) manualmente sem entender o schema — use `scripts/recovery-wizard.py` se precisar reconstruir.
- Editar L4 outputs commitados (decisions.md, ADRs) sem nova versão ou superseding — vide `_config/icm-conventions.md`.

---

## References

| Doc | Conteúdo |
|---|---|
| `references/state-machine-schema.md` | Schema completo L1 (yaml frontmatter + history append-only) |
| `references/git-hooks.md` | Pre-commit hook: regras 1-6, padrões regex, anti-bypass |
| `references/recovery-wizard.md` | 6 inconsistências detectadas + ações A/B/C |
| `references/changelog.md` | Versões da skill |
| `references/v2.4-snapshot/` | Snapshot da v2.4 anterior (pra referência histórica) |
| `system-requirements.md` | Runtime + permissions allowlist |
| `templates/_config/profile-matrix.md` | Matriz canônica 10 profiles × 4 tiers |
| `templates/workspace/CLAUDE.md.tpl` | Template L0 com placeholders |
| `templates/workspace/CONTEXT.md.tpl` | Template L1 com placeholders |

**Referências de algoritmo (Wave 3+ da skill — em construção):**

- `references/wave-planner-algorithm.md` — DAG construction, sub-waves, LLM review subagent
- `references/agent-team-protocol.md` — spawn, mailbox, plan approval, mid-wave reduce
- `references/stop-points-canonical.md` — 12 stop points + thresholds por tier
- `references/4-block-contract-template.md` — O QUE / COMO / NÃO QUERO / VALIDAÇÃO
- `references/feedback-intake-fase08.md` — 3 saídas A/B/C
- `references/profile-matrix.md` — calibração por profile/tier (estágios pulados, etc.)
- `references/doc-reading-protocol.md` — 3 canais de docs (L2 Inputs, lead injeta, plan.md declara)

**Referências de testes:**

- `tests/run.sh` — orquestrador (pytest + bats)
- `tests/unit/` — unit + property-based via Hypothesis
- `tests/integration/` — bats integration (CI-only)
- `tests/e2e/` — bats e2e (CI-only)
- `.github/workflows/test-skill.yml` — CI GitHub Actions (Wave 6)
