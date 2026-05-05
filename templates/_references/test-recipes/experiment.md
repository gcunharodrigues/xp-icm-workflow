# Test Recipe — experiment

> Test strategy reference for throwaway spikes/POCs.
> Read by the discovery session (stage 01).

## No mandatory test requirements

Profile `experiment` (any tier) has `test_types_required: []` — a throwaway spike does not require a formal test suite.

## When to write tests anyway

- Discovered something that will become `development` later → write a "proof of concept" unit test.
- The POC's main function may be reused → extract and test it before promoting.
- Want to document "why this approach works" → a test as executable documentation.

## If you decide to write tests

```python
# Basic pytest is enough — no coverage overhead, no targets
def test_poc_core_idea_works():
    """POC: confirms that library X does what we expect."""
    result = new_library.do_thing("input")
    assert result is not None  # proves it does not blow up
    assert "expected_key" in result
```

## Promotion to development

If the POC becomes a real project, invoke `/xp-icm-workflow` with `tier=development` and use the recipe for the correct profile (`app_web_backend`, `agent_ia`, etc.) as the starting point for the Test Strategy.
