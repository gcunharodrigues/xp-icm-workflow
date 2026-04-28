# Test Recipe — app_web_backend

> Referência de estratégia de teste para APIs/serviços backend HTTP.
> Lido pela sessão de discovery (stage 01) e usado para preencher §Test Strategy no plan.md (stage 02).

## Tipos de teste obrigatórios

| Tipo | O que testa | Quando usar |
|---|---|---|
| **Unit** | Funções/handlers isolados com dependências mockadas | Todo código de lógica de negócio |
| **Integration** | Handler + DB real (test database) + HTTP stack | Endpoints completos, migrations, queries |

## Frameworks recomendados por linguagem

| Linguagem | Unit | Integration/HTTP | DB fixture |
|---|---|---|---|
| Python | `pytest` + `pytest-asyncio` | `httpx.AsyncClient` + FastAPI `TestClient` | `pytest-postgresql` / SQLite in-memory / transaction rollback |
| Node.js/TS | `vitest` ou `jest` | `supertest` | `pg` com transaction rollback, `testcontainers` |
| Go | `testing` stdlib | `httptest` | `testcontainers-go` |
| Ruby | `rspec` | `rack-test` | `database_cleaner` |

## Padrões essenciais

### DB strategy — preferir transaction rollback

```python
# pytest: rollback por test evita estado global
@pytest.fixture(autouse=True)
async def db_transaction(db):
    async with db.begin_nested() as savepoint:
        yield db
        await savepoint.rollback()
```

### Factory pattern para dados de teste

```python
# Não usar fixtures estáticas — usar factories
def make_user(email="test@example.com", role="user", **overrides):
    return {"email": email, "role": role, **overrides}
```

### Teste de endpoint completo (integration)

```python
async def test_create_user_returns_201(client, db):
    payload = make_user(email="new@example.com")
    response = await client.post("/users", json=payload)
    assert response.status_code == 201
    assert response.json()["email"] == payload["email"]
    # verificar persitência real
    user_in_db = await db.execute(select(User).where(User.email == payload["email"]))
    assert user_in_db.scalar() is not None
```

## Estrutura de arquivos

```
tests/
  unit/
    test_<module>.py       # testes isolados, sem IO
  integration/
    test_<endpoint>.py     # testes de rota completa com DB real
  conftest.py              # fixtures compartilhadas (client, db, factories)
```

## Coverage configuration

```ini
# pyproject.toml / setup.cfg
[tool.coverage.run]
source = ["src"]
omit = ["tests/*", "*/__init__.py", "*/migrations/*"]
branch = true

[tool.coverage.report]
fail_under = 80   # ajustar conforme tier (80% development, 90% production)
```

## Anti-patterns

- `unittest.mock.patch` em demasia — prefira injeção de dependência real em testes de integração.
- `sleep()` em testes assíncronos — use `pytest-anyio` com `await asyncio.sleep(0)` se necessário.
- Banco de dados compartilhado entre testes paralelos sem isolamento.
- Testar apenas happy path — incluir: input inválido, auth falha, 404, rate limit, DB constraint.

## Checklist rápido (auto-QA Akita suporte)

- [ ] Cada endpoint tem ≥1 unit test de handler + ≥1 integration test com DB real
- [ ] Auth paths têm 100% unit coverage (token ausente, expirado, inválido, válido)
- [ ] Erros de validação de input testados (400 Bad Request com schema errado)
- [ ] Coverage ≥ threshold do tier (ver `_config/profile-effective.yaml`)
- [ ] PII não aparece em logs de teste
