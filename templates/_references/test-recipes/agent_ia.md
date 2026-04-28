# Test Recipe — agent_ia

> Referência de estratégia de teste para agentes LLM, orquestradores com tools, e skills/MCP.
> Lido pela sessão de discovery (stage 01) e usado para preencher §Test Strategy no plan.md (stage 02).

## Desafio central: não-determinismo

LLM outputs são não-determinísticos por natureza. TDD clássico RED→GREEN pressupõe outputs deterministicos.
Estratégia: **isolar o determinístico (tools) do não-determinístico (LLM output)**.

| Camada | Testabilidade | Estratégia |
|---|---|---|
| Tool functions | Determinística | Unit test clássico |
| Tool dispatch (agente chama tool certa?) | Semi-determinística | Integration test com LLM real ou mock |
| Output do LLM | Não-determinístico | Eval framework (similarity, rubric, judge) |
| Comportamento de prompt | Parcialmente determinístico | Golden output comparison com threshold |

## Tipos de teste

### 1. Unit tests de tools

```python
# tools/search.py
def search_documents(query: str, limit: int = 5) -> list[dict]:
    """Tool determinística — testável classicamente."""
    ...

# tests/unit/test_tools_search.py
def test_search_returns_at_most_limit_results(mock_db):
    results = search_documents("python testing", limit=3)
    assert len(results) <= 3

def test_search_empty_query_returns_empty():
    results = search_documents("", limit=5)
    assert results == []

def test_search_result_has_required_fields(mock_db):
    results = search_documents("pytest")
    for r in results:
        assert "title" in r and "content" in r and "score" in r
```

### 2. Integration tests — tool dispatch

```python
# Testar se o agente invoca a tool correta dado um prompt fixo.
# Usar LLM real com seed fixo OU mockar o LLM e testar a lógica de routing.

def test_agent_calls_search_tool_for_query(agent, mock_llm):
    """Mock LLM retorna tool_call fixo; valida que agent executa corretamente."""
    mock_llm.returns_tool_call("search_documents", {"query": "testing"})
    result = agent.run("Busque documentos sobre testing")
    assert mock_llm.tool_calls[0]["name"] == "search_documents"
    assert result["documents_found"] >= 0
```

### 3. Eval — golden output comparison

```python
# Usar framework de eval (DeepEval, PromptFoo, ou custom)
# Golden output = resposta esperada gravada manualmente

import json
from difflib import SequenceMatcher

GOLDEN_OUTPUTS_DIR = "tests/evals/golden/"

def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def test_summarization_matches_golden(agent):
    input_doc = open("tests/fixtures/input_doc.txt").read()
    golden = open(f"{GOLDEN_OUTPUTS_DIR}/summarize_input_doc.txt").read()

    actual = agent.run(f"Summarize: {input_doc}")
    score = similarity(actual, golden)
    assert score >= 0.85, f"Similarity {score:.2f} below threshold 0.85"
```

## Frameworks de eval recomendados

| Framework | Uso | URL |
|---|---|---|
| `deepeval` | Métricas LLM (faithfulness, answer relevancy, hallucination) | deepeval.com |
| `promptfoo` | Comparação de prompts, CI-friendly, YAML config | promptfoo.dev |
| `ragas` | Específico para RAG (context precision, recall) | ragas.io |
| Custom similarity | Simples, sem dependência, threshold ajustável | Ver exemplo acima |

## Estrutura de arquivos

```
tests/
  unit/
    test_tool_search.py       # tools determinísticas
    test_tool_format.py
    test_context_manager.py   # lógica de contexto
  integration/
    test_agent_routing.py     # dispatch de tools com mock LLM
    test_agent_error_handling.py
  evals/
    golden/
      summarize_doc.txt       # outputs esperados gravados manualmente
      classify_intent.json
    test_summarization.py     # eval similarity
    test_intent_classification.py
  fixtures/
    input_doc.txt
    sample_conversation.json
```

## Determinismo nos evals

```python
# Usar seed fixo quando o LLM suportar (Anthropic não suporta seed, mas temperatura 0 reduz variância)
client = anthropic.Anthropic()
response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    temperature=0,  # reduz (não elimina) variância
    messages=[{"role": "user", "content": prompt}],
)
```

## Anti-patterns

- Assertions de string exata em outputs LLM — use similarity threshold.
- Testar o LLM em si (não é responsabilidade do projeto) — testar a *integração* com ele.
- Golden outputs sem data de criação — LLM behavior muda entre versões de modelo.
- Sem fixture de prompt: testar com prompt variável → flaky test.
- Mock total do LLM em integration tests: perde cobertura real de tool parsing.

## Checklist rápido (auto-QA Akita suporte)

- [ ] Toda tool function tem ≥1 unit test clássico
- [ ] Tool dispatch testado com mock LLM (agente chama tool certa?)
- [ ] Eval de golden output existe para o output principal do agente
- [ ] Similarity threshold ≥ 0.85 (ou justificado no plan.md se menor)
- [ ] Temperatura 0 nos evals para reduzir variância
- [ ] Golden outputs commitados em `tests/evals/golden/` com data de criação
