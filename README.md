# xp-icm-workflow

> **Skill de orquestração de projetos via filesystem para Claude Code.** Bootstrap one-shot cria estrutura ICM (Interpretable Context Methodology) num projeto e SAI; o filesystem governa o ciclo. Cada estágio = 1 sessão Claude. v3.7.0.

[![tests](https://img.shields.io/badge/tests-782%20passed-brightgreen)](tests/)
[![coverage](https://img.shields.io/badge/coverage-83%25-brightgreen)](pyproject.toml)
[![python](https://img.shields.io/badge/python-3.11%2B-blue)](system-requirements.md)
[![version](https://img.shields.io/badge/version-v3.7.0-blue)](references/changelog.md)
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

Abra Claude Code no diretório do projeto e rode:

```
/xp-icm-workflow profile=app_web_backend tier=development
```

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
- **11 profiles × 4 tiers** calibrando rigor (TDD obrigatório, security gate, stop points, cap subagents).
- **Subagentes paralelos** em fase 04 via Agent Tool (`Agent(isolation: "worktree")`).
- **Wave Planner determinístico:** DAG → topological sort → sub-waves (HITL isoladas cap=1).
- **15 stop points canônicos** + thresholds calibrados por tier.
- **Recovery Wizard** detecta 14 tipos de inconsistência + ações A/B/C.
- **Drift detector** automático: bump de versão sem sweep multi-arquivo é bloqueado em CI.
- **Runtime cleanup obrigatório** (v3.7.0) pré-saída fase 08: 6 categorias, strict universal.
- **Spawn handoff zero-friction** (v3.7.0): `.icm/spawn-pending.json` auto-detectado pelo bootstrap.

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

**v3.7.0** — runtime cleanup obrigatório pré-saída fase 08 + spawn-pending handoff zero-friction + drift detector hardened + migration encadeada v3.3→v3.7.

Versão canônica: [`scripts/bootstrap.py:SKILL_VERSION`](scripts/bootstrap.py). Histórico completo: [`references/changelog.md`](references/changelog.md).

### Highlights por versão

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
- **Ecosystem:** [Claude Code](https://docs.claude.com/en/docs/claude-code) + [Anthropic Skills system](https://docs.claude.com/en/docs/agents/skills).

Se você identifica fonte não creditada, [abra issue](https://github.com/gcunharodrigues/xp-icm-workflow/issues) com label `attribution-fix`.
