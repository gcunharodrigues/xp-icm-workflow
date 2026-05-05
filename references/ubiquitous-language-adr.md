# ADR — Ubiquitous Language and en-US Migration (v3.11.0 / v3.12.0)

> **Version:** v3.12.0
> **Skill:** `xp-icm-workflow`
> **Status:** Accepted (amended 2026-05-05)
> **Decision context:** Full migration of skill artifacts from pt-BR to en-US (v3.11.0), followed by elimination of all preserved pt-BR keywords (v3.12.0 zero-pt-BR amendment).

## Decision

**v3.12.0 amendment (2026-05-05):** All previously preserved pt-BR keywords have been translated to en-US. The skill now has a single en-US canonical source with NO pt-BR carry-overs.

Translation applied:

- `O QUE` → `WHAT`
- `COMO` → `HOW`
- `NÃO QUERO` → `OUT OF SCOPE` <!-- i18n-allow: historical translation record -->
- `VALIDAÇÃO` → `VALIDATION`
- `ADRs aplicáveis` → `Applicable ADRs`
- `feedback_ambiguous` → `ambiguous_feedback` (stop point ID, en-US adj-noun word order)
- Stage 08 retrospective: `O QUE FUNCIONOU` → `WHAT WORKED`, `O QUE NÃO FUNCIONOU` → `WHAT DID NOT WORK`, `QUAL DOR PERSISTE` → `WHAT PAIN PERSISTS`, `QUE LIÇÃO TIRAR` → `WHAT LESSON TO DRAW` <!-- i18n-allow: historical translation record -->
- `Saída A/B/C` → `Exit A/B/C`
- File rename `references/feedback-intake-fase08.md` → `references/feedback-intake-stage08.md`
- Historical changelog (pre-v3.11.0) translated to en-US (mixed-language cutoff marker removed).

**Breaking change:** Parser regex in `scripts/forensic-plus.py`, `scripts/agent-brief-render.py`, and `scripts/wave-planner-script.py` now match en-US headers (`### WHAT`, `### HOW`, `### OUT OF SCOPE`, `### VALIDATION`, `### Applicable ADRs`). Workspaces created on v3.10.0 or earlier require migration.

Migration step `migrate_3_11_0_to_3_12_0` (in `scripts/migrate-workspace.py`) rewrites L1 history stop-point IDs and plan.md 4-block headers in existing workspaces.

## Original v3.11.0 decision (superseded by v3.12.0)

> **Note:** This section is preserved as a historical record. The categories below were preserved in v3.11.0 and have since been translated in v3.12.0.

The skill was migrated to en-US as the canonical source language. **Six categories of terms were preserved in pt-BR** as ubiquitous-language anchors (DDD-style) in v3.11.0:

1. **4-block headers** in `plan.md` task schema:
   - `O QUE` (now: `WHAT`)
   - `COMO` (now: `HOW`)
   - `NÃO QUERO` (now: `OUT OF SCOPE`) <!-- i18n-allow: historical record of superseded v3.11.0 decision -->
   - `VALIDAÇÃO` (now: `VALIDATION`)

2. **4-block metadata field** parsed from plan.md tasks:
   - `ADRs aplicáveis` (now: `Applicable ADRs`)

3. **Stop point IDs** — still snake_case en-US identifiers, no pt-BR exception:
   - `ambiguous_feedback`
   - `design_system_cascade`

4. **Status enum values** — already en-US. No exception.

5. **Stage names** — already en-US. No exception.

6. **Historical changelog entries** (pre-v3.11.0) — preserved as written in v3.11.0; translated in v3.12.0.

### v3.11.0 rationale (superseded)

The v3.11.0 rationale for preserving 4-block headers was parser stability: changing them would break existing `plan.md` files and require destructive migration. This concern was resolved in v3.12.0 by shipping `migrate_3_11_0_to_3_12_0` which rewrites plan.md headers in-place.

The v3.11.0 rationale for preserving the historical changelog was historical accuracy. This was overridden in v3.12.0 in favor of a single-language canonical source.

## Consequences (v3.12.0)

### Positive

- Single en-US source for all artifacts — zero exception tracking required.
- `i18n-audit.py` PRESERVED_KEYWORDS whitelist reduced to meta-references + 2 stop point IDs.
- Better alignment with LLM training distributions.
- Existing parsers updated; no silent language mix in task files.

### Negative

- Breaking change for workspaces on v3.10.0 or earlier — migration required before running stage 04 with new parsers.
- Historical changelog entries translated (potential minor semantic drift from original Portuguese phrasing).

### Neutral

- Stop point IDs `ambiguous_feedback` / `design_system_cascade` remain unchanged (were already en-US).
- No behavioral change to the 9-stage pipeline logic.

## Drift detection

The drift gate `tests/unit/test_no_drift.py:test_no_pt_br_in_canonical` scans canonical files using a heuristic regex and fails the build if matches are found outside the whitelist of preserved keywords. <!-- i18n-allow: exemplifying the detection patterns -->

The v3.12.0 whitelist (in `scripts/i18n-audit.py:PRESERVED_KEYWORDS`):

- `ambiguous_feedback`, `design_system_cascade` — stop point IDs (en-US identifiers).
- `pt-BR`, `Portuguese`, `Brazilian` — meta-references to the source language.
- `ubiquitous-language-adr` — reference to this file itself.

## References

- `scripts/forensic-plus.py` — regex parsers now match en-US 4-block headers.
- `scripts/agent-brief-render.py` — `parse_4block` mapping updated to en-US.
- `scripts/wave-planner-script.py` — task header parser updated to en-US.
- `references/4-block-contract-template.md` — schema definition with en-US headers.
- `references/stop-points-canonical.md` — stop point catalog.
- `references/changelog.md` — fully en-US (v3.12.0+).
- `scripts/migrate-workspace.py` — `migrate_3_11_0_to_3_12_0` step.
- DDD ubiquitous language principle: Eric Evans, *Domain-Driven Design* (2003).
