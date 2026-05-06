# v4 QA Stack — Consolidated Reference

> **Version:** v4.0
> **Replaces:** forensic-plus-protocol.md, critic-protocol.md, e2e-coverage-protocol.md, lead-resolution-protocol.md, mocking-guidelines.md, 4-block-contract-template.md (QA sections), script-cli-reference.md

## Overview

Stage 04 (implementation waves) uses a 3-layer QA stack per task:

| Layer | Name | Tokens | What |
|-------|------|--------|------|
| L2 | Forensic+ extended | 0 | 8 deterministic git-only checks |
| L3 | Orthogonal critic | ~3-8k | Fresh-context Agent reviews diff |
| L4 | Wave gate | 0 (CI) | CI green + E2E green + cross-task coherence |

## L2: Forensic+ Extended (8 checks)

```bash
python scripts/forensic-plus.py \
    --workspace-num <NNN> --wave <N> --task-slug <slug> \
    --base-branch <BASE> --tier <T> \
    --plan <path>/plan.md --output json
```

| # | Check | Severity | Description |
|---|-------|----------|-------------|
| 1 | Test assertions | HARD | ≥2 assertions in diff |
| 2 | Files outside declared | HARD | Files modified not in plan.md declared files_touched |
| 3 | Scope creep | SOFT (exp/tool) / HARD (dev/prod) | > 3× estimated lines |
| 4 | TODO/FIXME/HACK | SOFT | New technical debt markers |
| 5 | Acceptance↔test mapping | HARD | Acceptance bullets without corresponding tests |
| 6 | OUT OF SCOPE violations | HARD | Implementation in declared OUT OF SCOPE areas |
| 7 | ADR import drift | HARD | Depends on ADRs not listed in plan.md |
| 8 | E2E coverage | SOFT (exp/tool) / HARD (dev/prod) | Task with `Requires E2E update: true` must touch e2e/ paths |

HARD in any check → skip L3, surgical retry. SOFT only → proceed to L3.
Max 3 attempts per task (1 original + 2 retries).

## L3: Orthogonal Critic

Fresh-context Agent, model = tier ceiling, anti-sycophancy hardcoded.

```bash
python scripts/render-critic-prompt.py \
    --task-slug <slug> --wave <N> --tier <TIER> \
    --workspace-num <NNN> --base-branch <BASE> \
    --plan <path>/plan.md --critic-model <model> \
    --output output/wave-<N>/task-<slug>-critic-prompt-round<R>.md
```

Critic output: JSON triplet per concern — claim, evidence (file:line), counterexample, severity (BLOCKING|MAJOR|MINOR), decision (APPROVE|REJECT|ABSTAIN).

- REJECT (≥1 BLOCKING or ≥2 MAJOR) → diagnose → retry or escalate
- APPROVE → task PASS

## L4: Wave Gate

After all tasks merged:
- **CI green** (always, all tiers)
- **E2E green** (tier dev/prod with user_facing_paths)
- **Cross-task coherence** (production tier, ≥2 tasks sharing file/API)

## Lead-Resolution (when QA loop exhausted)

2 options, 1 attempt each:

| Action | What | When |
|--------|------|------|
| RETRY | Rewrite spec + spawn 1 final writer | Ambiguous spec, convergence trip |
| VOID | Declare task void with rationale | Catastrophic, ADR conflict, RETRY failed |

```bash
python scripts/lead-diagnose.py \
    --task-slug <slug> --wave <N> --workspace-num <NNN> \
    --base-branch <BASE> --critic-rounds <round1.json>[,round2.json] \
    --files-touched <paths> --forensic-files-outside <int> \
    --output output/wave-<N>/task-<slug>-diagnose.md
```

## Model Selection (v4.0 heuristic)

Inline in `agent-brief-render.py`:
- `doc_only: true`, `config_only: true`, `css_only: true` → **haiku**
- `security_sensitive: true`, `public_api_change: true`, `algorithm_heavy: true`, `estimated_lines > 200` → **opus**
- default → **sonnet**

## Mocking Guidelines

Boundaries only. Mock at system edges (HTTP, DB, filesystem, external APIs). Never mock internal domain objects. Aligned with mattpocock/skills boundary-mocking pattern.

## Task Report Format

Lead-written from Agent tool output. Minimal:

```markdown
# Task <slug> — COMPLETE
## Summary
<1-3 sentences>
## Modified files
- <list>
## Tests
- <test file>: <count> tests
## ADRs applied
- <list>
```
