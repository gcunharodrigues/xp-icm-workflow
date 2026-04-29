# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install deps
pip install -r requirements.txt

# Run all tests (pytest + bats if available)
bash tests/run.sh

# Run pytest only (faster local iteration)
bash tests/run.sh --no-bats

# CI mode (coverage XML)
bash tests/run.sh --ci

# Run single test file
pytest tests/unit/test_bootstrap.py -v

# Run single test by name
pytest tests/unit/test_bootstrap.py::test_validate_slug -v

# Pre-flight runtime check
bash scripts/check-runtime.sh
```

## Architecture

This is a **filesystem-based project orchestration skill** for Claude Code implementing ICM (Interpretable Context Methodology). The core idea: folder structure replaces traditional orchestration; each stage = 1 Claude session.

### 5-Layer Context Model

| Layer | File | Role |
|---|---|---|
| L0 | `workspaces/NNN/CLAUDE.md` | Identity — immutable, always loaded |
| L1 | `workspaces/NNN/CONTEXT.md` | State machine — YAML frontmatter, always loaded |
| L2 | `workspaces/NNN/stages/NN/CONTEXT.md` | Stage instructions — current stage only |
| L3 | `_config/`, `_references/`, `docs/` | Rules & reference — loaded as needed |
| L4 | `stages/NN/output/` | Working outputs — product artifacts |

### 9-Stage Pipeline

`00:recon → 01:discovery → 02:design → 03:wave-planner → 04:implementation-waves → 05:verification → 06:review → 07:merge → 08:feedback-intake`

Stage 04 exception: each wave = 1 lead session; subagents spawned via `Agent` tool (no worktrees), branch setup mandatory.

### Key Scripts (`/scripts/`)

- **bootstrap.py** — One-shot workspace creation (folder structure, L0/L1/L2 files, git branch, pre-commit hooks, atomic commit, project-root CLAUDE.md render)
- **profile-merge.py** — Merges 10 profiles × 4 tiers → deterministic effective hash (sha256)
- **handoff.py** — Renders `_kickoff.md` (L4) + manages `<project_root>/CLAUDE.md` ICM region (update/remove/deactivate)
- **wave-planner-script.py** — Parses `plan.md` → DAG → cycle detection (DFS 3-color) → topological sort (Kahn) → sub-wave subdivision (HITL tasks isolated cap=1)
- **wave-planner-llm-review.py** — Optional LLM review subagent for wave plan validation
- **agent-brief-render.py** — Generates AGENT-BRIEF for stage 04 subagent dispatch (parses plan.md task → behavioral brief with acceptance criteria)
- **recovery-wizard.py** — Detects/repairs 7 workspace inconsistency types (HASH_MISMATCH, MISSING_COMMIT, MISSING_OUTPUT, STALE_IN_PROGRESS, BRANCH_MISSING, CLAUDE_MD_ROOT_STALE, CLAUDE_MD_ROOT_MISSING)
- **validate_state.py** — L1 YAML validation against state-machine-schema
- **lessons-match.py** — Extracts top-3 relevant lessons for current task

### Profile System

10 profiles (e.g., `app_web_backend`, `ml_project`, `agent_ia`) × 4 tiers (`experimental`, `tool`, `development`, `production`). Config keys: `stages_skipped`, `tdd_required`, `security_gate`, `stop_points_calibration`. See `templates/_config/profile-matrix.md`.

### Naming Conventions

- **Workspace ID:** `NNN-slug` (e.g., `042-feat-auth`), auto-incremented
- **Branches:** `workspace/NNN-slug` (state files), `wave-NNN-N/<task-slug>` (code)
- **Commits:** prefix `workspace NNN: <action>` — enforced by pre-commit hook
- **Task slugs:** `^[a-z0-9][a-z0-9-]*$`

### L1 State Machine

YAML frontmatter in `CONTEXT.md` tracks: `workspace`, `profile_base`, `profile_effective_hash`, `tier`, `stage_atual`, `sub_stage`, `status`, `iteration`, `history[]`, `last_transition`. Schema spec: `references/state-machine-schema.md`.

### Template Placeholders

Templates in `/templates/` use `{{WORKSPACE}}`, `{{PROFILE}}`, `{{TIER}}`, `{{PROFILE_EFFECTIVE_HASH}}`, `{{SKILL_VERSION}}`, `{{STAGES_SKIPPED}}`, etc.

## Key Reference Docs

- `SKILL.md` — Skill entry point, CLI args, intent inference protocol
- `references/session-handoff-protocol.md` — 1-stage-1-session flow
- `references/state-machine-schema.md` — L1 YAML spec
- `references/wave-planner-algorithm.md` — DAG construction details
- `references/stop-points-canonical.md` — 12 stop points + tier thresholds
- `references/example-run.md` — Full 9-session E2E walkthrough

## Tests

548 tests, 83%+ coverage. `tests/unit/` uses pytest + Hypothesis (property-based). `tests/integration/` and `tests/e2e/` use bats (CI-only, Ubuntu). Mock LLM responses in `tests/mocks/llm_review_responses/`. Fixtures in `tests/fixtures/`.

Playwright plugin disabled in `pyproject.toml` (workaround — leave it).

## v3.3.0 — patterns adopted from mattpocock/skills

8 patterns (Tier 1+2) + Design It Twice (T3 promovido). Doc canônico de cada em `references/`:

| Pattern | Doc | Stage(s) consumidor |
|---|---|---|
| Project root CLAUDE.md | `project-root-claude-md.md` | bootstrap + handoff (cross-session signaling) |
| AGENT-BRIEF template | `agent-brief-template.md` | 04 (lead → subagent context injection) |
| Ubiquitous Language | `context-format.md` | 01 (grilling) → 02+ (consume) |
| ADR 3-criteria gate | `adr-format.md` | 02 (decisions) |
| Diagnose 6-fase | `diagnose-protocol.md` | 05 fallback (CI fail) |
| HITL/AFK | `task-types-hitl-afk.md` | 02 → 03 → 04 |
| Triage state machine | `triage-state-machine.md` | 08 (feedback intake) |
| OUT-OF-SCOPE kb | `out-of-scope-kb.md` | 02 (iter>0) + 08 (wontfix) |
| Design It Twice | `design-it-twice.md` | 02 (módulos core) |

## Pendências para próxima sessão

Itens identificados durante implementação v3.3.0 mas não atacados. Ordenados por prioridade:

### Tier 3 (originalmente fora de escopo)

- **Deep modules + deletion test** — ferramenta de architecture review pra stage 02. Doc canônico inspirado em [mattpocock/skills/engineering/improve-codebase-architecture]. Adicionar `references/deep-modules.md` + checklist em `templates/workspace/stages/02_design/CONTEXT.md.tpl` + tests `test_deep_modules_doc.py`.
- **Git guardrails hook (production tier)** — `templates/.claude/hooks/block-dangerous-git.sh` que bloqueia `git push --force`, `reset --hard`, `clean -fd`, `branch -D`, `checkout .` via PreToolUse hook. Bootstrap adiciona condicionalmente quando `tier=production`. Inspirado em [mattpocock/skills/misc/git-guardrails-claude-code].
- **PreToolUse anti-`/init`** — hook que bloqueia invocação de `/init` enquanto há workspace ICM ativo (G14 do adversarial review do plan v3.3.0). Mitigação atual é apenas warning textual na região ICM do CLAUDE.md root.
- **Zoom-out instruction completo em stage 00** — adicionei placeholder no L2 mas falta seção structured guiando o agent quando encontra módulo desconhecido (mapear callers + adicionar termos candidatos ao glossário pré-stage-01).

### Tests opcionais

- `tests/unit/test_context_md_template.py` — validar render do `_config/CONTEXT.md` template + frontmatter.
- `tests/unit/test_adr_gate.py` — property-based tests do gate de 3 critérios.
- `tests/unit/test_diagnose_doc.py` — smoke test parsability + 6 fases presentes.
- `tests/unit/test_triage_state_machine.py` — classificação + transições válidas.
- `tests/integration/test_pre_commit_whitelist.bats` — bats CI-only test que `CLAUDE.md` root passa whitelist em workspace branch (G6).

(Cobertura redundante — docs canônicos já exercitados via lista `runtime_refs` em bootstrap. Tests acima são reforço explícito.)

### Smoke manual end-to-end

Checklist atualizada em `references/smoke-manual-checklist.md` mas execução em projeto real não rodada nesta sessão. Cobre:

- Greenfield bootstrap (verifica todos arquivos novos criados)
- Brownfield COM marcadores (preserva conteúdo fora byte-a-byte)
- Brownfield SEM marcadores (insere após `^# `)
- Multi-workspace (2 blocos no CLAUDE.md root)
- Handoff transitions atualizam bloco do workspace dono
- Saída A do último workspace ativa região idle
- Recovery wizard detecta `CLAUDE_MD_ROOT_STALE` quando L1 diverge
- Pre-commit hook permite CLAUDE.md root em workspace branch
- HITL task fica isolada em wave cap=1

### Plan original

Plan completo em `~/.claude/plans/primeiro-fa-a-um-plano-sunny-glade.md` (Context, Avaliação de redundâncias, Adversarial review G1-G17, decisões de design, escopo aprovado). Refere ao implementador da próxima sessão para contexto histórico.

### Branch v3-implementation

5 commits sequenciais (`74f050b` → `321ad3f`). Pronto para PR ou merge para main quando smoke manual validar.
