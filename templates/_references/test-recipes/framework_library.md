# Test Recipe — framework_library

> Referência de estratégia de teste para bibliotecas/frameworks reutilizáveis (publicados em registry).
> Lido pela sessão de discovery (stage 01) e usado para preencher §Test Strategy no plan.md (stage 02).

## Especificidade de libraries

Libraries são consumidas por código desconhecido. Isso exige:
- **Coverage mais alta** (+10% vs tier default) — falha silenciosa de um edge case quebra N projetos downstream.
- **API pública 100% unit tested** — consumidores usam apenas a API pública; gaps = surpresas.
- **Backward compat tests** — previnem breaking changes acidentais.
- **Doctests** — exemplos na docstring são executáveis e testam simultaneamente docs + código.

## Tipos de teste obrigatórios

| Tipo | O que testa | Quando usar |
|---|---|---|
| **Unit** | Toda função pública isolada | Sempre |
| **Integration** | Combinações de features, casos compostos | Features que interagem entre si |
| **Doctest** | Exemplos na docstring | Toda função pública com exemplo |
| **Property-based** | Invariantes matemáticos/de contrato | Transformações, codecs, parseadores |

## Frameworks recomendados

| Tipo | Python | TypeScript/JS |
|---|---|---|
| Unit + Integration | `pytest` | `vitest` ou `jest` |
| Doctest | `doctest` (stdlib) ou `pytest --doctest-modules` | `tsdoc` examples |
| Property-based | `hypothesis` | `fast-check` |

## Padrões essenciais

### API pública explicitamente testada

```python
# Cada função/classe exportada em __init__.py deve ter test case
# src/mylib/__init__.py exports: parse, format, validate

# tests/unit/test_parse.py
class TestParse:
    def test_parse_valid_input(self):
        result = parse("input:value")
        assert result == {"input": "value"}

    def test_parse_empty_string_returns_none(self):
        assert parse("") is None

    def test_parse_invalid_format_raises_ParseError(self):
        with pytest.raises(ParseError, match="invalid format"):
            parse("no colon here")

    def test_parse_unicode_input(self):
        result = parse("chave:valor_com_açúcar")
        assert result["chave"] == "valor_com_açúcar"
```

### Doctests executáveis

```python
def format_date(date: datetime, locale: str = "pt-BR") -> str:
    """Formata datetime no locale especificado.

    Args:
        date: datetime a formatar
        locale: locale string (default: pt-BR)

    Returns:
        String formatada

    Examples:
        >>> from datetime import datetime
        >>> format_date(datetime(2026, 1, 15), locale="pt-BR")
        '15/01/2026'
        >>> format_date(datetime(2026, 1, 15), locale="en-US")
        '01/15/2026'
    """
    ...
```

```ini
# pytest.ini — habilitar doctests
[pytest]
addopts = --doctest-modules
```

### Property-based com Hypothesis

```python
from hypothesis import given, strategies as st

@given(st.text(min_size=1))
def test_parse_format_roundtrip(value: str):
    """parse(format(x)) deve retornar x para qualquer input válido."""
    formatted = format(value)
    parsed = parse(formatted)
    assert parsed == value
```

### Backward compat test

```python
# tests/compat/test_v1_api.py
# Garante que API da v1 ainda funciona na versão atual

def test_v1_parse_signature_still_works():
    """parse(str) -> dict ainda funciona (era a assinatura da v1)."""
    result = parse("key:value")
    assert isinstance(result, dict)

def test_v1_error_class_still_importable():
    """ParseError ainda importável do path v1."""
    from mylib.errors import ParseError  # não quebre importers existentes
    assert ParseError is not None
```

## Estrutura de arquivos

```
tests/
  unit/
    test_parse.py         # cada função pública
    test_format.py
    test_validate.py
  integration/
    test_parse_format.py  # combinações de features
  compat/
    test_v1_api.py        # backward compat
  property_based/
    test_roundtrips.py    # Hypothesis
```

## Coverage para libraries

```ini
# pyproject.toml
[tool.coverage.report]
fail_under = 90   # +10% vs tier default; libraries precisam cobertura alta
exclude_lines = [
    "if TYPE_CHECKING:",
    "@(abc\\.)?abstractmethod",
]
```

## Anti-patterns

- Testar apenas happy path — edge cases de library quebram downstream silenciosamente.
- Sem testes de error types — consumers dependem dos tipos de exceção específicos.
- Doctests desatualizados (não executados em CI) — docs mentem sobre o comportamento.
- Sem property-based tests para funções de parsing/transformação — espaço de inputs é grande.
- Breaking change sem major version bump — cobrir com compat tests.

## Checklist rápido (auto-QA Akita suporte)

- [ ] 100% das funções/classes da API pública têm unit test
- [ ] Doctests existem e passam (`pytest --doctest-modules`)
- [ ] Property-based tests para funções de parse/format/transform
- [ ] Backward compat tests para API da versão anterior
- [ ] Coverage ≥ tier threshold + 10% (ver `_config/profile-effective.yaml`)
- [ ] Tipos de exceção testados (não apenas mensagem de erro)
