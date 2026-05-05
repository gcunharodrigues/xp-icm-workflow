# CI Global Rollback Protocol — Stage 04 Post-Merge

> Canonical rollback doc when global CI fails after sequential wave merge (step 10). Referenced by `templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl`.

## When it triggers

Lead completed step 9 (sequential merge) successfully. Step 10 runs full CI (`bash tests/run.sh` or the project equivalent pipeline). Result: red. State: `BASE_BRANCH` has all wave merges applied; CI is broken.

## Pre-rollback state

- `BASE_BRANCH` HEAD = last wave merge (green commit locally but global CI red).
- L1: `IN_PROGRESS`, sub_stage `04_wave_<N>_in_progress`.
- Cleanup (step 11) NOT yet executed — wave worktrees + branches still intact.

## Protocol

### Phase 1: Diagnose (do not skip)

1. Lead invokes `references/diagnose-protocol.md` (build feedback loop → reproduce → hypothesise → fix). Time cap: 30min lead-side.
2. Diagnose result:
   - **Cause identified + fix < 50 lines:** lead applies fix directly on `BASE_BRANCH` (commit `workspace <NNN>: ci-fix wave <N> <hypothesis>`). Returns to step 10. Loop max 3 times.
   - **Cause in specific task + fix > 50 lines OR multiple tasks affected:** go to Phase 2 (rollback).
   - **Cause not identified after cap:** go to Phase 2 (rollback).

### Phase 2: Rollback

1. Lead captures `pre_wave_sha` from L1 history.
2. Lead updates L1:
   - `status: BLOCKED_ERROR`
   - `error_type: ci_global_red`
   - `history` append: `{event: "ci_global_red", wave: <N>, diagnose_attempts: <N>, rolling_back: true}`
3. Lead executes `git reset --hard <pre_wave_sha>` on `BASE_BRANCH`. Destructive change — entire wave reverted.
4. Lead PRESERVES wave branches (does not delete). Ephemeral worktrees: normal cleanup (no `--force` if Auto-QA passed; see decision matrix step 11).
5. Lead writes `output/wave-<N>/ci-rollback.md`:
   - Before/after SHAs.
   - Diagnose attempts log.
   - CI symptoms (logs).
   - Wave tasks (all affected).
6. Lead atomic commit:
   ```
   workspace <NNN>: ci rollback wave <N> — diagnose inconclusive
   ```
7. Lead prints human gate prompt. WAITS.

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🛑 BLOCKED_ERROR — CI global red post-merge wave <N>

Diagnose: <cause-identified-or-inconclusive>
Diagnose attempts: <N>/3

BASE_BRANCH reverted to <pre_wave_sha> (wave merges destroyed).
Wave branches PRESERVED for investigation:
  - wave-<NNN>-<N>/<slug-1>
  - wave-<NNN>-<N>/<slug-2>
  ...

Next options:
  A) Redo wave: reply "redo wave" → lead re-spawns subagents
     with lessons learned in channel 2. Existing wave branches
     deleted; new ones created.
  B) Redo specific task: reply "redo task <slug>" → lead
     re-spawns only that task; others keep original branches
     (sequential re-merge after).
  C) Abandon wave: reply "abandon" → marks workspace
     BLOCKED_ERROR permanently; human decides stage 05+.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Phase 3: Human response

#### "redo wave"

1. Lead deletes existing wave branches: `git branch -D wave-<NNN>-<N>/<slug>` (force because not-merged after reset).
2. Lead injects into channel 2 of the next run: lessons from `ci-rollback.md` (symptoms + identified cause if any).
3. Lead updates L1: `status: IN_PROGRESS`, history append `{event: "wave_redo", wave: <N>}`.
4. Returns to step 2 of Process (create branches + spawn subagents).

#### "redo task <slug>"

1. Lead identifies task by slug.
2. Lead deletes ONLY that branch: `git branch -D wave-<NNN>-<N>/<slug>`. Other wave branches remain.
3. Lead updates L1: `status: IN_PROGRESS`, history append `{event: "task_redo", task: <slug>}`.
4. Lead spawns ONLY one Agent for that task. When it returns COMPLETE, goes to step 9 — SEQUENTIAL re-merge of ALL wave branches (including the preserved ones).
5. Returns to step 10 (global CI gate).

#### "abandon"

1. Lead updates L1: `status: BLOCKED_ERROR`, `error_type: wave_abandoned`. Sub_stage stays `04_wave_<N>_in_progress`.
2. Wave branches remain (preserves evidence).
3. Lead atomic commit + EXIT.

## Invariants

- **Reset --hard only with explicit SHA from `pre_wave_sha`.** Captured in L1 history at the start of the wave (step 1 of Process must record it).
- **Wave branches preserved during BLOCKED_ERROR ci_global_red.** Cleanup only after resolution (redo wave / redo task / abandon).
- **Diagnose protocol is mandatory before rollback.** Do not skip to rollback directly — cheap cost vs re-implementation cost.
- **L1 history tracks all attempts:** `wave_started`, `ci_global_red`, `wave_redo`, etc.

## Dependency

Step 1 of Process must record `pre_wave_sha: <BASE_BRANCH HEAD sha>` in L1 history event `wave_started`. Without this, rollback is blind. Check/add in step 1 template if absent.
