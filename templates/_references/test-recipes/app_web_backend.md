# Test Recipe — app_web_backend

> Test strategy reference for HTTP backend APIs/services.
> Read by the discovery session (stage 01) and used to fill §Test Strategy in plan.md (stage 02).

## Required test types

| Type | What it tests | When to use |
|---|---|---|
| **Unit** | Isolated functions/handlers with mocked dependencies | All business logic code |
| **Integration** | Handler + real DB (test database) + HTTP stack | Complete endpoints, migrations, queries |

## Recommended frameworks by language

| Language | Unit | Integration/HTTP | DB fixture |
|---|---|---|---|
| Python | `pytest` + `pytest-asyncio` | `httpx.AsyncClient` + FastAPI `TestClient` | `pytest-postgresql` / SQLite in-memory / transaction rollback |
| Node.js/TS | `vitest` or `jest` | `supertest` | `pg` with transaction rollback, `testcontainers` |
| Go | `testing` stdlib | `httptest` | `testcontainers-go` |
| Ruby | `rspec` | `rack-test` | `database_cleaner` |

## Essential patterns

### DB strategy — prefer transaction rollback

```python
# pytest: per-test rollback avoids global state
@pytest.fixture(autouse=True)
async def db_transaction(db):
    async with db.begin_nested() as savepoint:
        yield db
        await savepoint.rollback()
```

### Factory pattern for test data

```python
# Do not use static fixtures — use factories
def make_user(email="test@example.com", role="user", **overrides):
    return {"email": email, "role": role, **overrides}
```

### Full endpoint test (integration)

```python
async def test_create_user_returns_201(client, db):
    payload = make_user(email="new@example.com")
    response = await client.post("/users", json=payload)
    assert response.status_code == 201
    assert response.json()["email"] == payload["email"]
    # verify real persistence
    user_in_db = await db.execute(select(User).where(User.email == payload["email"]))
    assert user_in_db.scalar() is not None
```

## File structure

```
tests/
  unit/
    test_<module>.py       # isolated tests, no IO
  integration/
    test_<endpoint>.py     # full route tests with real DB
  conftest.py              # shared fixtures (client, db, factories)
```

## Coverage configuration

```ini
# pyproject.toml / setup.cfg
[tool.coverage.run]
source = ["src"]
omit = ["tests/*", "*/__init__.py", "*/migrations/*"]
branch = true

[tool.coverage.report]
fail_under = 80   # adjust per tier (80% development, 90% production)
```

## Anti-patterns

- Excessive `unittest.mock.patch` — prefer real dependency injection in integration tests.
- `sleep()` in async tests — use `pytest-anyio` with `await asyncio.sleep(0)` if needed.
- Shared database between parallel tests without isolation.
- Testing only the happy path — include: invalid input, auth failure, 404, rate limit, DB constraint.

## Quick checklist (auto-QA Akita support)

- [ ] Each endpoint has ≥1 handler unit test + ≥1 integration test with real DB
- [ ] Auth paths have 100% unit coverage (token missing, expired, invalid, valid)
- [ ] Input validation errors tested (400 Bad Request with wrong schema)
- [ ] Coverage ≥ tier threshold (see `_config/profile-effective.yaml`)
- [ ] PII does not appear in test logs
