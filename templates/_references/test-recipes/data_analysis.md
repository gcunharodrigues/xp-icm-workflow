# Test Recipe — data_analysis

> Referência de estratégia de teste para análises pontuais e notebooks orientados a relatório.
> Lido pela sessão de discovery (stage 01) e usado para preencher §Test Strategy no plan.md (stage 02).

## Contexto: análise vs produto

Data analysis é diferente de produção. O objetivo é **reprodutibilidade** e **correção dos cálculos**,
não cobertura de branches de software. Notebooks em si não são testados diretamente — as funções extraídas deles sim.

## Tipos de teste obrigatórios

| Tipo | O que testa | Quando usar |
|---|---|---|
| **Unit** | Funções de transformação extraídas do notebook | Toda lógica reutilizável |

## Padrão: Extract-Transform-Test

```
notebook_analysis.ipynb
  → extrai funções para src/transforms.py
  → testa src/transforms.py com pytest
  → notebook importa de src/ e orquestra
```

## Frameworks recomendados

| Tipo | Framework |
|---|---|
| Unit | `pytest` |
| Notebook execution (smoke) | `nbmake` ou `pytest-notebook` |
| Data validation | `pandera` |

## Padrões essenciais

### Unit test de transformação

```python
# src/analysis/clean.py
def remove_outliers_iqr(series: pd.Series, multiplier: float = 1.5) -> pd.Series:
    Q1, Q3 = series.quantile([0.25, 0.75])
    IQR = Q3 - Q1
    return series[(series >= Q1 - multiplier * IQR) & (series <= Q3 + multiplier * IQR)]

# tests/unit/test_clean.py
def test_remove_outliers_removes_extreme_values():
    data = pd.Series([1, 2, 3, 4, 5, 100])  # 100 é outlier
    result = remove_outliers_iqr(data)
    assert 100 not in result.values
    assert len(result) == 5

def test_remove_outliers_no_outliers_returns_unchanged():
    data = pd.Series([1, 2, 3, 4, 5])
    result = remove_outliers_iqr(data)
    assert len(result) == len(data)
```

### Smoke test de notebook (opcional)

```bash
# pytest --nbmake notebooks/analysis.ipynb
# Garante que o notebook roda sem exceção com dados de fixture
```

## Estrutura de arquivos

```
src/
  analysis/
    clean.py           # funções de limpeza extraídas
    aggregate.py       # funções de agregação
    visualize.py       # helpers de visualização
tests/
  unit/
    test_clean.py
    test_aggregate.py
notebooks/
  main_analysis.ipynb  # importa de src/analysis/
data/
  fixtures/
    sample_input.parquet  # amostra pequena para testes
```

## Anti-patterns

- Testar notebooks diretamente sem extrair funções — notebooks são difíceis de testar.
- Fixtures que baixam dados da internet em CI — usar dados versionados em `data/fixtures/`.
- Coverage 100% forçada em código exploratório — foco nos cálculos críticos.

## Checklist rápido

- [ ] Funções de transformação extraídas do notebook e testadas isoladamente
- [ ] Notebook smoke test (se CI suportar `nbmake`)
- [ ] Fixtures de dados pequenas e commitadas em `data/fixtures/`
- [ ] Edge cases: NaN, empty DataFrame, tipos incorretos
