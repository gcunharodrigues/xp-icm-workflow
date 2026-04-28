# Test Recipe — experiment

> Referência de estratégia de teste para spikes/POCs descartáveis.
> Lido pela sessão de discovery (stage 01).

## Sem requisitos de teste obrigatórios

Profile `experiment` (tier qualquer) tem `test_types_required: []` — spike descartável não exige suite de testes formal.

## Quando escrever testes mesmo assim

- Descobriu algo que vai virar `development` depois → escreva um unit test de "prova de conceito".
- A função principal do POC pode ser reutilizada → extraia e teste ela antes de promover.
- Quer documentar "por que esta abordagem funciona" → um test como documentação executável.

## Se decidir escrever testes

```python
# Basta pytest básico — sem overhead de coverage, sem metas
def test_poc_core_idea_works():
    """POC: confirma que a biblioteca X faz o que esperamos."""
    result = new_library.do_thing("input")
    assert result is not None  # prova que não explode
    assert "expected_key" in result
```

## Promoção para development

Se o POC virar projeto real, invocar `/xp-icm-workflow` com `tier=development` e usar a receita do profile correto (`app_web_backend`, `agent_ia`, etc.) como ponto de partida para a Test Strategy.
