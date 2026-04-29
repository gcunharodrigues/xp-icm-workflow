# Diagnose Protocol — 6 fases

Adaptado de [mattpocock/skills/skills/engineering/diagnose/SKILL.md].

Disciplina para hard bugs e performance regressions. Stage 05 (verification)
ativa este protocolo quando CI fail OU coverage fail. Stage 04 (subagent) pode
usar antes de declarar BLOCKED em bug recorrente.

## Fase 1 — Build a feedback loop

**Esta é a skill.** O resto é mecânico. Sem feedback loop fast/deterministic/
agent-runnable, nenhuma quantidade de stare-at-code resolve.

Spend disproportionate effort here. **Be aggressive. Be creative. Refuse to
give up.**

### Maneiras de construir feedback loop (em ordem)

1. **Failing test** — qualquer seam (unit, integration, e2e).
2. **Curl / HTTP script** contra dev server rodando.
3. **CLI invocation** com fixture input, diff stdout vs known-good snapshot.
4. **Headless browser** (Playwright / Puppeteer) — drives UI, asserts em DOM/console/network.
5. **Replay captured trace.** Save real network request / payload / event log; replay isolado.
6. **Throwaway harness.** Subset mínimo do sistema (1 service, mocked deps) que exercita bug code path com 1 function call.
7. **Property / fuzz loop.** Bug "sometimes wrong output": 1000 random inputs.
8. **Bisection harness.** Bug entre 2 known states: automate "boot at state X, check, repeat" → `git bisect run`.
9. **Differential loop.** Mesmo input em old vs new (config X vs Y), diff outputs.
10. **HITL bash script.** Last resort. Use `_config/hitl-loop.template.sh`.

Build right feedback loop e bug é 90% fixed.

### Iterate na loop

Treat loop as product:
- Faster? (Cache setup, skip unrelated init, narrow scope.)
- Sharper signal? (Assert specific symptom, not "didn't crash".)
- More deterministic? (Pin time, seed RNG, isolate fs, freeze network.)

30-second flaky loop é barely better than no loop. 2-second deterministic é
debugging superpower.

### Non-deterministic bugs

Goal não é clean repro mas **higher reproduction rate**. Loop trigger 100×,
parallelise, add stress, narrow timing windows, inject sleeps. 50%-flake é
debuggable; 1% não é — keep raising rate.

### Quando não dá pra construir loop

Stop e diga explicitamente. List o que tentou. Pergunte ao usuário: (a) acesso
ao env que reproduz, (b) artifact captured (HAR, log dump, core dump, screen
recording com timestamps), (c) permissão pra add temporary production
instrumentation. **Não proceda pra Phase 2 sem loop.**

## Fase 2 — Reproduce

Run the loop. Watch o bug aparecer.

Confirme:
- [ ] Loop produz **failure mode que o user descreveu** — não outro failure que
  acontece de estar perto. Wrong bug = wrong fix.
- [ ] Failure é reprodutível em multiple runs (ou, non-deterministic, em rate
  alto suficiente).
- [ ] Capturou symptom exato (error msg, wrong output, slow timing) pra fases
  later verificarem.

Não proceda sem reproduzir.

## Fase 3 — Hypothesise

Generate **3-5 ranked hypotheses** antes de testar qualquer uma. Single-hyp
generation anchors no first plausible idea.

Cada hipótese deve ser **falsifiable**: state the prediction.

> Format: "If `<X>` is the cause, then changing `<Y>` will make the bug
> disappear / changing `<Z>` will make it worse."

Sem prediction → vibe → discard or sharpen.

**Show ranked list ao user antes de testar.** User tem domain knowledge que
re-ranks instantly ("acabamos de deployar mudança no #3"), ou sabe hypotheses
que já ruled out. Cheap checkpoint, big time saver. Não bloqueie — proceda
com seu ranking se user AFK.

## Fase 4 — Instrument

Cada probe deve mapear pra prediction específica de Phase 3. **Mude uma
variable por vez.**

Tool preference:
1. **Debugger / REPL inspection** se env supports. One breakpoint > ten logs.
2. **Targeted logs** nos boundaries que distinguem hipóteses.
3. **Nunca "log everything and grep".**

**Tag every debug log** com prefix único: `[DEBUG-a4f2]`. Cleanup no fim =
single grep. Untagged logs survive; tagged logs die.

**Perf branch.** Performance regressions: logs are usually wrong. Em vez
disso: baseline measurement (timing harness, `performance.now()`, profiler,
query plan), depois bisect. Measure first, fix second.

## Fase 5 — Fix + regression test

Write regression test **antes do fix** — mas só se há **correct seam**.

Correct seam = test exercita **real bug pattern** como ocorre no call site.
Se único seam disponível é too shallow (single-caller test quando bug needs
multiple callers, unit test que can't replicate chain que triggered bug),
regression test ali dá false confidence.

**Sem correct seam, isso é a finding.** Note. Architecture is preventing bug
from being locked down. Flag pra próxima fase.

Se correct seam existe:
1. Turn minimised repro em failing test.
2. Watch fail.
3. Apply fix.
4. Watch pass.
5. Re-run Phase 1 loop contra original (un-minimised) scenario.

## Fase 6 — Cleanup + post-mortem

Required antes de declarar done:
- [ ] Original repro no longer reproduces (re-run Phase 1 loop)
- [ ] Regression test passes (ou absence of seam documented)
- [ ] All `[DEBUG-...]` instrumentation removed (`grep` o prefix)
- [ ] Throwaway prototypes deleted (ou movidos pra debug location clearly-marked)
- [ ] Hypothesis correta stated em commit / PR message — próximo debugger learns

**Then ask: o que teria prevented este bug?** Se resposta envolve architectural
change (no good test seam, tangled callers, hidden coupling), record finding
no `output/diagnose-report.md` para review na fase 06.

## Output Stage 05

`stages/05_verification/output/diagnose-report.md` com:
- **Repro evidence** — comando que dispara bug + output observado
- **Ranked hypotheses** — 3-5 falsifiable com predictions
- **Instrumentation** — quais logs/probes foram usados
- **Root cause** — hypothesis vencedora + evidência
- **Fix applied** — diff + arquivo modificado (path no stage 04)
- **Regression test** — path do test + seam usado (ou "no correct seam: <razão>")
- **Architectural finding (opcional)** — se cleanup phase identificou
