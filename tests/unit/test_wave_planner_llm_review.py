"""Testes unitarios para wave-planner-llm-review.py.

Cobertura:
  - Skip threshold (<=2 tasks ou <=1 wave)
  - Pass-through de respostas APPROVE / PROPOSE_CHANGES validas
  - Validacao de schema (verdict enum, issues, proposed_dag_changes)
  - Erros de mock ausente / NotImplementedError em prod
  - CLI canonico (escreve output json)
  - Property: todas as 3 verdict-strings validam OK quando bem formadas
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

# ----------------------------------------------------------------------------
# Boot do script como modulo (hifen no nome impede import direto)
# ----------------------------------------------------------------------------
SKILL_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = SKILL_ROOT / "scripts" / "wave-planner-llm-review.py"
MOCKS_DIR = SKILL_ROOT / "tests" / "mocks" / "llm_review_responses"

_spec = importlib.util.spec_from_file_location("wave_planner_llm_review", SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
wave_planner_llm_review = importlib.util.module_from_spec(_spec)
sys.modules["wave_planner_llm_review"] = wave_planner_llm_review
_spec.loader.exec_module(wave_planner_llm_review)

LLMReviewError = wave_planner_llm_review.LLMReviewError
WavePlanSummary = wave_planner_llm_review.WavePlanSummary
parse_wave_plan = wave_planner_llm_review.parse_wave_plan
should_skip = wave_planner_llm_review.should_skip
request_review = wave_planner_llm_review.request_review
validate_response = wave_planner_llm_review.validate_response
build_skipped_verdict = wave_planner_llm_review.build_skipped_verdict
main = wave_planner_llm_review.main


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def _write_wave_plan(path: Path, *, total_tasks: int, total_waves: int, total_sub_waves: int | None = None) -> None:
    """Escreve um wave-plan.md minimo com frontmatter compativel."""
    if total_sub_waves is None:
        total_sub_waves = total_waves
    fm_lines = [
        "---",
        "generated_at: 2026-04-25T00:00:00Z",
        "plan_source: stages/02_design/output/plan.md",
        "tier: development",
        "profile: app_web_backend",
        "cap_subagents_per_wave: 5",
        f"total_tasks: {total_tasks}",
        f"total_waves: {total_waves}",
        f"total_sub_waves: {total_sub_waves}",
        "llm_review: PENDING",
        "llm_review_iterations: 0",
        "---",
        "",
        "# Wave Plan",
        "",
    ]
    path.write_text("\n".join(fm_lines), encoding="utf-8")


def _write_plan_stub(path: Path) -> None:
    path.write_text("# Plan stub\n\n## Task t1: T1\n", encoding="utf-8")


def _write_ambiguities_stub(path: Path) -> None:
    path.write_text("# Ambiguities Resolved\n\nNenhuma ambiguidade.\n", encoding="utf-8")


def _make_workspace(tmp_path: Path, *, total_tasks: int, total_waves: int) -> dict[str, Path]:
    wave_plan = tmp_path / "wave-plan.md"
    plan = tmp_path / "plan.md"
    amb = tmp_path / "ambiguities-resolved.md"
    output = tmp_path / "llm-review-verdict.json"
    _write_wave_plan(wave_plan, total_tasks=total_tasks, total_waves=total_waves)
    _write_plan_stub(plan)
    _write_ambiguities_stub(amb)
    return {"wave_plan": wave_plan, "plan": plan, "amb": amb, "output": output}


def _argv(paths: dict[str, Path], *, mock: Path | None = None) -> list[str]:
    args = [
        "--wave-plan", str(paths["wave_plan"]),
        "--plan", str(paths["plan"]),
        "--ambiguities", str(paths["amb"]),
        "--output", str(paths["output"]),
    ]
    if mock is not None:
        args += ["--mock-response", str(mock)]
    return args


# ============================================================================
# 1. Skip threshold tests
# ============================================================================

def test_skip_when_only_2_tasks(tmp_path):
    paths = _make_workspace(tmp_path, total_tasks=2, total_waves=2)
    rc = main(_argv(paths))
    assert rc == 0
    out = json.loads(paths["output"].read_text(encoding="utf-8"))
    assert out["verdict"] == "SKIPPED"
    assert out["skip_reason"] == "total_tasks=2"
    assert out["issues"] == []
    assert out["proposed_dag_changes"] == []


def test_skip_when_only_1_wave(tmp_path):
    paths = _make_workspace(tmp_path, total_tasks=5, total_waves=1)
    rc = main(_argv(paths))
    assert rc == 0
    out = json.loads(paths["output"].read_text(encoding="utf-8"))
    assert out["verdict"] == "SKIPPED"
    assert out["skip_reason"] == "total_waves=1"


def test_skip_reason_recorded_in_output(tmp_path):
    paths = _make_workspace(tmp_path, total_tasks=2, total_waves=3)
    rc = main(_argv(paths))
    assert rc == 0
    out = json.loads(paths["output"].read_text(encoding="utf-8"))
    assert out["verdict"] == "SKIPPED"
    assert out["skip_reason"] == "total_tasks=2"


def test_should_skip_unit():
    assert should_skip(WavePlanSummary(total_tasks=2, total_waves=4, total_sub_waves=4)) == (True, "total_tasks=2")
    assert should_skip(WavePlanSummary(total_tasks=8, total_waves=1, total_sub_waves=1)) == (True, "total_waves=1")
    assert should_skip(WavePlanSummary(total_tasks=8, total_waves=3, total_sub_waves=3)) == (False, "")


# ============================================================================
# 2. APPROVE pass-through
# ============================================================================

def test_approve_response_passes_through(tmp_path):
    paths = _make_workspace(tmp_path, total_tasks=8, total_waves=3)
    mock = MOCKS_DIR / "approve_clean.json"
    rc = main(_argv(paths, mock=mock))
    assert rc == 0
    out = json.loads(paths["output"].read_text(encoding="utf-8"))
    assert out["verdict"] == "APPROVE"
    assert out["issues"] == []
    assert out["proposed_dag_changes"] == []


# ============================================================================
# 3. PROPOSE_CHANGES validation
# ============================================================================

def test_propose_changes_response_validates(tmp_path):
    paths = _make_workspace(tmp_path, total_tasks=8, total_waves=3)
    mock = MOCKS_DIR / "propose_implicit_dep.json"
    rc = main(_argv(paths, mock=mock))
    assert rc == 0
    out = json.loads(paths["output"].read_text(encoding="utf-8"))
    assert out["verdict"] == "PROPOSE_CHANGES"
    assert len(out["issues"]) == 2
    assert len(out["proposed_dag_changes"]) == 1
    assert out["proposed_dag_changes"][0]["action"] == "add_dep"


# ============================================================================
# 4. Invalid verdict in mock
# ============================================================================

def test_invalid_verdict_in_mock_raises(tmp_path, capsys):
    paths = _make_workspace(tmp_path, total_tasks=8, total_waves=3)
    mock = MOCKS_DIR / "invalid_verdict.json"
    rc = main(_argv(paths, mock=mock))
    assert rc == 1
    captured = capsys.readouterr()
    assert "invalid verdict" in captured.err.lower() or "MAYBE" in captured.err


# ============================================================================
# 5. Missing issues field
# ============================================================================

def test_missing_issues_field_raises(tmp_path, capsys):
    paths = _make_workspace(tmp_path, total_tasks=8, total_waves=3)
    bad_mock = tmp_path / "bad.json"
    bad_mock.write_text(
        json.dumps({"verdict": "PROPOSE_CHANGES", "proposed_dag_changes": []}),
        encoding="utf-8",
    )
    rc = main(_argv(paths, mock=bad_mock))
    assert rc == 1
    captured = capsys.readouterr()
    assert "issues" in captured.err.lower()


def test_missing_proposed_dag_changes_raises(tmp_path, capsys):
    paths = _make_workspace(tmp_path, total_tasks=8, total_waves=3)
    bad_mock = tmp_path / "bad.json"
    bad_mock.write_text(
        json.dumps({"verdict": "APPROVE", "issues": []}),
        encoding="utf-8",
    )
    rc = main(_argv(paths, mock=bad_mock))
    assert rc == 1
    captured = capsys.readouterr()
    assert "proposed_dag_changes" in captured.err.lower()


# ============================================================================
# 6. Sem mock + sem Task tool -> NotImplementedError -> exit 1
# ============================================================================

def test_no_mock_no_task_tool_raises(tmp_path, capsys):
    paths = _make_workspace(tmp_path, total_tasks=8, total_waves=3)
    rc = main(_argv(paths))  # sem --mock-response
    assert rc == 1
    captured = capsys.readouterr()
    assert "task tool integration is wave 5+" in captured.err.lower()


# ============================================================================
# 7. CLI canonical writes output json
# ============================================================================

def test_cli_canonical_writes_output_json(tmp_path):
    paths = _make_workspace(tmp_path, total_tasks=8, total_waves=3)
    mock = MOCKS_DIR / "approve_clean.json"
    rc = main(_argv(paths, mock=mock))
    assert rc == 0
    assert paths["output"].exists()
    parsed = json.loads(paths["output"].read_text(encoding="utf-8"))
    assert parsed["verdict"] == "APPROVE"


def test_cli_creates_output_parent_dir(tmp_path):
    paths = _make_workspace(tmp_path, total_tasks=8, total_waves=3)
    paths["output"] = tmp_path / "deep" / "nested" / "verdict.json"
    mock = MOCKS_DIR / "approve_clean.json"
    rc = main(_argv(paths, mock=mock))
    assert rc == 0
    assert paths["output"].exists()


def test_cli_stdout_format(tmp_path, capsys):
    paths = _make_workspace(tmp_path, total_tasks=8, total_waves=3)
    mock = MOCKS_DIR / "propose_implicit_dep.json"
    rc = main(_argv(paths, mock=mock))
    assert rc == 0
    captured = capsys.readouterr()
    # Format: verdict=X issues=N proposed_changes=M skipped=true|false
    assert "verdict=PROPOSE_CHANGES" in captured.out
    assert "issues=2" in captured.out
    assert "proposed_changes=1" in captured.out
    assert "skipped=false" in captured.out


def test_cli_stdout_format_skipped(tmp_path, capsys):
    paths = _make_workspace(tmp_path, total_tasks=2, total_waves=2)
    rc = main(_argv(paths))
    assert rc == 0
    captured = capsys.readouterr()
    assert "verdict=SKIPPED" in captured.out
    assert "skipped=true" in captured.out


# ============================================================================
# 8. Property-based: every valid verdict normalizes cleanly
# ============================================================================

def _make_response(verdict: str) -> dict:
    base = {"verdict": verdict, "issues": [], "proposed_dag_changes": []}
    if verdict == "SKIPPED":
        base["skip_reason"] = "total_tasks=2"
    return base


@pytest.mark.parametrize("verdict", ["APPROVE", "PROPOSE_CHANGES", "SKIPPED"])
def test_validate_response_accepts_all_valid_verdicts(verdict):
    resp = _make_response(verdict)
    out = validate_response(resp)
    assert out["verdict"] == verdict
    assert out["issues"] == []
    assert out["proposed_dag_changes"] == []


# ============================================================================
# 9. validate_response edge cases
# ============================================================================

def test_validate_rejects_non_dict():
    with pytest.raises(LLMReviewError, match="must be a dict"):
        validate_response(["not", "a", "dict"])


def test_validate_rejects_invalid_issue_type():
    bad = {
        "verdict": "PROPOSE_CHANGES",
        "issues": [{
            "type": "BOGUS_TYPE",
            "from": "a",
            "to": "b",
            "reason": "x",
            "severity": "warning",
        }],
        "proposed_dag_changes": [],
    }
    with pytest.raises(LLMReviewError, match="type"):
        validate_response(bad)


def test_validate_rejects_invalid_severity():
    bad = {
        "verdict": "PROPOSE_CHANGES",
        "issues": [{
            "type": "implicit_dep",
            "from": "a",
            "to": "b",
            "reason": "x",
            "severity": "blocker",
        }],
        "proposed_dag_changes": [],
    }
    with pytest.raises(LLMReviewError, match="severity"):
        validate_response(bad)


def test_validate_rejects_invalid_action():
    bad = {
        "verdict": "PROPOSE_CHANGES",
        "issues": [],
        "proposed_dag_changes": [{"action": "delete_universe"}],
    }
    with pytest.raises(LLMReviewError, match="action"):
        validate_response(bad)


def test_validate_rejects_issue_missing_field():
    bad = {
        "verdict": "PROPOSE_CHANGES",
        "issues": [{"type": "implicit_dep", "from": "a", "to": "b"}],  # falta reason+severity
        "proposed_dag_changes": [],
    }
    with pytest.raises(LLMReviewError, match="missing key"):
        validate_response(bad)


def test_validate_rejects_issues_not_list():
    bad = {
        "verdict": "APPROVE",
        "issues": "not a list",
        "proposed_dag_changes": [],
    }
    with pytest.raises(LLMReviewError, match="must be a list"):
        validate_response(bad)


# ============================================================================
# 10. parse_wave_plan edge cases
# ============================================================================

def test_parse_wave_plan_missing_file(tmp_path):
    with pytest.raises(LLMReviewError, match="not found"):
        parse_wave_plan(tmp_path / "nonexistent.md")


def test_parse_wave_plan_no_frontmatter(tmp_path):
    p = tmp_path / "wp.md"
    p.write_text("# No frontmatter here\n", encoding="utf-8")
    with pytest.raises(LLMReviewError, match="frontmatter"):
        parse_wave_plan(p)


def test_parse_wave_plan_missing_total_tasks(tmp_path):
    p = tmp_path / "wp.md"
    p.write_text(
        "---\ntotal_waves: 3\ntotal_sub_waves: 3\n---\n\n# Body\n",
        encoding="utf-8",
    )
    with pytest.raises(LLMReviewError, match="total_tasks"):
        parse_wave_plan(p)


def test_parse_wave_plan_unclosed_frontmatter(tmp_path):
    p = tmp_path / "wp.md"
    p.write_text("---\ntotal_tasks: 5\n", encoding="utf-8")
    with pytest.raises(LLMReviewError, match="not closed"):
        parse_wave_plan(p)


def test_parse_wave_plan_canonical(tmp_path):
    p = tmp_path / "wp.md"
    _write_wave_plan(p, total_tasks=8, total_waves=3, total_sub_waves=4)
    summary = parse_wave_plan(p)
    assert summary.total_tasks == 8
    assert summary.total_waves == 3
    assert summary.total_sub_waves == 4


# ============================================================================
# 11. request_review (mock vs prod)
# ============================================================================

def test_request_review_with_mock(tmp_path):
    mock = tmp_path / "m.json"
    mock.write_text(json.dumps({"verdict": "APPROVE", "issues": [], "proposed_dag_changes": []}), encoding="utf-8")
    out = request_review("wp", "p", "amb", mock_response_path=mock)
    assert out["verdict"] == "APPROVE"


def test_request_review_mock_missing_file(tmp_path):
    with pytest.raises(LLMReviewError, match="not found"):
        request_review("wp", "p", "amb", mock_response_path=tmp_path / "absent.json")


def test_request_review_mock_invalid_json(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(LLMReviewError, match="invalid JSON"):
        request_review("wp", "p", "amb", mock_response_path=bad)


def test_request_review_no_mock_raises_not_implemented():
    with pytest.raises(NotImplementedError, match="Wave 5"):
        request_review("wp", "p", "amb", mock_response_path=None)


# ============================================================================
# 12. build_skipped_verdict
# ============================================================================

def test_build_skipped_verdict_shape():
    v = build_skipped_verdict("total_tasks=2")
    assert v == {
        "verdict": "SKIPPED",
        "issues": [],
        "proposed_dag_changes": [],
        "skip_reason": "total_tasks=2",
    }
