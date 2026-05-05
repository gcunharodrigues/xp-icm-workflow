# Conflict Resolution Protocol — Stage 04 Mid-Wave

> Canonical doc for merge conflict resolution during stage 04 (sequential wave merge). Referenced by `templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl` step 9.

## When it triggers

Lead executes `git merge --no-ff wave-<NNN>-<N>/<task-slug>` in step 9 → command returns non-zero with `CONFLICT (content): Merge conflict in <file>`. Lead remains on `BASE_BRANCH` with working tree in mid-merge state.

## Pre-resolution state

- `HEAD` on `BASE_BRANCH` with merge in-flight (`.git/MERGE_HEAD` present).
- Working tree contains files with markers `<<<<<<<`, `=======`, `>>>>>>>`.
- Remaining wave branches (not yet merged): waiting.
- L1 still `IN_PROGRESS`; lead will transition to `BLOCKED_ERROR`.

## Protocol

### Phase 1: Lead pauses + signals

1. Lead does NOT attempt to resolve autonomously (deliberate decision — merge code is high risk).
2. Lead updates L1:
   - `status: BLOCKED_ERROR`
   - `error_type: merge_conflict`
   - `last_transition.note: "merge conflict wave <N> task <conflicted-slug>"`
   - `history` append: `{event: "merge_conflict", wave: <N>, task: <slug>, conflicted_files: [...]}`
3. Lead writes `output/wave-<N>/merge-conflict-<slug>.md` documenting:
   - Conflicted branch.
   - List of files in conflict (`git diff --name-only --diff-filter=U`).
   - Diff of conflicted hunks.
   - Remaining wave tasks NOT yet merged.
4. Lead atomic commit:
   ```
   workspace <NNN>: BLOCKED merge conflict wave <N>
   ```
   (commit includes L1 + merge-conflict-<slug>.md; does NOT include working tree changes in conflict.)
5. Lead prints resolution prompt for human. WAITS in the same session.

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🛑 BLOCKED_ERROR — merge conflict wave <N>

Conflicted branch: wave-<NNN>-<N>/<task-slug>
Files:
  - <path/to/file1>
  - <path/to/file2>

Working tree in mid-merge state (.git/MERGE_HEAD present).
Remaining wave tasks (NOT yet merged): <list>

Options:
  A) Resolve manually in the files + `git add` + `git commit` →
     reply "resolved" to resume step 9 on remaining tasks.
  B) Abort this merge: `git merge --abort` →
     reply "abort task" to mark the task as BLOCKED_ERROR and
     skip it; lead proceeds to the remaining ones.
  C) Abort entire wave: reply "abort wave" → lead reverts
     all merges in this wave (`git reset --hard <pre-wave-sha>`),
     marks workspace BLOCKED_ERROR, exits.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Phase 2: Human response

#### "resolved"

1. Lead validates: `git status --porcelain` returns empty for conflicted files; `.git/MERGE_HEAD` still present OR already committed.
2. If MERGE_HEAD still present: human forgot to commit — lead executes `git commit --no-edit` (merge default message).
3. Lead updates L1: `status: IN_PROGRESS`, history append `{event: "conflict_resolved", task: <slug>}`.
4. Lead resumes step 9 on the remaining wave tasks (plan order).

#### "abort task"

1. Lead executes `git merge --abort`.
2. Marks `output/wave-<N>/task-<slug>-blocked.md` with `reason: merge_conflict_aborted`.
3. Updates L1: `status: IN_PROGRESS`, history append `{event: "task_aborted_conflict", task: <slug>}`.
4. Lead skips current task, proceeds to step 9 on the remaining ones.
5. Final wave-summary.md lists task as unresolved BLOCKED_ERROR; human decides stage 05+.

#### "abort wave"

1. Lead captures `pre_wave_sha` from L1 history (recorded at the start of the wave).
2. Lead executes `git merge --abort` + `git reset --hard <pre_wave_sha>` on `BASE_BRANCH`.
3. Updates L1: `status: BLOCKED_ERROR`, `error_type: wave_aborted`.
4. Lead writes `output/wave-<N>/wave-aborted.md` with original SHAs + tasks that were pending.
5. Lead atomic commit + EXIT. Next session: human decides whether to redo the wave or skip it.

### Phase 3: Post-resolution cleanup

- Resolved/aborted tasks: normal cleanup (step 11).
- Tasks with aborted merge conflict: branch remains (not deleted via `git branch -d` because it was not merged); human can investigate later.
- Wave-summary.md (step 12) records: `conflicts: [{task: <slug>, resolution: <resolved|aborted>}]`.

## Invariants

- **Lead never resolves conflict autonomously.** Human always decides.
- **Reset --hard only with explicit pre-wave SHA** (recorded in L1 history). Never `reset --hard HEAD~N`.
- **Wave conflict branch is not deleted** automatically (preserves evidence).
- **L1 status reflects reality:** `BLOCKED_ERROR` while waiting, `IN_PROGRESS` after resolved/aborted.
