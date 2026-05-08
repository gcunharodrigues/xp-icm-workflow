# Forensic+ Protocol — Canonical (v3.10.0)

> **Version:** v3.10.0
> **Skill:** `xp-icm-workflow`
> **Consumer stage:** `04_implementation_waves` (PHASE 3 VERIFY — L2 deterministic gate)
> **Purpose:** canonical document for Forensic+ — structural anti-fraud audit per task in the wave-reviewer. Describes the 8 checks (4 original v3.8.0 + 3 v3.9.0 + 1 v3.10.0), tier × severity matrix, HARD/SOFT actions, re-spawn cap, edge cases, and JSON schema for `scripts/forensic-plus.py`.

## Summary (1 paragraph)

Forensic+ is a deterministic, git-only audit run by the wave-reviewer for each AFK task in the wave. It runs 8 checks: (1) test file with ≥2 assertions, (2) files outside declared `files_touched`, (3) scope creep > 3× plan estimate, (4) TODO/FIXME/HACK added, (5) acceptance ↔ test mapping, (6) OUT OF SCOPE violations, (7) ADR import drift, (8) user-journey coverage (e2e). Each violation has tier-aware severity (HARD/SOFT). HARD blocks merge and forces re-spawn (cap `MAX_FORENSIC_RETRIES = 2`); SOFT accumulates in `wave-summary.md`. Tasks `type: HITL` are skipped. Output via `scripts/forensic-plus.py` as structured JSON, parsed by the reviewer Agent. v3.9.0: gate is antechamber to L3 critic (`references/critic-protocol.md`); HARD violation skips L3. v3.10.0: Check 8 closes the E2E coverage gap (see `references/e2e-coverage-protocol.md`).

## The 8 checks

### Check 1 — Test file with ≥2 assertions

Ensures that test files declared in `files_touched` contain ≥2 tokens recognized as assertions (count-based, not semantic filtering). Skip when task has `Conventions extras: doc-only` or `config-only`.

Command: `git show wave-<NNN>-<N>/<slug>:<test-file>` per test file.

Language-aware regex (extension → pattern):

| Ext | Pattern | Threshold |
|-----|---------|-----------|
| `.py` | `\bassert\b\|pytest\.raises\|self\.assert\w+` | ≥ 2 |
| `.ts/.tsx/.js/.jsx` | `\b(expect\|assert\|should\|it\(\|test\()\b` | ≥ 2 |
| `.go` | `\bt\.\(Errorf\|Fatal\|Run\)\b` | ≥ 2 |
| `.rb` | `\b(expect\|assert\|should)\b` | ≥ 2 |
| `.rs` | `\bassert(_eq\|_ne)?!\b` | ≥ 2 |
| `.java/.kt` | `\b(assert\|@Test\|assertEquals)` | ≥ 2 |
| `.cs` | `\b(Assert\.\|\[Test\]\|\[Fact\]\|\[Theory\])` | ≥ 2 |

Severity: **HARD** on every tier.

### Check 2 — Files outside declared `files_touched`

Compares filenames in the diff (`git diff --name-only BASE...wave`) against those declared in the plan.md task. The set difference (actual − declared) is a violation, except when the filename is in the global lockfile/cache allowlist.

Tier-agnostic allowlist: `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`, `bun.lockb`, `Cargo.lock`, `Gemfile.lock`, `poetry.lock`, `go.sum`, `.prettierrc.cache`, `.eslintcache`.

Severity:

| Tier | Severity |
|------|----------|
| experimental/tool | SOFT |
| development/production | HARD |

### Check 3 — Scope creep > 3× plan estimate

Reads `### Estimated lines` optional field from the plan.md task (see `references/4-block-contract-template.md`). Compares against `git diff --shortstat` insertions count. Triggered when `insertions > 3 × estimate`. If field is absent, skip silently (backward compat).

Severity:

| Tier | Severity |
|------|----------|
| experimental/tool/development | SOFT |
| production | HARD |

### Check 4 — TODO/FIXME/HACK added

Counts lines starting with `+` (not `+++`) that match `(TODO|FIXME|HACK|XXX)` in code files (`.py .ts .tsx .js .jsx .go .rb .rs .java .kt .cs`). Ignores removed lines (`-`) and context.

Severity:

| Tier | Severity |
|------|----------|
| experimental/tool/development | SOFT |
| production | HARD |

### Check 5 — Acceptance ↔ test mapping (v3.9.0)

Each bullet in the VALIDATION block of the task in plan.md must map to ≥1 test name present in the test file(s) declared in `files_touched`. Heuristic: regex extracts test names from the VALIDATION block (pattern `test_<name>`, `it("<desc>")`, `should <action>`, etc.) + grep test files for matches. Bullet without a matching test = violation.

Implementation:
1. Parse the VALIDATION block of the task in plan.md.
2. Extract test name candidates via regex (language-aware):
   - Direct pattern: `\btest_[a-z_0-9]+\b` or `\b[a-z][a-zA-Z0-9_]*Test\b`.
   - Indirect pattern: bullet starting with `Test [a-z_0-9]+:` or `it\("...\)` or `should ...`.
3. For each test name candidate, search in test files (`grep -E "<pattern>"`).
4. Bullet without a match = violation.

Skip when task has `Conventions extras: doc-only` or `config-only`. Skip when bullet starts with `Coverage ≥` (coverage threshold, not a test name).

Severity:

| Tier | Severity |
|------|----------|
| experimental/tool | SOFT |
| development/production | HARD |

### Check 6 — OUT OF SCOPE violations (v3.9.0)

Bullets in the OUT OF SCOPE block may declare detectable prohibited patterns in the diff. Supported patterns:

| Pattern syntax | Meaning | Detection |
|----------------|---------|-----------|
| `Mock interno de <module>` | prohibits `jest.mock("<module>")` or `mocker.patch("<module>")` in diff | grep diff for pattern |
| `Import <lib>` | prohibits `import ... from "<lib>"` or `from <lib> import ...` | grep diff |
| `<keyword>` (uppercase, ≥6 chars) | prohibits literal presence in added lines | grep diff `^+.*<keyword>` |

Bullets that do not match patterns are descriptive (skip). Forensic+ does not attempt to interpret free prose — the pattern is literal.

Edge case: bullet `Cache results in memory` (descriptive) → skipped. Bullet `Mock interno de jose` → checked.

Severity:

| Tier | Severity |
|------|----------|
| experimental | SOFT |
| tool/development/production | HARD |

### Check 7 — ADR import drift (v3.9.0)

Each applicable ADR (field `Applicable ADRs`) declared for the task may list prohibited libs/patterns via a structured marker in the ADR markdown:

```markdown
## Forbidden imports
- `jsonwebtoken` (use `jose`; see §Stack section)
- `axios` (use native `fetch`)
```

Forensic+ parses the `## Forbidden imports` section of the ADR file, extracts lib names between backticks, and checks the diff for matching imports. Pattern detection (language-aware):

| Ext | Pattern |
|-----|---------|
| `.ts/.tsx/.js/.jsx` | `^\+.*\b(import\|require)\b.*['"]<LIB>['"]` |
| `.py` | `^\+.*\b(import\|from)\b.*\b<LIB>\b` |
| `.go` | `^\+.*\bimport\s+["']<LIB>["']` |
| `.rs` | `^\+.*\buse\s+<LIB>` |

ADR without a `## Forbidden imports` section = check skipped silently (backward compat).

Severity:

| Tier | Severity |
|------|----------|
| experimental | SOFT |
| tool/development/production | HARD |

### Check 8 — User-journey coverage / E2E (v3.10.0)

Task with `Requires E2E update: true` in its metadata (auto-emitted by wave-planner when `Files touched` matches `user_facing_paths` from profile-effective) must have ≥1 file modified in a recognized E2E directory.

Recognized directories (allowlist):

```
e2e/
cypress/
playwright/
tests/e2e/
tests/integration/
test/e2e/
__e2e__/
```

Detection:
1. Parse plan.md task → check metadata `Requires E2E update`.
2. If `true` AND task does NOT have `**E2E:** skip` in the 4-block → check is active.
3. `git diff --name-only BASE...wave` → does it contain ≥1 path matching e2e dirs?
4. If none → violation.

Skip:
- `Requires E2E update: false` or absent.
- `**E2E:** skip` declared in the 4-block (rationale audited at Stage 05).
- `Conventions extras: doc-only` or `config-only`.
- Task `type: HITL`.

Severity:

| Tier | Severity |
|------|----------|
| experimental | SOFT |
| tool | SOFT |
| development | HARD |
| production | HARD |

Canonical E2E reinforcement doc: `references/e2e-coverage-protocol.md`.

## Consolidated tier × violation matrix

| Check | exp | tool | dev | prod |
|-------|-----|------|-----|------|
| 1. Test assertions | HARD | HARD | HARD | HARD |
| 2. Files outside declared | SOFT | SOFT | HARD | HARD |
| 3. Scope creep 3× | SOFT | SOFT | SOFT | HARD |
| 4. TODO/FIXME/HACK | SOFT | SOFT | SOFT | HARD |
| 5. Acceptance↔test | SOFT | SOFT | HARD | HARD |
| 6. OUT OF SCOPE | SOFT | HARD | HARD | HARD |
| 7. ADR import drift | SOFT | HARD | HARD | HARD |
| 8. User-journey (e2e) | SOFT | SOFT | HARD | HARD |

## HARD vs SOFT action

- **HARD on ≥1 check** → reviewer emits `approved_pending_ci: false`, lead re-spawns original subagent.
- **SOFT only** → reviewer emits `approved_pending_ci: true`, violations written to `wave-summary.md`, merge proceeds.
- **None** → standard approved.

## Re-spawn cap + prescriptive brief

Cap: `MAX_FORENSIC_RETRIES = 2` (hardcoded in `scripts/forensic-plus.py`, drift-checked). Tier-agnostic.

| Attempt | Result | Action |
|---------|--------|--------|
| 1st original | HARD | re-spawn round 1 |
| 2nd (round 1) | HARD | re-spawn round 2 |
| 3rd (round 2) | HARD | `BLOCKED_ERROR error_type: forensic_max_retries`, escalate to human |
| Any | SOFT only | merge proceeds |
| Any | NONE | merge proceeds |

Re-spawn brief injected into subagent AGENT-BRIEF:

| Violation | Injected text |
|-----------|---------------|
| `test_assertions_too_few` | "Test file `<path>` has `<N>` assertions. Add ≥2 non-trivial assertions covering edge cases + happy path." |
| `files_outside_declared` | "You touched `<path>` not declared in files_touched. Revert or write `output/wave-<N>/task-<slug>-blocked.md` to escalate (no new stop point — use existing BLOCKED handoff)." |
| `scope_creep` | "Diff `<X>` lines vs estimate `<Y>`. Reduce or split. If real scope is larger, escalate via stop point `over_eng`." |
| `todo_added` | "TODOs added: `<list>`. Remove or convert to issues." |
| `acceptance_test_unmapped` | "VALIDATION bullet `<bullet>` has no matching test. Add explicit test name OR write a test covering the criterion." |
| `nao_quero_violation` | "Diff touches prohibited pattern `<pattern>` declared in OUT OF SCOPE. Revert OR escalate via stop point if requirement changed." |
| `adr_import_drift` | "Import `<lib>` is prohibited by ADR `<adr-file>` (§Forbidden imports). Replace with the alternative documented in the ADR." |
| `e2e_coverage_missing` | "Task declared `Requires E2E update: true` but diff does not touch `e2e/`/`cypress/`/`playwright/`/`tests/e2e/`. Add ≥1 test covering the end-to-end flow. If the refactor has no behavior change, declare `**E2E:** skip - <rationale>` in the 4-block." |

## Edge cases

| EC | Scenario | Behavior |
|----|----------|----------|
| EC1 | `forensic-plus.py` crash (git missing branch / plan malformed) | Script exit 1 + stderr. Reviewer emits `forensic_passed: null, forensic_error: <stderr>`. Lead → `BLOCKED_ERROR error_type: forensic_script_crash`. Escalate to human. |
| EC2 | JSON parse fail | Treat as EC1. |
| EC3 | Re-spawn introduces a new different HARD | Counts as a retry. Cap 2 still applies. Anti-gaming. |
| EC4 | Wave with HITL + AFK tasks | Runs only on AFK. HITL → `forensic_passed: null`. |
| EC5 | Wave with 1 task | Forensic+ runs. Akita-style cross-task skipped (`skip_cross_task_audit: true`). |
| EC6 | TODO obfuscation (`T0D0`, `F1XME`) | Out of scope. |
| EC7 | Lockfile vulnerabilities | Allowlist ignores. Stage 05 / security_gate covers. |

## CI global step 10 interaction

Unchanged. `approved_pending_ci: true` is semantic (final decision pending CI). Step 10 red → existing `references/ci-rollback-protocol.md`. Forensic+ does not trigger automatic rollback.

## JSON schema for `scripts/forensic-plus.py`

**Input (CLI):**

```bash
python scripts/forensic-plus.py \
    --workspace-num <NNN> \
    --wave <N> \
    --task-slug <slug> \
    --base-branch <BASE> \
    --plan <path-to-plan.md> \
    --tier <experimental|tool|development|production> \
    --output json
```

**Output (stdout JSON):**

```json
{
  "task_slug": "<slug>",
  "violations": [
    {
      "check": "<test_assertions_too_few|files_outside_declared|scope_creep|todo_added|acceptance_test_unmapped|nao_quero_violation|adr_import_drift|e2e_coverage_missing>",
      "severity": "<HARD|SOFT>",
      "evidence": "<human-readable explanation>"
    }
  ],
  "forensic_passed": true | false | null,
  "max_severity": "HARD" | "SOFT" | "NONE" | null,
  "skipped_reason": "task type=HITL"   // present only if HITL
}
```

**Exit codes:**
- `0` — script ran successfully (regardless of violations).
- `1` — script crash (git missing, plan malformed). Stderr formatted.

## Cross-references

- 5-phase pipeline consumer: `references/wave-execution-protocol.md` PHASE 3 VERIFY.
- Task plan.md schema: `references/4-block-contract-template.md` (`### Estimated lines`).
- L2 runtime: `templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl`.
- State machine: `references/state-machine-schema.md` (`error_type: forensic_max_retries|forensic_script_crash`).
- Stop points (table: this audit is not a stop point, it is a post-COMPLETE audit): `references/stop-points-canonical.md`.
- Conflict / CI rollback: `references/conflict-resolution-protocol.md`, `references/ci-rollback-protocol.md`.
