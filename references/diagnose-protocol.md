# Diagnose Protocol — 6 phases

Adapted from [mattpocock/skills/skills/engineering/diagnose/SKILL.md].

Discipline for hard bugs and performance regressions. Stage 05 (verification)
activates this protocol when CI fails OR coverage fails. Stage 04 (subagent) may
use it before declaring BLOCKED on a recurring bug.

## Phase 1 — Build a feedback loop

**This is the skill.** The rest is mechanical. Without a fast/deterministic/
agent-runnable feedback loop, no amount of staring at code will resolve it.

Spend disproportionate effort here. **Be aggressive. Be creative. Refuse to
give up.**

### Ways to build a feedback loop (in order)

1. **Failing test** — any seam (unit, integration, e2e).
2. **Curl / HTTP script** against a running dev server.
3. **CLI invocation** with fixture input, diff stdout vs known-good snapshot.
4. **Headless browser** (Playwright / Puppeteer) — drives UI, asserts on DOM/console/network.
5. **Replay captured trace.** Save real network request / payload / event log; replay in isolation.
6. **Throwaway harness.** Minimal system subset (1 service, mocked deps) that exercises the bug code path with 1 function call.
7. **Property / fuzz loop.** Bug "sometimes wrong output": 1000 random inputs.
8. **Bisection harness.** Bug between 2 known states: automate "boot at state X, check, repeat" → `git bisect run`.
9. **Differential loop.** Same input in old vs new (config X vs Y), diff outputs.
10. **HITL bash script.** Last resort. Use `_config/hitl-loop.template.sh`.

Build the right feedback loop and the bug is 90% fixed.

### Iterate on the loop

Treat loop as product:
- Faster? (Cache setup, skip unrelated init, narrow scope.)
- Sharper signal? (Assert specific symptom, not "didn't crash".)
- More deterministic? (Pin time, seed RNG, isolate fs, freeze network.)

A 30-second flaky loop is barely better than no loop. A 2-second deterministic one is a
debugging superpower.

### Non-deterministic bugs

Goal is not a clean repro but **higher reproduction rate**. Trigger loop 100×,
parallelise, add stress, narrow timing windows, inject sleeps. 50%-flake is
debuggable; 1% is not — keep raising the rate.

### When a loop cannot be built

Stop and say so explicitly. List what was tried. Ask the user: (a) access
to the env that reproduces it, (b) captured artifact (HAR, log dump, core dump, screen
recording with timestamps), (c) permission to add temporary production
instrumentation. **Do not proceed to Phase 2 without a loop.**

## Phase 2 — Reproduce

Run the loop. Watch the bug appear.

Confirm:
- [ ] Loop produces the **failure mode the user described** — not another failure that
  happens to be nearby. Wrong bug = wrong fix.
- [ ] Failure is reproducible across multiple runs (or, non-deterministic, at a
  high enough rate).
- [ ] Captured exact symptom (error msg, wrong output, slow timing) for later phases to verify.

Do not proceed without reproducing.

## Phase 3 — Hypothesise

Generate **3-5 ranked hypotheses** before testing any of them. Single-hypothesis
generation anchors on the first plausible idea.

Each hypothesis must be **falsifiable**: state the prediction.

> Format: "If `<X>` is the cause, then changing `<Y>` will make the bug
> disappear / changing `<Z>` will make it worse."

No prediction → vibe → discard or sharpen.

**Show the ranked list to the user before testing.** User has domain knowledge that
re-ranks instantly ("we just deployed a change to #3"), or knows hypotheses
already ruled out. Cheap checkpoint, big time saver. Do not block — proceed
with your ranking if user is AFK.

## Phase 4 — Instrument

Each probe must map to a specific prediction from Phase 3. **Change one
variable at a time.**

Tool preference:
1. **Debugger / REPL inspection** if env supports it. One breakpoint > ten logs.
2. **Targeted logs** at the boundaries that distinguish hypotheses.
3. **Never "log everything and grep".**

**Tag every debug log** with a unique prefix: `[DEBUG-a4f2]`. Cleanup at end =
single grep. Untagged logs survive; tagged logs die.

**Perf branch.** Performance regressions: logs are usually wrong. Instead:
baseline measurement (timing harness, `performance.now()`, profiler,
query plan), then bisect. Measure first, fix second.

## Phase 5 — Fix + regression test

Write the regression test **before the fix** — but only if there is a **correct seam**.

Correct seam = test exercises the **real bug pattern** as it occurs at the call site.
If the only available seam is too shallow (single-caller test when the bug needs
multiple callers, unit test that can't replicate the chain that triggered the bug),
a regression test there gives false confidence.

**Without a correct seam, that is the finding.** Note it. The architecture is preventing the bug
from being locked down. Flag for the next phase.

If a correct seam exists:
1. Turn minimised repro into a failing test.
2. Watch it fail.
3. Apply fix.
4. Watch it pass.
5. Re-run Phase 1 loop against the original (un-minimised) scenario.

## Phase 6 — Cleanup + post-mortem

Required before declaring done:
- [ ] Original repro no longer reproduces (re-run Phase 1 loop)
- [ ] Regression test passes (or absence of seam documented)
- [ ] All `[DEBUG-...]` instrumentation removed (`grep` the prefix)
- [ ] Throwaway prototypes deleted (or moved to a clearly-marked debug location)
- [ ] Correct hypothesis stated in commit / PR message — next debugger learns

**Then ask: what would have prevented this bug?** If the answer involves an architectural
change (no good test seam, tangled callers, hidden coupling), record the finding
in `output/diagnose-report.md` for review in stage 06.

## Output Stage 05

`stages/05_verification/output/diagnose-report.md` with:
- **Repro evidence** — command that triggers the bug + observed output
- **Ranked hypotheses** — 3-5 falsifiable with predictions
- **Instrumentation** — which logs/probes were used
- **Root cause** — winning hypothesis + evidence
- **Fix applied** — diff + modified file (path in stage 04)
- **Regression test** — test path + seam used (or "no correct seam: <reason>")
- **Architectural finding (optional)** — if the cleanup phase identified one
