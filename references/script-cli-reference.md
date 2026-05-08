# Script CLI Reference v3.12.1

Canonical CLI contracts for every script in `scripts/`. LLM agents must follow these
formats exactly — deviation causes parse errors.

> **Version:** v3.12.1

## Format contracts (critical)

These formats are used across multiple stages. Getting them wrong breaks the pipeline.

### `--prev-outputs` (handoff.py render)

```
path1:summary1,path2:summary2
```

- **Delimiter:** comma between entries. Paths always start with `stages/NN_name/output/`.
  The parser splits on `,(?=\s*stages/\d+)` — commas inside summaries are safe.
- **Each entry:** `path:summary` — colon separates path from one-line summary.
- **Summary:** free text, no newlines. Keep under ~80 chars. No `:` in path.
- **Empty:** `""` or omit the flag.

Example:
```
--prev-outputs "stages/02_design/output/plan.md:Plan with 8 tasks, 2 ADRs,stages/02_design/output/decisions.md:ADR index"
```

### `--pending` (handoff.py render)

```
item1|item2|item3
```

- **Delimiter:** pipe `|`. Each item is a short description of pending work.
- **Empty:** `""` or omit.

Example:
```
--pending "Execute wave 1 sub-wave 1.a (project-setup)|Execute wave 1 sub-wave 1.b (config-module)"
```

### Plan.md dependency sentinel

Root tasks (no dependencies) use `- none` in the `### Depends on` section:
```markdown
### Depends on
- none
```

Legacy Portuguese `- nenhum` also accepted for backward compatibility.

### 4-block headers (plan.md)

After v3.12.0, parser regex matches English only:
```
### WHAT
### HOW
### OUT OF SCOPE
### VALIDATION
### Files touched
### Depends on
### Applicable ADRs
```

---

## handoff.py

Primary script for stage transitions. Three subcommands: `render`, `update`, `remove`.

### handoff.py render

Generates `_kickoff.md` for the next stage.

```
python scripts/handoff.py render \
  --workspace-root <path> \
  --prev-stage <NN> \
  --prev-stage-name <snake_case> \
  --stage-target <NN> \
  --stage-target-name <snake_case> \
  --commit-sha <sha> \
  --prev-outputs "path:summary,path:summary" \
  --pending "item1|item2|item3" \
  --decisions-summary "<markdown>" \
  --prev-state-prose "<text>" \
  --next-tasks-prose "<text>" \
  [--project-root <path>]
```

| Flag | Required | Format | Notes |
|------|----------|--------|-------|
| `--workspace-root` | yes | path | e.g. `/project/workspaces/001-slug` |
| `--prev-stage` | yes | int | e.g. `02` |
| `--prev-stage-name` | yes | string | e.g. `design` |
| `--stage-target` | yes | int | e.g. `03` |
| `--stage-target-name` | yes | string | e.g. `wave_planner` |
| `--commit-sha` | yes | hex | 7-char git SHA |
| `--prev-outputs` | no | see above | comma-separated `path:summary` |
| `--pending` | no | see above | pipe-separated items |
| `--decisions-summary` | no | markdown | prose summary |
| `--prev-state-prose` | no | text | human-readable prior state |
| `--next-tasks-prose` | no | text | human-readable next steps |
| `--project-root` | no | path | default: workspace_root.parent.parent |

### handoff.py update

Updates L1 state machine in `CONTEXT.md`.

```
python scripts/handoff.py update \
  --project-root <path> \
  --workspace <NNN-slug> \
  --profile <profile> \
  --tier <tier> \
  --stage-atual <NN> \
  --stage-dir <NN_name> \
  --sub-stage <sub_stage_value> \
  --status <status> \
  --iteration <N> \
  --last-action "<text>" \
  --last-action-at "<ISO8601>" \
  --next-action "<text>" \
  --skill-dir <path>
```

### handoff.py remove

Removes a workspace's ICM block from project-root CLAUDE.md.

```
python scripts/handoff.py remove \
  --project-root <path> \
  --workspace <NNN-slug> \
  [--closed-at "<ISO8601>"]
```

---

## wave-planner-script.py

Parses `plan.md`, builds DAG, topological-sorts into waves, renders `wave-plan.md`.

```
python scripts/wave-planner-script.py \
  --plan stages/02_design/output/plan.md \
  --tier development \
  --profile app_web_backend \
  --workspace 042-feat-auth \
  --output stages/03_wave_planner/output/wave-plan.md \
  [--ambiguities-output stages/03_wave_planner/output/ambiguities-resolved.md]
```

**Plan.md requirements:**
- Each task: `## Task <slug>: <title>`
- Mandatory sections: `### Files touched`, `### Depends on`
- Optional: `**Type:** HITL` or `**Type:** AFK` (default AFK)
- Dependency format: `- <slug>` or `- none` (root task)
- Parenthetical notes in deps stripped automatically: `- config-module (needs api_key)` → `config-module`

**Stdout:** `total_tasks=N total_waves=M total_sub_waves=K ambiguities=A`
**Exit 0:** success. **Exit 1:** error (cycle, unknown dep, invalid schema).

---

## forensic-plus.py

Audits AFK task branches with 8 git-only checks. Used in stage 04 step 8a.

**Precondition:** task branch `wave-<NNN>-<N>/<slug>` must exist with ≥1 commit.
Script checks this first — clear error if branch missing.

```
python scripts/forensic-plus.py \
  --workspace-num <NNN> \
  --wave <N> \
  --task-slug <slug> \
  --base-branch main \
  --plan stages/02_design/output/plan.md \
  --tier development \
  --output json
```

**Checks:** test assertions ≥2, files outside declared, scope creep >3× estimate,
TODO/FIXME/HACK added, acceptance↔test mapping, OUT OF SCOPE violations,
ADR import drift, E2E coverage.

**Output:** JSON to stdout. Exit 0: passes. Exit 1: check failures.

---

## agent-brief-render.py

Generates AGENT-BRIEF for stage 04 subagent dispatch. Supports 3 isolation modes
(worktree, manual-worktree, direct) with auto-detection via `--isolation-mode auto`.

```
python scripts/agent-brief-render.py \
  --task <task-slug> \
  --plan stages/02_design/output/plan.md \
  --workspace-num <NNN> \
  --wave <N> \
  --project-root <path> \
  --base-branch main \
  [--adrs <project>/.icm-main/docs/decisions] \
  [--tier development] \
  [--isolation-mode auto|worktree|manual-worktree|direct] \
  [--strict]
```

Output: markdown brief with behavioral instructions, acceptance criteria, and
mode-specific isolation rules. Exit 1 if task not found or `--strict` with warnings.

---

## lead-diagnose.py

Post-forensic diagnostic: Jaccard cluster analysis, catastrophic detection, bucket recommendation.

```
python scripts/lead-diagnose.py \
  --task-slug <slug> \
  --wave <N> \
  --workspace-num <NNN> \
  --base-branch main \
  --plan stages/02_design/output/plan.md \
  --forensic-results <path-to-json> \
  --files-touched "src/a.py,src/b.py" \
  [--forensic-files-outside <N>] \
  [--build-command "pytest"] \
  [--trigger forensic_hard_fail] \
  [--output <path>] \
  [--format md|json]
```

---

## pick-model.py

Scores task complexity and selects writer/critic models with tier ceiling.

```
python scripts/pick-model.py \
  --plan stages/02_design/output/plan.md \
  --task-slug <slug> \
  --tier development \
  --output json
```

---

## profile-merge.py

Merges 11 profiles × 4 tiers → deterministic effective hash (SHA-256).

```
python scripts/profile-merge.py \
  --profile app_web_backend \
  --tier development \
  [--override .icm-profile.local.yaml]
```

Stdout: `profile_effective_hash=<sha256>`.

---

## wave-planner-llm-review.py

Optional LLM review subagent for wave plan validation (stage 03).

```
python scripts/wave-planner-llm-review.py \
  --plan stages/02_design/output/plan.md \
  --wave-plan stages/03_wave_planner/output/wave-plan.md \
  --tier development \
  --profile app_web_backend \
  --workspace <NNN-slug> \
  --output stages/03_wave_planner/output/llm-review-verdict.json \
  [--model claude-sonnet-4-6]
```

---

## wave-preflight.py

Deterministic pre-flight checks before Agent spawn in stage 04 (9 checks). Replaces
the ~150-line manual pre-flight checklist. All checks are git + filesystem + script
`--help` — zero token cost.

```
python scripts/wave-preflight.py \
  --workspace-num <NNN> \
  --workspace-slug <slug> \
  --wave <N> \
  --project-root <path> \
  --base-branch main \
  [--skill-dir <path>] \
  [--json]
```

| Flag | Required | Format | Notes |
|------|----------|--------|-------|
| `--workspace-num` | yes | NNN | Numeric part of workspace ID (e.g. `001`) |
| `--workspace-slug` | yes | string | Slug part (e.g. `flap-bird-clone`). Combined: `NNN-slug` |
| `--wave` | yes | N | Wave number (e.g. `3`) |
| `--project-root` | yes | path | Project root directory |
| `--base-branch` | no | string | Default `main` |
| `--skill-dir` | no | path | Auto-detected from script location if omitted |
| `--json` | no | flag | Output JSON instead of text |

**Checks:** workspace_branch, wave_plan_exists, branch_naming, skill_dir_callable,
output_dir, worktree_topology, orphan_worktrees, orphan_branches, clean_working_tree.

**Output:** JSON to stdout (with `--json`). Exit 0: all pass. Exit 1: failures present.

---

## recovery-wizard.py

Detects and repairs 7 workspace inconsistency types.

```
python scripts/recovery-wizard.py \
  --project-root <path> \
  --workspace-dir <path> \
  [--dry-run] \
  [--repair]
```

---

## validate_state.py

Validates L1 YAML frontmatter against state-machine schema.

```
python scripts/validate_state.py \
  --context-md <path>
```

Exit 0: valid. Exit 1: invalid (errors to stderr).

---

## bootstrap.py

One-shot workspace creation (stage 00).

```
python scripts/bootstrap.py \
  --profile app_web_backend \
  --tier development \
  --project-root <path> \
  --workspace-name <slug> \
  [--logs-root <path>] \
  [--override <path>]
```

---

## migrate-workspace.py

Migrates workspace from older skill version to current.

```
python scripts/migrate-workspace.py \
  --workspace-root <path> \
  [--project-root <path>] \
  [--target <version>] \
  [--dry-run] \
  [--no-backup]
```

---

## lessons-match.py

Extracts top-N relevant lessons for current task.

```
python scripts/lessons-match.py \
  --lessons path/to/lessons.md \
  --profile app_web_backend \
  --tier development \
  --tags "auth,api" \
  --files "src/auth.py,src/api.py" \
  [--top-n 3]
```

---

## runtime-registry.py

Manages runtime resources (dev servers, CDP browsers) across workspace sessions.

```
# Register
python scripts/runtime-registry.py register \
  --workspace-root <path> \
  --kind dev_server|cdp_browser \
  [--pid <N>] [--port <N>] [--command "<cmd>"] [--metadata "<json>"]

# List
python scripts/runtime-registry.py list \
  --workspace-root <path> \
  [--kind dev_server] [--format json|text]

# Unregister
python scripts/runtime-registry.py unregister \
  --workspace-root <path> \
  --id <entry_id>

# Purge all
python scripts/runtime-registry.py purge \
  --workspace-root <path>

# Legacy cleanup
python scripts/runtime-registry.py cleanup-legacy \
  --project-root <path>
```

---

## runtime-status.py

Checks runtime environment health for a workspace.

```
python scripts/runtime-status.py \
  --workspace-root <path> \
  --project-root <path> \
  [--check dev_server|cdp|deps|all] \
  [--format json|text] \
  [--exit-code]
```

---

## icm-cleanup.py

Removes ICM scaffolding from project after workspace completion.

```
python scripts/icm-cleanup.py \
  --project-root <path> \
  --workspace <NNN-slug> \
  [--base-branch main] \
  [--dry-run]
```

---

## i18n-audit.py

Audits codebase for residual pt-BR tokens (internal QA tool).

```
python scripts/i18n-audit.py \
  --skill-dir <path> \
  [--format json|text]
```

---

## migrate-v3.3-to-v3.4.py

One-time migration from v3.3 workspace format to v3.4.

```
python scripts/migrate-v3.3-to-v3.4.py \
  --project-root <path> \
  [--update-paths] \
  [--dry-run]
```

---

## bootstrap.sh

Shell wrapper for `bootstrap.py`. Interactive prompts for profile/tier/workspace-name when not provided via flags.

```
bash scripts/bootstrap.sh \
  --profile app_web_backend \
  --tier development \
  --project-root /path/to/project \
  [--workspace-name my-feature] \
  [--logs-root /path/to/logs] \
  [--override /path/to/icm-profile.local.yaml]
```

Profiles: app_web_backend, app_web_frontend, fullstack, dashboard, data_analysis, ml_project, agent_ia, cli_tool, framework_library, technical_article, experiment
Tiers: experimental, tool, development, production

---

## git-hook-installer.sh

Installs pre-commit + commit-msg hooks idempotently. Used by bootstrap and recovery wizard.

```
bash scripts/git-hook-installer.sh <project_root>
```

---

## validate-state.sh

Validates L1 CONTEXT.md YAML frontmatter against state-machine schema. Wrapper around `validate_state.py`.

```
bash scripts/validate-state.sh --workspace <path>
```

Exit 0: valid. Exit 1: invalid (errors to stderr).

---

## render-critic-prompt.py

Renders L3 critic prompt from `templates/critic-prompt.md` with all 10 placeholders substituted. Captures git diff + test output automatically.

```
python scripts/render-critic-prompt.py \
  --task-slug <slug> --wave <N> --tier <tier> \
  --workspace-num <NNN> --base-branch main \
  --plan stages/02_design/output/plan.md \
  --critic-model <model_from_pick_model_py> \
  [--test-command "pytest tests/ -x --tb=short"] \
  [--cwd /path/to/project] \
  [--output /tmp/critic-prompt.md]
```

Stdout: rendered prompt ready for Agent tool injection. Exit 0: success. Exit 1: error.
