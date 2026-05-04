# Mocking Guidelines — Canonical (v3.9.0)

> **Versão:** v3.9.0
> **Skill:** `xp-icm-workflow`
> **Estágio consumidor:** `04_implementation_waves` (writer subagente, ciclo TDD vertical)
> **Propósito:** documento canônico de mocking — alinhado com mattpocock principles. Mock só boundaries (HTTP/DB/time/randomness/env); nunca internals do projeto. Aplicável todos profiles (backend, frontend, fullstack, ml, agent_ia).

## Resumo (1 parágrafo)

Mock é ferramenta para isolar **boundaries externos** (rede, disco, time, randomness, env). Não é ferramenta para evitar entender o sistema. Internals do projeto (helpers, classes, services) NÃO devem ser mockados — testar com objetos reais é mais lento mas mais correto. Quando o teste fica lento OR difícil, o sinal é que o módulo deveria ser refatorado (single responsibility violation, dependências erradas, abstração leaky), não que precisa de mock.

## Os 5 boundaries — únicos casos legítimos

| Boundary | Mock action | Lib típica |
|----------|-------------|------------|
| HTTP / network | intercept request, return canned response | msw, nock, requests-mock, vcr |
| Database | use real DB (sqlite in-memory OR test container) preferred; mock só quando schema é externalizado | testcontainers, sqlite-memory |
| Time / clock | freeze OR advance manually | freezegun, sinon.useFakeTimers |
| Randomness | seed fix; OR inject random fn | seed param, dependency injection |
| Env vars / secrets | set test value via fixture | pytest fixture, vitest setup, env file |

**Regra:** se o boundary não está nesta lista, NÃO mock.

## Anti-patterns — proibidos

| Anti-pattern | Por que ruim | Alternativa |
|--------------|--------------|-------------|
| Mock helper interno (`utils/format-date.ts`) | esconde bug real do helper; test verde mas sistema quebrado | usar helper real; se lento, refatorar helper |
| Mock service injetado (`UserService` num test de `AuthController`) | acopla test à arquitetura; refactor quebra mock; coverage falsa | usar instância real com fixtures (DB seeded) |
| Mock factory que retorna mock factory | indireção sem benefício; debug impossível | direct fake object com 3-5 props essenciais |
| `jest.mock('./module')` sem boundary justification | "mock por hábito"; perde cobertura sem ganho | remove mock; se lento, identifica boundary real |
| Mock que retorna sempre `undefined` | test não exercita lógica; só não-explode | fixture com dados reais (golden path + edge case) |

## Por que não mockar internals (mattpocock alignment)

Mock interno = test acopla-se à implementação atual, não ao contrato. Quando refactor muda implementação (mas preserva contrato), test quebra falsamente. Inverso também: bug interno passa despercebido porque mock retorna o que test esperava.

Sinais de design ruim mascarados por mock interno:
- Função X depende de 5 services → mock todos → test "passa" mas sistema real falha por ordering
- Helper formata date → mock helper → bug em formato edge (DST, UTC offset) só descoberto em prod
- Class herda 3 níveis → mock parent → child override quebra invariant não testado

**Heurística:** se você precisa mockar mais que 2 internals para um test rodar, o módulo sob teste tem responsabilidade demais.

## Per-profile guidance

### Backend (`app_web_backend`)
- DB: testcontainer (PostgreSQL/MySQL real) OR sqlite in-memory.
- HTTP outbound: msw OR nock.
- Cache (Redis): test container OR fakeredis.
- Queue: test broker OR in-memory bus.

### Frontend (`app_web_frontend`)
- HTTP: msw browser handlers (intercept fetch/XHR).
- Component children: render tree real; mock só quando child faz HTTP/storage.
- localStorage/sessionStorage: in-memory shim ou jest-localstorage-mock.
- Router: real router com test history.

### Fullstack
- Sum dos dois. Critical: e2e tests usam DB real + frontend real (sem mock entre layers).

### ML / agent_ia
- Model inference: cache golden output (fixture); skip live API.
- Randomness: seed fix obrigatório.
- External tools (web search, files): mock fixture.
- Token consumption: test isolado por contract validation, não geração real.

## Tier-aware enforcement

Forensic+ Check 6 (NÃO QUERO violations) e Check 7 (ADR import drift) detectam padrões proibidos automaticamente quando:
- Bloco NÃO QUERO da task declara "no mock for internals"
- ADR aplicável proíbe lib específica (ex: jest.mock disabled em path crítico)

Tier production: violation = HARD. Tier dev: SOFT. Tier exp/tool: ignored.

## Examples

### ✅ Bom — boundary mock

```python
# test_user_service.py
import requests_mock

def test_user_creation_calls_audit_api(db_session):
    with requests_mock.Mocker() as m:
        m.post("https://audit.internal/log", status_code=204)
        service = UserService(db=db_session)  # DB real
        user = service.create(email="x@y.com")
        assert user.id
        assert m.called
```

DB real (sqlite in-memory via fixture). HTTP boundary mocked.

### ❌ Ruim — internal mock

```python
# test_user_service.py
def test_user_creation(mocker):
    mock_validator = mocker.patch("app.services.validate_email")
    mock_validator.return_value = True
    mock_audit = mocker.patch("app.services.AuditClient")
    mock_audit.return_value.log.return_value = None
    service = UserService(db=mocker.MagicMock())  # DB mock
    user = service.create(email="invalid-email")
    assert user  # passes — mas sistema real rejeitaria!
```

Validator mockado (esconde bug real). DB mockado. AuditClient mockado. Test verde mas inútil.

### ✅ Bom — time mock

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

Time é boundary. Mock OK. Lógica de expiry roda real.

## Integração com 4-block contract

Bloco NÃO QUERO de task pode declarar mocks proibidos:

```markdown
### NÃO QUERO
- Mock de UserService nem AuditClient (use instâncias reais com DB seeded)
- jest.mock em qualquer arquivo dentro de src/auth/
```

Forensic+ Check 6 detecta diff que viola declaração. HARD em tier production.

## Cross-references

- 4-block contract: `references/4-block-contract-template.md` (bloco NÃO QUERO)
- Forensic+ Check 6: `references/forensic-plus-protocol.md`
- ADR format: `references/adr-format.md`
- Stage 04 runtime: `templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl`
- Source upstream: mattpocock/skills/testing/test-style-guidelines (philosophy alignment, não copy)
