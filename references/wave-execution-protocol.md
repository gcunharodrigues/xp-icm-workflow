# Wave Execution Protocol — Stage 04 (Canonical)

> Canonical doc for the wave cycle in stage 04. Source of truth — other docs point here.

## Summary (1 paragraph)

Stage 04 = N sequential waves. Each wave = 1 lead session. Lead spawns subagents in manual worktrees at `.claude/worktrees/icm-wave-<NNN>-<N>-<slug>/`, one per task (up to cap per tier 2/3/5/5). Subagent follows TDD 7-step cycle + HARD GATES. After all tasks complete: L2 forensic+ + L3 critic verify, lead merges via `.icm-main/` into `main` (plan order), global CI, cleanup, handoff. Mid-wave handoff is automatic; last wave requires human gate.

## Actors

| Actor | Session | CWD | Branch | Role |
|------|--------|-----|--------|--------|
| Lead | 1 (entire wave) | `{{PROJECT_ROOT}}` | `workspace/{{WORKSPACE}}` | Orchestrates, manages L1 state, merges via `.icm-main/` |
| Subagent N | Spawned by lead via Agent | `.claude/worktrees/icm-wave-<NNN>-<N>/<slug>` | `wave-<NNN>-<N>/<slug>` | TDD 7 steps + HARD GATES, returns structured result |
| Wave-reviewer | Spawned by lead via Agent (no isolation) | Lead CWD | `workspace/{{WORKSPACE}}` | Audits forensic+ output, critic output, acceptance |
| Human | Async (inline gate) | — | — | Approves last wave, resolves conflicts, answers stop points |

## Branches during wave

```
main (= BASE_BRANCH)              ← stable, lead merges here via .icm-main/
  └─ workspace/<NNN-slug>          ← lead works here (state files L1/L2, outputs)
       └─ wave-<NNN>-<N>/<slug-1>  ← subagent 1 (in .claude/worktrees/)
       └─ wave-<NNN>-<N>/<slug-2>  ← subagent 2
       └─ ...
```

## 5-Phase Pipeline

| Phase | Entry criteria | Exit criteria |
|-------|---------------|---------------|
| 1 PREPARE | L1 `sub_stage = 04_wave_N_in_progress` | wave-preflight.py PASS; AGENT-BRIEF rendered per task; channel 2 injected |
| 2 EXECUTE | Pre-flight complete | All subagents returned COMPLETE; task reports written |
| 3 VERIFY | All task reports present | Per task: APPROVE or escalated to lead-resolution |
| 4 MERGE | All tasks APPROVED or VOIDed | Merged into main via `.icm-main/`; L4 wave gate green |
| 5 CLOSE | Wave gate green | Worktrees removed; branches deleted; wave-summary written; handoff |

### PHASE 1: PREPARE

1. Read L0, L1, L2, wave-plan.md, plan.md. Identify current wave N.
2. Run `wave-preflight.py --workspace-num <NNN> --workspace-slug <slug> --wave <N> --project-root <path> --base-branch main --json` (deterministic, 0 token). Failures → fix before proceeding.
3. For each task: render AGENT-BRIEF via `agent-brief-render.py`. HARD GATE — never spawn without it.
4. Channel 2 injection: ADR subset + top-3 lessons + design subset INTO AGENT-BRIEF prompt.
5. Record `pre_wave_sha` in L1 history.

### PHASE 2: EXECUTE

1. For each task: `git branch wave-<NNN>-<N>/<slug> main`
2. For each task: `git worktree add .claude/worktrees/icm-wave-<NNN>-<N>-<slug> wave-<NNN>-<N>/<slug>`
3. Spawn ALL subagents in ONE message (parallel dispatch):
   ```
   Agent(isolation=None,
         cwd="<project>/.claude/worktrees/icm-wave-<NNN>-<N>-<slug>",
         subagent_type="general-purpose",
         model=<writer_model>,
         description="wave <N> task <slug>",
         prompt=<AGENT-BRIEF + channel-2>)
   ```
4. Subagent executes TDD 7-step cycle + HARD GATES (branch verify, sync-first, commit verify).
5. Lead receives results via Agent tool output, writes task reports at `output/wave-<N>/task-<slug>.md`.

Stop points within the cycle: subagent detects `new_dep`/`irreversible`/`over_eng`/`prod_migration`/`adr_drift` → A/B/C menu → L1 `BLOCKED` with `block_reason: stop_point`.

### PHASE 3: VERIFY

For each AFK task (skip HITL):

1. **L2 Forensic+ (0 token):** `forensic-plus.py --workspace-num <NNN> --wave <N> --task-slug <slug> --base-branch main --tier <T> --plan <plan.md> --output json`
   - HARD in any check → skip L3, go to step 3 (diagnose)
   - SOFT only or NONE → proceed to L3
2. **L3 Orthogonal Critic:** render critic prompt + spawn fresh-context Agent (model = tier ceiling). Anti-sycophancy hardcoded. Output: APPROVE/REJECT/ABSTAIN with triplets.
3. **Diagnose (if HARD or REJECT):** `lead-diagnose.py` → trigger detection (T1 cap exhausted / T2 convergence / T3 catastrophic) → action recommendation.
4. **Decision:** APPROVE → proceed to merge. RETRY (cap 3) → re-spawn writer with surgical brief. Escalate → lead-resolution (RETRY/VOID).

Lead-resolution (when QA loop exhausted): RETRY (rewrite spec + 1 final spawn) or VOID (task removed from plan). Cap: 1 RETRY → VOID (terminal).

### PHASE 4: MERGE

1. For each APPROVED task in plan order (skip VOIDed):
   ```bash
   cd .icm-main
   git merge --no-ff wave-<NNN>-<N>/<slug>
   cd ..
   ```
   Project root NEVER leaves `workspace/<NNN-slug>`. No stash. No buffer.

2. **L4 Wave Gate:**
   - CI global green (always, all tiers) — run from `.icm-main/`
   - E2E green (tier dev/prod with user_facing_paths)
   - Cross-task coherence (production tier, ≥2 tasks sharing file/API)

   CI red → revert merges on main, diagnose, retry. See `references/ci-rollback-protocol.md`.

### PHASE 5: CLOSE

1. **Cleanup:**
   ```bash
   git worktree remove .claude/worktrees/icm-wave-<NNN>-<N>-<slug>
   git branch -d wave-<NNN>-<N>/<slug>
   ```
   For all tasks in the wave. Paths are deterministic — always known.

2. **Sync `.icm-main/`:**
   ```bash
   cd .icm-main
   git fetch origin main 2>/dev/null && git merge --ff-only FETCH_HEAD || true
   cd ..
   ```

3. **Write `wave-summary.md`** with completed tasks, decisions, § L2/L3 summary, § Lead resolutions.

4. **Handoff:**
   - **Mid-wave (wave N → N+1):** automatic — update L1, commit, exit session.
   - **Last wave → stage 08:** human gate mandatory. L1 `status: BLOCKED, block_reason: human_gate`. Human approves → transition to stage 08.

## Canonical statuses (v4.0)

- `IN_PROGRESS` — wave executing
- `BLOCKED` — requires `block_reason`: `human_gate`, `stop_point`, `error`, `hitl`, `lead_resolution`

## Cross-references

- Isolation: `references/isolation-protocol.md`
- AGENT-BRIEF: `references/agent-brief-template.md` + `scripts/agent-brief-render.py`
- Forensic+: `references/forensic-plus-protocol.md`
- L3 Critic: `references/critic-protocol.md`
- Lead-resolution: `references/lead-resolution-protocol.md`
- Stop points: `references/stop-points-canonical.md`
- Merge conflict: `references/conflict-resolution-protocol.md`
- CI rollback: `references/ci-rollback-protocol.md`
- Handoff: `references/session-handoff-protocol.md`
- L2 runtime: `templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl`

## Global invariants

- Lead always on `workspace/<NNN-slug>`. Never switches off during stage 04.
- Subagents always in `.claude/worktrees/icm-wave-<NNN>-<N>-<slug>/`.
- Wave branches created from `main`, NOT from workspace branch.
- Merge via `.icm-main/` — project root untouched.
- Sequential merge follows plan order, not Agent return order.
- `pre_wave_sha` captured in L1 history for rollback.
- Wave branches deleted ONLY after successful merge + CI green.
- Subagent MUST be isolated from project root. NEVER `isolation=none` at project root for code-writing tasks.
