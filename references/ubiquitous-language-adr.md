# ADR — Ubiquitous Language Preservation in en-US Migration (v3.11.0)

> **Version:** v3.11.0
> **Skill:** `xp-icm-workflow`
> **Status:** Accepted (2026-05-04)
> **Decision context:** Full migration of skill artifacts from pt-BR to en-US. This ADR documents which terms remain pt-BR despite the global translation, and why.

## Decision

The skill is migrated to en-US as the canonical source language. **Five categories of terms are preserved in pt-BR** as ubiquitous-language anchors (DDD-style):

1. **4-block headers** in `plan.md` task schema:
   - `O QUE` (instead of "WHAT")
   - `COMO` (instead of "HOW")
   - `NÃO QUERO` (instead of "NOT WANTED" / "OUT OF SCOPE")
   - `VALIDAÇÃO` (instead of "VALIDATION")

2. **Stop point IDs** with pt-BR semantics in their snake_case identifier:
   - `feedback_ambiguous`
   - `design_system_cascade`
   - (others follow snake_case en-US already; no exception needed)

3. **Status enum values** — already en-US (`COMPLETED_AWAITING_HUMAN`, `BLOCKED_HITL`, `LEAD_RESOLUTION_IN_PROGRESS`, etc). No exception.

4. **Stage names** — already en-US (`recon`, `discovery`, `design`, `wave_planner`, `implementation_waves`, `verification`, `review`, `merge`, `feedback_intake`). No exception.

5. **Historical changelog entries** (pre-v3.11.0) — preserved as written. v3.11.0+ entries in en-US.

## Rationale

### Why preserve `O QUE / COMO / NÃO QUERO / VALIDAÇÃO`

These four headers are bound to deterministic regex parsers across the skill:

- `scripts/forensic-plus.py:parse_plan_for_task` — `_bullets_under("NÃO QUERO")` and `_bullets_under("VALIDAÇÃO")` extract metadata used by Checks 5 and 6.
- `scripts/agent-brief-render.py:parse_4block` — regex `^### N[ÃA]O QUERO\s*$` and `^### VALIDA[ÇC][ÃA]O\s*$` map blocks to AGENT-BRIEF sections.
- `scripts/wave-planner-script.py` — task header parser and `Files touched` extractor depend on header layout stability.

Translating these headers to "WHAT / HOW / NOT WANTED / VALIDATION" would:

- Break parsing of every existing `plan.md` in workspaces created before v3.11.0.
- Require a destructive migration that rewrites historical user content.
- Lose the linguistic anchor that has been in continuous use since v3.0.0-beta5.

The DDD principle of ubiquitous language argues for stable terms across all artifacts, even when they cross language boundaries. The 4-block keywords are part of the skill's shared vocabulary with the user.

### Why preserve stop point IDs with pt-BR roots

`feedback_ambiguous` and `design_system_cascade` are referenced in:

- `references/stop-points-canonical.md` catalog.
- `templates/workspace/_config/stop-points.md` (per-workspace config, may be edited by user).
- `_config/profile-effective.yaml:stops_calibration` (computed by `profile-merge.py`).
- L1 history `event: stop_point_triggered, stop_point_id: <id>`.

Renaming the IDs would break:

- All workspaces with these stop points already triggered in their `history`.
- User overrides in `stop-points.md` config (edits would fail to match).
- Recovery wizard cross-references.

The IDs are stable identifiers. The descriptive prose around them is translated to en-US.

### Why translate everything else

- **Reference docs (`references/*.md`)**: read by both the skill author and runtime agents (via `_references/runtime/` mirror in workspaces). en-US is the lingua franca of code-generation models trained primarily on English corpora.
- **Templates (`templates/**/*.tpl`)**: rendered into workspace files used by Claude Code sessions. en-US matches the default communication language.
- **Scripts (`scripts/*.py`)**: docstrings and comments help future maintainers (including LLMs reading the codebase) understand intent. Identifier names (functions, vars) are unchanged.
- **Top-level docs (`SKILL.md`, `README.md`, `CLAUDE.md`)**: skill discovery and onboarding for new users globally.

### Why keep historical changelog in pt-BR

The changelog records what was decided and shipped in each version. Rewriting it in en-US would:

- Distort the historical record (entries were authored in pt-BR with specific phrasing).
- Risk subtle semantic drift (a translation may not capture the original intent).
- Provide no value to readers tracing past decisions (they would not seek translation accuracy from a changelog).

Going forward, v3.11.0+ entries are authored in en-US natively. The changelog becomes mixed-language with a clear cutoff.

## Consequences

### Positive

- Single en-US source for all forward-looking artifacts.
- Lower friction for international contributors.
- Better alignment with LLM training distributions (more accurate reasoning over docs).
- Existing parsers continue to work without migration.

### Negative

- Mixed-language reading experience for users tracing 4-block tasks (en-US prose + pt-BR headers).
- Changelog mixed-language requires a cutoff marker.
- Slight cognitive overhead for translators handling the preserved keywords.

### Neutral

- No behavioral change for runtime parsers, gates, or scripts.
- Existing workspaces continue running unchanged after the bump.

## Drift detection

A new test (`tests/unit/test_no_drift.py:test_no_pt_br_in_canonical`) scans canonical files (`references/*.md` excluding `changelog.md`, `scripts/*.py`, `templates/**/*`, `SKILL.md`, `README.md`, `CLAUDE.md`) using a heuristic regex (matches frequent pt-BR markers like `não`, `são`, `ção`, `ões`) and fails the build if matches are found outside the whitelist of preserved keywords.

The whitelist:

- `O QUE`, `COMO`, `NÃO QUERO`, `VALIDAÇÃO` — 4-block headers (in prose explaining the schema).
- `pt-BR`, `Portuguese`, `Brazilian` — meta-references to the source language.
- `feedback_ambiguous`, `design_system_cascade` — stop point IDs.

False positives in the heuristic (e.g., quoted historical text, code samples) are added to the whitelist explicitly with a `# i18n-allow: <reason>` comment.

## References

- `scripts/forensic-plus.py` — regex parsers bound to 4-block headers.
- `scripts/agent-brief-render.py` — `parse_4block` mapping.
- `references/4-block-contract-template.md` — schema definition (preserves headers).
- `references/stop-points-canonical.md` — stop point catalog.
- `references/changelog.md` — mixed-language cutoff at v3.11.0.
- DDD ubiquitous language principle: Eric Evans, *Domain-Driven Design* (2003).
