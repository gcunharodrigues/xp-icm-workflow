# Isolation Protocol — Canonical (v4.0.x)

> **Version:** v4.0.x
> **Skill:** `xp-icm-workflow`
> **Purpose:** Single canonical source for subagent isolation rules in stage 04. Single path — all subagents use manual worktrees.

## Summary

Subagents in stage 04 run in isolated worktrees at `.claude/worktrees/icm-wave-<NNN>-<N>-<slug>/` on branch `wave-<NNN>-<N>-<slug>`. The project root stays on `workspace/<NNN-slug>` for the entire wave — never switches to `main` during stage 04. Merge happens via `.icm-main/` (linked worktree on `main`), keeping the project root untouched.

## Why isolation is mandatory

A subagent at project root that runs `git checkout <wave-branch>` switches the project root's working tree. This destroys:
- `workspaces/` directory (only exists on `workspace/<NNN-slug>`)
- L0, L1, L2, plan.md, wave-plan.md — GONE from working tree
- Parallel subagents race on branch checkout — each checkout wipes the previous subagent's branch

Isolation is not optional.

## Single isolation path

All subagents follow the same procedure. No topology detection needed.

### Lead steps (for each task)

1. Create branch from main:
   ```bash
   git branch wave-<NNN>-<N>/<slug> main
   ```

2. Create manual worktree:
   ```bash
   mkdir -p .claude/worktrees
   git worktree add .claude/worktrees/icm-wave-<NNN>-<N>-<slug> wave-<NNN>-<N>/<slug>
   ```
   `.claude/` is gitignored by ICM bootstrap. Worktree path is deterministic.

3. Spawn subagent:
   ```python
   Agent(
       isolation=None,
       cwd="<project_root>/.claude/worktrees/icm-wave-<NNN>-<N>-<slug>",
       subagent_type="general-purpose",
       model=<writer_model>,
       description="wave <N> task <slug>",
       prompt=<AGENT-BRIEF + channel-2>,
   )
   ```
   The manual worktree IS the isolation.

## Branch verification (subagent startup — mandatory)

Subagent executes GATE 1 first, before any Write/Edit/Bash:

```
1. git branch --show-current
   Must show: wave-<NNN>-<N>/<slug>
2. git status --short → must be clean
3. If wrong → STOP, report Status: BLOCKED
```

Subagent NEVER runs `git checkout`, `git switch`, `git rebase`, or `git push`. Branch is pre-created by lead.

## Merge via .icm-main/ — project root never switches

After all tasks in the wave are approved, lead merges via `.icm-main/`:

```bash
cd .icm-main
git merge --no-ff wave-<NNN>-<N>/<slug>
# CI runs from .icm-main/
cd ..
```

Project root never leaves `workspace/<NNN-slug>`. No stash dance. No buffer. L1 updates intact.

Repeat for each task in plan order. Skip VOIDed tasks.

## Reviewer/critic isolation

Wave-reviewer and L3 critic use the project root (on `workspace/<NNN-slug>`). They are READ-ONLY — `git show`/`git diff` only. NEVER write code.

## Anti-patterns

| # | Anti-pattern | Consequence |
|---|-------------|-------------|
| 1 | `Agent(isolation=None)` at project root for code tasks | `workspaces/` destroyed on disk |
| 2 | Subagent runs `git checkout` or `git checkout -b` | Branch already exists; checkout may switch away from correct branch |
| 3 | Subagent writes to `{{PROJECT_ROOT}}` via absolute paths | Corrupts state files (L0/L1/L2) on workspace branch |
| 4 | Subagent writes to `.icm-main/` | Corrupts base-branch linked worktree |
| 5 | Merging from project root (switching off workspace branch) | Stash complexity, risk of L1 update loss |

## Cleanup

After merge + CI green, lead removes worktrees and deletes merged branches:

```bash
git worktree remove .claude/worktrees/icm-wave-<NNN>-<N>-<slug>
git branch -d wave-<NNN>-<N>/<slug>
```

Paths are deterministic — always known. No capture of Agent tool return values needed.

## If worktree creation fails

`status: BLOCKED, block_reason: error`. Diagnose root cause. Never proceed without isolation.

## Cross-references

- Wave execution pipeline: `references/wave-execution-protocol.md`
- Subagent spawn protocol: `references/subagent-protocol.md`
- AGENT-BRIEF template: `references/agent-brief-template.md`
- L2 runtime instructions: `templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl`
- Pre-flight script: `scripts/wave-preflight.py`
