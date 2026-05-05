# Maintainer Checklist — xp-icm-workflow

Checklist for modifying the skill's own code. Every operation lists the exact
files that must be touched. Follow this or drift detectors will catch you.

> **Version:** v3.12.1

---

## 1. Bump SKILL_VERSION

When: any change that increments the version number.

| # | File | Action |
|---|------|--------|
| 1 | `scripts/bootstrap.py` | `SKILL_VERSION = "X.Y.Z"` |
| 2 | `SKILL.md` | Update header `# xp-icm-workflow vX.Y.Z` |
| 3 | `README.md` | Badge `version-vX.Y.Z` + new `## vX.Y.Z — <title>` section + highlights entry |
| 4 | `references/design-system.md` | Title + `> **Version:** vX.Y.Z` |
| 5 | `references/preview-loop-protocol.md` | Title + `> **Version:** vX.Y.Z` |
| 6 | `references/script-cli-reference.md` | `> **Version:** vX.Y.Z` |
| 7 | `references/changelog.md` | New `## vX.Y.Z — <title> (YYYY-MM-DD)` entry at top |
| 8 | `scripts/migrate-workspace.py` | `CURRENT_SKILL_VERSION` + `SUPPORTED_VERSIONS` last entry + new `migrate_X_to_Y` function + `STEP_FUNCTIONS` entry |
| 9 | `tests/unit/test_migrate_workspace.py` | New smoke + idempotency tests |
| 10 | Any script with `CURRENT_SKILL_VERSION` | grep for it: `pick-model.py`, `lead-diagnose.py` |

**Drift detectors:** `test_version_consistency_canonical_files`, `test_changelog_has_entry_for_canonical_version`, `test_scripts_skill_version_sync`

---

## 2. Create a new Python script

When: adding `scripts/new-tool.py`.

| # | File | Action |
|---|------|--------|
| 1 | `scripts/new-tool.py` | Create. Include `CURRENT_SKILL_VERSION = "X.Y.Z"` if drift-checked |
| 2 | `CLAUDE.md` | Add to "Key Scripts" section if user-facing |
| 3 | `tests/unit/test_new_tool.py` | Create test file (smoke + edge cases) |
| 4 | `references/script-cli-reference.md` | Add CLI section with exact command examples |
| 5 | Any stage template that calls it | Add `python {{SKILL_DIR}}/scripts/new-tool.py` invocation |

**If script has `CURRENT_SKILL_VERSION`:** detector H (`test_scripts_skill_version_sync`) auto-validates version sync. No manual step needed.

**If script is called by stage templates:** add a drift detector that verifies the script exists and is referenced correctly.

---

## 3. Create a new reference doc

When: adding `references/new-protocol.md`.

| # | File | Action |
|---|------|--------|
| 1 | `references/new-protocol.md` | Create the doc |
| 2 | `scripts/bootstrap.py` | Add to `runtime_refs` tuple (if referenced by ANY workspace template) |
| 3 | `tests/unit/test_no_drift.py` | Add to `SKILL_MD_INDEXED_DOCS` (if canonical). Add existence check + cross-ref detectors |
| 4 | `SKILL.md` | Add bullet in "Algorithm References" section |
| 5 | `references/changelog.md` | Record in version entry |
| 6 | Stage templates that reference it | Add `references/new-protocol.md` or `_references/runtime/new-protocol.md` |
| 7 | `CLAUDE.md` | Add to "Key Reference Docs" if relevant |

**Rule:** any `.md` in `references/` referenced by a workspace template MUST be in `runtime_refs`. Drift detector `test_runtime_refs_covers_all_workspace_template_references` enforces this.

**Rule:** any canonical doc MUST be in `SKILL_MD_INDEXED_DOCS`. Drift detector `test_skill_md_indexes_canonical_docs` enforces this.

---

## 4. Add a new template variable

When: adding `{{NEW_VAR}}` to any `.tpl` file.

| # | File | Action |
|---|------|--------|
| 1 | The `.tpl` file | Add `{{NEW_VAR}}` |
| 2 | The renderer (bootstrap.py, handoff.py, etc.) | Add key to placeholder dict |
| 3 | Drift detector for that template | If template has a placeholder↔renderer sync test, it auto-catches. If not, add one. |

**Existing sync tests:**
- `test_kickoff_template_placeholders_match_handoff` — `_kickoff.md.tpl` ↔ `handoff._build_placeholders()`
- `test_version_consistency_canonical_files` — version-bearing templates ↔ bootstrap SKILL_VERSION
- `test_runtime_refs_covers_all_workspace_template_references` — workspace `.tpl` doc refs ↔ bootstrap runtime_refs

**If your template has no sync test:** add one following the pattern in `test_no_drift.py`.

---

## 5. Add a new stage

When: adding stage 09 or inserting between existing stages.

| # | File | Action |
|---|------|--------|
| 1 | `scripts/bootstrap.py` | Add to `STAGES` dict, `STAGE_DIR_BY_ID`, update `CANONICAL_PROFILES` if stage affects profile config |
| 2 | `templates/workspace/stages/NN_name/CONTEXT.md.tpl` | Create L2 template |
| 3 | `templates/workspace/stages/NN_name/output/` | Bootstrap creates `output/` dir automatically |
| 4 | `scripts/handoff.py` | Add to `STAGE_DIR_BY_ID` |
| 5 | `references/session-handoff-protocol.md` | Add stage-specific handoff rules |
| 6 | `references/state-machine-schema.md` | Add `NN_in_progress`, `NN_completed` to status enum |
| 7 | `scripts/validate_state.py` | Add new statuses to `ALLOWED_STATUSES` |
| 8 | `references/stage-templates.md` | Document new stage |
| 9 | `tests/unit/test_no_drift.py` | Add cross-ref + status enum drift detectors |
| 10 | `templates/workspace/_config/stop-points.md` | May need new stop points |
| 11 | `references/stop-points-canonical.md` | May need new stop point IDs |

---

## 6. Add a new profile

When: adding to `CANONICAL_PROFILES` in `profile-merge.py`.

| # | File | Action |
|---|------|--------|
| 1 | `scripts/profile-merge.py` | Add to `CANONICAL_PROFILES` dict |
| 2 | `templates/_references/test-recipes/<profile>.md` | Create test recipe |
| 3 | `references/stage-templates.md` | Document profile behavior |
| 4 | `tests/unit/test_no_drift.py` | Profile count drift detector auto-catches via `PROFILE_COUNT_WHITELIST` |
| 5 | `scripts/wave-planner-script.py` | Add to `USER_FACING_PATHS_BY_PROFILE` if profile has user-facing paths |

---

## 7. Add a new drift detector

When: you discover an inconsistency that can be checked automatically.

| # | File | Action |
|---|------|--------|
| 1 | `tests/unit/test_no_drift.py` | Add test function. Follow existing patterns: parse source files, extract canonical values, compare. |
| 2 | `CLAUDE.md` "Pre-merge drift audit" section | Update detector count + letter assignment |

**Existing detectors (21+):** A (version consistency), A' (changelog entry), B (profile count), C/D (status enum sync), E (markdown cross-refs), F (CRLF in templates), H (script version sync), 4-block parser, v3.8.0 forensic+, v3.9.0 QA loop (9 detectors), v3.10.0 E2E (6 detectors), v3.12.1 (runtime_refs + kickoff sync).

---

## 8. Modify what gets copied to workspace

When: changing bootstrap's file copying logic.

| # | File | Action |
|---|------|--------|
| 1 | `scripts/bootstrap.py` | Edit `runtime_refs`, copy loops, or `_WORKSPACE_HOOK_FILES` |
| 2 | `templates/_references/runtime/README.md` | Update if runtime_refs changed (documents the convention) |
| 3 | `tests/unit/test_no_drift.py` | Update or add drift detector |

**Rule:** if a workspace template references `_references/runtime/<file>.md` or `references/<file>.md`, that file MUST be in `runtime_refs`. Drift detector `test_runtime_refs_covers_all_workspace_template_references` enforces this.

---

## 9. Create a new template (.tpl file)

When: adding `templates/path/to/new-file.md.tpl`.

| # | File | Action |
|---|------|--------|
| 1 | Create the `.tpl` file | Use `{{VARIABLE}}` placeholders |
| 2 | The renderer script | Add placeholder values. If no renderer exists, create one. |
| 3 | `tests/unit/test_no_drift.py` | Add sync test: template placeholders ↔ renderer keys |
| 4 | `scripts/bootstrap.py` | If copied to workspace, add copy step |

**Anti-pattern:** creating a `.tpl` file with placeholders and no renderer. The `critic-prompt.md` template was orphaned for 3 versions before `render-critic-prompt.py` was created. Every `.tpl` must have exactly one renderer.

---

## Red flags

Signs the modification is incomplete:

- New `references/<file>.md` created but NOT in `runtime_refs` → 404 at runtime.
- New `{{PLACEHOLDER}}` in template but NOT in renderer → `HandoffError` at runtime.
- New script created but no `script-cli-reference.md` entry → LLM doesn't know CLI format.
- New canonical doc created but NOT in `SKILL_MD_INDEXED_DOCS` → not discoverable from skill entry point.
- New `CURRENT_SKILL_VERSION` in script but detector H not updated → version drift undetected.
- `_kickoff.md.tpl` headers changed but `kickoff_canonical.expected.md` not updated → snapshot test fails.
- Template with `{{...}}` placeholders created but no sync test → future changes to renderer silently break template.
- Function referenced in templates as `render_foo()` but no `def render_foo` in any `.py` file → dead pseudo-code (see `render_critic_prompt` pre-v3.12.1).

If any red flag: fix before committing. Drift detectors will catch most, but not all.

---

## Quick reference: "I changed X, what tests should run?"

| Changed | Run |
|---------|-----|
| Any `.py` in scripts/ | `pytest tests/unit/ -k "script_name"` + full suite |
| Any `.tpl` template | `pytest tests/unit/test_no_drift.py` |
| `bootstrap.py` | `pytest tests/unit/test_no_drift.py tests/unit/test_bootstrap.py` |
| `handoff.py` | `pytest tests/unit/test_handoff.py tests/unit/test_no_drift.py` |
| `migrate-workspace.py` | `pytest tests/unit/test_migrate_workspace.py tests/unit/test_no_drift.py` |
| `wave-planner-script.py` | `pytest tests/unit/test_wave_planner_dag.py tests/unit/test_no_drift.py` |
| Any `references/*.md` | `pytest tests/unit/test_no_drift.py` |
| `SKILL.md` or `README.md` | `pytest tests/unit/test_no_drift.py` |
| Multiple files | `pytest tests/unit/` (full suite) |

Always run drift detectors (`test_no_drift.py`) before merging — they catch cross-file inconsistencies that unit tests miss.
