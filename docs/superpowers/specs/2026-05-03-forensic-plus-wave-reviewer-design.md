# Forensic+ Wave Reviewer — Design Spec (v3.8.0)

> **Date:** 2026-05-03
> **Skill version target:** v3.7.2 → v3.8.0 (minor bump)
> **Stage affected:** `04_implementation_waves` (step 8 wave-reviewer)
> **Status:** approved design, pending implementation plan

## 1. Context

O wave-reviewer atual (step 8 do pipeline 12 passos em `references/wave-execution-protocol.md`) audita 3 dimensões de cada wave após COMPLETE dos subagentes: (a) Auto-QA Akita 15-itens declarado pelo subagente, (b) `Files touched` reais via `git diff` batem com o declarado em `plan.md`, (c) acceptance criteria. Adiciona um forensic audit anti-fraude: conta commits RED/GREEN/REFACTOR no git log da wave branch contra `qa_loops_used` declarado.

Esse setup tem dois problemas reconhecidos:

1. **Self-grading bias.** O subagente que implementa também escreve seus próprios testes E grada o próprio Auto-QA Akita. Pesquisa empírica recente é unânime contra isso: AgentCoder (Programmer + Test Designer separados, +6 a +26pp pass@1), Agent-as-a-Judge (NeurIPS 2024, agent-as-judge ≈ humanos quando tem tools), Self-Correction Benchmark 2025 (self-correction sem feedback externo = +1.09%, ruído).
2. **Audit declarativo.** O wave-reviewer atual confere se Akita 15-itens **foi declarado**, não **re-executa** os critérios.

A pesquisa também mostra trade-offs contra abordagens caras:

- **Akita re-run prompt-only** (reviewer lê código completo + processa 15 itens × N tasks): caro em tokens, e prompt-review sem execução cai no mesmo bias do implementer.
- **External critic com execução real** (rodar suite completa por task): alinhado ao SOTA mas com latência alta em production, custo dobrado.

A escolha de design é o caminho intermediário: **expandir a unique-no-SOTA capability do ICM (forensic audit via git log) para cobrir mais vetores de fraude estrutural, sem importar prompt-only Akita re-run**.

## 2. Decision summary

| # | Decisão | Resultado |
|---|---------|-----------|
| Q1 | Como integrar Forensic+ no pipeline | A: Forensic+ como sub-step de 8 (8a/8b/8c/8d). Reviewer emite `approved_pending_ci`. CI global step 10 confirma ou reabre via `ci-rollback-protocol.md` existente. |
| Q2 | Action matrix por violation severity | B: tier-aware. Production trata mais SOFT como HARD; experimental/tool relaxa. |
| Q3 | Wave 1-task skip (F2) | B: aplica Forensic+ inclusive em wave 1-task. Skip apenas Akita-tipo cross-task (renomeia flag `skip_wave_reviewer` → `skip_cross_task_audit`). |
| Q4 | Task `type: HITL` | A: skip Forensic+. Humano = gate humano por design. |
| Q5 | Onde gravar resultados | A+B: detalhe estruturado em `task-<slug>.md` frontmatter; resumo humano em `wave-summary.md`. |
| Q6 | Version bump | B: minor (v3.7.2 → v3.8.0). Feature observable. |

## 3. Architecture

### 3.1 Pipeline integration

Step 8 do pipeline 12-passos é re-organizado em sub-steps:

```
8. Wave-reviewer (Agent sem worktree)
   8a. Forensic+ checks
       Para cada task da wave (skip type: HITL):
         python scripts/forensic-plus.py --workspace-num <NNN> --wave <N>
                --task-slug <slug> --base-branch <BASE> --plan <plan.md>
                --tier <T> --output json
       Reviewer parse JSON → grava task-md frontmatter forensic_*.
   8b. Audit existente (Akita declared, files touched real, acceptance)
       (skip cross-task audit em wave 1-task — flag skip_cross_task_audit)
   8c. Forensic git log (qa_loops_used vs commits) — mantém status quo
   8d. Emit decision:
       - HARD em ≥1 task → approved_pending_ci: false, issues: [...]
                            → lead re-spawn subagente original (cap 2 retries)
       - apenas SOFT     → approved_pending_ci: true, warnings: [...]
       - nenhum          → approved_pending_ci: true
9. Merge sequencial (apenas se 8d = true)
10. CI global → green confirma; red dispara ci-rollback-protocol.md (inalterado)
```

### 3.2 Skip rules consolidated

| Wave/task condition | Forensic+ aplica? | Akita-tipo cross-task? |
|---------------------|-------------------|------------------------|
| Wave > 1 task, todas AFK | sim | sim |
| Wave 1 task AFK | sim | não (skip_cross_task_audit) |
| Task `type: HITL` | não | n/a |
| Wave mista AFK + HITL | sim para AFK, skip HITL | sim para AFK |

## 4. Components

### 4.1 The 4 checks

#### Check 1 — Test file with non-trivial assertions

**Rationale:** wave-planner force ≥1 test file declared in `files_touched`, but only checks declaration, not content. Subagent could declare the file and commit it empty or with `assert True`.

**Command:** `git show wave-<NNN>-<N>/<slug>:<test-file>` per declared test file.

**Language-aware regex:**

| Ext | Pattern | Threshold |
|-----|---------|-----------|
| `.py` | `\bassert\b\|pytest\.raises\|self\.assert\w+` | ≥ 2 |
| `.ts/.tsx/.js/.jsx` | `\b(expect\|assert\|should\|it\(\|test\()\b` | ≥ 2 |
| `.go` | `\bt\.\(Errorf\|Fatal\|Run\)\b` | ≥ 2 |
| `.rb` | `\b(expect\|assert\|should)\b` | ≥ 2 |
| `.rs` | `\bassert(_eq\|_ne)?!\b` | ≥ 2 |
| `.java/.kt` | `\b(assert\|@Test\|assertEquals)` | ≥ 2 |
| `.cs` | `\b(Assert\.\|\[Test\]\|\[Fact\]\|\[Theory\])` | ≥ 2 |

**Skip:** task with `Conventions extras: doc-only` or `config-only` (existing wave-planner exemption).

**Severity:** HARD em todo tier (root da cadeia TDD).

#### Check 2 — Files outside declared `files_touched`

**Command:** `git diff --name-only <BASE>...wave-<NNN>-<N>/<slug>`

**Logic:** set difference `actual − declared`. Files in `actual` but not `declared` = violation.

**Allowlist tier-agnostic:**
- Lockfiles: `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`, `bun.lockb`, `Cargo.lock`, `Gemfile.lock`, `poetry.lock`, `go.sum`.
- Auto-format caches: `.prettierrc.cache`, `.eslintcache`.

**Severity:**

| Tier | Severity |
|------|----------|
| experimental/tool | SOFT |
| development/production | HARD |

#### Check 3 — Scope creep > 3× plan estimate

**Command:** `git diff --shortstat <BASE>...wave-<NNN>-<N>/<slug>`

**Estimate source:** new optional field in plan.md task:

```markdown
## Task <slug>:
### Estimated lines
~250
```

**Logic:**
- Field present: trigger if `insertions > 3 × estimated_lines`.
- Field absent: skip check 3 silently (backward compat).

**Severity:**

| Tier | Severity |
|------|----------|
| experimental/tool/development | SOFT |
| production | HARD |

#### Check 4 — TODO/FIXME/HACK added

**Command:**
```bash
git diff <BASE>...wave-<NNN>-<N>/<slug> -- '*.py' '*.ts' '*.tsx' '*.js' '*.jsx' '*.go' '*.rb' '*.rs' '*.java' '*.kt' '*.cs'
```

**Logic:** lines starting `+` (not `+++`) matching `(TODO|FIXME|HACK|XXX)`. Counts only added; ignores removed/context.

**Severity:**

| Tier | Severity |
|------|----------|
| experimental/tool/development | SOFT |
| production | HARD |

### 4.2 Tier × violation matrix consolidated

| Check | exp | tool | dev | prod |
|-------|-----|------|-----|------|
| Test assertions | HARD | HARD | HARD | HARD |
| Files outside declared | SOFT | SOFT | HARD | HARD |
| Scope creep 3× | SOFT | SOFT | SOFT | HARD |
| TODO/FIXME/HACK | SOFT | SOFT | SOFT | HARD |

### 4.3 Implementation: standalone script

`scripts/forensic-plus.py` — pure I/O contract:

**Invocation:**
```bash
python scripts/forensic-plus.py \
    --workspace-num <NNN> \
    --wave <N> \
    --task-slug <slug> \
    --base-branch <BASE_BRANCH> \
    --plan <path-to-plan.md> \
    --tier <experimental|tool|development|production> \
    --output json
```

**Argument source resolution (lead session populates from L1):**
- `--workspace-num`: parsed from L1 `workspace` field (format `NNN-slug` → `NNN`).
- `--wave`: parsed from L1 `waves.current`.
- `--task-slug`: iterated from current wave tasks list (`wave-plan.md`).
- `--base-branch`: from L1 `base_branch`.
- `--plan`: resolved as `<workspace_root>/stages/02_design/output/plan.md`.
- `--tier`: from L1 `tier`.

**Stdout (JSON):**
```json
{
  "task_slug": "add-login",
  "violations": [
    {"check": "scope_creep", "severity": "SOFT", "evidence": "+847 lines vs 250 estimate"},
    {"check": "files_outside_declared", "severity": "HARD", "evidence": "src/utils/helper.ts not in files_touched"}
  ],
  "forensic_passed": false,
  "max_severity": "HARD"
}
```

**Exit codes:**
- `0` — script ran successfully (regardless of violations found).
- `1` — script crashed (git command failed, plan.md malformed, branch missing). Stderr formatted.

**Justification (script vs inline in L2):**
- Testable unitarily (`tests/unit/test_forensic_plus.py`).
- Deterministic — no prompt drift.
- Reduces reviewer Agent token cost (parses JSON, doesn't construct git commands).
- Aligned with repo pattern (all runtime logic lives in `scripts/`).

## 5. Schema changes

### 5.1 `output/wave-<N>/task-<slug>.md` frontmatter

**New optional fields:**

```yaml
---
# existing fields...
forensic_violations:
  - check: scope_creep
    severity: SOFT
    evidence: "+847 lines vs 250 estimate"
  - check: files_outside_declared
    severity: HARD
    evidence: "src/utils/helper.ts not in files_touched"
forensic_passed: false   # true if no HARD; null if task type=HITL
forensic_max_severity: HARD   # HARD | SOFT | NONE | null (HITL)
forensic_respawn_count: 1   # 0..MAX_FORENSIC_RETRIES (2). Symmetric with qa_loops_used.
---
```

**Backward compat:** existing workspaces without these fields parse as `forensic_violations: []`, `forensic_passed: null`, `forensic_respawn_count: 0`.

### 5.2 `output/wave-<N>/wave-summary.md` new section

Always present (empty if no violations):

```markdown
## Forensic+ summary

**Counts by severity:**
- HARD: 1
- SOFT: 2
- NONE (clean): 3

**HARD violations (blocked merge, forced re-spawn):**
- `<task-slug>`: files_outside_declared — `src/utils/helper.ts` not in files_touched
  - Re-spawn round: 1 → fixed on 2nd attempt

**SOFT violations (warnings, merge proceeded):**
- `<task-slug-x>`: scope_creep — +847 lines vs 250 estimate
- `<task-slug-y>`: todo_added — `// TODO: refactor later` added in src/api.ts:42

**HITL tasks (Forensic+ skipped):** `<task-slug-z>`
```

### 5.3 `plan.md` task — new optional field

Slot in `references/4-block-contract-template.md` immediately after `### Files touched` (natural grouping: scope concerns):

```markdown
## Task <slug>:

### Files touched
- src/api/login.ts
- tests/api/login.test.ts

### Estimated lines
~250

### Depends on
...
```

**Logic:**
- Wave-planner reads but does not use.
- forensic-plus.py reads. Absent → skip check 3.
- Optional. Plan author opts in for critical tasks.

### 5.4 Negative space — what does NOT change

- L1 `CONTEXT.md` frontmatter: unchanged. Forensic+ is per-task audit, not state machine.
- L0 `CLAUDE.md` workspace-level: unchanged.
- Status enum (`ALLOWED_STATUSES`): unchanged. Forensic+ uses existing `BLOCKED_ERROR` with new `error_type: forensic_max_retries` or `error_type: forensic_script_crash`.
- `wave-plan.md` schema: unchanged except flag rename (see EC5 below).
- `references/state-machine-schema.md`: unchanged.

## 6. Error handling and violation flow

### 6.1 HARD violation flow

```
Step 8a Forensic+ detects HARD on task <slug>
  ↓
Step 8b/8c continue normal audit
  ↓
Step 8d emits approved_pending_ci: false, issues: [forensic_violation: <details>]
  ↓
Lead receives → re-spawns original subagent (existing path step 8)
  ↓
AGENT-BRIEF re-spawn injects:
  - "Forensic+ detected: <violation_type>: <evidence>"
  - "Fix: <prescriptive action per type, table 6.3>"
  ↓
Subagent retries (full TDD 7 steps, qa_loops_used reset to 0)
  ↓
Lead invokes Forensic+ again post-COMPLETE
  ↓
Loop until MAX_FORENSIC_RETRIES = 2 OR approved
```

### 6.2 Re-spawn cap

`MAX_FORENSIC_RETRIES = 2` (hardcoded, not tier-aware).

| Attempt | Result | Action |
|---------|--------|--------|
| 1st original | HARD | re-spawn round 1 |
| 2nd (round 1) | HARD | re-spawn round 2 |
| 3rd (round 2) | HARD | `BLOCKED_ERROR error_type: forensic_max_retries`, escalate to human via wave-summary |
| Any | SOFT only | merge proceeds |
| Any | NONE | merge proceeds |

**Justification for 2:** Forensic+ violations are structural (fake test, files outside declared). A capable subagent fixes within 1 retry. 2+ retries with same pattern indicate the subagent cannot, escalate.

### 6.3 Re-spawn brief — prescriptive fix per violation type

| Violation | Text injected into re-spawn AGENT-BRIEF |
|-----------|----------------------------------------|
| `test_assertions_too_few` | "Test file `<path>` has only `<N>` non-trivial assertions. Add tests covering: edge cases declared in acceptance criteria + happy path. Minimum 2 non-trivial assertions." |
| `files_outside_declared` | "You touched `<path>` not declared in `files_touched`. Options: (a) revert the change, (b) if legitimately needed, write `output/wave-<N>/task-<slug>-blocked.md` with rationale and exit so lead can update plan.md and re-spawn (no new stop point — uses existing BLOCKED handoff)." |
| `scope_creep` | "Diff `<X>` lines vs estimate `<Y>`. Reduce scope or split into smaller commits. If real scope is larger, escalate via stop point `over_eng`." |
| `todo_added` | "TODOs added: `<list line:content>`. Remove or convert to issues. Committed code does not carry TODOs." |

### 6.4 SOFT violations cumulative tracking

SOFT does not block. Accumulates in `wave-summary.md` Forensic+ section. After last wave (gate human Phase 1 WORK_DONE), human sees totals and decides whether to accept or send wave back.

**Future calibration (out of scope, recorded for v3.9+):** if SOFT count > threshold per wave for N consecutive waves on same profile/tier, consider promoting SOFT → HARD on that combo. Metric lives in `wave-summary.md` (machine-parseable). Calibration decision = human + future iteration.

### 6.5 Edge cases

| EC | Scenario | Behavior |
|----|----------|----------|
| EC1 | `forensic-plus.py` crash or git command fail | Reviewer captures stderr, emits `forensic_passed: null, forensic_error: <stderr>, approved_pending_ci: false`. Lead → `BLOCKED_ERROR error_type: forensic_script_crash`. No re-spawn (not subagent fault). Escalate to human via wave-summary. |
| EC2 | JSON parse fail on script output | Treat as EC1. |
| EC3 | Re-spawn introduces new HARD different from original | Counts as retry. Cap 2 still applies. Prevents gaming via violation rotation. |
| EC4 | Wave with HITL + AFK tasks | Forensic+ runs only on AFK. HITL → `forensic_passed: null`. Wave-summary lists HITL in own section. |
| EC5 | Wave 1-task | Forensic+ runs (Q3=B). Akita-tipo cross-task skipped. Flag rename `skip_wave_reviewer` → `skip_cross_task_audit`. Backward-compat: parser accepts both in v3.8.0, deprecation warning, removes old in v3.9+. |
| EC6 | Subagent obfuscates TODOs (`T0D0`, `F1XME`) | Out of scope. No incentive structure for this in cooperative subagents. Wave-reviewer 8c acceptance audit catches deeper semantic issues if any. |
| EC7 | Lockfile genuinely introduces vulnerabilities | Allowlist in check 2 ignores. Security audit responsibility belongs to stage 05 verification or production tier security_gate hooks. Out of scope Forensic+. |

### 6.6 CI global step 10 interaction

Unchanged. `approved_pending_ci: true` is semantic (reviewer acknowledges final decision still pending CI). Step 10 red → existing `ci-rollback-protocol.md`. Forensic+ violations do not trigger automatic rollback — they ran post-COMPLETE pre-merge, and HARD violations already blocked merge.

## 7. Testing

### 7.1 Unit tests

**`tests/unit/test_forensic_plus.py`** (~25 tests):

| Test | Coverage |
|------|----------|
| `test_check1_test_assertions_python_pass` | `.py` with 3 asserts → pass |
| `test_check1_test_assertions_python_fail` | `.py` with `assert True` only → HARD |
| `test_check1_skip_doc_only` | task with `Conventions extras: doc-only` → skip |
| `test_check1_multi_lang` | mixed `.ts` + `.py` → language-aware regex |
| `test_check2_files_outside` | diff touches undeclared file → violation |
| `test_check2_lockfile_allowlist` | `package-lock.json` in diff → ignored |
| `test_check2_tier_severity_matrix` | exp/tool=SOFT, dev/prod=HARD |
| `test_check3_estimated_lines_present` | insertions > 3× → trigger |
| `test_check3_estimated_lines_absent_skip` | field absent → silent skip |
| `test_check3_production_hard` | tier=production HARD, others SOFT |
| `test_check4_todo_added` | `+// TODO: ...` added → violation |
| `test_check4_todo_removed_ignored` | `-// TODO: ...` removed → no violation |
| `test_check4_existing_todo_untouched` | context line without `+` → no violation |
| `test_json_output_schema` | Hypothesis property-test: output always conforms schema |
| `test_exit_code_always_zero_on_success` | exit=0 even with HARD found |
| `test_crash_git_missing_branch` | exit=1, stderr formatted (EC1) |
| `test_crash_plan_malformed` | exit=1 (EC1) |
| `test_hitl_task_returns_null` | task `type: HITL` → `forensic_passed: null` (Q4) |
| `test_property_no_violations_when_clean_diff` | Hypothesis: clean diff respecting declared + lockfile-only → 0 violations |

Coverage target ≥ 90%.

**`tests/unit/test_wave_reviewer_forensic_integration.py`** (~6 tests, mocks Agent tool):

- Reviewer parser handles `forensic_script_crash` → `BLOCKED_ERROR`.
- Re-spawn loop respects `MAX_FORENSIC_RETRIES = 2`.
- 3rd retry → escalate via wave-summary.
- SOFT-only does not trigger re-spawn.
- HARD + SOFT mix → re-spawn (HARD wins).
- HITL skipped, AFK audited, same wave.

### 7.2 Integration tests (bats CI-only)

`tests/integration/test_forensic_plus_e2e.bats`:
- `git init` fictional project.
- Bootstrap workspace via `bootstrap.py`.
- Generate fictional plan.md (4 tasks with planted violations).
- Run mock wave (mocked subagent via fixtures).
- Invoke `forensic-plus.py` real, parse output.
- Assert task-md frontmatter populated.
- Assert wave-summary.md section populated.

### 7.3 Snapshot fixtures

`tests/fixtures/forensic-plus-expected/`:
- 6 input/output JSON pairs.
- Each: (plan.md fixture, git fixture, tier) → expected JSON.
- Detects silent regression.

### 7.4 Drift detector updates

`tests/unit/test_no_drift.py` adds:

```python
def test_forensic_plus_doc_canonical_exists():
    """Ensure references/forensic-plus-protocol.md exists + cross-refs resolve."""

def test_forensic_plus_referenced_in_l2_stage_04():
    """L2 04_implementation_waves/CONTEXT.md.tpl mentions forensic-plus-protocol step 8."""

def test_forensic_plus_in_runtime_refs_bootstrap():
    """bootstrap.py runtime_refs list includes forensic-plus-protocol.md."""

def test_wave_execution_protocol_has_forensic_substeps():
    """references/wave-execution-protocol.md step 8 expanded into 8a/8b/8c/8d
    matching this spec — prevents spec/canonical drift."""
```

## 8. Version sweep — 7 canonical files (CLAUDE.md v3.7.0 rule)

| # | File | Change |
|---|------|--------|
| 1 | `scripts/bootstrap.py` | `SKILL_VERSION = "3.8.0"` + add `forensic-plus.py` to runtime_refs (if applicable) |
| 2 | `SKILL.md` | header `# xp-icm-workflow v3.8.0` |
| 3 | `README.md` | badge `version-v3.8.0` + new section `## v3.8.0 — Forensic+ wave reviewer` |
| 4 | `references/design-system.md` | frontmatter `format (v3.8.0)` + `> **Versão:** v3.8.0` |
| 5 | `references/preview-loop-protocol.md` | title `(v3.8.0)` + version line |
| 6 | `references/changelog.md` | new entry `## v3.8.0 — Forensic+ wave reviewer (2026-05-03)` with concrete change list |
| 7 | `scripts/migrate-workspace.py` | `CURRENT_SKILL_VERSION = "3.8.0"` + tuple last entry + `migrate_3_7_2_to_3_8_0` (bump-only) + `STEP_FUNCTIONS` entry |
| 8 (extra) | `tests/unit/test_migrate_workspace.py` | smoke + idempotency for new step |

**Migration `migrate_3_7_2_to_3_8_0`:** bump-only. No data mutation needed because:
- task-md without new fields → parser default `[]` / `null`. Natural backward compat.
- plan.md without `estimated_lines` → check 3 silently skipped.
- wave-summary.md without Forensic+ section → empty display OK.

## 9. New files inventory

| Path | Type | Approx size |
|------|------|-------------|
| `scripts/forensic-plus.py` | runtime | ~400 LOC |
| `references/forensic-plus-protocol.md` | canonical doc | ~150 lines markdown |
| `tests/unit/test_forensic_plus.py` | unit test | ~600 LOC |
| `tests/unit/test_wave_reviewer_forensic_integration.py` | integration mock | ~300 LOC |
| `tests/integration/test_forensic_plus_e2e.bats` | bats CI | ~120 lines |
| `tests/fixtures/forensic-plus-expected/*.json` | snapshot fixtures | 6 × ~80 lines |

## 10. Edited files inventory

| Path | Change |
|------|--------|
| `references/wave-execution-protocol.md` | step 8 expanded into 8a/8b/8c/8d, cross-ref forensic-plus-protocol.md |
| `templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl` | step 8 detailed, new error_type `forensic_max_retries`, re-spawn brief path |
| `references/4-block-contract-template.md` | optional section `### Estimated lines` |
| `references/state-machine-schema.md` | comment about `error_type: forensic_max_retries` (no enum change) |
| `scripts/wave-planner-script.py` | rename `skip_wave_reviewer` → `skip_cross_task_audit` (+ backward-compat alias for v3.8.0) |
| `references/wave-planner-algorithm.md` | update §10 (the doc owns the flag name canonically); rename `skip_wave_reviewer` → `skip_cross_task_audit` with backward-compat note |
| `scripts/bootstrap.py` | runtime_refs adds forensic-plus-protocol.md |

## 11. New canonical doc structure: `references/forensic-plus-protocol.md`

Sections (target ~150 lines):
- Summary (1 paragraph).
- The 4 checks (command + parsing + threshold per check).
- Tier × severity matrix.
- HARD vs SOFT action.
- Re-spawn cap + prescriptive brief.
- Edge cases EC1–EC7.
- forensic-plus.py I/O JSON schema.
- Cross-refs (wave-execution-protocol, 4-block-contract, state-machine-schema).

## 12. Out of scope (recorded for future)

- Programmer / Test Designer agent split (AgentCoder pattern). Larger structural change; revisit if Forensic+ proves insufficient.
- Tools-empowered prompt review (reviewer running test suite per task). Higher cost, considered but rejected for v3.8.0 in favor of Forensic+ which reuses existing CI global as the execution gate.
- TODO obfuscation detection (T0D0, F1XME). Cooperative subagent context, low risk.
- Lockfile vulnerability scanning. Security gate / stage 05 responsibility.
- Per-task `forensic_strict: true` override. YAGNI per CLAUDE.md guidance.
- Calibration loop (auto-promotion SOFT → HARD based on metrics). Wait for v3.9+ data.

## 13. Pre-merge gate

- `pytest tests/unit/test_no_drift.py` — all detectors green.
- `pytest tests/unit/test_forensic_plus.py` — 25+ tests green.
- `pytest tests/unit/test_wave_reviewer_forensic_integration.py` — 6+ tests green.
- `pytest tests/unit/test_migrate_workspace.py` — smoke + idempotency green.
- `bash tests/run.sh --no-bats` — total suite green (548+ baseline per CLAUDE.md tests section).
- `bash tests/run.sh --ci` (CI) — bats integration green.

## 14. Sources

- Cognition — Don't Build Multi-Agents — https://cognition.ai/blog/dont-build-multi-agents
- Cognition — Devin's 2025 Performance Review — https://cognition.ai/blog/devin-annual-performance-review-2025
- Cursor 2.0 announcement — https://cursor.com/blog/2-0
- OpenHands paper (ICLR 2025) — https://arxiv.org/abs/2407.16741
- OpenHands SDK V1 (arxiv 2511.03690) — https://arxiv.org/html/2511.03690v1
- Anthropic — Claude Code Advanced Patterns (subagents, MCP, scaling)
- GitHub — Copilot coding agent automatic security/quality validation (Oct 2025) — https://github.blog/changelog/2025-10-28-copilot-coding-agent-now-automatically-validates-code-security-and-quality/
- Huang et al. — LLMs Cannot Self-Correct Reasoning Yet (ICLR 2024) — https://arxiv.org/abs/2310.01798
- Kamoi et al. — When Can LLMs Actually Correct Their Own Mistakes? (TACL 2024) — https://aclanthology.org/2024.tacl-1.78.pdf
- Self-Correction Benchmark 2025 — https://arxiv.org/html/2510.16062v1
- AgentCoder — Multi-Agent Code Framework — https://www.emergentmind.com/topics/agentcoder
- Zhuge et al. — Agent-as-a-Judge (NeurIPS 2024, arxiv 2410.10934) — https://arxiv.org/abs/2410.10934
