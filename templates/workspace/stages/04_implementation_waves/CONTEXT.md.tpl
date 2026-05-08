---
layer: L2
stage: "04"
stage_name: "implementation_waves"
sub_stage_enum:
  - "04_wave_<N>_in_progress"
  - "04_wave_<N>_completed"
sub_stage_pattern: "^04_wave_\\d+_(in_progress|completed)$"
applicable_stop_points:
  - "new_dep"
  - "irreversible"
  - "over_eng"
  - "prod_migration"
  - "adr_drift"
  - "ambiguous_feedback"
  - "design_system_cascade"
output_files:
  - "output/wave-<N>/task-<slug>.md"
  - "output/wave-<N>/wave-summary.md"
  - "output/wave-<N>/task-<slug>-blocked.md"
  - "output/wave-<N>/task-<slug>-critic-round<R>.json"
  - "output/wave-<N>/task-<slug>-diagnose.md"
  - "output/wave-<N>/task-<slug>-lead-decision.md"
next_stage: "08"
---

# Stage 04 — implementation_waves (L2)

Parallel execution in waves. Lead orchestrates subagents in manual worktrees at `.claude/worktrees/icm-wave-{{WORKSPACE_NUM}}-<N>/<slug>/` on branches `wave-{{WORKSPACE_NUM}}-<N>/<slug>` (from `{{BASE_BRANCH}}`). Subagent follows vertical TDD cycle + HARD GATES. Per-task QA: L2 forensic+ (8 checks, 0 token) → L3 orthogonal critic (fresh-context Agent, anti-sycophancy). Cap 3 attempts. When cap exhausted or convergence detected → lead-resolution (RETRY or VOID). Lead merges via `.icm-main/` — project root never leaves `workspace/{{WORKSPACE}}`. One sub_stage per wave: `04_wave_<N>_in_progress` → `04_wave_<N>_completed`. Repeats until `wave-plan.md` exhausted.

**Consolidated canonical docs:**
- `references/wave-execution-protocol.md` — 5-phase pipeline
- `references/isolation-protocol.md` — single manual worktree path, merge via .icm-main
- `references/agent-brief-template.md` — HARD GATES + isolation rules
- `references/forensic-plus-protocol.md` — 8 checks
- `references/critic-protocol.md` — L3 critic
- `references/lead-resolution-protocol.md` — RETRY/VOID
- `references/4-block-contract-template.md` — TDD 7-step cycle

## SKILL_DIR resolution

{{SKILL_DIR}} in this document refers to the xp-icm-workflow skill installation directory.
To resolve it: `python -c "import xp_icm_workflow; print(xp_icm_workflow.__path__[0])" 2>/dev/null`
or check L0 `CLAUDE.md` frontmatter for `skill_dir`. If neither works:
`find ~/.claude/skills -name 'agent-brief-render.py' -path '*/xp-icm-workflow/*' | head -1 | xargs dirname`.

## Inputs (reads ONLY these, in order)

| # | Path | Layer | Required? |
|---|------|-------|-----------|
| 1  {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/CLAUDE.md | L0 | yes |
| 2  {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/CONTEXT.md | L1 | yes |
| 3  {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/04_implementation_waves/CONTEXT.md | L2 | yes |
| 4  {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/02_design/output/wave-plan.md | L4 | yes |
| 5  {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/02_design/output/plan.md | L4 | yes |
| 6  {{PROJECT_ROOT}}/.icm-main/docs/decisions/ | L3 | conditional: only ADRs listed in task's "Applicable ADRs" |
| 7  {{PROJECT_ROOT}}/.icm-main/docs/lessons.md | L3 | conditional: lead pre-extracts via lessons-match.py |
| 8  {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/superpowers-summary/test-driven-development-200tok.md | L3 | yes |
| 9  {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/superpowers-summary/subagent-driven-development-200tok.md | L3 | yes |
| 10  {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/runtime/4-block-contract-template.md | L3 | yes |
| 11  {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_config/xp-conventions.md | L3 | yes |
| 12  {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_config/profile-effective.yaml | L3 | yes |
| 13  {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_config/stop-points.md | L3 | yes |
| 14  {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/runtime/subagent-protocol.md | L3 | yes |
| 15  {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/04_implementation_waves/_kickoff.md | L4-kickoff | conditional |
| 16  {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/runtime/session-handoff-protocol.md | L3 | conditional: final handoff |
| 17  {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/runtime/stop-points-canonical.md | L3 | conditional |
| 18  {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/runtime/critic-protocol.md | L3 | yes |
| 19  {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/runtime/lead-resolution-protocol.md | L3 | yes |
| 20  {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/runtime/forensic-plus-protocol.md | L3 | yes |
| 21  {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/runtime/mocking-guidelines.md | L3 | yes |
| 22  {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/runtime/e2e-coverage-protocol.md | L3 | yes |

## Does Not Read (negative constraint)

- {{PROJECT_ROOT}}/workspaces/ (other workspaces — workspace isolation)
- ADRs NOT listed in "Applicable ADRs" of the current task
- Outputs of other stages in the same workspace (00, 01) — only plan.md and wave-plan.md from stage 02
- {{PROJECT_ROOT}}/.icm-main/docs/tech_debt.md directly — enters via lead's channel 2 if applicable

## Critical invariants (READ FIRST)

| # | Invariant | Violation consequence |
|---|-----------|----------------------|
| 1 | **HARD GATES must be at TOP of every AGENT-BRIEF.** `agent-brief-render.py` renders them. NEVER hand-write prompt without it. | Subagent skips branch verify, exits without commit (sessao-recorrencia) |
| 2 | **Single isolation path.** All subagents: `.claude/worktrees/icm-wave-{{WORKSPACE_NUM}}-<N>-<slug>/`. No `Agent(isolation="worktree")`. No `isolation=none` at project root. | `workspaces/` vanishes from disk |
| 3 | **Merge via `.icm-main/`.** `cd .icm-main && git merge --no-ff <branch> && cd ..`. Never switch project root off `workspace/{{WORKSPACE}}`. | Stash complexity, L1 update loss risk |
| 4 | **Project root stays on `workspace/{{WORKSPACE}}` for entire wave.** Switches to `main` only after stage 08. | State files destroyed |
| 5 | **AGENT-BRIEF HARD GATE.** NEVER spawn Agent without AGENT-BRIEF rendered and saved to `output/wave-<N>/task-<slug>-brief.md`. | No behavioral contract, no isolation rules, no acceptance criteria |
| 6 | **Model selection.** Use heuristic: doc/config/CSS-only → haiku, security/public-API/large → opus, default → sonnet. Set `model:` on every `Agent()` call. | Mechanical tasks waste tokens; architecture tasks under-modeled |
| 7 | **Branch naming.** Exact format: `wave-{{WORKSPACE_NUM}}-<N>/<slug>`. forensic-plus.py and lead-diagnose.py depend on this pattern. | Scripts crash with "branch not found" |

## Process — 5 Phases

**Preview Loop (conditional):** if `preview_loop.preview_loop_enabled: true` in
`_config/profile-effective.yaml`, execute Preview Loop entry hook (see § "Preview Loop")
BEFORE Phase 1.

### PHASE 1: PREPARE

1. **Read:** L0, L1, L2, wave-plan.md, plan.md. Identify current wave N via L1 `waves.current`.
   If L1 `status: BLOCKED` → check `block_reason`:
   - `human_gate` → human approved, set `status: IN_PROGRESS`, resume
   - `hitl` → HITL task completed, set `status: IN_PROGRESS`, resume
   - `stop_point` → human resolved A/B/C menu, resume
   - `error` → unresolved, human must intervene

2. **Run wave-preflight.py** (deterministic, 0 token):
   ```bash
   python {{SKILL_DIR}}/scripts/wave-preflight.py \
       --workspace-num {{WORKSPACE_NUM}} --wave <N> \
       --project-root {{PROJECT_ROOT}} --base-branch {{BASE_BRANCH}} --json
   ```
   If `all_pass: false` → fix violations before proceeding. Pre-flight checks:
   - Lead on `workspace/{{WORKSPACE}}` branch
   - wave-plan.md exists and non-empty
   - Output directory exists
   - No orphan worktrees or branches
   - Working tree clean

3. **Render AGENT-BRIEF per task** (HARD GATE — never spawn without it):
   ```bash
   python {{SKILL_DIR}}/scripts/agent-brief-render.py \
       --task <slug> --plan {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/02_design/output/plan.md \
       --workspace-num {{WORKSPACE_NUM}} --wave <N> \
       --project-root {{PROJECT_ROOT}} --base-branch {{BASE_BRANCH}} \
       --tier <T> > {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/04_implementation_waves/output/wave-<N>/task-<slug>-brief.md
   ```
   Output MUST contain HARD GATES at top. Verify with: `head -5 <file> | grep -q "HARD GATES"`.

4. **Channel 2 injection** (do BEFORE spawn — merge INTO AGENT-BRIEF prompt):
   - Applicable ADR content (from `.icm-main/docs/decisions/` — only those listed in task's "Applicable ADRs")
   - Top-3 lessons via `lessons-match.py`
   - DESIGN.md subset (if frontend/fullstack)
   - TDD 7-step contract + mocking guidelines

5. Record `pre_wave_sha = git rev-parse {{BASE_BRANCH}}` in L1 history:
   `{event: "wave_started", wave: <N>, pre_wave_sha: <sha>}`

### PHASE 2: EXECUTE

1. **Create branches from main:**
   ```bash
   git branch wave-{{WORKSPACE_NUM}}-<N>/<slug> {{BASE_BRANCH}}
   ```

2. **Create manual worktrees:**
   ```bash
   mkdir -p .claude/worktrees
   git worktree add .claude/worktrees/icm-wave-{{WORKSPACE_NUM}}-<N>-<slug> wave-{{WORKSPACE_NUM}}-<N>/<slug>
   ```

3. **Spawn ALL subagents in ONE message** (parallel dispatch for independent tasks):
   ```
   Agent(
       isolation=None,
       cwd="{{PROJECT_ROOT}}/.claude/worktrees/icm-wave-{{WORKSPACE_NUM}}-<N>-<slug>",
       subagent_type="general-purpose",
       model=<writer_model>,
       description="wave <N> task <slug>",
       prompt=<AGENT-BRIEF + channel-2>,
   )
   ```
   `.claude/` is gitignored. Worktree path is deterministic. Manual worktree IS the isolation.

4. **Subagent executes TDD 7-step cycle + HARD GATES:**
   - **GATE 1** (first action): `git branch --show-current` → must match `wave-{{WORKSPACE_NUM}}-<N>/<slug>`. Wrong → STOP.
   - **GATE 2**: use synchronous Bash for tests. NEVER Monitor for <5min tasks.
   - **Tracer-first** → RED → GREEN → CI scope → REFACTOR → repeat. 1 commit per iteration.
   - **Anti-horizontal slicing**: forbidden to write all tests at once or all impl at once.
   - **GATE 3** (before COMPLETE): `git log --oneline {{BASE_BRANCH}}..HEAD` ≥1 commit + clean working tree.

5. **Stop points within cycle:** subagent detects `new_dep`/`irreversible`/`over_eng`/`prod_migration`/`adr_drift` → A/B/C menu → L1 `BLOCKED, block_reason: stop_point`.

6. **Lead receives results, writes task reports:**
   Lead buffers result from Agent tool output. Lead writes task report at `output/wave-<N>/task-<slug>.md` with summary, modified files, tests, ADRs applied. Subagent NEVER writes workspace state files.

### PHASE 3: VERIFY

Pre-condition: lead on `workspace/{{WORKSPACE}}` branch. All task reports exist.

For each AFK task (skip `type: HITL`):

1. **L2 Forensic+ (0 token):**
   ```bash
   python {{SKILL_DIR}}/scripts/forensic-plus.py \
       --workspace-num {{WORKSPACE_NUM}} --wave <N> --task-slug <slug> \
       --base-branch {{BASE_BRANCH}} --tier <T> \
       --plan {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/02_design/output/plan.md \
       --output json
   ```
   Parse JSON. HARD in any check → skip L3, go to step 3 (diagnose). SOFT only → proceed to L3. Internal cap: `MAX_FORENSIC_RETRIES = 2` (3 attempts total = 1 original + 2 retries).

2. **L3 Orthogonal Critic (~3-8k tokens):**
   ```bash
   python {{SKILL_DIR}}/scripts/render-critic-prompt.py \
       --task-slug <slug> --wave <N> --tier <T> \
       --workspace-num {{WORKSPACE_NUM}} --base-branch {{BASE_BRANCH}} \
       --plan {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/02_design/output/plan.md \
       --critic-model <model> \
       --output output/wave-<N>/task-<slug>-critic-prompt-round<R>.md
   ```
   Spawn critic via `Agent(isolation=None, ...)` — fresh context, anti-sycophancy hardcoded. Output: APPROVE/REJECT/ABSTAIN with triplets. Critic model = tier ceiling (experimental→haiku, tool→sonnet, dev/prod→opus).

3. **Diagnose (if HARD or REJECT):**
   ```bash
   python {{SKILL_DIR}}/scripts/lead-diagnose.py \
       --task-slug <slug> --wave <N> --workspace-num {{WORKSPACE_NUM}} \
       --base-branch {{BASE_BRANCH}} \
       --critic-rounds output/wave-<N>/task-<slug>-critic-round1.json \
       --files-touched <comma-sep from git diff> \
       --forensic-files-outside <int from check 2> \
       --output output/wave-<N>/task-<slug>-diagnose.md
   ```
   Detects trigger: T1 (cap 3 exhausted), T2 (Jaccard convergence ≥0.7), T3 (catastrophic). Recommends RETRY or VOID.

4. **Decision per task:**
   - **APPROVE** (forensic+ passed + critic APPROVE) → task passes, proceed to merge.
   - **RETRY** (cap 3, not convergence, not catastrophic) → surgical brief re-spawn. Return to PHASE 2 step 4.
   - **Escalate to lead-resolution** (cap exhausted, convergence, or catastrophic) → RETRY or VOID.

   **Lead-resolution:** Lead reads diagnose.md. May override with justification in `lead-decision.md`.
   - RETRY: rewrite task spec in plan.md, 1 final spawn. APPROVE → merge. REJECT → VOID.
   - VOID: declare task unmergeable with VOIDED block. Re-run wave-planner. Continue with remaining.
   - Cap: 1 RETRY → VOID (terminal).

### PHASE 4: MERGE

1. **Merge via `.icm-main/`** — project root NEVER leaves `workspace/{{WORKSPACE}}`:
   ```bash
   cd {{PROJECT_ROOT}}/.icm-main
   git merge --no-ff wave-{{WORKSPACE_NUM}}-<N>/<slug>
   cd {{PROJECT_ROOT}}
   ```
   Repeat for each APPROVED task in plan order. Skip VOIDed tasks. No stash. No buffer.

2. **L4 Wave Gate:**
   - CI green (run from `.icm-main/`) — always, all tiers
   - E2E green — tier dev/prod with `user_facing_paths`
   - Cross-task coherence — production tier, ≥2 tasks sharing files

   CI red → revert merges on main (`git reset --hard pre_wave_sha`). Diagnose. Retry. See `references/ci-rollback-protocol.md`.

### PHASE 5: CLOSE

1. **Cleanup worktrees + branches:**
   ```bash
   git worktree remove .claude/worktrees/icm-wave-{{WORKSPACE_NUM}}-<N>-<slug>
   git branch -d wave-{{WORKSPACE_NUM}}-<N>/<slug>
   ```
   Repeat for all tasks. Paths deterministic — always known. `git branch -d` refuses unmerged (intentional) — never use `-D`.

2. **Sync `.icm-main/`:**
   ```bash
   cd {{PROJECT_ROOT}}/.icm-main
   if git remote get-url origin >/dev/null 2>&1; then
       git fetch origin main 2>/dev/null && git merge --ff-only FETCH_HEAD || true
   else
       git merge --ff-only main 2>/dev/null || true
   fi
   cd {{PROJECT_ROOT}}
   ```

3. **Write `wave-summary.md`** with: completed tasks, decisions, § L2/L3 summary (SOFT violations + critic MINOR concerns), § Lead resolutions, cleanup warnings.

CWD: lead at `{{PROJECT_ROOT}}` on `workspace/{{WORKSPACE}}` — MUST stay here for entire wave. Subagent in `.claude/worktrees/icm-wave-{{WORKSPACE_NUM}}-<N>-<slug>/` on `wave-{{WORKSPACE_NUM}}-<N>/<slug>`.

## Outputs

- `output/wave-<N>/task-<slug>.md` — task report (lead-written from Agent tool output)
- `output/wave-<N>/wave-summary.md` — lead synthesis post merge
- `output/wave-<N>/task-<slug>-blocked.md` — conditional: stop point triggered or cap exhausted
- `output/wave-<N>/task-<slug>-critic-round<R>.json` — L3 critic output (PHASE 3)
- `output/wave-<N>/task-<slug>-diagnose.md` — diagnose report (lead-diagnose.py output)
- `output/wave-<N>/task-<slug>-lead-decision.md` — lead decision (RETRY/VOID, when diagnose escalated)

## Sub_stage transitions

Valid enum: `04_wave_<N>_in_progress`, `04_wave_<N>_completed` (`<N>` positive integer). Pattern: `^04_wave_\d+_(in_progress|completed)$`.

`04_wave_<N>_in_progress` → `04_wave_<N>_completed` fires when:
- All subagents delivered COMPLETE.
- Wave-reviewer approved.
- Sequential merge + CI green.
- `wave-summary.md` written.

`04_wave_<N>_completed` → `04_wave_<N+1>_in_progress` (more waves) internal to stage. Last wave → `next_stage: 08`.

## Canonical statuses (v4.0)

- `IN_PROGRESS` — wave executing (lead orchestrating, subagents working, lead resolution active)
- `BLOCKED` — requires `block_reason`: `human_gate`, `stop_point`, `error`, `hitl`, `lead_resolution`

## Applicable stop points

Canonical catalogue: `references/stop-points-canonical.md`. Triggerable in stage 04:
- `new_dep` — new dependency not in plan.md
- `irreversible` — destructive operation without safety net
- `over_eng` — 3+ new abstraction layers without requirement
- `prod_migration` — production-volume table migration without maintenance window
- `adr_drift` — implementation diverges from active ADR
- `ambiguous_feedback` — (preview loop) vague human visual feedback
- `design_system_cascade` — (preview loop) token change affects > threshold components

## Skill superpowers reference

TDD summary: `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/superpowers-summary/test-driven-development-200tok.md`
Subagent summary: `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/superpowers-summary/subagent-driven-development-200tok.md`
Formal skills: `superpowers:test-driven-development` + `superpowers:subagent-driven-development` (escape hatch).

## Gates

- **Human:** approves last wave → stage 08; responds to A/B/C stop point menus; resolves merge conflicts
- **Automatic (CI):** commit-msg hook validates prefix `workspace {{WORKSPACE_NUM}}:` on workspace branch; global CI runs after each wave merge; L2 forensic+ + L3 critic validate per task
- **Approval to transition:** wave closes when merge + CI green + wave-summary written. Last wave needs human approval → stage 08

## End of stage handoff (v4.0 wave-aware)

Each wave = 1 lead session. Lead closes wave updating L1 for next wave or stage 08.

### Case A: mid-wave handoff (wave N → N+1) — automatic

1. **Update L1:**
   - `sub_stage = 04_wave_<N+1>_in_progress`
   - `status = IN_PROGRESS`
   - `waves.current = <N+1>`, append `<N>` to `waves.completed`
   - Set `prev_outputs` (wave N output paths) and `pending` (wave N+1 task slugs)
   - `last_transition.from = 04_wave_<N>_in_progress`, `last_transition.to = 04_wave_<N+1>_in_progress`
   - `history` append: `{event: "stage_transition", note: "mid-wave auto-handoff, waves.current = <N+1>"}`

2. **Atomic commit** (outputs + L1). EXIT session.

### Case B: last wave → stage 08 — human gate

**Phase 1: WORK_DONE**

1. Update L1: `sub_stage = 04_wave_<N>_completed`, `status = BLOCKED`, `block_reason = human_gate`. Set `prev_outputs`.
2. Commit: `workspace <NNN>: stage 04 work done (last wave), awaiting human gate`
3. Print gate prompt for human. WAIT in same session.

**Phase 2: HUMAN_APPROVED**

4. Human replies "approved" → update L1: `stage_atual = 08`, `sub_stage = 08_in_progress`, `status = IN_PROGRESS`
5. Commit: `workspace <NNN>: gate approved, transitioning to stage 08 (feedback)`
6. Run `handoff.py update-project-md` to update project root CLAUDE.md dashboard
7. Print handoff message. EXIT session.

"adjust X" → return to work. "abort" → `BLOCKED, block_reason: error`, exit.

---

## Reference CLI signatures

### agent-brief-render.py (PHASE 1)

```bash
python {{SKILL_DIR}}/scripts/agent-brief-render.py \
    --task <slug> --plan stages/02_design/output/plan.md \
    --adrs {{PROJECT_ROOT}}/.icm-main/docs/decisions \
    --workspace-num {{WORKSPACE_NUM}} --wave <N> \
    --project-root {{PROJECT_ROOT}} --base-branch {{BASE_BRANCH}}
```

### forensic-plus.py (PHASE 3)

```bash
python {{SKILL_DIR}}/scripts/forensic-plus.py \
    --workspace-num {{WORKSPACE_NUM}} --wave <N> --task-slug <slug> \
    --base-branch {{BASE_BRANCH}} --tier <T> \
    --plan stages/02_design/output/plan.md --output json
```

### render-critic-prompt.py (PHASE 3)

```bash
python {{SKILL_DIR}}/scripts/render-critic-prompt.py \
    --task-slug <slug> --wave <N> --tier <T> \
    --workspace-num {{WORKSPACE_NUM}} --base-branch {{BASE_BRANCH}} \
    --plan stages/02_design/output/plan.md --critic-model <model> \
    --output output/wave-<N>/task-<slug>-critic-prompt-round<R>.md
```

### lead-diagnose.py (PHASE 3)

```bash
python {{SKILL_DIR}}/scripts/lead-diagnose.py \
    --task-slug <slug> --wave <N> --workspace-num {{WORKSPACE_NUM}} \
    --base-branch {{BASE_BRANCH}} \
    --critic-rounds output/wave-<N>/task-<slug>-critic-round1.json[,round2.json,...] \
    --files-touched <comma-sep> --forensic-files-outside <int> \
    --output output/wave-<N>/task-<slug>-diagnose.md
```

### lessons-match.py (Channel 2)

```bash
python {{SKILL_DIR}}/scripts/lessons-match.py \
    --task <slug> --plan stages/02_design/output/plan.md \
    --lessons {{PROJECT_ROOT}}/.icm-main/docs/lessons.md --top 3
```

### HITL handling (task-level)

Mixed wave (some tasks HITL, others AFK): lead spawns Agents for AFK tasks in parallel; for HITL tasks generates AGENT-BRIEF + writes `output/wave-<N>/task-<slug>.md` with frontmatter `status: AWAITING_HITL`. After AFK Agents return, if HITL tasks still pending: L1 `status=BLOCKED, block_reason=hitl, sub_stage=04_wave_N_partial_hitl_pending`, EXIT. Next session validates HITL tasks completed (human edited) and resumes PHASE 3.

---

## Preview Loop entry/exit hooks (v3.6.0)

Applies ONLY when `preview_loop.preview_loop_enabled: true` in `_config/profile-effective.yaml`.
Canonical doc: `_references/runtime/preview-loop-protocol.md`.

### Entry hook (before PHASE 1)

1. Detect package manager via lockfile (bun > pnpm > yarn > npm). None → BLOCKED.
2. Verify runtime registry: `runtime-registry.py list --kind dev_server`. Alive → reuse. Dead → unregister. None → start new.
3. Start dev server + register: `<pm> run dev > .icm-main/.dev-server.log 2>&1 &` + `runtime-registry.py register`.
4. Print kickoff priming for human visual feedback.

### Exit hook (after Case B Phase 2 GATE_APPROVED)

1. List dev_server entries from registry. Kill alive PIDs. Unregister entries.
2. Delete `.dev-server.log`. Do NOT delete `.icm-chrome-profile/`.

Stage 08 does NOT depend on the dev server.
