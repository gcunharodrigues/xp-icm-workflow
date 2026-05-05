# Test Recipe — ml_project

> Test strategy reference for ML pipelines (training, eval, serving).
> Read by the discovery session (stage 01) and used to fill §Test Strategy in plan.md (stage 02).

## Required test types

| Type | What it tests | When to use |
|---|---|---|
| **Unit** | Transformation functions, feature engineering, metrics | All pure Python logic |
| **Pipeline** | Pipeline stages: ingest → transform → train → eval | Stage integration with fixture data |
| **Model regression** | Model performance has not regressed vs baseline (dev/prod) | After retraining or feature changes |

## Recommended frameworks

| Type | Framework |
|---|---|
| Unit + Pipeline | `pytest` + `pytest-mock` |
| Data validation | `great_expectations` or `pandera` |
| Model performance | `pytest` with metric assertions, `mlflow` for logging |
| Property-based | `hypothesis` for data transformations |

## Essential patterns

### Transformation unit test

```python
# src/features/normalize.py
def normalize_age(age: float, min_age: float = 0, max_age: float = 120) -> float:
    if age < min_age or age > max_age:
        raise ValueError(f"age {age} out of range [{min_age}, {max_age}]")
    return (age - min_age) / (max_age - min_age)

# tests/unit/test_normalize.py
def test_normalize_age_midpoint():
    assert normalize_age(60) == pytest.approx(0.5)

def test_normalize_age_boundary_values():
    assert normalize_age(0) == 0.0
    assert normalize_age(120) == 1.0

def test_normalize_age_invalid_raises():
    with pytest.raises(ValueError):
        normalize_age(-1)
```

### Pipeline smoke test with data fixture

```python
# tests/integration/test_pipeline_smoke.py
@pytest.fixture
def sample_dataset(tmp_path):
    """Minimal dataset covering all pipeline cases."""
    df = pd.DataFrame({
        "age": [25, 40, 55, None],  # includes missing value
        "income": [50000, 80000, 120000, 60000],
        "label": [0, 1, 1, 0],
    })
    path = tmp_path / "sample.parquet"
    df.to_parquet(path)
    return path

def test_pipeline_runs_without_error(sample_dataset, tmp_path):
    """Full pipeline does not raise with minimal data."""
    result = run_pipeline(input_path=sample_dataset, output_dir=tmp_path)
    assert result["status"] == "success"
    assert (tmp_path / "predictions.parquet").exists()

def test_pipeline_handles_missing_values(sample_dataset, tmp_path):
    """Pipeline handles NaN without crashing."""
    result = run_pipeline(input_path=sample_dataset, output_dir=tmp_path)
    predictions = pd.read_parquet(tmp_path / "predictions.parquet")
    assert predictions.shape[0] == 4  # no rows lost
    assert predictions["prediction"].notna().all()
```

### Model regression test

```python
# tests/model_eval/test_regression.py
BASELINE_METRICS = {
    "accuracy": 0.85,
    "f1_weighted": 0.83,
    "roc_auc": 0.90,
}
TOLERANCE = 0.02  # accepts up to 2pp drop

@pytest.fixture
def eval_dataset():
    """Fixed evaluation dataset — MUST NOT change between runs."""
    return load_dataset("tests/fixtures/eval_set_v1.parquet")

def test_model_accuracy_not_regressed(trained_model, eval_dataset):
    X, y = eval_dataset
    predictions = trained_model.predict(X)
    actual_accuracy = accuracy_score(y, predictions)
    baseline = BASELINE_METRICS["accuracy"]
    assert actual_accuracy >= baseline - TOLERANCE, (
        f"Accuracy regressed: {actual_accuracy:.3f} < baseline {baseline:.3f} - tolerance {TOLERANCE}"
    )
```

## File structure

```
tests/
  unit/
    test_features_normalize.py
    test_features_encode.py
    test_metrics_custom.py
  integration/
    test_pipeline_smoke.py
    test_data_validation.py
  model_eval/
    test_regression.py
    test_model_serving.py
  fixtures/
    sample_dataset.parquet     # small (< 1000 rows), versioned in git
    eval_set_v1.parquet        # fixed evaluation dataset — DO NOT modify
```

## Anti-patterns

- Using the training dataset for model regression — contamination; use a separate fixed split.
- Randomly generated data fixtures without a fixed seed — flaky tests.
- Exact equality assertions on ML floats — use `pytest.approx` or a threshold.
- Pipeline tests that download data from the internet — use fixture data in `tests/fixtures/`.
- No fixed dataset for regression — each re-run compares against a different baseline.

## Quick checklist (auto-QA Akita support)

- [ ] All feature engineering functions have unit tests
- [ ] Pipeline smoke test covers missing values, boundary cases
- [ ] Fixture dataset is small (< 1000 rows) and committed
- [ ] Model regression test exists with baseline and tolerance declared
- [ ] Eval dataset is separate from training and DOES NOT change between runs
- [ ] Property-based tests for critical transformations (via Hypothesis)
