# Subagent Protocol

> **Version:** v4.0.x
> **Skill:** `xp-icm-workflow`
> **Purpose:** How the lead orchestrates subagents in stage 04. Single isolation path — all subagents use manual worktrees at `.claude/worktrees/icm-wave-*`.
>
> **Single source of truth for the pipeline:** `references/wave-execution-protocol.md`
> **Single source of truth for isolation:** `references/isolation-protocol.md`

---

## 1. When to use subagents (vs single sequential session)

Subagent cap per wave per **tier**:

| Tier | Cap |
|---|---|
| experimental | 2 |
| tool | 3 |
| development | 5 |
| production | 5 |

**Skip subagents** (run sequential single-agent in stage 04) when:
- `tier=experimental` AND ≤2 tasks in the wave.
- `tier=tool` AND 1 task in the wave.

Profile overrides: `framework_library` and `ml_project` cap=3.

---

## 2. Subagent spawn by lead

Lead in stage 04:

1. Reads `stages/02_design/output/wave-plan.md` (generated inline by stage 02).
2. Identifies current wave via L1 `waves.current`.
3. For each task: spawns subagent via `Agent` tool with AGENT-BRIEF + channel-2 injection.

### 2.1 Subagent prompt contract

Lead injects into the Agent tool prompt:

- AGENT-BRIEF (rendered by `agent-brief-render.py` — includes HARD GATES, isolation rules, behavioral spec)
- Channel 2: applicable ADRs + top-3 lessons + design subset (if frontend/fullstack)
- TDD 7-step cycle contract (`4-block-contract-template.md`)
- Mocking guidelines (`mocking-guidelines.md`)

Subagent does NOT read raw `lessons.md` — lead pre-processes via `lessons-match.py`.

### 2.2 Isolation — single manual worktree path

All subagents use the same procedure. Canonical doc: `references/isolation-protocol.md`.

**Lead steps (for each task):**
1. Create branch: `git branch wave-<NNN>-<N>/<slug> main`
2. Create worktree: `git worktree add .claude/worktrees/icm-wave-<NNN>-<N>-<slug> wave-<NNN>-<N>/<slug>`
3. Spawn: `Agent(isolation=None, cwd="<project>/.claude/worktrees/icm-wave-<NNN>-<N>-<slug>", ...)`

The manual worktree IS the isolation. `.claude/` is gitignored by ICM bootstrap.

**Anti-pattern — NEVER do this:**
```python
Agent(isolation=None, description="wave 2 task foo", prompt=...)  # ← DESTROYS workspace files
```
Subagent at project root runs `git checkout` → switches working tree to wave branch → `workspaces/` vanishes.

### 2.3 Branch verification (HARD GATE 1)

Subagent executes GATE 1 first, before any Write/Edit/Bash:

```
1. git branch --show-current
   Must show: wave-<NNN>-<N>/<slug>
2. If wrong → STOP, report Status: BLOCKED
3. git status --short → confirm clean working tree
```

Subagent NEVER runs `git checkout`, `git switch`, `git rebase`, or `git push`. Branch is pre-created.

### 2.4 Branches

- Branch: `wave-<NNN>-<N>/<slug>` created from `main`
- After task completion, subagent commits on the task branch
- Lead merges completed branches into `main` via `.icm-main/` at end of wave

Workspace branch (`workspace/<NNN-slug>`) remains only for state files — NEVER touches `src/`.

---

## 3. Coordination

Coordination happens via:

1. **Lead waits for each subagent's result.** Agent tool is synchronous — lead receives output directly.
2. **Task output.** Subagent returns structured results in Agent tool output. Lead synthesizes `task-<slug>.md` from the output. Subagent NEVER writes to workspace branch.
3. **Status in report.** Each task report ends with `## Status` containing `COMPLETE` or `BLOCKED`.

---

## 4. Wave-reviewer

After all wave subagents complete, lead spawns wave-reviewer (no isolation) for cross-task coherence.

Wave-reviewer does NOT revalidate code (that passed forensic+ + critic). Verifies:
- Outputs declared in `Files touched` exist in final wave merge
- Inter-task dependencies work (smoke test)
- Consistent conventions across tasks

**Skip:** wave with 1 task skips wave-reviewer. Global CI covers.

---

## 5. Sequential merge

After all tasks approved, lead merges via `.icm-main/` in plan order:

```bash
cd .icm-main
git merge --no-ff wave-<NNN>-<N>/<slug>
# CI runs from .icm-main/
cd ..
```

Project root never leaves `workspace/<NNN-slug>`. No stash. No buffer.

Merge conflict → human resolves (no auto-solve). See `references/conflict-resolution-protocol.md`.

### 5.1 Post-merge cleanup

After merge + CI green, lead removes worktrees and deletes merged branches:

```bash
git worktree remove .claude/worktrees/icm-wave-<NNN>-<N>-<slug>
git branch -d wave-<NNN>-<N>/<slug>
```

`git branch -d` refuses unmerged branch (intentional) — never use `-D`. Cleanup paths are deterministic.

---

## 6. Global CI between waves

Wave N+1 only starts after:
1. Wave N entirely merged into `main`.
2. Global CI green (integrated tests — not just per-task).

Pre-flight check for next wave validates both.

---

## 7. Mid-wave reduce

Lead may end a wave partially when drift is observed:
- **Stuck cycles:** subagent failed 3× in TDD cycle
- **Timeout:** subagent did not complete in reasonable time
- **Budget growing:** tokens consumed > 2× estimate

Lead writes `mid-wave-reduce.md`, sets L1 `BLOCKED_ERROR`. Human chooses: continue, rethink plan, or abort.

---

## 8. Peer-reviewer ad-hoc (production tier)

For tasks with `Requires_peer_review: true`, lead spawns a peer-reviewer AFTER main subagent signals COMPLETE. Focus: correctness, security, perf. Output: `peer-review-<slug>.md`.

---

## 9. Synchronous-first

Subagents MUST prefer synchronous tools for expected duration <5min. HARD GATE 2 enforces this. Async (`Bash run_in_background=true` + `Monitor`) reserved for long processes: dev server, build watch, deploy.

**Why:** sessao-recorrencia incident — subagent used Monitor for 14s pytest, lost track of completion, exited without `git commit`. Async overhead not justified for short duration.

---

## 10. Target token budget (reference)

| Role | Typical tokens |
|---|---|
| Lead (orchestration) | ~1k |
| Subagent (each) | ~5-8k |
| Wave-reviewer | ~3k |
| Peer-reviewer (ad-hoc) | ~3k |

---

## 11. Cross-references

| Doc | Related content |
|---|---|
| `references/isolation-protocol.md` | Worktree setup, merge via .icm-main, cleanup |
| `references/agent-brief-template.md` | HARD GATES, isolation rules in AGENT-BRIEF |
| `references/wave-execution-protocol.md` | 5-phase pipeline |
| `references/4-block-contract-template.md` | TDD 7-step cycle per subagent |
| `references/wave-planner-algorithm.md` | DAG, Q10 lesson match, Q6 peer-review trigger |
| `references/stop-points-canonical.md` | 15 stop points + escalation |
| `references/recovery-wizard.md` | Recovery if lead crashed mid-wave |
| `templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl` | L2 runtime |

---

## v4.0.x — Single isolation path

Eliminated Path A (`Agent(isolation: "worktree")`). All subagents use manual worktrees at deterministic paths. No topology detection needed. Merge via `.icm-main/` — project root never switches off workspace branch.
