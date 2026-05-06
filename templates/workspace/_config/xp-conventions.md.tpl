---
layer: L3
scope: conventions
workspace: "{{WORKSPACE}}"
profile: "{{PROFILE}}"
tier: "{{TIER}}"
---

# Conventions — {{WORKSPACE}}

Code and process conventions for this workspace. Derived from profile `{{PROFILE}}` / tier `{{TIER}}`.

**Lineage:** Clean Code and TDD rules from the `xp-workflow` v3 skill (Akita: "Clean Code for AI Agents"). This document is the bridge — the ICM skill does not invoke `xp-workflow` at runtime, but its conventions are materialized here and in the Akita auto-QA (15 items, `references/4-block-contract-template.md` §5).

## Naming

- **Files:** kebab-case (`user-model.ts`, `auth-routes.py`)
- **Directories:** kebab-case (`api-handlers/`, `data-pipelines/`)
- **Code identifiers:** follow language convention (camelCase JS, snake_case Python)
- **Grep-friendly names:** `rg "<name>"` must return <5 unrelated hits. If it returns more, rename to be more specific.
- **Domain terms without a good translation:** allowed in PT (`nota_fiscal`, `cnpj`, `cpf`, `cfop`, `icms`). Everything else in English.
- **ADRs:** `NNNN-slug.md` in `docs/decisions/`

## Functions & Files (Clean Code gates)

- **Functions:** 4-20 lines. Exceeds only with a justification comment. If >20, split.
- **Files:** <300 lines = ok. 300-500 = warn. >500 = mandatory split.
- **Nesting:** max 2 levels. Prefer early return. Deep if/else = refactor.
- **Duplication:** zero tolerance. If you copied, extract. Every duplication is immediate technical debt.
- **DI via constructor/parameter.** Never global. Explicit injection = testable.

## Types & Boundaries

- **Explicit types** on params, returns, and exports. No `any`, no untyped function.
- **Error messages** include the offending value + expected form: `Expected UserDTO, got null` (not `Invalid input`).
- **Boundaries** (user input, external API, database): explicit and defensive validation. Inside a module: trust the types.

## Imports & Structure

- Imports grouped: stdlib → third-party → local
- Order: alphabetical within each group
- Path aliases: declare in `tsconfig.json` / `pyproject.toml` per language
- **Circular imports:** zero. If detected, refactor immediately.
- **Dead code:** zero. Unused functions, imports, and variables = delete in refactor.

## Docstrings & Comments

- **Mandatory docstrings** on every public function. 4 elements:
  1. What it does (clear language)
  2. What it is for (project need)
  3. Inputs and outputs (in practical terms)
  4. Side-effect warnings (writes to DB, calls external API, deletes file)
- **Inline comments:** WHY, not WHAT. Exception: technical reference (RFC, issue, commit SHA).
- **Comments with provenance:** agent preserves comments it wrote. Do not prune.
- **Commented-out code (ghost code):** zero. Delete or git-blame.

## Formatting

- Linter: follow language default (ESLint/Prettier for JS, Ruff/Black for Python)
- Max line length: 120 characters
- Indentation: 2 spaces (JS/TS), 4 spaces (Python)

## Git

- Commits on workspace branch: mandatory prefix `workspace {{WORKSPACE_NUM}}:` (enforced by commit-msg hook). Format: `workspace {{WORKSPACE_NUM}}: <description>` or `workspace {{WORKSPACE_NUM}}: <type>: <description>` (type = feat/fix/refactor/test/docs/chore/perf/ci, optional but recommended).
- Commits on wave branches (`wave-{{WORKSPACE_NUM}}-<N>/<task-slug>`): standard Conventional Commits without ICM prefix. Format: `<type>: <description>`. Examples: `feat: add JWT validation`, `test: unit tests for auth middleware`.
- Branches: `workspace/{{WORKSPACE}}` for state files, `wave-{{WORKSPACE_NUM}}-<N>/<task-slug>` for code
- Never `--no-verify` on workspace branch

## Testing (calibrated by tier)

- **experimental:** TDD optional (skip allowed; no penalty in verification)
- **tool:** TDD mandatory when task touches >1 module or public API; optional for single-file/internal tasks
- **development:** TDD mandatory (all tasks; stage 04 implementation waves inline gates enforces)
- **production:** TDD mandatory + security gate (all tasks; stage 05 + stage 04 (L3 critic) enforce)

Canonical cycle per task (7 steps): RED → GREEN → CI gate → REFACTOR → CI gate → Auto-QA Akita → COMPLETE. Details in `references/4-block-contract-template.md` §3.

### Dirt Check (post-cycle, Akita step 6)

After each TDD cycle, 3 mandatory questions:
1. Is there duplication introduced in this cycle? Factor it out now.
2. Did any name become generic/grep-unfriendly? Rename now.
3. Did a function exceed 20 lines or a file exceed 300? Split now.

## Security (calibrated by tier)

- **experimental:** no gate
- **tool:** no gate
- **development:** security gate on (item 8 PII)
- **production:** security gate on + DPO (item 8 hard+DPO)

### Secrets & PII

- Never commit `.env`, credentials, API keys, tokens.
- Always `.env.example` with placeholders.
- Read via env var only. Never hardcoded in code.
- Logs do not contain PII or tokens. Log error type + anonymous context, never the value.
- If a secret leaks: rotate immediately, document incident in `docs/lessons.md`.

## Clean Code gates by language (CI + pre-commit)

Applied according to the stack declared in ADRs. Each gate enforced by tooling, not manual review.

| Gate | Python | TypeScript/JS | Others |
|---|---|---|---|
| Formatter | `ruff format` / `black` | `prettier` | language default |
| Linter | `ruff` | `eslint` | canonical linter |
| Type check | `mypy --strict` | `tsc --strict` | native or `--strict` equivalent |
| Complexity | `radon`, `xenon` | `eslint-plugin-sonarjs` | equivalent tool |
| Duplication | `pylint --duplicate-code` | `jscpd` | equivalent tool |
| Size (func/file) | custom linter | `eslint max-lines` | custom linter |
| Security | `bandit`, `pip-audit` | `npm audit`, `semgrep` | equivalent tool |
| Secrets | `gitleaks` | `gitleaks` | `gitleaks` |
| Coverage | `pytest-cov` | `vitest --coverage` | equivalent tool |

**Tier calibrates rigor:** gates mandatory in `development` and `production`. `tool` runs formatter + linter + secrets. `experimental` runs formatter only.

## Stop Points

Detailed in `_config/stop-points.md` (rendered by bootstrap with tier calibration).

## Runtime dependencies

- **jq** — required for hook `context-check.sh` (anti-compact). If absent, the hook fails silently (no context alert, but the session continues). Install via OS package manager (`apt install jq`, `brew install jq`, `choco install jq`).
