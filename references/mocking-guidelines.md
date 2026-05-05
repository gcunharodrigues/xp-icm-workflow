# Mocking Guidelines — Canonical (v3.9.0)

> **Version:** v3.9.0
> **Skill:** `xp-icm-workflow`
> **Consumer stage:** `04_implementation_waves` (writer subagent, vertical TDD cycle)
> **Purpose:** canonical document on mocking — aligned with mattpocock principles. Mock only boundaries (HTTP/DB/time/randomness/env); never project internals. Applicable to all profiles (backend, frontend, fullstack, ml, agent_ia).

## Summary (1 paragraph)

Mocking is a tool for isolating **external boundaries** (network, disk, time, randomness, env). It is not a tool for avoiding understanding the system. Project internals (helpers, classes, services) should NOT be mocked — testing with real objects is slower but more correct. When a test becomes slow OR difficult, the signal is that the module should be refactored (single responsibility violation, wrong dependencies, leaky abstraction), not that it needs a mock.

## The 5 boundaries — the only legitimate cases

| Boundary | Mock action | Typical lib |
|----------|-------------|-------------|
| HTTP / network | intercept request, return canned response | msw, nock, requests-mock, vcr |
| Database | use real DB (sqlite in-memory OR test container) preferred; mock only when schema is externalized | testcontainers, sqlite-memory |
| Time / clock | freeze OR advance manually | freezegun, sinon.useFakeTimers |
| Randomness | fix seed; OR inject random fn | seed param, dependency injection |
| Env vars / secrets | set test value via fixture | pytest fixture, vitest setup, env file |

**Rule:** if the boundary is not in this list, do NOT mock.

## Anti-patterns — prohibited

| Anti-pattern | Why it is bad | Alternative |
|--------------|---------------|-------------|
| Mock internal helper (`utils/format-date.ts`) | hides real bug in helper; test green but system broken | use real helper; if slow, refactor helper |
| Mock injected service (`UserService` in a `AuthController` test) | couples test to architecture; refactor breaks mock; false coverage | use real instance with fixtures (seeded DB) |
| Mock factory returning mock factory | indirection with no benefit; impossible to debug | direct fake object with 3-5 essential props |
| `jest.mock('./module')` without boundary justification | "mock by habit"; loses coverage with no gain | remove mock; if slow, identify the real boundary |
| Mock that always returns `undefined` | test does not exercise logic; just does-not-explode | fixture with real data (golden path + edge case) |

## Why not mock internals (mattpocock alignment)

Internal mock = test couples itself to the current implementation, not to the contract. When refactoring changes the implementation (but preserves the contract), the test breaks falsely. The inverse is also true: an internal bug goes undetected because the mock returns what the test expected.

Signs of bad design masked by internal mock:
- Function X depends on 5 services → mock all → test "passes" but real system fails by ordering
- Helper formats date → mock helper → edge-case bug (DST, UTC offset) only found in prod
- Class inherits 3 levels → mock parent → child override breaks untested invariant

**Heuristic:** if you need to mock more than 2 internals for a test to run, the module under test has too much responsibility.

## Per-profile guidance

### Backend (`app_web_backend`)
- DB: testcontainer (real PostgreSQL/MySQL) OR sqlite in-memory.
- HTTP outbound: msw OR nock.
- Cache (Redis): test container OR fakeredis.
- Queue: test broker OR in-memory bus.

### Frontend (`app_web_frontend`)
- HTTP: msw browser handlers (intercept fetch/XHR).
- Component children: render real tree; mock only when child does HTTP/storage.
- localStorage/sessionStorage: in-memory shim or jest-localstorage-mock.
- Router: real router with test history.

### Fullstack
- Sum of the two. Critical: e2e tests use real DB + real frontend (no mock between layers).

### ML / agent_ia
- Model inference: cache golden output (fixture); skip live API.
- Randomness: mandatory seed fix.
- External tools (web search, files): mock fixture.
- Token consumption: test isolated by contract validation, not real generation.

## Tier-aware enforcement

Forensic+ Check 6 (NÃO QUERO violations) and Check 7 (ADR import drift) detect prohibited patterns automatically when:
- The task NÃO QUERO block declares "no mock for internals"
- An applicable ADR prohibits a specific lib (e.g., jest.mock disabled in a critical path)

Tier production: violation = HARD. Tier dev: SOFT. Tier exp/tool: ignored.

## Examples

### ✅ Good — boundary mock

```python
# test_user_service.py
import requests_mock

def test_user_creation_calls_audit_api(db_session):
    with requests_mock.Mocker() as m:
        m.post("https://audit.internal/log", status_code=204)
        service = UserService(db=db_session)  # real DB
        user = service.create(email="x@y.com")
        assert user.id
        assert m.called
```

Real DB (sqlite in-memory via fixture). HTTP boundary mocked.

### ❌ Bad — internal mock

```python
# test_user_service.py
def test_user_creation(mocker):
    mock_validator = mocker.patch("app.services.validate_email")
    mock_validator.return_value = True
    mock_audit = mocker.patch("app.services.AuditClient")
    mock_audit.return_value.log.return_value = None
    service = UserService(db=mocker.MagicMock())  # DB mock
    user = service.create(email="invalid-email")
    assert user  # passes — but real system would reject!
```

Validator mocked (hides real bug). DB mocked. AuditClient mocked. Test green but useless.

### ✅ Good — time mock

```typescript
// test_session_expiry.test.ts
import { useFakeTimers } from "sinon";

test("session expires after 1h inactivity", () => {
  const clock = useFakeTimers(new Date("2026-01-01T00:00:00Z"));
  const session = createSession(userId);
  clock.tick(60 * 60 * 1000 + 1);  // 1h + 1ms
  expect(session.isExpired()).toBe(true);
  clock.restore();
});
```

Time is a boundary. Mock OK. Expiry logic runs real.

## Integration with 4-block contract

The task NÃO QUERO block may declare prohibited mocks:

```markdown
### NÃO QUERO
- Mock de UserService nem AuditClient (use instâncias reais com DB seeded)
- jest.mock em qualquer arquivo dentro de src/auth/
```

Forensic+ Check 6 detects diff that violates the declaration. HARD in tier production.

## Cross-references

- 4-block contract: `references/4-block-contract-template.md` (NÃO QUERO block)
- Forensic+ Check 6: `references/forensic-plus-protocol.md`
- ADR format: `references/adr-format.md`
- Stage 04 runtime: `templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl`
- Source upstream: mattpocock/skills/testing/test-style-guidelines (philosophy alignment, not a copy)
