# Spawn Handoff Protocol — v3.7.0

> Canonical doc for the stage 08 exit C handoff → next workspace bootstrap.
> Replaces UX H2 from v3.0+ (human pasted a long command) with a
> `.icm/spawn-pending.json` file auto-detected by bootstrap.

---

## Why it exists

Pre-v3.7.0, stage 08 exit C printed an explicit command like:

```
/xp-icm-workflow project-root=<long-path> spawn_from=NNN-old-slug
```

Human copied it manually. High friction: long command, easy to mistype the
slug, lost context if session closed between kickoff and bootstrap.

v3.7.0: stage 08 exit C writes `<project_root>/.icm/spawn-pending.json`
as a structured file. Next bootstrap session **auto-detects** it + proposes values
+ unlinks it after success. Zero manual command in the common case.

Explicit fallback: `--spawn-from <slug>` arg still accepted for manual
re-spawn or edge cases without a pending file.

---

## Canonical schema

`<project_root>/.icm/spawn-pending.json`:

```json
{
  "spawn_from": "001-001-saas-psicologo-mvp",
  "intake_report_path": "workspaces/001-001-saas-psicologo-mvp/stages/08_feedback_intake/output/intake-report.md",
  "intake_report_branch": "workspace/001-001-saas-psicologo-mvp",
  "proposed_workspace_name": "002-e2e-playwright-suite",
  "proposed_profile": "app_web_frontend",
  "proposed_tier": "tool",
  "intake_commit_sha": "abc1234",
  "agent_brief": {
    "por_que_spawn": "Suite E2E precisa cobertura Playwright completa.",
    "escopo_motivador": "Cobrir fluxos críticos: booking, payment, cancel.",
    "heranca_aplicavel": "ADRs 0001-0003 (stack), lessons sobre auth.",
    "nao_quero": "Tests unitários (já cobertos no parent).",
    "notes_livre": ""
  },
  "created_at": "2026-05-01T12:00:00Z"
}
```

### Required fields

| Field | Type | Description |
|---|---|---|
| `spawn_from` | string | parent workspace slug (NNN-NNN-slug) |
| `intake_report_path` | string | path relative to project_root for the intake-report.md |
| `intake_report_branch` | string | git branch where intake-report resides |
| `proposed_workspace_name` | string | suggested slug for the new workspace |
| `proposed_profile` | string | profile inferred from the motivating scope |
| `proposed_tier` | string | inferred tier |
| `intake_commit_sha` | string | sha of the stage 08 exit C commit |
| `agent_brief` | object | structured brief (4 fields + notes) |
| `created_at` | string | ISO 8601 UTC |

### `agent_brief` structure

| Field | Content |
|---|---|
| `por_que_spawn` | Reason for spawn vs restart B (pivot, distinct scope) |
| `escopo_motivador` | What the new workspace should cover |
| `heranca_aplicavel` | ADRs/lessons from parent that apply |
| `nao_quero` | Explicit out-of-scope (avoids overlap) |
| `notes_livre` | Optional extra context |

New workspace (stage 00 recon) consumes `agent_brief` in the recon-report seed.

---

## Cross-branch read of the intake-report

New workspace NNN-2 is checked out in `workspace/NNN-2`. Directory
`workspaces/NNN-1/` does NOT exist in that branch (each workspace branch only
has its own dir). Intake-report lives in branch
`workspace/NNN-1/workspaces/NNN-1/stages/08_feedback_intake/output/intake-report.md`.

Read pattern (documented in L2 stage 00 of the new workspace):

```bash
git show <intake_report_branch>:<intake_report_path>
```

Example:

```bash
git show workspace/001-001-saas-psicologo-mvp:workspaces/001-001-saas-psicologo-mvp/stages/08_feedback_intake/output/intake-report.md
```

Zero overhead — pattern already used for cross-branch reads via `.icm-main/`
in other stages.

---

## Bootstrap detection flow

```
[bootstrap.py main]

  1. detect_spawn_pending(project_root)
     → reads .icm/spawn-pending.json
     → validates schema (9 required fields)
     → returns dict or None

  2. resolve_spawn_source(project_root, spawn_from_arg)
     → consolidates file + CLI arg:
       - source="none" — neither file nor arg → normal flow
       - source="arg"  — only arg → bootstrap uses arg
       - source="file" — only file OR arg matches → file wins
       - source="conflict" — file+arg from different workspaces

  3. If source="conflict":
     human menu [a] use file (NNN-X) [b] use arg (NNN-Y) [c] cancel

  4. If source ∈ {file, arg}:
     - If file: payload pre-populates --profile, --tier, --workspace-name
     - Human confirms OR adjusts in interactive menu
     - Bootstrap proceeds with resolved values

  5. After successful bootstrap:
     consume_spawn_pending(project_root)
     → unlink .icm/spawn-pending.json
     → idempotent (no-op if absent)
```

---

## Edge cases

### File present but workspace already closed/opened

`spawn_from` points to a workspace that has already completed its cycle (status COMPLETED).
OK — bootstrap only reads metadata, does not modify parent. Expected pattern:
parent closed via stage 08 exit C, wrote spawn-pending.

### File present but target workspace already exists

`proposed_workspace_name` already created in workspaces/NNN-NNN-slug/.
Bootstrap detects collision in validate_slug step → human menu:
- `[a]` cancel bootstrap (resolve manually)
- `[b]` propose next free NNN
- `[c]` accept override (danger: potential data loss)

### File present across 2+ machines (clone)

`.icm/spawn-pending.json` is gitignored (v3.7.0 GITIGNORE_LINES) —
does not travel between clones. Accepted trade-off: skill is local-first; human
on another machine needs to trigger manual flow `--spawn-from <slug>`.

### Corrupted file (invalid JSON)

`detect_spawn_pending` raises `BootstrapError`. Bootstrap aborts before
main flow — human resolves (delete file if obsolete, or
recreate via stage 08 re-execute).

### Multiple pending files (impossible by design)

Schema allows only 1 pending spawn per project_root. Stage 08 exit C
overwrites `.icm/spawn-pending.json` if it already exists (last wins). This
behavior is intentional: 2 workspaces closing with exit C
sequentially, last spawn-pending wins; human chooses which
bootstrap to run.

---

## Pre-commit hook implications

`.icm/spawn-pending.json` is in `GITIGNORE_LINES` v3.7.0
(`bootstrap.py:67`). Pre-commit hook never sees the file in the staged set —
zero risk of accidental commit.

If human `git add -f` forces it:
- Path `.icm/...` is outside the hook whitelist → rejected.
- Message guides: "directory .icm/ is local-only (transient handoff)".

---

## Cross-refs

- Bootstrap helpers: `scripts/bootstrap.py` (`detect_spawn_pending`,
  `resolve_spawn_source`, `consume_spawn_pending`,
  `SPAWN_PENDING_REQUIRED_FIELDS`)
- Stage 08 L2: `templates/workspace/stages/08_feedback_intake/CONTEXT.md.tpl` §"Exit C"
- Feedback intake: `references/feedback-intake-fase08.md` §"Exit C — Spawn new workspace"
- Stage 00 L2 (target consumer): `templates/workspace/stages/00_recon/CONTEXT.md.tpl` §"Record inheritance"
- GITIGNORE_LINES: `scripts/bootstrap.py:67` (`.icm/spawn-pending.json`)
