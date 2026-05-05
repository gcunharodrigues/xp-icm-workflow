# Test Recipe — dashboard

> Test strategy reference for analytics dashboards (Streamlit, Dash, Looker, Superset, Metabase).
> Read by the discovery session (stage 01) and used to fill §Test Strategy in plan.md (stage 02).

## Required test types

| Type | What it tests | When to use |
|---|---|---|
| **Unit** | Data transformation functions, metric calculations, formatting | All pure Python/SQL logic |
| **Integration** | Query against test DB, data pipeline to final DataFrame | Full data flow |

## Recommended frameworks

| Type | Framework |
|---|---|
| Unit + Integration | `pytest` |
| DB fixtures | `pytest-postgresql` / SQLite in-memory / `duckdb` |
| Streamlit testing | `streamlit.testing.v1.AppTest` |
| Dash testing | `dash.testing` + `pytest-dash` |
| Data validation | `pandera` |

## Essential patterns

### Unit test for a calculated metric

```python
# src/metrics/revenue.py
def calculate_mrr(subscriptions: list[dict]) -> float:
    """Calculates Monthly Recurring Revenue."""
    return sum(s["amount"] for s in subscriptions if s["status"] == "active")

# tests/unit/test_metrics_revenue.py
def test_mrr_sum_active_only():
    subs = [
        {"amount": 100, "status": "active"},
        {"amount": 200, "status": "cancelled"},  # should not count
        {"amount": 150, "status": "active"},
    ]
    assert calculate_mrr(subs) == 250.0

def test_mrr_empty_returns_zero():
    assert calculate_mrr([]) == 0.0
```

### Integration test for query + pipeline

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

### Streamlit AppTest (if using Streamlit)

```python
from streamlit.testing.v1 import AppTest

def test_dashboard_renders_without_error():
    at = AppTest.from_file("src/app.py")
    at.run()
    assert not at.exception

def test_filter_updates_chart(mock_db):
    at = AppTest.from_file("src/app.py")
    at.run()
    # Simulate date filter selection
    at.selectbox[0].set_value("2026-01").run()
    assert "january" in at.markdown[0].value.lower()
```

## File structure

```
tests/
  unit/
    test_metrics_revenue.py
    test_metrics_churn.py
    test_formatters.py        # number/date formatting
  integration/
    test_queries_revenue.py   # queries against test DB
    test_pipeline_etl.py      # ETL end-to-end with DuckDB/SQLite
```

## Anti-patterns

- Testing queries against the production database — use an isolated DB fixture.
- No edge value tests: zero subscriptions, negative values, invalid dates.
- Relying on committed real data — use factories or SQL INSERT in fixtures.

## Quick checklist

- [ ] Each business metric has an isolated unit test
- [ ] Queries tested against a fixture DB (DuckDB or SQLite)
- [ ] Edge cases: empty dataset, null values, boundary dates
- [ ] Coverage ≥ tier threshold
