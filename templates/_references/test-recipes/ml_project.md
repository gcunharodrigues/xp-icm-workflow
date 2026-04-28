# Test Recipe — ml_project

> Referência de estratégia de teste para pipelines ML (treino, eval, serving).
> Lido pela sessão de discovery (stage 01) e usado para preencher §Test Strategy no plan.md (stage 02).

## Tipos de teste obrigatórios

| Tipo | O que testa | Quando usar |
|---|---|---|
| **Unit** | Funções de transformação, feature engineering, métricas | Toda lógica Python pura |
| **Pipeline** | Etapas do pipeline: ingest → transform → train → eval | Integração entre etapas com dados de fixture |
| **Model regression** | Performance do modelo não regrediu vs baseline (dev/prod) | Após re-treino ou mudança de features |

## Frameworks recomendados

| Tipo | Framework |
|---|---|
| Unit + Pipeline | `pytest` + `pytest-mock` |
| Data validation | `great_expectations` ou `pandera` |
| Model performance | `pytest` com asserções de métricas, `mlflow` para logging |
| Property-based | `hypothesis` para transformações de dados |

## Padrões essenciais

### Unit test de transformação

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

### Pipeline smoke test com fixture de dados

```python
# tests/integration/test_pipeline_smoke.py
@pytest.fixture
def sample_dataset(tmp_path):
    """Dataset mínimo que cobre todos os casos do pipeline."""
    df = pd.DataFrame({
        "age": [25, 40, 55, None],  # inclui missing value
        "income": [50000, 80000, 120000, 60000],
        "label": [0, 1, 1, 0],
    })
    path = tmp_path / "sample.parquet"
    df.to_parquet(path)
    return path

def test_pipeline_runs_without_error(sample_dataset, tmp_path):
    """Pipeline completo não lança exceção com dados mínimos."""
    result = run_pipeline(input_path=sample_dataset, output_dir=tmp_path)
    assert result["status"] == "success"
    assert (tmp_path / "predictions.parquet").exists()

def test_pipeline_handles_missing_values(sample_dataset, tmp_path):
    """Pipeline trata NaN sem crashar."""
    result = run_pipeline(input_path=sample_dataset, output_dir=tmp_path)
    predictions = pd.read_parquet(tmp_path / "predictions.parquet")
    assert predictions.shape[0] == 4  # sem linhas perdidas
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
TOLERANCE = 0.02  # aceita até 2pp de queda

@pytest.fixture
def eval_dataset():
    """Dataset de avaliação fixo — NÃO pode mudar entre runs."""
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

## Estrutura de arquivos

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
    sample_dataset.parquet     # pequeno (< 1000 rows), versionado em git
    eval_set_v1.parquet        # dataset de avaliação fixo — NÃO modificar
```

## Anti-patterns

- Usar o dataset de treino para regressão de modelo — contaminação; usar split separado fixo.
- Fixtures de dados geradas aleatoriamente sem seed fixo — testes flaky.
- Assertions de igualdade exata em floats de ML — usar `pytest.approx` ou threshold.
- Pipeline test que baixa dados da internet — usar dados de fixture em `tests/fixtures/`.
- Sem dataset fixo para regressão — cada re-run compara baseline diferente.

## Checklist rápido (auto-QA Akita suporte)

- [ ] Todas as funções de feature engineering têm unit tests
- [ ] Pipeline smoke test cobre missing values, boundary cases
- [ ] Dataset de fixture é pequeno (< 1000 rows) e commitado
- [ ] Model regression test existe com baseline e tolerance declarados
- [ ] Eval dataset é separado do treino e NÃO muda entre runs
- [ ] Property-based tests para transformações críticas (via Hypothesis)
