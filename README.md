# xp-icm-workflow

> **Project orchestration skill via filesystem for Claude Code.** One-shot bootstrap creates the ICM (Interpretable Context Methodology) structure in a project and exits; the filesystem governs the cycle. Each stage = 1 Claude session. v3.10.0.

[![tests](https://img.shields.io/badge/tests-855%20passed-brightgreen)](tests/)
[![coverage](https://img.shields.io/badge/coverage-83%25-brightgreen)](pyproject.toml)
[![python](https://img.shields.io/badge/python-3.11%2B-blue)](system-requirements.md)
[![version](https://img.shields.io/badge/version-v4.0.0-blue)](references/changelog.md)
[![license](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## Why it exists

Non-trivial projects with Claude Code quickly run into:

- Context window overflows when 1 session tries to cover discovery → design → implementation → review.
- Architectural decisions disappear between sessions (no durable record).
- Parallel subagents lack deterministic coordination.
- Recovery from inconsistent state becomes a manual investigation.

**ICM** (Interpretable Context Methodology) solves this via filesystem-as-state: numbered folders represent stages, markdown carries context, fresh sessions read L0+L1+L2 of the current stage and get to work. The skill is a **one-shot midwife** — it creates the structure, exits, and never appears again in the project runtime.

Theoretical basis: VanClief & McDermott, 2025 (`references/icm-paper-summary.md`).

---

## Quickstart (5 minutes)

### 1. Install the skill

Clone into the Claude Code skills directory:

```bash
# Linux/macOS
git clone https://github.com/gcunharodrigues/xp-icm-workflow ~/.claude/skills/xp-icm-workflow

# Windows
git clone https://github.com/gcunharodrigues/xp-icm-workflow %USERPROFILE%\.claude\skills\xp-icm-workflow
```

Install Python deps:

```bash
cd ~/.claude/skills/xp-icm-workflow   # or %USERPROFILE%\... on Windows
pip install -r requirements.txt
bash scripts/check-runtime.sh         # validates runtime (Python 3.11+, git 2.30+, PyYAML)
```

### 2. Bootstrap a workspace in a project

Open Claude Code in the project directory. Two ways:

**Option A — Recommended: let the agent infer everything (free-form description).**

```
/xp-icm-workflow
```

The agent reads your prompt, infers `profile` + `tier` + `workspace-name` via heuristics (keywords: "API/backend" → `app_web_backend`, "React/UI component" → `app_web_frontend`, "ML/train model" → `ml_project`, "POC/spike" → tier `experimental`, etc.), and confirms with you in a short menu before creating the structure. Discovery pending items go into the stage 00 `_seed.md` — you don't need to make any technical decisions before bootstrap.

Example real-world usage:

```
/xp-icm-workflow

> I want to create a REST API for task management in FastAPI with JWT auth
> and pytest tests. It will run in production on AWS.
```

Agent responds:

```
Inferred: profile=app_web_backend tier=production workspace-name=001-api-tarefas-jwt
[a] confirm   [b] correct   [c] cancel
```

You reply `a`, and bootstrap runs.

**Option B — Advanced: pass explicit args** (useful in scripts or when you know exactly what you want):

```
/xp-icm-workflow profile=app_web_backend tier=development
```

Full table of combinations below (§Profiles and §Tiers).

---

The skill creates:

```
your-project/
├── .gitignore                          # updated
├── CLAUDE.md                           # ICM dashboard
├── .icm-main/                          # linked worktree (base branch)
└── workspaces/
    └── 001-<slug>/
        ├── CLAUDE.md                   # L0: immutable identity
        ├── CONTEXT.md                  # L1: state machine
        └── stages/
            ├── 00_recon/CONTEXT.md     # L2: current stage instructions
            ├── 01_discovery/...
            └── ...
```

And exits. The next Claude session in the same dir reads L0+L1+L2 automatically and continues.

### 3. Advance through the stages

Each stage ends by writing `_kickoff.md` to the next one. You open a new Claude session, it reads the kickoff, and continues. Full walkthrough: [`references/example-run.md`](references/example-run.md).

---

## Features

- **5 active stages (v4.0):** `00 recon → 01 discovery → 02 design+plan → 04 implementation waves → 08 feedback intake` (03 wave_planner, 05 verification, 06 review, 07 merge deprecated — merged into 02 and 04).
- **11 profiles × 4 tiers = 44 combinations** calibrating rigor (mandatory TDD, security gate, stop points, subagent cap).
- **Parallel subagents** in stage 04 via Agent Tool (`Agent(isolation: "worktree")`).
- **Deterministic Wave Planner:** DAG → topological sort → sub-waves (HITL isolated cap=1).
- **15 canonical stop points** + thresholds calibrated per tier.
- **Recovery Wizard** detects 14 inconsistency types + A/B/C actions.
- **Automatic drift detector:** version bump without multi-file sweep is blocked in CI.
- **Mandatory runtime cleanup** (v3.7.0) pre-exit stage 08: 6 categories, strict universal.
- **Zero-friction spawn handoff** (v3.7.0): `.icm/spawn-pending.json` auto-detected by bootstrap.

---

## Profiles (11 canonical)

Each profile calibrates skipped stages, mandatory TDD, security gate, peer-review, subagent cap, and stop point thresholds. Operational details: [`templates/_config/profile-matrix.md`](templates/_config/profile-matrix.md).

| Profile | When to use | Prompt signals |
|---|---|---|
| **`app_web_backend`** | REST/GraphQL API, microservices, backend services, endpoints | "API", "backend", "endpoint", "FastAPI/Express/Django/Spring" |
| **`app_web_frontend`** | SPA/PWA, React/Vue/Svelte components, web pages | "web page", "React/Vue component", "UI", "Next.js/Vite" |
| **`fullstack`** | Complete coordinated backend + frontend app | "fullstack", "complete app", "backend + frontend" |
| **`dashboard`** | BI, analytics, data visualization, admin panels | "dashboard", "BI", "analytics", "metrics", "Streamlit/Tableau" |
| **`data_analysis`** | EDA, notebooks, statistical analysis, reports | "EDA", "notebook", "data analysis", "Jupyter/pandas" |
| **`ml_project`** | ML pipeline, fine-tune, model training, MLOps | "train model", "ML pipeline", "fine-tune", "PyTorch/scikit-learn" |
| **`agent_ia`** | Claude Code skills, LLM agents, subagents, MCP servers | "skill", "agent", "subagent", "LLM tool", "MCP" |
| **`cli_tool`** | Command-line tool, shell automation | "CLI", "command", "command-line tool" |
| **`framework_library`** | Lib, SDK, framework, distributable package | "lib", "SDK", "framework", "package", "npm/pypi" |
| **`technical_article`** | Article, paper, technical post, in-depth documentation | "article", "paper", "technical post", "blog post" |
| **`experiment`** | POC, spike, throwaway experiment, proof of concept | "POC", "spike", "experiment", "proof of concept" |

---

## Tiers (4 canonical)

Tier scales rigor independently of profile. The same profile at tier `experimental` vs `production` receives different calibration (optional vs mandatory TDD, security gate off vs on, etc.).

| Tier | When to use | Primary calibration |
|---|---|---|
| **`experimental`** | POCs, spikes, throwaway code, hypothesis-validation code | Optional TDD, no security gate, peer-review off, subagent cap=2, loose stop points (item 5 R$50, item 7/8 warning) |
| **`tool`** | Internal tools, personal automations, side projects | Optional TDD, security gate off, peer-review off, subagent cap=3, moderate stop points (item 5 R$200) |
| **`development`** | Apps in active development, team projects pre-prod | Mandatory TDD, security gate on, optional peer-review, subagent cap=5, strict stop points (item 5 R$500, item 7 hard) |
| **`production`** | Production apps, critical systems, real user data | Mandatory TDD, security gate on, mandatory peer-review, subagent cap=5, maximum strict stop points (item 5 R$1000, item 8 hard+DPO) |

**Default when not specified:** `tier=development` (medium). Interactive bootstrap asks if missing.

---

## Key documents

| Doc | Contents |
|---|---|
| [`SKILL.md`](SKILL.md) | Skill entry point |
| [`references/icm-paper-summary.md`](references/icm-paper-summary.md) | ICM theoretical basis |
| [`references/example-run.md`](references/example-run.md) | Concrete E2E 9-session walkthrough |
| [`references/state-machine-schema.md`](references/state-machine-schema.md) | L1 schema + sub_stage enum |
| [`references/stop-points-canonical.md`](references/stop-points-canonical.md) | 15 stop points + thresholds per tier |
| [`references/runtime-cleanup-protocol.md`](references/runtime-cleanup-protocol.md) | 6-category checklist pre-exit stage 08 (v3.7.0) |
| [`references/spawn-handoff-protocol.md`](references/spawn-handoff-protocol.md) | `.icm/spawn-pending.json` + `--spawn-from` arg (v3.7.0) |
| [`references/preview-loop-protocol.md`](references/preview-loop-protocol.md) | Build-iterate visual frontend (v3.6.0) |
| [`references/design-system.md`](references/design-system.md) | DESIGN.md format frontend/fullstack |
| [`references/4-block-contract-template.md`](references/4-block-contract-template.md) | 4-block + 7-step TDD cycle + Akita 15-item |
| [`references/wave-planner-algorithm.md`](references/wave-planner-algorithm.md) | DAG + LLM review subagent |
| [`references/subagent-protocol.md`](references/subagent-protocol.md) | Spawn via Agent tool + mid-wave reduce |
| [`references/feedback-intake-stage08.md`](references/feedback-intake-stage08.md) | 3 outcomes A/B/C |
| [`references/recovery-wizard.md`](references/recovery-wizard.md) | 14 inconsistencies + reconstruction |
| [`references/worktree-model.md`](references/worktree-model.md) | Parallel worktree `.icm-main/` (v3.4.0) |
| [`references/changelog.md`](references/changelog.md) | Full version history |
| [`system-requirements.md`](system-requirements.md) | Runtime + permissions allowlist |

---

## Layered architecture

| Layer | Contents | Typical path |
|---|---|---|
| **L0** | Immutable workspace identity | `workspaces/NNN/CLAUDE.md` |
| **L1** | State machine (YAML frontmatter) | `workspaces/NNN/CONTEXT.md` |
| **L2** | Current stage instructions | `workspaces/NNN/stages/<NN>/CONTEXT.md` |
| **L3** | Conventions, superpowers summaries, runtime refs | `workspaces/NNN/_config/`, `_references/` |
| **L4** | Nascent outputs (discovery.md, plan.md, etc.) | `workspaces/NNN/stages/<NN>/output/` |

---

## Tests

```bash
bash tests/run.sh             # pytest + bats (if available)
bash tests/run.sh --ci        # coverage XML for CI
bash tests/run.sh --no-bats   # pytest only, skip bats
```

CI: [`.github/workflows/test-skill.yml`](.github/workflows/test-skill.yml) — Ubuntu runner with Python 3.13 + bats.

---

## Contributing

Bug reports, feature requests and PRs are welcome.

### Report a bug

Open an issue at [github.com/gcunharodrigues/xp-icm-workflow/issues](https://github.com/gcunharodrigues/xp-icm-workflow/issues) with:

1. **Version** of the skill (paste `bootstrap.py:SKILL_VERSION`).
2. **OS + Python version** (`python --version`, `uname -a` or `ver` on Windows).
3. **Minimal reproduction:** exact commands + relevant output (with PII removed).
4. **Expected vs observed behavior.**
5. **Logs:** if available, `workspaces/<NNN>/CONTEXT.md` (L1 frontmatter + history) and `_kickoff.md` from the stage where it broke.

### Submit a PR

1. **Fork** this repo.
2. **Branch:** `feat/<short-slug>` or `fix/<short-slug>` from `main`.
3. **Mandatory tests:** TDD-first. Add tests in `tests/unit/` covering the new case. PR without tests = blocked.
4. **Drift gate:** run `pytest tests/unit/test_no_drift.py -v` before merging. If version changed, README/SKILL.md/changelog need sync (see [CONTRIBUTING.md](CONTRIBUTING.md)).
5. **Conventional Commits:** `feat:`, `fix:`, `docs:`, `test:`, `refactor:`. Subject ≤ 70 chars.
6. **Green suite:** `bash tests/run.sh --no-bats` must pass 782+ tests.
7. Open PR against `main` with description: motivation, changes, breaking changes (if any), tests added.

Flow details, code standards, and drift rules in [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Current version

**v3.12.1** — Script CLI contract hardening + residual pt-BR cleanup. Fixed wave-planner "none" sentinel (accepts both `none` and legacy `nenhum`), comma-safe `--prev-outputs` parsing, parenthetical stripping in deps. New `references/script-cli-reference.md` documents exact CLI format for all 18 scripts. Stage templates cross-ref the new doc. See [`references/changelog.md`](references/changelog.md) for full entry.

## v3.12.1 — Script CLI contract hardening + residual pt-BR cleanup

Fixed 3 parser bugs and created canonical CLI reference doc. See [`references/changelog.md`](references/changelog.md).

## v3.12.0 — Zero pt-BR (full migration)

Eliminated all preserved pt-BR keywords. Parser regex updated to match en-US headers (`### WHAT`, `### HOW`, `### OUT OF SCOPE`, `### VALIDATION`). Migration step `migrate_3_11_0_to_3_12_0` handles L1 history + plan.md 4-block rewrite. ADR amended: zero pt-BR keywords. Cross-ref: [`references/changelog.md`](references/changelog.md).

## v3.11.0 — Full migration to en-US

All user-facing text (templates, reference docs, scripts, SKILL.md, README.md, CLAUDE.md skill section) translated from pt-BR to en-US. No schema or behavioral change. Cross-ref: [`references/changelog.md`](references/changelog.md).

---

**v3.10.0** — E2E coverage reinforcement (Level 2). Wave-planner detects user-facing tasks via `USER_FACING_PATHS_BY_PROFILE` defaults (backend/frontend/fullstack/cli/agent_ia/etc) and auto-emits annotation in wave-plan.md. Forensic+ Check 8 validates that tasks with `Requires E2E update: true` in plan.md have ≥1 file in `e2e/`/`cypress/`/`playwright/`/`tests/e2e/` (HARD dev/prod, SOFT exp/tool). L4 wave gate step 11b runs E2E suite **universally** for tier dev/prod (profile-independent). Stage 05 sub-step 4.7 audits suite exists + freshness < 7 days + skip rationale. New doc `references/e2e-coverage-protocol.md`. Recovery wizard +`E2E_SUITE_STALE`.

Canonical version: [`scripts/bootstrap.py:SKILL_VERSION`](scripts/bootstrap.py). Full history: [`references/changelog.md`](references/changelog.md).

### Highlights by version

- **v3.12.1** (2026-05-05) — Script CLI contract hardening + residual pt-BR cleanup. Fixed wave-planner "none" sentinel, comma-safe `--prev-outputs` parsing, parenthetical stripping. New `script-cli-reference.md`.
- **v3.12.0** (2026-05-05) — Zero pt-BR (full migration). All preserved pt-BR keywords translated; parser regex updated to en-US headers; migration step `migrate_3_11_0_to_3_12_0`; ADR amended; changelog fully en-US.
- **v3.10.0** (2026-05-04) — E2E coverage reinforcement. Wave-planner auto-detects user-facing tasks; forensic+ Check 8 enforces ≥1 e2e file in diff (HARD dev/prod); L4 wave gate universal tier dev/prod; Stage 05 audits suite freshness. Doc: `e2e-coverage-protocol.md`.
- **v3.9.0** (2026-05-04) — Layered dev↔QA loop + lead-resolution tier. L2 forensic+ extended (7 checks) + L3 orthogonal critic (intra-Claude Sonnet/Opus mix, anti-sycophancy) + buckets B1 REWRITE_SPEC / B3 DIRECT_IMPL / B4 VOID_TASK. Vertical TDD + tracer-first. Drop Akita 15-item checklist. Pick-model heuristic (writer/critic split by complexity score + tier ceiling). Docs: `critic-protocol.md`, `lead-resolution-protocol.md`, `mocking-guidelines.md`.
- **v3.8.0** (2026-05-03) — Forensic+ wave reviewer. 4 anti-fraud checks per task in step 8 wave-reviewer (test assertions, files outside declared, scope creep, TODO/FIXME). Tier-aware HARD/SOFT severity. Re-spawn cap 2. Doc: `references/forensic-plus-protocol.md`.
- **v3.7.2** (2026-05-01) — Exit A/C for last active workspace triggers automatic `/init` + opt-in cleanup menu (`scripts/icm-cleanup.py`). `.index.md` + `settings.local.json` hooks cleaned. SessionStart hook prefers L1 status over `.index.md`. Recovery wizard new detector `STALE_ICM_MAIN_AFTER_CLOSE`.
- **v3.7.0** (2026-05-01) — Runtime cleanup + spawn-pending handoff. Stop point #15 `runtime_cleanup_failed`. Migration v3.3→v3.7.
- **v3.6.0** (2026-04-30) — Frontend preview loop (build-iterate visual). Chrome CDP integration, tier-based mock data.
- **v3.5.0** (2026-04-29) — Stage 04 protocol gaps fix (10 edge cases). Drift detector introduced.
- **v3.4.0** (2026-04-28) — Cross-branch worktree model (`.icm-main/`). Cross-branch visibility resolved.
- **v3.3.0** (2026-04-25) — 8 patterns adopted from [mattpocock/skills](https://github.com/mattpocock/skills) (AGENT-BRIEF, Ubiquitous Language, ADR gate, Diagnose 6-phase, Triage, etc.).

---

## License

MIT — see [LICENSE](LICENSE).

---

## Maintainer

[@gcunharodrigues](https://github.com/gcunharodrigues)

## Acknowledgments

This skill is a synthesis of multiple external sources. Full attributions in [ACKNOWLEDGMENTS.md](ACKNOWLEDGMENTS.md):

- **Theoretical basis:** ICM Paper (VanClief & McDermott, 2025).
- **Superpowers** ([obra/superpowers-marketplace](https://github.com/obra/superpowers-marketplace)) — Jesse Vincent (@obra). The subagent-driven-development philosophy, strict TDD, brainstorming-first, dispatching-parallel-agents has permeated this skill since v3.0. 200-token summaries in `_references/superpowers-summary/`.
- **9 patterns adopted:** [mattpocock/skills](https://github.com/mattpocock/skills) — ADR format, AGENT-BRIEF, Ubiquitous Language, Diagnose 6-phase, Triage state machine, OUT-OF-SCOPE, HITL/AFK, Design It Twice, Deep modules.
- **Auto-QA Akita checklist (TDD loop):** inspired by [Fabio Akita](https://www.akitaonrails.com/) blog posts (clean code, naming, justified abstractions).
- **Design system inspiration:** [VoltAgent/awesome-design-md](https://github.com/VoltAgent/awesome-design-md), [Manavarya09/design-extract](https://github.com/Manavarya09/design-extract).
- **Algorithms:** Kahn (1962) topological sort + DFS 3-color cycle detection (Wave Planner). Cockburn — Hexagonal Architecture. Beck — TDD red/green + YAGNI (XP). Hunt & Thomas — DRY (Pragmatic Programmer).
- **Ecosystem:** [Anthropic Claude](https://www.anthropic.com/claude) (LLM engine of the skill) + [Claude Code](https://docs.claude.com/en/docs/claude-code) + [Anthropic Skills system](https://docs.claude.com/en/docs/agents/skills).

If you identify an uncredited source, [open an issue](https://github.com/gcunharodrigues/xp-icm-workflow/issues) with label `attribution-fix`.
