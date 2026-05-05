# Test Recipe — data_analysis

> Test strategy reference for one-off analyses and report-oriented notebooks.
> Read by the discovery session (stage 01) and used to fill §Test Strategy in plan.md (stage 02).

## Context: analysis vs product

Data analysis is different from production. The goal is **reproducibility** and **correctness of calculations**,
not branch coverage of software. Notebooks themselves are not tested directly — the functions extracted from them are.

## Required test types

| Type | What it tests | When to use |
|---|---|---|
| **Unit** | Transformation functions extracted from the notebook | All reusable logic |

## Pattern: Extract-Transform-Test

```
notebook_analysis.ipynb
  → extract functions to src/transforms.py
  → test src/transforms.py with pytest
  → notebook imports from src/ and orchestrates
```

## Recommended frameworks

| Type | Framework |
|---|---|
| Unit | `pytest` |
| Notebook execution (smoke) | `nbmake` or `pytest-notebook` |
| Data validation | `pandera` |

## Essential patterns

### Transformation unit test

```python
# src/analysis/clean.py
def remove_outliers_iqr(series: pd.Series, multiplier: float = 1.5) -> pd.Series:
    Q1, Q3 = series.quantile([0.25, 0.75])
    IQR = Q3 - Q1
    return series[(series >= Q1 - multiplier * IQR) & (series <= Q3 + multiplier * IQR)]

# tests/unit/test_clean.py
def test_remove_outliers_removes_extreme_values():
    data = pd.Series([1, 2, 3, 4, 5, 100])  # 100 is an outlier
    result = remove_outliers_iqr(data)
    assert 100 not in result.values
    assert len(result) == 5

def test_remove_outliers_no_outliers_returns_unchanged():
    data = pd.Series([1, 2, 3, 4, 5])
    result = remove_outliers_iqr(data)
    assert len(result) == len(data)
```

### Notebook smoke test (optional)

```bash
# pytest --nbmake notebooks/analysis.ipynb
# Ensures the notebook runs without exception with fixture data
```

## File structure

```
src/
  analysis/
    clean.py           # extracted cleaning functions
    aggregate.py       # aggregation functions
    visualize.py       # visualization helpers
tests/
  unit/
    test_clean.py
    test_aggregate.py
notebooks/
  main_analysis.ipynb  # imports from src/analysis/
data/
  fixtures/
    sample_input.parquet  # small sample for tests
```

## Anti-patterns

- Testing notebooks directly without extracting functions — notebooks are hard to test.
- Fixtures that download data from the internet in CI — use versioned data in `data/fixtures/`.
- Forced 100% coverage on exploratory code — focus on critical calculations.

## Quick checklist

- [ ] Transformation functions extracted from the notebook and tested in isolation
- [ ] Notebook smoke test (if CI supports `nbmake`)
- [ ] Small data fixtures committed in `data/fixtures/`
- [ ] Edge cases: NaN, empty DataFrame, incorrect types
