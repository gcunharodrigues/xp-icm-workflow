# `<project_root>/CLAUDE.md` — Canonical contract

> Canonical doc for the `CLAUDE.md` file at the project root, managed by the
> `xp-icm-workflow` skill. Covers: contract with `/init`, brownfield, multi-workspace,
> atomicity, recovery, versioning.

## Purpose

`<project_root>/CLAUDE.md` is the **external dashboard** of active ICM workspace state.
Claude Code loads this file automatically in any fresh session opened at the project root,
eliminating the need for manual copy/paste of KICKOFF prompts between sessions.

## Structure — two regions

```
# CLAUDE.md — <project_name>

This file provides guidance ...

<!-- ICM-START -->
## Active ICM Workspaces
<block per active workspace>
...
<!-- ICM-END -->

<free content — filled by /init or by the user>
```

- **ICM region** (between `<!-- ICM-START -->` and `<!-- ICM-END -->`) — exclusive
  to the skill. Bootstrap inserts; handoff updates; recovery wizard regenerates.
- **Codebase region** (outside the markers) — free. Bootstrap never touches it.
  Can be filled by a future `/init` or manually.

## When it is written

| Event | Function | Behavior |
|---|---|---|
| Bootstrap of new workspace | `bootstrap.py:_render_project_claude_md` | Adds block of new workspace to ICM region. Brownfield: preserves rest byte-for-byte. |
| Handoff on stage transition | `handoff.py:update_project_claude_md` | Updates only the block of the workspace owning the transition. Other blocks untouched. |
| Exit A (close), Exit C (spawn) | `handoff.py:remove_workspace_block` | Removes the block of the workspace that finished. If zero active workspaces remain, `deactivate_project_claude_md` replaces region with "none active" message **and migrates the CLAUDE.md root to the base branch via `.icm-main/`** (v3.4.1). **(v3.7.0)** stage 08 session also auto-invokes `Skill(skill: "init")` when CLI exit code = `2` (`--exit-2-if-last-active`). |
| Recovery wizard | `recovery-wizard.py` (Plan A) | Regenerates block from L1 when it detects `CLAUDE_MD_ROOT_STALE` or `CLAUDE_MD_ROOT_MISSING`. |

## Idempotent insertion algorithm (brownfield)

1. **File does not exist:** create from
   `templates/project_root/CLAUDE.md.tpl` with the complete ICM region.
2. **File exists WITH markers:** replace content only between
   `<!-- ICM-START -->` and `<!-- ICM-END -->`. Bytes outside the markers
   preserved intact.
3. **File exists WITHOUT markers (brownfield):** locate first `^# `
   (main title). Insert ICM region right after the title and its immediate blank lines.
   All other content preserved.

## Multi-workspace (G3)

More than one workspace may be active simultaneously
(`status != COMPLETED`). The ICM region lists one block per workspace. Order:
ascending by workspace ID.

Example:

```markdown
<!-- ICM-START -->
## Active ICM Workspaces

> ...

### Workspace `042-feat-auth` · profile=app_web_backend · tier=development
- Current stage: `03` (03_wave_planner) ...
- Read order: workspaces/042-feat-auth/CLAUDE.md → ...

---

### Workspace `043-payment-gateway` · profile=app_web_backend · tier=production
- Current stage: `06` (06_review) ...
- Read order: workspaces/043-payment-gateway/CLAUDE.md → ...

---

**Skill:** ... · **Recovery:** ...
<!-- ICM-END -->
```

## Stage 08 exits and CLAUDE.md root

| Exit | Function | Post-exit state |
|---|---|---|
| **A** (close) | `remove_workspace_block(workspace)` | Workspace block removed. If it was the last: ICM region replaced by "none active + run /init"; CLAUDE.md root is also copied to `.icm-main/CLAUDE.md` + committed to base branch (v3.4.1). **(v3.7.0)** stage 08 session auto-invokes `Skill(skill: "init")` in the SAME session when `remove-block --exit-2-if-last-active` returns exit `2` (was the last). Skipped if other active workspaces remain (`/init` prohibited during active workspace). |

### Owner transition on exit A (v3.4.1)

During the ICM cycle, `<project_root>/CLAUDE.md` lives in the **workspace branch**
(written by bootstrap/handoff). When the workspace branch is archived/deleted
after exit A, that CLAUDE.md would disappear without a trace in the base.

To ensure continuity, `deactivate_project_claude_md` (called when
zero active workspaces remain) does:

1. Rewrites `<project_root>/CLAUDE.md` with idle region (workspace branch tree).
2. Copies the same content to `<project_root>/.icm-main/CLAUDE.md` and commits
   to the base branch via worktree (`cd .icm-main && git commit ...`).

Result: idle dashboard persisted both in the workspace branch (will disappear
when branch deleted) and in the base branch (survives). Future sessions
at project_root opened on the base branch read the idle directly.

Idempotent: re-execution with same content generates no extra commit
(`git status` detects no-op).
| **B** (restart stage X, iteration++) | `update_project_claude_md(workspace, stage_target=X, iteration=N+1, ...)` | Block updated showing new stage and iteration. |
| **C** (spawn new workspace) | `remove_workspace_block(workspace)` in session A; bootstrap in session B adds new block | Block of owning workspace removed. Session B (separate) bootstraps new workspace and adds its block. **(v3.7.0)** stage 08 session (exit C) also auto-invokes `Skill(skill: "init")` when `remove-block --exit-2-if-last-active` returns exit `2` (was last active) — captures pre-pivot code snapshot. Skipped if other active workspaces. |

## Contract with `/init` (G4)

`/init` from Claude Code regenerates CLAUDE.md from the project code. **Does not
know about ICM markers by default.**

**Rule during active workspace:** **DO NOT invoke `/init`**. Explicit warning
is in the ICM region itself. Reason: `/init` may overwrite the ICM region,
breaking signaling.

**After Exit A of the last active workspace:** ICM region is replaced by
"none active + run /init" message. From that point, running `/init` is
safe — it will fill the codebase region with information from the built code.

**(v3.7.0) Auto-trigger `/init` in the stage 08 session itself:** when exit
A or C removes the last active workspace, the stage 08 session invokes
`Skill(skill: "init")` automatically before EXITING. Detection via
`handoff.py remove-block --exit-2-if-last-active` (exit code `2` = was
last). In multi-workspace with remaining active workspaces, exit `0` and `/init`
is NOT triggered. Exit B never triggers `/init` (workspace remains active).
See `templates/workspace/stages/08_feedback_intake/CONTEXT.md.tpl` exits A
and C step 6.

**Rule for `/init` skill-aware (future):** a future version of
`/init` may look for the markers and preserve them. Markers are
stable sentinels for any tool that wants to respect the region.

**Tier 3 (future work):** PreToolUse hook that blocks `/init` invocation
during active workspace. Out of scope for v3.1.0.

## Atomicity (G15)

All writes to `<project_root>/CLAUDE.md` use the write-tmp + fsync +
rename pattern:

```python
tmp = claude_md.with_suffix(".md.tmp")
tmp.write_text(content, encoding="utf-8")
fd = os.open(str(tmp), os.O_RDONLY)
os.fsync(fd)
os.close(fd)
tmp.replace(claude_md)
```

Crash mid-write does not corrupt the original file — `tmp.replace` is atomic on
POSIX and Windows (NTFS).

## Concurrency (G12)

Two sessions opened at the same project_root simultaneously may trigger
concurrent `handoff.py`. Mitigation:

- Workspace branch isolates: each session acts on its workspace branch.
- Git atomic commit prevents simultaneous write to the same file.
- In case of conflict, second write fails with git error → session aborts with
  `BLOCKED_ERROR`.
- Recovery wizard (`CLAUDE_MD_ROOT_STALE`) detects and regenerates.

## Versioning (G13)

`CLAUDE.md` at the project root is versioned on the **workspace branch** (not on
main) during each workspace's cycle. The whitelist in
`templates/.git-hooks/pre-commit` allows the file (R3.3 expanded in G6).

After Exit A, options for preserving `CLAUDE.md` in main:

1. Merge workspace branch → main (preserves current CLAUDE.md).
2. Run `/init` on main to regenerate the codebase region from the current code
   (the ICM region will already be empty — "none active").

The divergence between workspace branch (updated CLAUDE.md) and main (outdated
or absent CLAUDE.md) is **intentional** and safe — workspace branch is
an ephemeral state layer by ICM design.

## Encoding (G11)

The ICM region generated by the skill is in **en-US** (consistent with the rest of the
skill as of v3.11.0). The codebase region outside the markers is free — any language. No forced mixing.

## Recovery (G5)

Inconsistencies between L1 and CLAUDE.md root are detected by the recovery wizard:

- `CLAUDE_MD_ROOT_STALE` — `<project_root>/CLAUDE.md` shows `stage_atual`
  different from `L1.stage_atual` for some active workspace. Typical cause:
  session crash without calling handoff.
- `CLAUDE_MD_ROOT_MISSING` — workspace has `L1.status=IN_PROGRESS` but does not
  appear as a block in the ICM region of CLAUDE.md root.

Recovery (Plan A): regenerate the full ICM region from `.index.md` +
L1 of all active workspaces.

## Templating (G17)

The template `templates/project_root/CLAUDE.md.tpl` is used **only by the
initial bootstrap** when the file does not exist. Subsequent updates (handoff,
recovery) write markdown directly via helper functions, without using `{{}}`
placeholders. This avoids confusion between bootstrap templating and runtime
regeneration.
