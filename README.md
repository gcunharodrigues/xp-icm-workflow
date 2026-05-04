# xp-icm-workflow

> **Skill de orquestração de projetos via filesystem para Claude Code.** Bootstrap one-shot cria estrutura ICM (Interpretable Context Methodology) num projeto e SAI; o filesystem governa o ciclo. Cada estágio = 1 sessão Claude. v3.9.0.

[![tests](https://img.shields.io/badge/tests-855%20passed-brightgreen)](tests/)
[![coverage](https://img.shields.io/badge/coverage-83%25-brightgreen)](pyproject.toml)
[![python](https://img.shields.io/badge/python-3.11%2B-blue)](system-requirements.md)
[![version](https://img.shields.io/badge/version-v3.9.0-blue)](references/changelog.md)
[![license](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## Por que existe

Projetos não-triviais com Claude Code rapidamente esbarram em:

- Context window estoura quando 1 sessão tenta cobrir discovery → design → implementação → review.
- Decisões arquiteturais somem entre sessões (sem registro durável).
- Subagentes paralelos ficam sem coordenação determinística.
- Recovery de estado inconsistente vira investigação manual.

**ICM** (Interpretable Context Methodology) resolve via filesystem-as-state: pastas numeradas representam estágios, markdown carrega contexto, sessões fresh leem L0+L1+L2 do estágio atual e trabalham. Skill é **parteira one-shot** — cria estrutura, sai, e nunca mais aparece no runtime do projeto.

Base teórica: VanClief & McDermott, 2025 (`references/icm-paper-summary.md`).

---

## Quickstart (5 minutos)

### 1. Instalar skill

Clone no diretório de skills do Claude Code:

```bash
# Linux/macOS
git clone https://github.com/gcunharodrigues/xp-icm-workflow ~/.claude/skills/xp-icm-workflow

# Windows
git clone https://github.com/gcunharodrigues/xp-icm-workflow %USERPROFILE%\.claude\skills\xp-icm-workflow
```

Instalar deps Python:

```bash
cd ~/.claude/skills/xp-icm-workflow   # ou %USERPROFILE%\... no Windows
pip install -r requirements.txt
bash scripts/check-runtime.sh         # valida runtime (Python 3.11+, git 2.30+, PyYAML)
```

### 2. Bootstrappar workspace num projeto

Abra Claude Code no diretório do projeto. Duas formas:

**Opção A — Recomendada: deixe o agente inferir tudo (descrição livre).**

```
/xp-icm-workflow
```

O agente lê seu prompt, infere `profile` + `tier` + `workspace-name` via heurísticas (palavras-chave: "API/backend" → `app_web_backend`, "componente React/UI" → `app_web_frontend`, "ML/treinar modelo" → `ml_project`, "POC/spike" → tier `experimental`, etc.), e confirma com você num menu curto antes de criar a estrutura. Pendências de discovery vão pra `_seed.md` do estágio 00 — você não precisa decidir nada técnico antes do bootstrap.

Exemplo de uso real:

```
/xp-icm-workflow

> Quero criar uma API REST de gestão de tarefas em FastAPI com auth JWT
> e testes pytest. Vai rodar em produção na AWS.
```

Agente responde:

```
Inferido: profile=app_web_backend tier=production workspace-name=001-api-tarefas-jwt
[a] confirma   [b] corrige   [c] cancela
```

Você responde `a`, e o bootstrap roda.

**Opção B — Avançada: passe args explícitos** (útil em scripts ou quando você sabe exatamente o que quer):

```
/xp-icm-workflow profile=app_web_backend tier=development
```

Tabela completa de combinações abaixo (§Profiles e §Tiers).

---

A skill cria:

```
seu-projeto/
├── .gitignore                          # atualizado
├── CLAUDE.md                           # dashboard ICM
├── .icm-main/                          # worktree linkada (base branch)
└── workspaces/
    └── 001-<slug>/
        ├── CLAUDE.md                   # L0: identidade imutável
        ├── CONTEXT.md                  # L1: state machine
        └── stages/
            ├── 00_recon/CONTEXT.md     # L2: instruções stage atual
            ├── 01_discovery/...
            └── ...
```

E sai. Próxima sessão Claude no mesmo dir lê L0+L1+L2 automaticamente e continua.

### 3. Avançar pelos estágios

Cada estágio termina escrevendo `_kickoff.md` no próximo. Você abre nova sessão Claude, ela lê o kickoff e continua. Walkthrough completo: [`references/example-run.md`](references/example-run.md).

---

## Características

- **9 estágios canônicos:** `00 recon → 01 discovery → 02 design → 03 wave_planner → 04 implementation_waves → 05 verification → 06 review → 07 merge → 08 feedback_intake`.
- **11 profiles × 4 tiers = 44 combinações** calibrando rigor (TDD obrigatório, security gate, stop points, cap subagents).
- **Subagentes paralelos** em fase 04 via Agent Tool (`Agent(isolation: "worktree")`).
- **Wave Planner determinístico:** DAG → topological sort → sub-waves (HITL isoladas cap=1).
- **15 stop points canônicos** + thresholds calibrados por tier.
- **Recovery Wizard** detecta 14 tipos de inconsistência + ações A/B/C.
- **Drift detector** automático: bump de versão sem sweep multi-arquivo é bloqueado em CI.
- **Runtime cleanup obrigatório** (v3.7.0) pré-saída fase 08: 6 categorias, strict universal.
- **Spawn handoff zero-friction** (v3.7.0): `.icm/spawn-pending.json` auto-detectado pelo bootstrap.

---

## Profiles (11 canônicos)

Cada profile calibra estágios pulados, TDD obrigatório, security gate, peer-review, cap de subagentes, e thresholds de stop points. Detalhes operacionais: [`templates/_config/profile-matrix.md`](templates/_config/profile-matrix.md).

| Profile | Quando usar | Sinais no prompt |
|---|---|---|
| **`app_web_backend`** | API REST/GraphQL, microservices, backend services, endpoints | "API", "backend", "endpoint", "FastAPI/Express/Django/Spring" |
| **`app_web_frontend`** | SPA/PWA, componentes React/Vue/Svelte, páginas web | "página web", "componente React/Vue", "UI", "Next.js/Vite" |
| **`fullstack`** | App completo backend + frontend coordenado | "fullstack", "app completo", "backend + frontend" |
| **`dashboard`** | BI, analytics, visualização de dados, painéis admin | "dashboard", "BI", "analytics", "métricas", "Streamlit/Tableau" |
| **`data_analysis`** | EDA, notebooks, análise estatística, relatórios | "EDA", "notebook", "análise de dados", "Jupyter/pandas" |
| **`ml_project`** | Pipeline ML, fine-tune, treino de modelo, MLOps | "treinar modelo", "ML pipeline", "fine-tune", "PyTorch/scikit-learn" |
| **`agent_ia`** | Skills Claude Code, agentes LLM, subagentes, MCP servers | "skill", "agente", "subagent", "LLM tool", "MCP" |
| **`cli_tool`** | Ferramenta linha de comando, automação shell | "CLI", "comando", "ferramenta linha de comando" |
| **`framework_library`** | Lib, SDK, framework, package distribuível | "lib", "SDK", "framework", "package", "npm/pypi" |
| **`technical_article`** | Artigo, paper, post técnico, documentação aprofundada | "artigo", "paper", "post técnico", "blog post" |
| **`experiment`** | POC, spike, experimento descartável, prova de conceito | "POC", "spike", "experimento", "prova de conceito" |

---

## Tiers (4 canônicos)

Tier escala rigor independente do profile. Mesmo profile em tier `experimental` vs `production` recebe calibração diferente (TDD opcional vs obrigatório, security gate off vs on, etc.).

| Tier | Quando usar | Calibração principal |
|---|---|---|
| **`experimental`** | POCs, spikes, throwaway code, código pra validar hipótese | TDD opcional, sem security gate, peer-review off, cap subagents=2, stop points loose (item 5 R$50, item 7/8 warning) |
| **`tool`** | Ferramentas internas, automações pessoais, side projects | TDD opcional, security gate off, peer-review off, cap subagents=3, stop points moderado (item 5 R$200) |
| **`development`** | Apps em desenvolvimento ativo, projetos de equipe pré-prod | TDD obrigatório, security gate on, peer-review opcional, cap subagents=5, stop points strict (item 5 R$500, item 7 hard) |
| **`production`** | Apps em produção, sistemas críticos, dados reais de usuários | TDD obrigatório, security gate on, peer-review obrigatório, cap subagents=5, stop points strict máximo (item 5 R$1000, item 8 hard+DPO) |

**Default quando não-especificado:** `tier=development` (médio). Bootstrap interativo pergunta se faltar.

---

## Documentos chave

| Doc | Conteúdo |
|---|---|
| [`SKILL.md`](SKILL.md) | Entrada da skill |
| [`references/icm-paper-summary.md`](references/icm-paper-summary.md) | Base teórica ICM |
| [`references/example-run.md`](references/example-run.md) | E2E concreto 9 sessões |
| [`references/state-machine-schema.md`](references/state-machine-schema.md) | Schema L1 + sub_stage enum |
| [`references/stop-points-canonical.md`](references/stop-points-canonical.md) | 15 stop points + thresholds por tier |
| [`references/runtime-cleanup-protocol.md`](references/runtime-cleanup-protocol.md) | Checklist 6 categorias pré-saída fase 08 (v3.7.0) |
| [`references/spawn-handoff-protocol.md`](references/spawn-handoff-protocol.md) | `.icm/spawn-pending.json` + `--spawn-from` arg (v3.7.0) |
| [`references/preview-loop-protocol.md`](references/preview-loop-protocol.md) | Build-iterate visual frontend (v3.6.0) |
| [`references/design-system.md`](references/design-system.md) | DESIGN.md format frontend/fullstack |
| [`references/4-block-contract-template.md`](references/4-block-contract-template.md) | 4-block + ciclo TDD 7 passos + Akita 15-item |
| [`references/wave-planner-algorithm.md`](references/wave-planner-algorithm.md) | DAG + LLM review subagent |
| [`references/subagent-protocol.md`](references/subagent-protocol.md) | Spawn via Agent tool + mid-wave reduce |
| [`references/feedback-intake-fase08.md`](references/feedback-intake-fase08.md) | 3 saídas A/B/C |
| [`references/recovery-wizard.md`](references/recovery-wizard.md) | 14 inconsistências + reconstrução |
| [`references/worktree-model.md`](references/worktree-model.md) | Worktree paralelo `.icm-main/` (v3.4.0) |
| [`references/changelog.md`](references/changelog.md) | Histórico completo de versões |
| [`system-requirements.md`](system-requirements.md) | Runtime + permissions allowlist |

---

## Arquitetura em camadas

| Camada | Conteúdo | Path típico |
|---|---|---|
| **L0** | Identidade imutável do workspace | `workspaces/NNN/CLAUDE.md` |
| **L1** | State machine (frontmatter YAML) | `workspaces/NNN/CONTEXT.md` |
| **L2** | Instruções do estágio atual | `workspaces/NNN/stages/<NN>/CONTEXT.md` |
| **L3** | Conventions, sumários superpowers, runtime refs | `workspaces/NNN/_config/`, `_references/` |
| **L4** | Outputs nascentes (discovery.md, plan.md, etc.) | `workspaces/NNN/stages/<NN>/output/` |

---

## Tests

```bash
bash tests/run.sh             # pytest + bats (se disponível)
bash tests/run.sh --ci        # coverage XML para CI
bash tests/run.sh --no-bats   # só pytest, skip bats
```

CI: [`.github/workflows/test-skill.yml`](.github/workflows/test-skill.yml) — Ubuntu runner com Python 3.13 + bats.

---

## Contribuindo

Bug reports, feature requests e PRs são bem-vindos.

### Reportar bug

Abra uma issue em [github.com/gcunharodrigues/xp-icm-workflow/issues](https://github.com/gcunharodrigues/xp-icm-workflow/issues) com:

1. **Versão** da skill (cole `bootstrap.py:SKILL_VERSION`).
2. **OS + Python version** (`python --version`, `uname -a` ou `ver` em Windows).
3. **Reprodução mínima:** comandos exatos + output relevante (com PII removida).
4. **Comportamento esperado vs observado.**
5. **Logs:** se disponível, `workspaces/<NNN>/CONTEXT.md` (frontmatter L1 + history) e `_kickoff.md` do stage onde quebrou.

### Submeter PR

1. **Fork** este repo.
2. **Branch:** `feat/<slug-curto>` ou `fix/<slug-curto>` a partir de `main`.
3. **Tests obrigatórios:** TDD-first. Adicione testes em `tests/unit/` cobrindo o caso novo. PR sem teste = bloqueado.
4. **Drift gate:** rode `pytest tests/unit/test_no_drift.py -v` antes de mergear. Se mudou versão, README/SKILL.md/changelog precisam sync (ver [CONTRIBUTING.md](CONTRIBUTING.md)).
5. **Conventional Commits:** `feat:`, `fix:`, `docs:`, `test:`, `refactor:`. Subject ≤ 70 chars.
6. **Suite verde:** `bash tests/run.sh --no-bats` deve passar 782+ tests.
7. Abra PR contra `main` com descrição: motivação, mudanças, breaking changes (se houver), tests adicionados.

Detalhes de fluxo, padrões de código e regras de drift em [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Versão atual

**v3.9.0** — Layered dev↔QA loop + lead-resolution tier (lean). Stage 04 ganha 3 layers de QA: L2 forensic+ extended (4 checks v3.8.0 + 3 novos: acceptance↔test mapping, NÃO QUERO violations, ADR import drift) + L3 LLM critic ortogonal (sempre, todos tiers, model = TIER_CEILING, anti-sycophancy hardcoded) + lead-resolution tier B1/B3/B4 quando per-task loop esgota cap 3 attempts OR convergence trip OR catastrophic. Drop Akita 15-itens inline (delegado a L2/L3). Vertical TDD enforce (tracer-first + 1 test → 1 impl → repeat). Novo `scripts/pick-model.py` + `scripts/lead-diagnose.py`. Stage 05 +sub-step audit lead resolutions.

Versão canônica: [`scripts/bootstrap.py:SKILL_VERSION`](scripts/bootstrap.py). Histórico completo: [`references/changelog.md`](references/changelog.md).

### Highlights por versão

- **v3.9.0** (2026-05-04) — Layered dev↔QA loop + lead-resolution tier. L2 forensic+ extended (7 checks) + L3 critic ortogonal (intra-Claude Sonnet/Opus mix, anti-sycophancy) + buckets B1 REWRITE_SPEC / B3 DIRECT_IMPL / B4 VOID_TASK. Vertical TDD + tracer-first. Drop Akita 15-itens. Pick-model heuristic (writer/critic split por complexity score + tier ceiling). Docs: `critic-protocol.md`, `lead-resolution-protocol.md`, `mocking-guidelines.md`.
- **v3.8.0** (2026-05-03) — Forensic+ wave reviewer. 4 checks anti-fraude per task no step 8 wave-reviewer (test asserções, files fora declared, scope creep, TODO/FIXME). Tier-aware HARD/SOFT severity. Re-spawn cap 2. Doc: `references/forensic-plus-protocol.md`.
- **v3.7.2** (2026-05-01) — Saída A/C último ativo dispara `/init` automático + menu opt-in cleanup (`scripts/icm-cleanup.py`). `.index.md` + `settings.local.json` hooks limpos. SessionStart hook prefere L1 status sobre `.index.md`. Recovery wizard novo detector `STALE_ICM_MAIN_AFTER_CLOSE`.
- **v3.7.0** (2026-05-01) — Runtime cleanup + spawn-pending handoff. Stop point #15 `runtime_cleanup_failed`. Migration v3.3→v3.7.
- **v3.6.0** (2026-04-30) — Preview loop frontend (build-iterate visual). Chrome CDP integration, mock data tier-based.
- **v3.5.0** (2026-04-29) — Stage 04 protocol gaps fix (10 edge cases). Drift detector introduzido.
- **v3.4.0** (2026-04-28) — Cross-branch worktree model (`.icm-main/`). Visibility cross-branch resolvida.
- **v3.3.0** (2026-04-25) — 8 patterns adotados de [mattpocock/skills](https://github.com/mattpocock/skills) (AGENT-BRIEF, Ubiquitous Language, ADR gate, Diagnose 6-fase, Triage, etc.).

---

## License

MIT — ver [LICENSE](LICENSE).

---

## Maintainer

[@gcunharodrigues](https://github.com/gcunharodrigues)

## Acknowledgments

Esta skill é síntese de múltiplas fontes externas. Atribuições completas em [ACKNOWLEDGMENTS.md](ACKNOWLEDGMENTS.md):

- **Base teórica:** ICM Paper (VanClief & McDermott, 2025).
- **Superpowers** ([obra/superpowers-marketplace](https://github.com/obra/superpowers-marketplace)) — Jesse Vincent (@obra). Filosofia subagent-driven-development, TDD strict, brainstorming-first, dispatching-parallel-agents permeia esta skill desde v3.0. Sumários 200tok em `_references/superpowers-summary/`.
- **9 patterns adotados:** [mattpocock/skills](https://github.com/mattpocock/skills) — ADR format, AGENT-BRIEF, Ubiquitous Language, Diagnose 6-fase, Triage state machine, OUT-OF-SCOPE, HITL/AFK, Design It Twice, Deep modules.
- **Auto-QA Akita checklist (TDD loop):** inspirado nos blogposts de [Fabio Akita](https://www.akitaonrails.com/) (clean code, naming, abstrações justificadas).
- **Design system inspiration:** [VoltAgent/awesome-design-md](https://github.com/VoltAgent/awesome-design-md), [Manavarya09/design-extract](https://github.com/Manavarya09/design-extract).
- **Algoritmos:** Kahn (1962) topological sort + DFS 3-color cycle detection (Wave Planner). Cockburn — Hexagonal Architecture. Beck — TDD red/green + YAGNI (XP). Hunt & Thomas — DRY (Pragmatic Programmer).
- **Ecosystem:** [Anthropic Claude](https://www.anthropic.com/claude) (LLM motor da skill) + [Claude Code](https://docs.claude.com/en/docs/claude-code) + [Anthropic Skills system](https://docs.claude.com/en/docs/agents/skills).

Se você identifica fonte não creditada, [abra issue](https://github.com/gcunharodrigues/xp-icm-workflow/issues) com label `attribution-fix`.
