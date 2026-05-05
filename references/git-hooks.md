# Git hooks — pre-commit + commit-msg (xp-icm-workflow)

Two POSIX bash hooks that enforce isolation between the ICM workspace and the parent project's src. Distributed as templates in `templates/.git-hooks/{pre-commit,commit-msg}`. Installed together by `scripts/git-hook-installer.sh` (Wave 2) or by `bootstrap.py` (`_install_hooks`).

## Why 2 hooks (canonical split)

Git stages separate responsibilities by timing:

| Stage | When it runs | What it sees | What it validates (skill) |
|---|---|---|---|
| `pre-commit` | BEFORE `COMMIT_EDITMSG` is persisted | Staged files only | File checks + L1<->outputs atomicity |
| `commit-msg` | AFTER user provides msg, receives path in `$1` | Current message in the file | Message prefix |

**Bug v1 (fixed):** the initial version concentrated everything in `pre-commit`, including reading `.git/COMMIT_EDITMSG` to validate the prefix. But `pre-commit` runs BEFORE git writes the current message to the file — so it was validating the PREVIOUS commit's message (or empty on the first). Temporary workaround was to install the hook after bootstrap commits, but that only protected bootstrap; future user commits kept validating a stale message. Fix: split into 2 canonical stages.

**Anti-pattern:** NEVER read `COMMIT_EDITMSG` in `pre-commit`. If you need to validate the message, use `commit-msg` which receives the path in `$1`.

## SessionStart hook — `icm-session-check.sh` (v3.4.0)

Non-git hook that runs 1× when Claude Code opens a session in `<project_root>`. Validates the cross-branch runtime state of the model:

1. **Current branch** = active workspace branch (extracted from `workspaces/.index.md`).
2. **`.icm-main/` worktree** exists.
3. **`.icm-main/`** is checked out at `base_branch` (read from L1 `CONTEXT.md`).

Prints warning to stdout (visible in chat) if something is wrong. **Does not block** session start — only signals the human to fix before continuing.

**Installation:**
- Script copied by bootstrap to `workspaces/<NNN-slug>/.claude/hooks/icm-session-check.sh`.
- Registration goes in `<project_root>/.claude/settings.local.json` (gitignored). Bootstrap renders `.example` at project root for human to copy:

```bash
cp .claude/settings.local.json.example .claude/settings.local.json
```

**Doc:** `references/worktree-model.md`.

## Pre-commit — file checks

### R1 — Skip during rebase/merge

If `.git/rebase-merge/` or `.git/rebase-apply/` exists -> `exit 0`. Reason: during rebase, git touches historical commits that already passed through the hook; revalidating breaks the lead's automatic rebase in stage 04.

### R2 — Non-workspace branch passes freely

Regex: `^workspace/[0-9]{3}-`. If current branch does not match -> `exit 0`. Work in `main`, `feat/*`, `wave-NNN-N/*` is not affected.

### R3 — Reject src edits (tightened whitelist in v3.4.0)

On a workspace branch, every staged file must be in:

- `workspaces/NNN-slug/...` (workspace scope), OR
- `workspaces/.index.md` (registry of active/completed workspaces), OR
- `.gitignore` (ignore updates by bootstrap), OR
- `CLAUDE.md` (ICM dashboard at project root — written by handoff/bootstrap).

**Removed from whitelist in v3.4.0:** `docs/decisions/*.md`, `docs/lessons.md`,
`docs/tech_debt.md`. These paths now live ONLY in the base branch and are
modified via the linked `.icm-main/` worktree (`cd .icm-main && git commit`).
Canonical doc: `references/worktree-model.md`.

Other paths (`src/`, `tests/`, root, `docs/*`) -> reject:

```
ERROR: branch workspace/NNN-slug may only touch workspaces/NNN-slug/* or whitelisted files.
Offending file: <path>
To touch src/, docs/decisions/, docs/lessons.md, docs/tech_debt.md
or other base branch paths, use the linked worktree:
  cd .icm-main && git add <path> && git commit ...
```

### R3.5 — Reject `.icm-main/*` paths (v3.4.0)

`.icm-main/` is the linked worktree of the base branch and must be in
`.gitignore`. If any staged file matches `.icm-main/*`, hook rejects
immediately:

```
ERROR: file '.icm-main/<path>' is in .icm-main/ — directory reserved for the linked worktree of the base branch.
Worktree paths must NOT be tracked by the workspace branch.
```

Reason: commits to `.icm-main/` contents must happen INSIDE the
worktree (`cd .icm-main && git commit ...`), never via the workspace branch.

**Valid:** `workspaces/042-feat-auth/CONTEXT.md`, `workspaces/042-feat-auth/stages/02/output/plan.md`, `CLAUDE.md`

**Invalid:** `src/auth/middleware.py`, `docs/decisions/0042.md` (use `.icm-main/`), `.icm-main/docs/foo.md` (use `cd .icm-main && commit`)

### R4 — L1<->outputs atomicity

If any staged file matches `workspaces/NNN-slug/stages/<NN>/output/...` AND `workspaces/NNN-slug/CONTEXT.md` is NOT staged -> reject:

```
ERROR: stage <NN> outputs staged without updating CONTEXT.md.
L1<->outputs atomicity required.
```

Reason: each new output needs a trace in `history` and `last_transition` of the root CONTEXT.md. Output without state = future sessions cannot resume correctly.

## Commit-msg — message validation

### R5 — Skip in trivial cases

- `$1` absent or file does not exist -> `exit 0`.
- Non-workspace branch -> `exit 0`.
- Rebase/merge in progress -> `exit 0`.

### R6 — Message prefix (R2.3)

Line 1 of the message (ignoring `#` comment lines from git) must match:

```
^workspace [0-9]{3}: 
```

Valid example: `workspace 042: discovery complete`.

Invalid example: `feat: add auth` -> reject with suggested rewrite.

### R7 — ADR exception (R5.4)

If any staged file matches `docs/decisions/*.md` AND the message contains the literal substring `(workspace NNN ` (parenthesis + number + space), accept even without R6 prefix.

Reason: ADRs sometimes originate in another context and are refined in a workspace; the `(workspace NNN ...)` marker in the body is sufficient for traceability.

**Valid:** `docs(adr): record decision (workspace 042 design)`

**Invalid:** `docs(adr): record decision` (neither prefix nor marker).

### R7.5 — intake/feedback prefixes for stage 08 (R5.5)

Commit messages in stage 08 may use prefixes `intake:` or `feedback:` as an alternative to the `workspace NNN:` prefix. These prefixes are specific to the feedback intake stage where the workspace is already in a terminal stage and the context is different from prior stages.

**Valid:** `intake: stage 08 feedback collected`, `feedback: close workspace`

**Invalid:** `intake:` without message (empty after colon).

## Exact regex patterns (R6.4)

| Rule | Regex / Glob | Hook |
|---|---|---|
| Workspace branch | `^workspace/[0-9]{3}-` | both |
| Workspace ID extraction | `${branch#workspace/}` split at first `-` | both |
| Message prefix | `^workspace [0-9]{3}: ` | commit-msg |
| Intake/feedback prefix (stage 08) | `^(intake\|feedback): ` | commit-msg |
| ADR file glob | `docs/decisions/*.md` | both |
| Lessons file | `docs/lessons.md` | pre-commit |
| Tech debt file | `docs/tech_debt.md` | pre-commit |
| ADR message marker | literal substring `(workspace NNN ` | commit-msg |
| Stage output glob | `workspaces/<NNN-slug>/stages/<NN>/output/*` | pre-commit |
| Workspace index | `workspaces/.index.md` | pre-commit |
| Gitignore | `.gitignore` | pre-commit |
| Rebase markers | `.git/rebase-merge/` or `.git/rebase-apply/` | both |
| Wave branch detect | `^wave-[0-9]+-[0-9]+/` | commit-msg |
| Conventional Commit types | `^(feat\|fix\|refactor\|test\|docs\|chore\|perf\|ci\|build\|style\|revert)(\(.+\))?: .+` | commit-msg (R8 warning) |
| Comment lines (msg) | `^#` | commit-msg (strip before parse) |

## How to install

`scripts/git-hook-installer.sh <project_root>` installs BOTH hooks idempotently:

```bash
bash scripts/git-hook-installer.sh /path/to/project
```

Behavior per hook:
- Absent: copies template, `chmod +x`.
- Present + identical: no-op.
- Present + different: backup `.bak.<UTC-ts>`, overwrite, `chmod +x`.

`bootstrap.py::_install_hooks(project_root, skill_root)` does the same via Python (called by `bootstrap.sh`/`bootstrap.py` at the end of bootstrap).

Manual:

```bash
cp <skill-root>/templates/.git-hooks/pre-commit .git/hooks/pre-commit
cp <skill-root>/templates/.git-hooks/commit-msg .git/hooks/commit-msg
chmod +x .git/hooks/pre-commit .git/hooks/commit-msg
```

## Wave branches (`wave-NNN-N/<task-slug>`)

### R8 — Wave branch Conventional Commit warning

Wave branches receive a **warning** (not a block) via commit-msg hook R8 if the message does not follow Conventional Commits:

```
WARNING: wave branch detected without Conventional Commit.
Recommendation: use format "<type>: <description>" (feat, fix, test, etc).
```

Regex: `^(feat|fix|refactor|test|docs|chore|perf|ci|build|style|revert)(\(.+\))?: .+`

Commits on wave branches use **standard Conventional Commits** without the ICM prefix:

- Format: `<type>: <description>`
- Types: `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`, `perf:`, `ci:`
- Examples: `feat: add JWT validation`, `test: unit tests for auth middleware`

ICM hooks pass freely on wave branches (R2/R5: branch does not match workspace pattern = exit 0). This is intentional — wave branches are code scope, not state files. CI gate (lint, type-check, tests) replaces hook enforcement.

**Anti-pattern:** Do NOT commit state files (CONTEXT.md, _kickoff.md) on wave branches. State files belong on the workspace branch.

## Bypass via `--no-verify` and anti-pattern

`git commit --no-verify` skips BOTH hooks. **Do not use.** Reasons:

- Breaks L1<->outputs atomicity -> future sessions cannot resume.
- Allows src edits to leak into workspace branches -> messy history.
- Messages without prefix -> traceability lost.

If the hook rejects something you believe is legitimate:

1. Read the full error message — it suggests a specific fix.
2. If you believe it is a hook bug, open an issue instead of bypassing.
3. ADRs + cross-cutting commits have the documented R7 exception above.

## Documented exceptions

| Scenario | Behavior |
|---|---|
| Branches not matching `^workspace/NNN-` | Both hooks no-op |
| Rebase in progress | Both hooks no-op |
| ADR (`docs/decisions/*.md`) | Allowed on workspace branch (pre-commit R3) |
| ADR + msg with `(workspace NNN ` | Accepted without R6 prefix (commit-msg R7) |
| `commit-msg` called without `$1` | exit 0 (let git handle) |

## Tests

- `tests/integration/test_git_hooks.bats` — pre-commit (file checks). Covers R1-R4.
- `tests/integration/test_commit_msg_hook.bats` — commit-msg (message validation). Covers R5-R7 + regression of bug v1 (CURRENT msg via `$1`, not stale from prior commit).

CI-only via Ubuntu runner; bats does not run on local Windows. Wave 6 configures GitHub Actions with badge.

## Changelog

| Version | Change |
|---|---|
| v1 (Wave 2 initial) | Single `pre-commit` hook with file checks + message validation. **Bug:** message validation used `.git/COMMIT_EDITMSG` which pre-commit reads as stale (prior commit's message). Temporary workaround: install hook after bootstrap commits. |
| v2 (Wave 2 fix) | Split into `pre-commit` (file checks) + `commit-msg` (message validation). `commit-msg` receives path in `$1` with current message, correct validation. Regression test in `test_commit_msg_hook.bats`. |
| v3.4.0 | Pre-commit whitelist tightened: removed `docs/decisions/*.md`, `docs/lessons.md`, `docs/tech_debt.md` (go via `.icm-main/` worktree). Added R3.5 rejects `.icm-main/*` paths. New SessionStart hook `icm-session-check.sh` validates branch + worktree on session open. |
