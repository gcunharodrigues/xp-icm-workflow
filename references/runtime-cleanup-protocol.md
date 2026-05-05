# Runtime Cleanup Protocol — v3.7.0

> Canonical protocol for runtime side-effect cleanup BEFORE the stage 08 exit
> transition (A close, B restart, C spawn). Strict universal — all tiers go
> through the checklist without opt-out. Detector + human decision, NEVER
> automatic destructive action.

---

## Why it exists

Pre-v3.7.0, orphaned side-effects were a recurring problem: dev servers kept
running after a workspace was closed, `wave-NNN-*` branches remained orphaned,
Docker containers were left hanging, `.icm-main/` became dirty between
transitions. Recovery wizard v3.6.0 introduced `DEV_SERVER_ORPHAN` +
`CDP_DISCONNECTED` but these were detect-after-fact (the next session would
find the inconsistent state, not pre-transition).

v3.7.0 closes the gap: stage 08 exit A/B/C **blocks** transition until
the runtime checklist is confirmed clean (or human explicitly skips via stop
point #13 with documented consequences).

---

## Principles

1. **Skill detects, human decides.** ICM never kills a process, deletes a
   branch, or forces cleanup automatically. Every destructive action requires
   an explicit human decision per category.

2. **Strict universal.** Applicable in all tiers (`experimental` →
   `production`). No opt-out by tier — unlike TDD (calibrated by tier).

3. **Per-category, not global.** Human confirms each category separately
   (not 1 confirm "all clean?"). Reduces the risk of accidentally skipping
   a category that was missed.

4. **Idempotent.** Re-running the checklist = same result. Resolved items
   do not return to the list.

5. **Status reported in intake-report.md.** Section §"Runtime cleanup
   pre-exit (v3.7+)" records the final snapshot + human decisions (explicit
   skip vs resolved).

---

## 6 canonical categories

| # | Category | Detector | Default cleanup | Human override |
|---|---|---|---|---|
| 1 | `dev_servers` | runtime-registry kind=dev_server alive | `kill <pid>` + unregister | skip = warning, deferred |
| 2 | `background_tasks` | kind=background_task alive | same | same |
| 3 | `docker` | `docker ps --filter label=icm-workspace=NNN` | `docker stop <id>` (human runs) | skip = warning |
| 4 | `wave_branches` | `git branch --list wave-NNN-*` | `git branch -D <branch>` (human runs) | skip = historical leftover |
| 5 | `working_tree` | `git status --short` at project_root | human commits or stashes | skip = not allowed |
| 6 | `untracked` | `.icm-main/` dirty + ls-files --others | human commits or ignores | skip = warning |

**Category 5 (working_tree) is special:** dirt in the workspace branch working
tree causes confusion pre-merge stage 07 (already resolved) or indicates
untracked edits. Skip is not allowed — human MUST commit/stash before
closing stage 08.

---

## Canonical flow

### Stage 08 entry hook

```
[stage 08, sub_stage=08_in_progress, status=COMPLETED_AWAITING_HUMAN]

  Session synthesizes checklist:
  python <skill>/scripts/runtime-status.py \
      --workspace-root <ws> --project-root <pr> --format text

  Example output:
  ✓ dev_servers: no dev servers
  ✗ background_tasks: 1 background task(s) alive
  ✓ docker: no containers
  ✗ wave_branches: 2 wave branch(es) orphaned
  ✓ working_tree: clean
  ✗ untracked: .icm-main dirty: 3 entry(ies)

  Per non-clean category:
    Prints details (PIDs, branches, paths).
    Awaits human: "[s] resolved [n] cancel stage 08 [edit] describe".

  Re-run until all clean OR human cancels (stop point #13).
```

### Per-OS quirks

**Windows:**
- Kill process: `taskkill /PID <pid> /F`
- Process status: ctypes `OpenProcess` + `GetExitCodeProcess`
- Docker Desktop: requires running service; daemon down = "assumed clean".

**POSIX (Linux/macOS):**
- Kill process: `kill <pid>` (SIGTERM) or `kill -9 <pid>` (SIGKILL)
- Process status: `os.kill(pid, 0)` (sends no signal)
- Docker: `docker ps` requires daemon running; `docker stop --time 10`
  graceful shutdown.

`runtime-registry.py:_is_pid_alive` covers both OSes via lazy detection.

---

## Recovery if cleanup fails mid-exit

Scenarios and plan:

| Failure | Plan |
|---|---|
| `kill <pid>` returns permission error | suggest `kill -9` or human runs as root |
| Branch protected (push restriction) | suggest `git config branch.<name>.allowDeletion true` |
| Docker daemon down | warning "assumed clean", annotate in intake-report |
| Command timeout (>30s) | retry 1x, then mark as skip + warning |
| Human closes terminal mid-checklist | sub_stage stays `08_in_progress`; next session re-runs checklist (idempotent) |

Technical failures vs human cancellation:
- **Technical failure** (command errored) → Plan A retry, then stop point #13
- **Human cancellation** (answers [n]) → stop point #13 immediately
  + status `BLOCKED_STOP_POINT`

Stop point #13 A/B/C menu:
- `[a]` resolved manually, resume checklist
- `[b]` skip category + proceed with exit (workspace becomes inconsistent;
       recovery wizard detects later)
- `[c]` cancel stage 08 (status reverts to `COMPLETED_AWAITING_HUMAN`)

---

## Integration with runtime-registry

Categories 1-2 (dev_servers, background_tasks) consult
`workspaces/<NNN>/_state/runtime-registry.json`. Entries with a dead PID
do NOT mark the category as dirty (stale registry, no active side-effect) —
but generate an entry for registry cleanup via
`runtime-registry.py purge-dead`.

Migration v3.6.0 → v3.7.0: old workspaces with `.icm-main/.dev-server.pid`
should run `migrate-workspace.py --workspace-root <ws>` before the first
checklist (moves PID file → registry, idempotent).

---

## Override in tier=experimental?

**No.** Design decision (v3.7.0): strict universal applied to all tiers,
including `experimental`. Rationale:

- Experimental = POC/spike, but orphaned processes cost memory + port
  conflicts on the next bootstrap.
- Checklist friction is low: 6 categories, typically <30s human time.
- Tier-based override would open a complex precedent (which tiers? which
  categories?). Strict universal keeps the rule simple.

Anyone who truly wants to skip: use `[b]` in stop point #13 menu (deferred
cleanup, accepts an inconsistent workspace).

---

## Cross-refs

- Stage 08 L2 template: `templates/workspace/stages/08_feedback_intake/CONTEXT.md.tpl` §"Runtime Cleanup Checklist"
- Stop point #13: `templates/_config/stop-points.md` §"13. runtime_cleanup_failed"
- Recovery wizard: `references/recovery-wizard.md` (RUNTIME_REGISTRY_STALE detector)
- Runtime registry: `scripts/runtime-registry.py` (CRUD + legacy detect)
- Runtime status: `scripts/runtime-status.py` (checklist aggregator)
- Migration: `scripts/migrate-workspace.py` (legacy PID → registry)
- L0 R10: `templates/workspace/CLAUDE.md.tpl` §"Runtime side-effects"
