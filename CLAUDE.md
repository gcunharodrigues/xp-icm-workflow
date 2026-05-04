# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Workflow de modificações

**Toda modificação não-trivial segue este fluxo:**

```bash
# 1. Criar branch a partir de main
git checkout main
git checkout -b feat/<short-slug>

# 2. Executar mudanças (edits, tests, etc)
# ...

# 3. Commit(s) na branch
git add <paths>
git commit -m "feat: descrição"

# 4. Run tests (obrigatório antes do merge)
bash tests/run.sh --no-bats   # ou: python -m pytest tests/unit/

# 5. Merge para main (fast-forward) + push (se houver remote)
git checkout main
git merge --ff-only feat/<short-slug>
git push origin main          # apenas se remote configurado

# 6. Apagar branch (local + remote se aplicável)
git branch -d feat/<short-slug>
git push origin --delete feat/<short-slug>   # apenas se remote
```

**Regras:**
- Branch é descartada após merge — não acumular branches stale.
- Tests devem passar antes do merge (`538+/538+ tests` baseline).
- `--ff-only` força merge linear; conflito = rebase a branch antes.
- Trivial fix (typo, comentário) pode commit direto em `main` sem branch.
- Sem remote configurado nesse repo skill — passos `git push` viram no-op
  até remote ser adicionado.

## Pre-merge drift audit (mandatory)

**Toda PR que toca `references/`, `templates/`, `scripts/`, `SKILL.md`, `CLAUDE.md`, `README.md` DEVE rodar:**

```bash
pytest tests/unit/test_no_drift.py -v
```

**Detectores ativos (21, agrupados):**
- A: Versão consistente em arquivos canônicos (canonical = `scripts/bootstrap.py:SKILL_VERSION`).
- A': Changelog tem entrada para versão canônica.
- B: Profile count (canonical = `len(CANONICAL_PROFILES)` em `profile-merge.py`).
- C/D: Status enum sync (`validate_state.py:ALLOWED_STATUSES` ↔ `references/state-machine-schema.md`) + allow-list anti-typo.
- E: Cross-refs markdown em `references/` (direção `link → file` — target existe).
- F: Shell + git-hook templates sem CRLF.
- H: Scripts auxiliares com `CURRENT_SKILL_VERSION` sincronizam com bootstrap (genérico — pega scripts futuros).
- 4-block parser: heading levels canônicos + regex match no template.
- v3.8.0 (forensic+): canonical doc exists, bootstrap runtime_refs menciona, L2 stage 04 cross-ref + `MAX_FORENSIC_RETRIES`, wave-execution sub-steps, state-machine error_type values.
- SKILL.md indexa docs canônicos (whitelist `SKILL_MD_INDEXED_DOCS`, direção `file → menção`).

**Se test falha:**
- NÃO mergear até fix.
- Adicionar entrada no whitelist do test (`VERSION_WHITELIST` / `PROFILE_COUNT_WHITELIST`) APENAS se a divergência é legítima (changelog histórico, kickoff arquivado, fixture legacy explícita).
- Caso contrário: fix o drift no arquivo que diverge.

**Por que automatizado:** repo é highly-coupled (versão em 5+ arquivos, profile count em 8+, status enum em 3+). Auditar manualmente em sessão fresh é não-confiável. Test gate bloqueia drift no commit, sem precisar lembrar.

## Regra: bump de SKILL_VERSION exige sweep multi-arquivo (v3.7.0, estendido v3.7.2)

**Toda mudança em `scripts/bootstrap.py:SKILL_VERSION` requer atualização sincronizada:**

1. **`SKILL.md`** header `# xp-icm-workflow vX.Y.Z`
2. **`README.md`** badge `version-vX.Y.Z` + nova seção `## vX.Y.Z — <título>` no top da lista de versões
3. **`references/design-system.md`** frontmatter `format (vX.Y.Z)` + linha `> **Versão:** vX.Y.Z`
4. **`references/preview-loop-protocol.md`** título `build-iterate visual (vX.Y.Z)` + linha `> **Versão:** vX.Y.Z`
5. **`references/changelog.md`** nova entry `## vX.Y.Z — <título> (YYYY-MM-DD)` no top com seção `### Mudanças` listando alterações concretas
6. **`scripts/migrate-workspace.py`** `CURRENT_SKILL_VERSION = "X.Y.Z"` + última entry de `SUPPORTED_VERSIONS` tuple = X.Y.Z + nova função `migrate_<from>_to_<X_Y_Z>` (mesmo bump-only) + entry em `STEP_FUNCTIONS` dispatcher
7. **`tests/unit/test_migrate_workspace.py`** atualizar/adicionar cases pra novo step (smoke + idempotência)

**Validação automática:**
- `test_no_drift.py::test_version_consistency_canonical_files` (5 arquivos canônicos — items 1-4 + #6)
- `test_no_drift.py::test_changelog_has_entry_for_canonical_version` (#5)
- `test_no_drift.py::test_scripts_skill_version_sync` (genérico — varre `scripts/**/*.py` por `CURRENT_SKILL_VERSION` + tuple last entry, pega futuros scripts auxiliares)
- `test_migrate_workspace.py::test_current_skill_version_matches_bootstrap` (cross-check direto)

Falha em qualquer = NÃO mergear.

**Regra extra (v3.7.0):** README.md também exige entry de seção `## vX.Y.Z` resumindo mudanças (não só badge bump). Se mudanças muito amplas, README seção pode ser breve com cross-ref pra `references/changelog.md`.

**Regra extra (v3.7.2):** detector H pega scripts auxiliares que copiarem padrão `CURRENT_SKILL_VERSION` no futuro — não precisa atualizar `VERSION_MUST_MATCH` cirurgicamente pra cada novo script (mas pode adicionar pattern fixo se quiser dupla cobertura).

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

Stage 04 exception: each wave = 1 lead session; subagentes spawnados via `Agent(isolation: "worktree")` (worktree efêmera por task, criada pelo harness), branch `wave-<NNN>-<N>/<task-slug>` derivada de `BASE_BRANCH`. Doc canônico: `references/wave-execution-protocol.md`.

### Key Scripts (`/scripts/`)

- **bootstrap.py** — One-shot workspace creation (folder structure, L0/L1/L2 files, git branch, pre-commit hooks, atomic commit, project-root CLAUDE.md render)
- **profile-merge.py** — Merges 11 profiles × 4 tiers → deterministic effective hash (sha256)
- **handoff.py** — Renders `_kickoff.md` (L4) + manages `<project_root>/CLAUDE.md` ICM region (update/remove/deactivate)
- **wave-planner-script.py** — Parses `plan.md` → DAG → cycle detection (DFS 3-color) → topological sort (Kahn) → sub-wave subdivision (HITL tasks isolated cap=1)
- **wave-planner-llm-review.py** — Optional LLM review subagent for wave plan validation
- **agent-brief-render.py** — Generates AGENT-BRIEF for stage 04 subagent dispatch (parses plan.md task → behavioral brief with acceptance criteria)
- **recovery-wizard.py** — Detects/repairs 7 workspace inconsistency types (HASH_MISMATCH, MISSING_COMMIT, MISSING_OUTPUT, STALE_IN_PROGRESS, BRANCH_MISSING, CLAUDE_MD_ROOT_STALE, CLAUDE_MD_ROOT_MISSING)
- **validate_state.py** — L1 YAML validation against state-machine-schema
- **lessons-match.py** — Extracts top-3 relevant lessons for current task

### Profile System

11 profiles (e.g., `app_web_backend`, `app_web_frontend`, `fullstack`, `ml_project`, `agent_ia`) × 4 tiers (`experimental`, `tool`, `development`, `production`). Config keys: `stages_skipped`, `tdd_required`, `security_gate`, `stop_points_calibration`. See `templates/_config/profile-matrix.md`.

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

## v3.9.0 — Layered dev↔QA loop + lead-resolution tier

Stage 04 ganha 3 layers de QA, executados **sempre, todos tiers**:

- **L1 writer** (subagente) — vertical TDD: tracer-first + loop `RED → GREEN → CI scope → REFACTOR` (anti-horizontal slicing). Drop Akita 15-itens inline (self-grading bias documentado: Huang ICLR 2024, arxiv 2510.11822, arxiv 2509.16533).
- **L2 forensic+ extended** — 7 deterministic checks git-only (4 originais v3.8.0 + 3 novos): Check 5 acceptance↔test mapping, Check 6 NÃO QUERO violations, Check 7 ADR import drift. HARD → skip L3, surgical retry.
- **L3 critic ortogonal** — Agent fresh context, `model = TIER_CEILING[tier]` sempre, anti-sycophancy hardcoded em `templates/critic-prompt.md`. Output triplet (claim, evidence file:line, counterexample, severity BLOCKING|MAJOR|MINOR; decision APPROVE|REJECT|ABSTAIN).

**Per-task loop cap 3 attempts.** Esgotado OR convergence trip (Jaccard ≥ 0.7) OR catastrophic detected → **lead-resolution tier**:

- **B1 REWRITE_SPEC** — lead reescreve spec mais rigorosa, 1 final spawn writer.
- **B3 DIRECT_IMPL** — lead escreve direto em branch `wave-<NNN>-<N>/<slug>-lead-resolved`, passa L2+L3 igual.
- **B4 VOID_TASK** — bloco `### VOIDED` em plan.md com rationale concreto, wave-planner --recalculate.

Cap 1 attempt per bucket. Sequence B1→B3→B4. Stage 05 audit (sub-step novo 5.5) detecta loosen/silenced/vague — FAIL = `BLOCKED_ERROR error_type: lead_resolution_audit_failed`.

**Pick-model heurística** (`scripts/pick-model.py`): `compute_score(estimated_lines, hot_paths, security_sensitive, public_api_change, algorithm_heavy, doc_only/config_only/css_only, tier)` + tier ceiling cap. Writer ≤ ceiling; critic = ceiling sempre.

Docs canônicos: `references/critic-protocol.md`, `references/lead-resolution-protocol.md`, `references/mocking-guidelines.md` (boundaries-only mocking, mattpocock alignment).

Mudanças ativas em:
- `scripts/forensic-plus.py` (+Checks 5/6/7, JSON schema bump backward-compat)
- `scripts/lead-diagnose.py` (novo) — Jaccard cluster + catastrophic detector + bucket recommend + surgical brief render
- `scripts/pick-model.py` (novo) — score + tier ceiling + writer/critic split
- `scripts/agent-brief-render.py` (--tier flag integra pick-model)
- `templates/critic-prompt.md` (novo)
- `templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl` (flow novo: TDD vertical → L2 → L3 → diagnose → retry/lead-bucket; step 9 lead-resolution)
- `templates/workspace/stages/05_verification/CONTEXT.md.tpl` (sub-step 5.5 audit lead resolutions)
- `references/4-block-contract-template.md` (rewrite §3 vertical TDD; §5 Akita DELETED)
- `references/forensic-plus-protocol.md` (7 checks)
- `references/state-machine-schema.md` (+status LEAD_RESOLUTION_IN_PROGRESS, +5 error_types)
- `scripts/migrate-workspace.py` (3.8.0→3.9.0 step bump-only)
- `scripts/recovery-wizard.py` (+LEAD_RESOLUTION_STALE)
- `scripts/validate_state.py` (VALID_STATUSES += LEAD_RESOLUTION_IN_PROGRESS)
- 9 drift detectors novos em `tests/unit/test_no_drift.py`
- `tests/unit/test_lead_diagnose.py` (novo, 17 cases)
- `tests/unit/test_pick_model.py` (novo, 22 cases incl. property-based via Hypothesis)
- `tests/unit/test_forensic_plus.py` (+6 cases v3.9.0)
- `tests/unit/test_migrate_workspace.py` (+5 cases v3.9.0)

934 tests passing, 74% coverage.

## v3.8.0 — Forensic+ wave reviewer (anti-fraude estrutural)

Step 8 do pipeline 12-passos (stage 04) expandido em sub-steps 8a/8b/8c/8d. 8a = `scripts/forensic-plus.py` audita cada task AFK da wave (skip HITL): 4 checks git-only (test asserções ≥2, files fora `files_touched` declarado, scope creep > 3× `### Estimated lines`, TODO/FIXME/HACK adicionados). Severidade tier-aware (HARD/SOFT). HARD → `approved_pending_ci: false` + re-spawn cap `MAX_FORENSIC_RETRIES = 2` (3ª HARD → `BLOCKED_ERROR error_type: forensic_max_retries`); SOFT → `wave-summary.md § Forensic+ summary`; nenhum → approved. Crash do script (exit 1) → `BLOCKED_ERROR error_type: forensic_script_crash`.

Doc canônico: `references/forensic-plus-protocol.md`. Mudanças ativas em:
- `scripts/forensic-plus.py` (novo, 188 linhas)
- `templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl` step 8 → 8a/8b/8c/8d
- `references/wave-execution-protocol.md` step 8 expansion
- `references/wave-planner-algorithm.md` §10 flag rename: `skip_wave_reviewer` → `skip_cross_task_audit` (alias backward-compat até v3.9.0)
- `scripts/wave-planner-script.py` `render_wave_plan` emit annotation 1-task wave
- `references/4-block-contract-template.md` `### Estimated lines` opcional (Check 3)
- `references/state-machine-schema.md` documenta `error_type: forensic_max_retries|forensic_script_crash`
- 4 drift detectors novos em `tests/unit/test_no_drift.py` (doc canônico exists, bootstrap runtime_refs, L2 cross-ref, wave-execution sub-steps)

## v3.6.0 — Preview loop (build-iterate visual)

Profile `app_web_frontend` + `fullstack` ganham preview loop opt-in-by-default.
Doc canônico: `references/preview-loop-protocol.md`. Cobre 10 decisões consolidadas:

| # | Tópico | Decisão |
|---|---|---|
| 1 | Dev server lifecycle | Starta entry stage 04, mata exit. PID em `.icm-main/.dev-server.pid` |
| 2 | Mock data | Tier-based: exp/tool=fixtures; dev=msw_faker; prod=msw_faker_zod |
| 3 | Feedback comm | Combo livre + priming kickoff. Stop `feedback_ambiguous` |
| 4 | URL atual | CDP live (`--remote-debugging-port=9222 --user-data-dir=.icm-chrome-profile`) |
| 5 | Verificação | `tsc` cada Edit; lint+Playwright wave-end ou sob pedido |
| 6 | Storybook? | Vite/Next preview pages em `preview/` excluídos do production build |
| 7 | Screenshot tool | Sem padronização; tip kickoff (Win+Shift+S, ShareX) |
| 8 | Iter cap | Sem cap. Humano fecha quando OK |
| 9 | Design cascade | Threshold 5 componentes afetados → confirma |
| 10 | Multi-tela | CDP só URL default; replay sob pedido + auto-detect keywords |

Mudanças ativas em:
- `scripts/profile-merge.py:_preview_loop_config` emite bloco `preview_loop` em frontend/fullstack
- `scripts/bootstrap.py:detect_package_manager` (npm/pnpm/yarn/bun via lockfile)
- `scripts/recovery-wizard.py` tipos novos `DEV_SERVER_ORPHAN` + `CDP_DISCONNECTED`
- `templates/.claude/scripts/launch-chrome-cdp.{bat,sh}` helpers
- `templates/workspace/stages/02_design/CONTEXT.md.tpl` step 7.6 (mock schema)
- `templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl` entry/exit hooks + stop points novos

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
