# Test Recipe — dashboard

> Referência de estratégia de teste para painéis analíticos (Streamlit, Dash, Looker, Superset, Metabase).
> Lido pela sessão de discovery (stage 01) e usado para preencher §Test Strategy no plan.md (stage 02).

## Tipos de teste obrigatórios

| Tipo | O que testa | Quando usar |
|---|---|---|
| **Unit** | Funções de transformação de dados, cálculos de métricas, formatação | Toda lógica Python/SQL pura |
| **Integration** | Query contra DB de teste, pipeline de dados até DataFrame final | Fluxo completo de dados |

## Frameworks recomendados

| Tipo | Framework |
|---|---|
| Unit + Integration | `pytest` |
| DB fixtures | `pytest-postgresql` / SQLite in-memory / `duckdb` |
| Streamlit testing | `streamlit.testing.v1.AppTest` |
| Dash testing | `dash.testing` + `pytest-dash` |
| Data validation | `pandera` |

## Padrões essenciais

### Unit test de métrica calculada

```python
# src/metrics/revenue.py
def calculate_mrr(subscriptions: list[dict]) -> float:
    """Calcula Monthly Recurring Revenue."""
    return sum(s["amount"] for s in subscriptions if s["status"] == "active")

# tests/unit/test_metrics_revenue.py
def test_mrr_sum_active_only():
    subs = [
        {"amount": 100, "status": "active"},
        {"amount": 200, "status": "cancelled"},  # não contar
        {"amount": 150, "status": "active"},
    ]
    assert calculate_mrr(subs) == 250.0

def test_mrr_empty_returns_zero():
    assert calculate_mrr([]) == 0.0
```

### Integration test de query + pipeline

```python
# tests/integration/test_revenue_query.py
@pytest.fixture
def test_db(tmp_path):
    import duckdb
    conn = duckdb.connect(str(tmp_path / "test.db"))
    conn.execute("""
        CREATE TABLE subscriptions (id INT, amount FLOAT, status VARCHAR, created_at DATE)
    """)
    conn.execute("""
        INSERT INTO subscriptions VALUES
        (1, 100.0, 'active', '2026-01-01'),
        (2, 200.0, 'cancelled', '2026-01-15'),
        (3, 150.0, 'active', '2026-02-01')
    """)
    yield conn
    conn.close()

def test_revenue_query_returns_correct_mrr(test_db):
    from src.queries.revenue import get_monthly_revenue
    result = get_monthly_revenue(test_db, month="2026-01")
    assert result["mrr"] == pytest.approx(250.0)
    assert result["active_count"] == 2
```

### Streamlit AppTest (se usar Streamlit)

```python
from streamlit.testing.v1 import AppTest

def test_dashboard_renders_without_error():
    at = AppTest.from_file("src/app.py")
    at.run()
    assert not at.exception

def test_filter_updates_chart(mock_db):
    at = AppTest.from_file("src/app.py")
    at.run()
    # Simular seleção de filtro de data
    at.selectbox[0].set_value("2026-01").run()
    assert "janeiro" in at.markdown[0].value.lower()
```

## Estrutura de arquivos

```
tests/
  unit/
    test_metrics_revenue.py
    test_metrics_churn.py
    test_formatters.py        # formatação de números/datas
  integration/
    test_queries_revenue.py   # queries contra DB de teste
    test_pipeline_etl.py      # ETL end-to-end com DuckDB/SQLite
```

## Anti-patterns

- Testar queries contra banco de produção — usar fixture de DB isolado.
- Sem test de valores edge: zero subscriptions, valores negativos, datas inválidas.
- Depender de dados reais commitados — usar factories ou SQL INSERT nos fixtures.

## Checklist rápido

- [ ] Cada métrica de negócio tem unit test isolado
- [ ] Queries testadas contra DB de fixture (DuckDB ou SQLite)
- [ ] Edge cases: empty dataset, valores nulos, datas de borda
- [ ] Coverage ≥ threshold do tier
