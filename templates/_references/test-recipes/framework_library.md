# Test Recipe — framework_library

> Test strategy reference for reusable libraries/frameworks (published to a registry).
> Read by the discovery session (stage 01) and used to fill §Test Strategy in plan.md (stage 02).

## Library specifics

Libraries are consumed by unknown code. This requires:
- **Higher coverage** (+10% vs tier default) — a silent edge-case failure breaks N downstream projects.
- **100% unit tested public API** — consumers use only the public API; gaps = surprises.
- **Backward compat tests** — prevent accidental breaking changes.
- **Doctests** — docstring examples are executable and simultaneously test docs + code.

## Required test types

| Type | What it tests | When to use |
|---|---|---|
| **Unit** | Every isolated public function | Always |
| **Integration** | Feature combinations, composite cases | Features that interact with each other |
| **Doctest** | Docstring examples | Every public function with an example |
| **Property-based** | Mathematical/contract invariants | Transformations, codecs, parsers |

## Recommended frameworks

| Type | Python | TypeScript/JS |
|---|---|---|
| Unit + Integration | `pytest` | `vitest` or `jest` |
| Doctest | `doctest` (stdlib) or `pytest --doctest-modules` | `tsdoc` examples |
| Property-based | `hypothesis` | `fast-check` |

## Essential patterns

### Explicitly tested public API

```python
# Each function/class exported in __init__.py must have a test case
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
        result = parse("key:value_with_unicode")
        assert result["key"] == "value_with_unicode"
```

### Executable doctests

```python
def format_date(date: datetime, locale: str = "en-US") -> str:
    """Format a datetime in the specified locale.

    Args:
        date: datetime to format
        locale: locale string (default: en-US)

    Returns:
        Formatted string

    Examples:
        >>> from datetime import datetime
        >>> format_date(datetime(2026, 1, 15), locale="en-US")
        '01/15/2026'
        >>> format_date(datetime(2026, 1, 15), locale="pt-BR")
        '15/01/2026'
    """
    ...
```

```ini
# pytest.ini — enable doctests
[pytest]
addopts = --doctest-modules
```

### Property-based with Hypothesis

```python
from hypothesis import given, strategies as st

@given(st.text(min_size=1))
def test_parse_format_roundtrip(value: str):
    """parse(format(x)) must return x for any valid input."""
    formatted = format(value)
    parsed = parse(formatted)
    assert parsed == value
```

### Backward compat test

```python
# tests/compat/test_v1_api.py
# Ensures the v1 API still works in the current version

def test_v1_parse_signature_still_works():
    """parse(str) -> dict still works (was the v1 signature)."""
    result = parse("key:value")
    assert isinstance(result, dict)

def test_v1_error_class_still_importable():
    """ParseError still importable from the v1 path."""
    from mylib.errors import ParseError  # do not break existing importers
    assert ParseError is not None
```

## File structure

```
tests/
  unit/
    test_parse.py         # each public function
    test_format.py
    test_validate.py
  integration/
    test_parse_format.py  # feature combinations
  compat/
    test_v1_api.py        # backward compat
  property_based/
    test_roundtrips.py    # Hypothesis
```

## Coverage for libraries

```ini
# pyproject.toml
[tool.coverage.report]
fail_under = 90   # +10% vs tier default; libraries need high coverage
exclude_lines = [
    "if TYPE_CHECKING:",
    "@(abc\\.)?abstractmethod",
]
```

## Anti-patterns

- Testing only the happy path — library edge cases silently break downstream.
- No error type tests — consumers depend on specific exception types.
- Outdated doctests (not run in CI) — docs lie about behavior.
- No property-based tests for parsing/transformation functions — input space is large.
- Breaking change without a major version bump — cover with compat tests.

## Quick checklist (auto-QA Akita support)

- [ ] 100% of public API functions/classes have a unit test
- [ ] Doctests exist and pass (`pytest --doctest-modules`)
- [ ] Property-based tests for parse/format/transform functions
- [ ] Backward compat tests for the previous version's API
- [ ] Coverage ≥ tier threshold + 10% (see `_config/profile-effective.yaml`)
- [ ] Exception types tested (not just error messages)
