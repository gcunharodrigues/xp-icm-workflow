# Test Recipe — technical_article

> Test strategy reference for long technical articles with embedded code.
> Read by the discovery session (stage 01).

## Context: article vs product

Technical articles have embedded code as illustration. The risk is that the code examples in the article are wrong or outdated. Testing executable snippets ensures the article "does not lie".

## Test types

| Type | What it tests | Required? |
|---|---|---|
| **Unit** | Helper functions used in examples | Only if reusable |
| **Doctest** | Code snippets in the article body | Recommended for Python snippets |
| **Notebook execution** | Full notebook runs without error | If the article is a notebook |

## Pattern: snippets tested via doctest

```python
# If the article has a snippet like this:
# ---
# ```python
# >>> from mylib import compute
# >>> compute(10)
# 42
# ```
# ---
# Ensure the snippet is a real doctest in the function:

def compute(x: int) -> int:
    """Computes the result.

    >>> compute(10)
    42
    >>> compute(0)
    0
    """
    return x * 4 + 2
```

## Anti-pattern

- Code snippets in the article that are never run in CI → article publishes wrong code.
- Example code with `...` or placeholders that do not run — or are explicitly marked as pseudocode.

## Quick checklist

- [ ] Executable snippets in the article are doctests or in a testable file
- [ ] Notebook (if that is the format) passes `nbmake` without exception
- [ ] Examples with expected outputs confirmed manually before publishing
