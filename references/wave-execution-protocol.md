# Wave Execution Protocol — Stage 04 (Canonical)

> Canonical doc for the wave cycle in stage 04. Consolidates protocol scattered between the L2 template and references. Source of truth — other docs point here.

## Summary (1 paragraph)

Stage 04 = N sequential waves. Each wave = 1 lead session. Lead spawns subagents via `Agent(isolation: "worktree")`, one per task in the wave (up to cap per tier 2/3/5/5). Subagent works in an ephemeral isolated worktree on branch `wave-<NNN>-<N>/<task-slug>`. After all COMPLETE: wave-reviewer audits, lead merges sequentially into `BASE_BRANCH` (plan order), global CI, cleanup, handoff. Mid-wave handoff is automatic; last wave requires human gate.

## Actors

| Actor | Session | CWD | Branch | Role |
|------|--------|-----|--------|--------|
| Lead | 1 (entire wave) | `{{PROJECT_ROOT}}` | `workspace/{{WORKSPACE}}` | Orchestrates, manages L1 state, performs merges |
| Subagent N | Spawned by lead via Agent | Ephemeral worktree | `wave-<NNN>-<N>/<task-slug>` | TDD 7 steps, writes task report |
| Wave-reviewer | Spawned by lead via Agent (no worktree) | Lead CWD | `workspace/{{WORKSPACE}}` | Audits Auto-QA, files touched, acceptance |
| Human | Async (inline gate) | — | — | Approves last wave, resolves conflicts, answers stop points |

## Branches during wave

```
main (= BASE_BRANCH)         ← stable, lead merges here
  └─ workspace/<NNN-slug>     ← lead works here (state files L1/L2, outputs)
       └─ wave-<NNN>-<N>/<slug-1>  ← subagent 1 (ephemeral worktree)
       └─ wave-<NNN>-<N>/<slug-2>  ← subagent 2
       └─ ...
```

## Pipeline (14 steps — 1-8 pre-merge, 9 lead-resolution, 10-14 post-resolution)

### Entry/exit criteria per step

| Step | Entry criteria | Exit criteria |
|------|---------------|---------------|
| 1 Pre-flight | L1 `sub_stage = 04_wave_N_in_progress` | `pre_wave_sha` recorded; pre-flight checklist all [x]; model assigned per task |
| 2 Spawn | Pre-flight complete; branches created | All Agent calls dispatched; subagents report `Status: IN_PROGRESS` |
| 3 Channel 2 | Subagents spawned | ADRs + lessons + design subset injected into each prompt |
| 4 TDD 7 steps | Subagent in worktree on correct branch | Task report written; tracer test ≥1; CI green; REFACTOR done or skipped with Dirt Check |
| 5 Stop points | Subagent detects trigger signal | A/B/C menu written; L1 `BLOCKED_STOP_POINT`; human responds |
| 6 Cap 3 loops | Subagent returned result | `qa_loops_used` ≤ 3; L2+L3 passed OR cap exhausted → step 9 |
| 7 Lead receives | All subagents returned | Results buffered in `{task_slug: result}`; sorted by plan order |
| 8 Wave-reviewer | All task reports present; branches exist | Per task: forensic+ JSON + critic JSON; decision APPROVE/REJECT per task |
| 9 Lead-resolution | ≥1 task escalated from step 8 | Bucket B1/B3/B4 chosen with justification; `lead-decision.md` written |
| 10 Sequential merge | All tasks APPROVED or resolved | `git merge --no-ff` succeeded per task; no conflicts pending |
| 11 L4 wave gate | All merges complete | CI global green; E2E green (if applicable); cross-task coherence PASS (if applicable) |
| 12 Cleanup | Wave gate green | Worktrees removed; branches deleted; `.icm-main` synced |
| 13 Wave-summary | Cleanup complete | `wave-summary.md` written with all sections |
| 14 Handoff | Wave-summary written | Case A: kickoff for wave N+1, EXIT. Case B: gate-inline, human approves → kickoff for stage 05, EXIT |

1. **Pre-flight** — lead reads wave-plan.md, identifies current wave, records `pre_wave_sha` in L1 history.
2. **Spawn** — lead creates branches + invokes `Agent(isolation: "worktree")` in parallel (multi tool-use).
3. **Channel 2** — lead injects ADR subset + lessons + design subset (if frontend) into the Agent prompt.
4. **TDD 7 steps** — subagent in worktree: RED → GREEN → CI 1st → REFACTOR → CI 2nd → Auto-QA → COMPLETE.
5. **Stop points** — subagent detects `new_dep`/`irreversible`/`over_eng`/`prod_migration`/`adr_drift` → menu A/B/C.
6. **Cap 3 auto-QA loops** — `qa_loops_used` in task report; reviewer audits.
7. **Lead receives** — Agent results buffered in `{task_slug: result}`; sorted by plan order.
8. **Wave-reviewer** — Agent without worktree. Expanded into 8a/8b/8c/8d (v3.8.0):
   - **8a Forensic+** — `scripts/forensic-plus.py` per AFK task (4 checks: test assertions, files outside declared, scope creep, TODO/FIXME). Canonical doc: `references/forensic-plus-protocol.md`.
   - **8b Existing audit** — Auto-QA declared, files touched, acceptance.
   - **8c Forensic git log** — `qa_loops_used` vs actual commits.
   - **8d Decision** — HARD → `approved_pending_ci: false` + re-spawn (cap `MAX_FORENSIC_RETRIES = 2`); SOFT → warnings; NONE → approve.
9. **Sequential merge** — `git merge --no-ff` into `BASE_BRANCH`, plan order; conflict → `conflict-resolution-protocol.md`.
10. **Global CI** — green → 11; red → `ci-rollback-protocol.md`.
11. **Cleanup** — `git worktree remove` (decision matrix `--force`) + `git branch -d` (never `-D`); conditional `.icm-main` sync.
12. **Handoff** — mid-wave automatic or last wave human gate (see L2 § End of stage handoff).

## Canonical statuses

- `IN_PROGRESS`
- `COMPLETED_AWAITING_HUMAN` (last wave)
- `BLOCKED_STOP_POINT`
- `BLOCKED_ERROR` (merge conflict, CI red, cap 3 loops, cleanup unsafe)
- `BLOCKED_HITL` (mixed wave, HITL task pending)

## Cross-references

- Merge conflict: `references/conflict-resolution-protocol.md`
- Global CI red: `references/ci-rollback-protocol.md`
- AGENT-BRIEF render: `references/agent-brief-template.md` + `scripts/agent-brief-render.py`
- Stop points: `references/stop-points-canonical.md`
- Diagnose: `references/diagnose-protocol.md`
- Handoff: `references/session-handoff-protocol.md`
- HITL: `references/task-types-hitl-afk.md`
- L2 stage 04 (runtime instructions): `templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl`
- Forensic+ audit: `references/forensic-plus-protocol.md`

## Global invariants

- Lead always on `workspace/<NNN-slug>` for the entire wave.
- Subagents never read other workspaces.
- Wave branches are created from `BASE_BRANCH`, NOT from the workspace branch.
- Sequential merge follows plan order, not Agent return order.
- `pre_wave_sha` captured in L1 history for rollback.
- Wave branches deleted ONLY after successful merge + CI green + cleanup.
- Cleanup `--force` ONLY with `auto_qa_passed: true` in task report.
