# Recovery Wizard

> Detection and reconstruction of ICM workspaces in an inconsistent state. Triggered on pre-flight check of a NEW session (human explicitly resuming), never by timer/cron.

> **Path resolution:** all `scripts/` paths in this document refer to the `<SKILL_DIR>/scripts/` directory, where `SKILL_DIR` is defined in L0 (`CLAUDE.md`). In a workspace context, use the absolute path `${SKILL_DIR}/scripts/<script>`.

## When it triggers

`<SKILL_DIR>/scripts/recovery-wizard.py` is invoked:

1. **Bootstrap** detects `<project_root>/workspaces/NNN-slug/` ALREADY exists — could be a legitimate resume or an orphaned state.
2. **Pre-flight of each session** (Q1.1) — before loading L2, validates L1 via `${SKILL_DIR}/scripts/validate-state.sh`. Heuristics R2.7 → triggers wizard.

NEVER triggers: cron, timer, agent in loop, mid-flight session.

## Detected inconsistencies (R2.7 + R4.5 + R6.6 + G5)

| Code | Severity | Cause | Detection |
|---|---|---|---|
| `HASH_MISMATCH` | warning | `_config/profile-effective.yaml` edited outside of bootstrap | sha256 recomputed vs `profile_effective_hash` in L0 |
| `MISSING_OUTPUT` | warning | output declared in `history` absent from FS | regex `stages/\d{2}\w*/output/.+\.md` on history items; existence check |
| `STALE_IN_PROGRESS` | warning | session crashed or was abandoned | `status: IN_PROGRESS` AND no commit in `workspaces/NNN/*` for the last 24h |
| `MISSING_COMMIT` | critical | merge/force push eliminated the referenced commit | `git cat-file -e <last_transition.commit_sha>` fails |
| `BRANCH_MISSING` | critical | human deleted `workspace/NNN-slug` | `git branch --list workspace/NNN-slug` empty |
| `BOOTSTRAP_PARTIAL` | critical | bootstrap crashed between scaffold commit and hook install | workspace dir exists AND scaffold committed AND hooks absent in `.git/hooks/` |
| `CLAUDE_MD_ROOT_STALE` | warning | session crashed without calling `handoff.update_project_claude_md` | workspace block in `<project_root>/CLAUDE.md` (ICM region) has `stage_atual` ≠ `L1.stage_atual` |
| `CLAUDE_MD_ROOT_MISSING` | warning | block removed manually, or bootstrap pre-v3.1 | `L1.status=IN_PROGRESS` but comment `<!-- ICM-WORKSPACE:NNN-slug -->` absent |
| `WORKTREE_MISSING` (v3.4.0) | critical | `.icm-main/` linked worktree removed or not created | `<project_root>/.icm-main/` absent |
| `WORKTREE_WRONG_BRANCH` (v3.4.0) | warning | worktree was manually switched to another branch | `git rev-parse --abbrev-ref HEAD` in `.icm-main/` ≠ `base_branch` |
| `WRONG_BRANCH_CHECKOUT` (v3.4.0) | warning | human opened session without activating workspace branch | `<project_root>` checked out at branch ≠ `workspace_branch` while status ≠ COMPLETED |
| `KICKOFF_WITHOUT_GATE` (v3.4.2) | warning | symptom of pre-v3.4.2 bug — session rendered kickoff without waiting for gate | `_kickoff.md` at `stages/<NN+1>/_kickoff.md` exists AND L1 declares `stage_atual=NN, status=COMPLETED_AWAITING_HUMAN, sub_stage=NN_completed` |
| `WAVE_WORKTREE_ORPHAN` (v3.4.3) | warning | symptom of pre-v3.4.3 bug — lead did not remove ephemeral worktrees after merge | `git worktree list` shows worktree(s) with branch pattern `wave-<NNN>-` (NNN=workspace num) already merged into base_branch |

## Actions per inconsistency

| Code | A (preserve) | B (rollback) | C (escalate) |
|---|---|---|---|
| `HASH_MISMATCH` | recompute hash + update L0/L1 | restore `_config/profile-effective.yaml` from last commit | mark `BLOCKED_ERROR` |
| `MISSING_OUTPUT` | append `recovery_warning` to history (preserves append-only) | rollback to `last_transition` before output disappeared | mark `BLOCKED_ERROR` |
| `STALE_IN_PROGRESS` | append `recovery_applied` to history + status `COMPLETED_AWAITING_HUMAN` | same as A | mark `BLOCKED_ERROR` |
| `MISSING_COMMIT` | rollback `last_transition` to the second-to-last valid entry in history | same as A | mark `BLOCKED_ERROR` |
| `BRANCH_MISSING` | append `recovery_warning` with suggestion `git reflog \| grep workspace/NNN` | same as A | mark `BLOCKED_ERROR` (manual) |
| `BOOTSTRAP_PARTIAL` | install hooks via `git-hook-installer.sh` + `context-check.sh` | rollback: `git reset --soft HEAD~1` and re-run bootstrap | mark `BLOCKED_ERROR` |
| `CLAUDE_MD_ROOT_STALE` / `CLAUDE_MD_ROOT_MISSING` | regenerate block from L1 (calls `handoff.update_project_claude_md`) | same as A | mark `BLOCKED_ERROR` |
| `WORKTREE_MISSING` (v3.4.0) | run `git worktree add .icm-main <base_branch>` | n/a (always A) | mark `BLOCKED_ERROR` |
| `WORKTREE_WRONG_BRANCH` (v3.4.0) | `cd .icm-main && git checkout <base_branch>` | n/a | mark `BLOCKED_ERROR` |
| `WRONG_BRANCH_CHECKOUT` (v3.4.0) | `git -C <project_root> checkout <workspace_branch>` | n/a | mark `BLOCKED_ERROR` |
| `KICKOFF_WITHOUT_GATE` (v3.4.2) | approve gate retroactively: transition L1 to `stage_atual=NN+1`, keep kickoff already generated | delete `_kickoff.md` + revert to `sub_stage=NN_in_progress` (workspace continues working on stage NN) | mark `BLOCKED_ERROR` |
| `WAVE_WORKTREE_ORPHAN` (v3.4.3) | auto-cleanup: `git worktree remove <path>` + `git branch -d <branch>` (safe because detection filtered by already-merged branch) | n/a (always A) | mark `BLOCKED_ERROR` |

**Multiple inconsistencies:** wizard groups by code and applies in batch in canonical order:

```
HASH → BOOTSTRAP_PARTIAL → MISSING_COMMIT → MISSING_OUTPUT → STALE → BRANCH_MISSING
```

Each apply appends to `history`:

```yaml
- at: "<now ISO 8601>"
  event: "recovery_applied"
  note: "wizard fix: <codes>"
  context:
    plan: "A"
    inconsistencies_found: ["HASH_MISMATCH", "STALE_IN_PROGRESS"]
```

## CLI

```bash
# Audit only (without modifying)
python <SKILL_DIR>/scripts/recovery-wizard.py --workspace <path> --dry-run

# Interactive: prints plan, reads stdin for A/B/C choice
python <SKILL_DIR>/scripts/recovery-wizard.py --workspace <path>

# Non-interactive: applies plan directly
python <SKILL_DIR>/scripts/recovery-wizard.py --workspace <path> --apply A
```

**Exit codes:**

- `0` — workspace consistent OR recovery applied successfully OR dry-run complete (even with inconsistencies).
- `1` — invalid workspace path OR recovery failed OR invalid choice (`--apply Q`).

## UX example (interactive)

```
$ python <SKILL_DIR>/scripts/recovery-wizard.py --workspace ~/projects/aura/workspaces/042-feat-auth

🔍 Workspace: 042-feat-auth
🔍 Inconsistencies detected: 2

  [warning] HASH_MISMATCH
    Message: profile_effective.yaml edited outside of bootstrap.
              hash in L0 (9f3a8b2c...) ≠ recomputed hash (7c4e1d09...).
    Action A: recompute hash + update L0/L1
    Action B: restore _config/profile-effective.yaml from last commit
    Action C: mark BLOCKED_ERROR + escalate to human

  [warning] STALE_IN_PROGRESS
    Message: status=IN_PROGRESS with no commit in workspaces/042-feat-auth/*
              in the last 24h (last: 2026-04-23T14:30:00Z).
    Action A: append recovery_applied + status=COMPLETED_AWAITING_HUMAN
    Action B: same as A
    Action C: mark BLOCKED_ERROR

Choose plan (A/B/C): A
✅ Applied plan A on 2 inconsistencies.
   - HASH_MISMATCH: hash updated in L0 (9f3a... → 7c4e...)
   - STALE_IN_PROGRESS: status=COMPLETED_AWAITING_HUMAN
   history append: recovery_applied (codes=[HASH_MISMATCH, STALE_IN_PROGRESS])

Next: review L1 and proceed, or open an issue if something looks wrong.
```

## Documented anti-patterns

### Reflog retention (R5.5)

`git reflog` retains references for ~90 days by default. Workspace branch deleted > 90 days ago = state permanently lost. **No built-in workaround.**

If human deleted `workspace/NNN-slug` but reflog still has it:

```bash
git reflog | grep workspace/NNN-slug
# found: a1b2c3d HEAD@{42}: branch: deleted workspace/042-feat-auth
git branch workspace/042-feat-auth a1b2c3d
```

Wizard does NOT do this automatically — risk of masking intentional loss. Suggests command, human executes.

### Do not bypass the pre-commit hook

Wizard always commits via normal flow. NEVER `git commit --no-verify`. If the hook blocks the recovery commit, wizard reports the error for the human to resolve — no bypass.

### Do not auto-recreate branch

`BRANCH_MISSING` plan A only suggests the reflog command. Auto-recreate could mask:
- Branch intentionally deleted because workspace is garbage.
- Reflog inconsistent across machines (push/clone loses local reflog).
- New branch created from the wrong sha (without understanding original history).

Human decides.

## `Inconsistency` response schema

```python
@dataclass(frozen=True)
class Inconsistency:
    code: str        # "HASH_MISMATCH" | "MISSING_OUTPUT" | "STALE_IN_PROGRESS"
                     # | "MISSING_COMMIT" | "BRANCH_MISSING" | "BOOTSTRAP_PARTIAL"
    message: str     # human-readable specific message
    proposed_action: str  # suggested action A in short prose
    severity: str    # "critical" | "warning"
    context: dict    # auxiliary fields: paths, shas, timestamps, etc.
```

## Integration with other components

| Component | How it interacts |
|---|---|
| `<SKILL_DIR>/scripts/validate-state.sh` | Pre-flight call. Failure → triggers wizard. |
| `<SKILL_DIR>/scripts/bootstrap.sh` | Detects existing workspace dir → invokes wizard before creating a new one. |
| Pre-commit hook | Wizard does NOT bypass. Recovery commits go through the normal hook. |
| L1 history | Wizard ALWAYS appends `recovery_applied` or `recovery_warning`. |
| `references/state-machine-schema.md` | Wizard respects canonical schema in any modification. |

## Edge cases

| Case | Behavior |
|---|---|
| Consistent workspace + `--dry-run` | exit 0 + "workspace consistent" |
| Consistent workspace + `--apply A` | silent no-op + exit 0 |
| Non-existent workspace path | exit 1 + message `workspace not found at <path>` |
| Malformed L1 yaml | exit 1 + specific message from `validate-state.sh` |
| Multiple inconsistencies + `--apply A` | applies all in batch canonical order |
| `--apply Q` (invalid choice) | exit code != 0 (argparse reject) |

## Tests

- Unit: `tests/unit/test_recovery_wizard.py` — 28 tests covering detect + apply + deterministic CLI
- E2E: `tests/e2e/recovery_orphan.bats` — fixture + apply + verify (CI-only)
- Fixture: `tests/fixtures/workspace_orphan/` — stale L1 + outputs + missing commit

Current coverage: 73% (B paths less exercised; accepted by design — human rarely chooses rollback).
