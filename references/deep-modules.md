# Deep modules + deletion test (architecture review — stage 02)

> Canonical doc for architecture review in stage 02 (design). Principles
> inspired by [mattpocock/skills/engineering/improve-codebase-architecture]
> and John Ousterhout, *A Philosophy of Software Design*.
>
> Use during stage 02 when the design involves new modules or refactoring of
> existing modules. Not required for pure bug fixes.

## Concept — Deep modules

**Deep module:** small interface, rich implementation.

```
+-----------+
|  API      |   <- small (few methods, clear contracts)
+-----------+
| Implem    |
| richly    |   <- complexity lives here (validation, cache, retry, fallback)
| hidden    |
+-----------+
```

**Shallow module:** large interface, thin implementation (pass-through).

| Aspect | Deep | Shallow |
|---|---|---|
| Public methods | 1-5 | 10+ |
| Exported types | 1-2 (input/output) | many (leaked internal state) |
| Contract | "do X" | "configure A, B, C, then do X" |
| Cognitive cost for caller | low | high |

Principle: **complexity has to go somewhere**. In deep modules,
it is hidden behind the API; the caller pays a small price. In shallow modules,
complexity leaks to all callers.

## The 3 criteria for classifying a module

| Criterion | Question | Green signal | Red signal |
|---|---|---|---|
| **Minimal interface** | How many public methods? How many parameters per method? | ≤5 methods, ≤4 params | 10+ methods, exploded params |
| **Information hiding** | Does the caller need to know internal details to use it correctly? | No — caller passes input, receives output | Yes — caller must configure state, call order matters |
| **Single responsibility** | Does the module do **one** thing? | Yes — the module name describes it in 5 words | No — the name uses "and"/"or" or ends in "Util"/"Helper" |

Failure on any criterion → module is shallow or multi-responsibility.

## Deletion test (complementary heuristic)

> "If I deleted this module, what is the blast radius? If the answer is
> '~3 callers update imports', the module is deep. If the answer is
> 'half the app breaks', the module is shallow."

Apply mentally to each new module in the design:

1. Count the module's callers (`grep -r "from <module>"`).
2. Estimate how much each caller depends on internal behavior (not just
   the public signature).
3. If >30% of callers need to adapt logic instead of just renaming
   imports → the module is leaking state/contract → revise.

## Checklist for stage 02

For each new module introduced by the design (`docs/decisions/NNNN.md`
or `stages/02_design/output/plan.md`):

- [ ] **Minimal interface:** public API listed explicitly. ≤5 methods.
- [ ] **Information hiding:** API docstring mentions only input/output;
      internal details (cache layer, retry policy, etc.) do NOT appear in the API.
- [ ] **Single responsibility:** module name describes the responsibility
      in one sentence without conjunctions.
- [ ] **Deletion test:** blast radius estimate < 30% of callers
      needing to adapt logic (vs renaming imports).
- [ ] **Alternative considered:** ADR (`docs/decisions/NNNN.md`) mentions at
      least 1 alternative that was rejected (aligned with Design It Twice).

If ≥2 items fail: go back to the drawing board before proceeding to stage 03.

## Short examples

### Deep — `RetryableHTTPClient`

```python
# Public API: 1 method. Cache, backoff, jitter, circuit breaker are invisible.
class RetryableHTTPClient:
    async def request(self, method: str, url: str, *, body: bytes | None = None) -> Response:
        ...
```

Caller only passes method/url. No need to know about internal policies.

### Shallow — `HTTPClientUtil`

```python
# Public API: 8 methods. Caller orchestrates everything.
class HTTPClientUtil:
    def configure_retry(self, max_attempts: int, backoff_ms: int) -> None: ...
    def configure_circuit_breaker(self, threshold: int) -> None: ...
    def configure_cache(self, ttl: int, max_size: int) -> None: ...
    def request(self, ...) -> Response: ...
    def parse_response(self, raw: bytes) -> dict: ...   # should already be internal
    def log_request(self, ...) -> None: ...             # cross-cutting, leaks
    def get_metrics(self) -> dict: ...                  # another module
    ...
```

Caller must configure everything, order matters, state leaks. Refactor.

## When to skip this check

- Pure bug fix (no new module introduced).
- Trivial single-function module (e.g., `slugify(s: str) -> str` alone in a file).
- Rename or move refactor with no API change.

## Integration with other docs

- `references/adr-format.md` — 3-criteria gate for ADRs (different scale,
  but aligned spirit: force explicit trade-off).
- `references/design-it-twice.md` — requirement to explore 2 parallel designs
  for core modules. Deep modules emerge naturally from the exercise.
- `templates/workspace/stages/02_design/CONTEXT.md.tpl` — this doc's checklist
  is executed during design.

## External references

- John Ousterhout, *A Philosophy of Software Design*, chapters 4 (Modules
  Should Be Deep) and 5 (Information Hiding).
- mattpocock/skills/engineering/improve-codebase-architecture — source of
  inspiration for the "deletion test" as an operational heuristic.
