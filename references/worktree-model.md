# Worktree Model — Option B (canonical v3.4.0)

> **Version:** v3.4.0
> **Skill:** `xp-icm-workflow`
> **Replaces:** implicit cross-branch model from v3.3.x

## Problem (v3.3.x)

Workspace branch (`workspace/NNN-slug`) does not have `docs/`, `src/`, `tests/`
in the working tree (those paths only live in `base_branch`). But:

- L0 declares absolute paths `<project_root>/docs/decisions/...` as
  source of truth.
- L2 of stage 02 lists `docs/decisions/` as Input.
- Read tool reads from the current working tree filesystem = workspace branch tree.
- Result: `Read docs/decisions/0001.md` in a stage 02 session returns
  ENOENT even if the file exists in main.

Fragile workarounds:
- `git show main:docs/decisions/0001.md` via Bash (verbose, not cacheable).
- `git checkout main -- docs/decisions/` (leaves untracked, conflicts with
  pre-commit hook).
- Stash/checkout/commit/checkout/pop to create ADRs in main mid-stage.

## Canonical model v3.4.0 — `.icm-main/` parallel worktree

Bootstrap creates a linked worktree of `<BASE_BRANCH>` at
`<project_root>/.icm-main/`. Always present, always checked out on the base
branch, always available for both read **and** write cross-branch.

```
<project_root>/                       # main worktree (workspace branch during ICM cycle)
├── .git/                             # repo (shared between worktrees)
├── .gitignore                        # contains .icm-main/
├── CLAUDE.md                         # workspace branch tree
├── workspaces/                       # workspace branch tree
│   ├── .index.md
│   └── 001-.../
└── .icm-main/                        # linked worktree → base_branch (gitignored)
    ├── .git                          # file (not dir) pointing to repo
    ├── docs/
    │   ├── decisions/
    │   ├── lessons.md
    │   └── tech_debt.md
    ├── src/
    ├── tests/
    └── ...
```

Worktree is a **real filesystem**: Read tool works; Edit/Write works;
git status/add/commit inside `.icm-main/` are commits on base_branch.

## Canonical commands

| Operation | Command |
|---|---|
| Setup (bootstrap) | `git worktree add .icm-main <BASE_BRANCH>` |
| List worktrees | `git worktree list` |
| Update `.icm-main` (pull new main) | `cd .icm-main && git pull --ff-only` |
| Create ADR | `Write .icm-main/docs/decisions/NNNN-slug.md` |
| Commit ADR | `cd .icm-main && git add docs/decisions/NNNN-*.md && git commit -m "docs(decisions): ..."` |
| Read ADR | `Read .icm-main/docs/decisions/NNNN-slug.md` |
| Read existing code (stage 04+) | `Read .icm-main/src/...` |
| Remove (cleanup, very rare) | `git worktree remove .icm-main` |

## Usage rules

### 1. Worktree is conceptually READ-ONLY from workspace branch

Sessions on the workspace branch (stages 00–08) operate in `<project_root>`
checkout (workspace branch). To touch base branch files
(ADRs, lessons, tech_debt), agent MUST use `.icm-main/`:

- Editing `<project_root>/docs/decisions/...` directly **fails**: pre-commit
  hook rejects workspace branch touching paths outside `workspaces/`.
- Editing `<project_root>/.icm-main/docs/decisions/...` **works**: it is
  the base branch area, not the workspace.

### 2. Stage 02 design — canonical ADRs via `.icm-main/`

Process step 6 of L2 stage 02 instructs:

```
Spawn new ADR:
  1. Write .icm-main/docs/decisions/NNNN-<slug>.md (canonical format)
  2. cd .icm-main
  3. git add docs/decisions/NNNN-*.md
  4. git commit -m "docs(decisions): <slug> (workspace <NNN>)"
  5. cd <project_root>
  6. plan.md cites filename (not inline)
```

Output of step 4 gives SHA of commit on base_branch. plan.md may
reference `(commit <SHA>)` if useful.

### 3. Stage 04 implementation_waves — code via subagent worktrees

Lead stays on workspace branch (in `<project_root>`). Subagents via
Agent tool MUST use `isolation: "worktree"` (native tool parameter):

- Tool creates ephemeral worktree `<project_root>/.icm-wave-001-N-<task>/`
  (or similar) checked out on `wave-NNN-N/<task-slug>` derived from
  base_branch.
- Subagent works there: read existing code in `.` (own worktree),
  read ADRs in `../.icm-main/docs/decisions/` (stage 04 brief includes
  relative paths — `agent-brief-render.py` resolves).
- At subagent end, branch pushed; lead merges in base_branch via
  stage 04 protocol.

Tool with `isolation: worktree` auto-cleanup if subagent modifies nothing;
branch + path returned if it modified.

**Mandatory cleanup post-merge (v3.4.3):** subagent in stage 04 ALWAYS
modifies (TDD writes tests + impl), so Agent tool never auto-cleans up
wave worktree. Lead MUST execute explicit cleanup after sequential merge
+ CI green, before writing wave-summary.md:

```bash
# For each wave task:
git worktree remove <path-returned-by-Agent-tool>
git branch -d wave-<NNN>-<N>/<task-slug>     # safe if already merged --no-ff

# Fallback if worktree path was lost — search by pattern:
git worktree list --porcelain \
  | awk '/^worktree /{p=$2} /^branch refs\/heads\/wave-<NNN>-<N>/{print p}' \
  | xargs -I {} git worktree remove {}
```

Non-fatal failure: record warning in `wave-summary.md`. `git branch -d`
refuses un-merged branch (intentional — not using `-D` would mask bugs).
New Recovery Wizard type `WAVE_WORKTREE_ORPHAN` (v3.4.3) detects +
auto-cleans buggy workspaces pre-v3.4.3 where cleanup never ran.

### 4. Read code from prior iteration — stage 00 + 04+ cases

Stage 00 recon needs to scan active ADRs + lessons + current tech_debt.
Worktree ensures visibility:

- Stage 00 reads `.icm-main/docs/decisions/*.md` for ADR list.
- Stage 04 subagent in wave branch reads its own working tree (already has
  `src/`, `docs/`).

### 5. CLAUDE.md root — exception

`<project_root>/CLAUDE.md` is the external state dashboard, maintained by
`handoff.update_project_claude_md`. Lives in the workspace branch during
the active ICM cycle. Workspace exit A migrates to base_branch (see
`session-handoff-protocol.md`).

Does not go in `.icm-main/CLAUDE.md` — that file never exists in the base
branch while a workspace is active.

### 6. Synchronizing `.icm-main/` when waves merge

After stage 07 merges the wave branch into base_branch:

```
cd .icm-main
git pull --ff-only origin <BASE_BRANCH>   # or git fetch + git merge --ff-only
```

Stage 07 lead executes this command right after the merge so that
subsequent stages (08 or another workspace) see updated code in `.icm-main/`.

Recovery wizard validates fast-forwardability as a health check.

### 7. Multi-workspace coexistence

If 2+ workspaces are active at the same project_root (e.g., `001-feat-a` +
`002-feat-b` in parallel), `.icm-main/` is shared between both.
Each workspace has its own working tree in `<project_root>` but
switching between them requires `git checkout workspace/<other>` which forces
a change in the `<project_root>` checkout — `.icm-main/` remains untouched.

## Verifiable setup (bootstrap)

`scripts/bootstrap.py` step `_setup_main_worktree(project_root, base_branch)`:

```python
def _setup_main_worktree(project_root: Path, base_branch: str) -> None:
    worktree_path = project_root / ".icm-main"
    if worktree_path.exists():
        return  # idempotent
    _run_git(
        ["worktree", "add", str(worktree_path), base_branch],
        cwd=project_root,
    )
```

Idempotent: runs once at bootstrap; subsequent calls are no-ops.

`.gitignore` at project_root gains entry `.icm-main/`. Applied to all
branches via:

- main branch: versioned gitignore lists `.icm-main/`.
- workspace branch: same list (workspaces inherit .gitignore via merge
  at bootstrap).

## Common failures + recovery

### `.icm-main/` absent

Symptom: `Read .icm-main/docs/decisions/...` returns ENOENT.

Cause: old bootstrap (pre-v3.4.0) or worktree manually removed.

Recovery: `git worktree add .icm-main <BASE_BRANCH>`. Recovery wizard
detects + suggests command.

### Corrupted worktree (`.icm-main/.git` broken)

Symptom: git commands in `.icm-main/` fail.

Recovery: `git worktree repair` or `git worktree remove .icm-main --force` +
recreate.

### Wrong branch in `.icm-main/`

Symptom: `cd .icm-main && git branch --show-current` returns `wave-...`
instead of `<BASE_BRANCH>`.

Cause: subagent checked out wrong branch inside the worktree.

Recovery: `cd .icm-main && git checkout <BASE_BRANCH>`. Recovery wizard
detects + suggests command.

### Workspace branch has orphan `docs/`, `src/`

Symptom: old workspaces (pre-v3.4.0) had `docs/lessons.md`,
`docs/tech_debt.md` in the workspace branch tree.

Cause: old bootstrap created those paths in the workspace branch.

Recovery: migration script (in `scripts/migrate-v3.3-to-v3.4.py` —
NotImplemented; document as manual) removes those paths from the workspace
branch and copies content to base_branch (`.icm-main/`).

## Why not other options

| Option | Pro | Con |
|---|---|---|
| **A** — only on main, agent reads via `git show main:` | no extra disk; no worktree | verbose; does not cache well; hard for Read tool; fragmented SessionStart-side hooks |
| **B** — `.icm-main/` parallel worktree (chosen) | Read/Write/Bash work directly; cross-branch commits trivially atomic; multi-workspace sharing | duplicates project disk; bootstrap needs to create |
| **C** — single-branch (workspace + code coexist) | no cross-branch | loses isolation; atomicity hooks hard; exit A becomes a giant squash merge |
| **D** — copy-on-session via SessionStart hook | no visible worktree | machine-specific hook setup; no write-back atomicity; complex gitignore |

Option B wins because: (1) zero path ambiguity; (2) existing tools (`Read`, `Edit`, `Write`, `Bash`) work without change;
(3) cross-branch commits via `cd .icm-main && git commit` are ZERO-FRAGILE
(a single transaction per commit, not 2 commits + stash).

## Backward compatibility

Workspaces created in v3.3.x without `.icm-main/`:

1. Manual migration: `cd <project_root> && git worktree add .icm-main <BASE_BRANCH>`.
2. Add `.icm-main/` to `.gitignore` in workspace branch + commit (workspace branch).
3. Add `.icm-main/` to `.gitignore` in base_branch + commit (via worktree).
4. Old workspace L0 remains with v3.3.x paths; v3.4.0 agent understands both formats via fallback documented in recovery-wizard.

## Cross-references

- `templates/workspace/CLAUDE.md.tpl` — L0 template with `.icm-main/` paths.
- `templates/workspace/stages/02_design/CONTEXT.md.tpl` — process step 6 updated.
- `templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl` — subagent worktree usage.
- `templates/.git-hooks/pre-commit` — whitelist tightened (no docs/decisions/lessons/tech_debt).
- `scripts/bootstrap.py` — `_setup_main_worktree` step.
- `scripts/recovery-wizard.py` — branch + worktree validation.
- `references/git-hooks.md` — pre-commit + commit-msg + optional SessionStart.
- `references/changelog.md` — entry v3.4.0.
