# Test Recipe — agent_ia

> Test strategy reference for LLM agents, tool-based orchestrators, and skills/MCP.
> Read by the discovery session (stage 01) and used to fill §Test Strategy in plan.md (stage 02).

## Core challenge: non-determinism

LLM outputs are non-deterministic by nature. Classic TDD RED→GREEN assumes deterministic outputs.
Strategy: **isolate the deterministic (tools) from the non-deterministic (LLM output)**.

| Layer | Testability | Strategy |
|---|---|---|
| Tool functions | Deterministic | Classic unit test |
| Tool dispatch (does the agent call the right tool?) | Semi-deterministic | Integration test with real LLM or mock |
| LLM output | Non-deterministic | Eval framework (similarity, rubric, judge) |
| Prompt behavior | Partially deterministic | Golden output comparison with threshold |

## Test types

### 1. Tool unit tests

```python
# tools/search.py
def search_documents(query: str, limit: int = 5) -> list[dict]:
    """Deterministic tool — classically testable."""
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
# Test whether the agent invokes the correct tool given a fixed prompt.
# Use a real LLM with a fixed seed OR mock the LLM and test the routing logic.

def test_agent_calls_search_tool_for_query(agent, mock_llm):
    """Mock LLM returns fixed tool_call; validates that agent executes correctly."""
    mock_llm.returns_tool_call("search_documents", {"query": "testing"})
    result = agent.run("Search for documents about testing")
    assert mock_llm.tool_calls[0]["name"] == "search_documents"
    assert result["documents_found"] >= 0
```

### 3. Eval — golden output comparison

```python
# Use an eval framework (DeepEval, PromptFoo, or custom)
# Golden output = expected response recorded manually

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

## Recommended eval frameworks

| Framework | Use | URL |
|---|---|---|
| `deepeval` | LLM metrics (faithfulness, answer relevancy, hallucination) | deepeval.com |
| `promptfoo` | Prompt comparison, CI-friendly, YAML config | promptfoo.dev |
| `ragas` | RAG-specific (context precision, recall) | ragas.io |
| Custom similarity | Simple, no dependency, adjustable threshold | See example above |

## File structure

```
tests/
  unit/
    test_tool_search.py       # deterministic tools
    test_tool_format.py
    test_context_manager.py   # context logic
  integration/
    test_agent_routing.py     # tool dispatch with mock LLM
    test_agent_error_handling.py
  evals/
    golden/
      summarize_doc.txt       # expected outputs recorded manually
      classify_intent.json
    test_summarization.py     # eval similarity
    test_intent_classification.py
  fixtures/
    input_doc.txt
    sample_conversation.json
```

## Determinism in evals

```python
# Use a fixed seed when the LLM supports it (Anthropic does not support seed, but temperature 0 reduces variance)
client = anthropic.Anthropic()
response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    temperature=0,  # reduces (does not eliminate) variance
    messages=[{"role": "user", "content": prompt}],
)
```

## Anti-patterns

- Exact string assertions on LLM outputs — use similarity threshold.
- Testing the LLM itself (not the project's responsibility) — test the *integration* with it.
- Golden outputs without a creation date — LLM behavior changes between model versions.
- No prompt fixture: testing with variable prompt → flaky test.
- Full LLM mock in integration tests: loses real tool parsing coverage.

## Quick checklist (auto-QA Akita support)

- [ ] Every tool function has ≥1 classic unit test
- [ ] Tool dispatch tested with mock LLM (does agent call the right tool?)
- [ ] Golden output eval exists for the agent's main output
- [ ] Similarity threshold ≥ 0.85 (or justified in plan.md if lower)
- [ ] Temperature 0 in evals to reduce variance
- [ ] Golden outputs committed in `tests/evals/golden/` with creation date
