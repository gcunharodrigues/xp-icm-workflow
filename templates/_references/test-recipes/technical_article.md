# Test Recipe — technical_article

> Referência de estratégia de teste para artigos técnicos longos com código embutido.
> Lido pela sessão de discovery (stage 01).

## Contexto: artigo vs produto

Artigos técnicos têm código embutido como ilustração. O risco é que os exemplos de código no artigo estejam errados ou desatualizados. Testar snippets executáveis garante que o artigo "não mente".

## Tipos de teste

| Tipo | O que testa | Obrigatório? |
|---|---|---|
| **Unit** | Funções auxiliares usadas nos exemplos | Apenas se forem reutilizáveis |
| **Doctest** | Snippets de código no corpo do artigo | Recomendado para snippets Python |
| **Notebook execution** | Notebook completo roda sem erro | Se o artigo for um notebook |

## Padrão: snippets testados via doctest

```python
# Se o artigo tem um snippet como este:
# ---
# ```python
# >>> from mylib import compute
# >>> compute(10)
# 42
# ```
# ---
# Garanta que o snippet é um doctest real na função:

def compute(x: int) -> int:
    """Computa o resultado.

    >>> compute(10)
    42
    >>> compute(0)
    0
    """
    return x * 4 + 2
```

## Anti-pattern

- Snippets de código no artigo que nunca são executados em CI → artigo publica código errado.
- Código de exemplo com `...` ou placeholders que não rodam — ou são explicitamente marcados como pseudocódigo.

## Checklist rápido

- [ ] Snippets executáveis no artigo são doctests ou estão em arquivo testável
- [ ] Notebook (se for o formato) passa em `nbmake` sem exceção
- [ ] Exemplos com outputs esperados confirmados manualmente antes de publicar
