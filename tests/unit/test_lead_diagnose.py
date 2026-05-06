"""Unit tests for scripts/lead-diagnose.py (v3.9.0).

Cobertura:
- jaccard correctness (set-based similarity)
- catastrophic detector signals (massive scope creep, tests outside scope)
- action recommendation per trigger condition
- surgical brief render for RETRY (top-3 concerns + acceptance delta)
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "lead_diagnose", REPO_ROOT / "scripts" / "lead-diagnose.py",
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def ld():
    return _load_module()


# ============================================================================
# Jaccard correctness
# ============================================================================

def test_jaccard_identical_sets(ld):
    assert ld.jaccard({"a", "b", "c"}, {"a", "b", "c"}) == 1.0


def test_jaccard_disjoint_sets(ld):
    assert ld.jaccard({"a", "b"}, {"c", "d"}) == 0.0


def test_jaccard_partial_overlap(ld):
    # |A ∩ B| = 2 ({a,b}), |A ∪ B| = 4 ({a,b,c,d}) → 0.5
    assert ld.jaccard({"a", "b", "c"}, {"a", "b", "d"}) == 0.5


def test_jaccard_empty_sets(ld):
    assert ld.jaccard(set(), set()) == 0.0


def test_jaccard_one_empty(ld):
    assert ld.jaccard({"a"}, set()) == 0.0


# ============================================================================
# Critic concerns clustering
# ============================================================================

def test_critic_to_set_filters_minor(ld):
    critic = {
        "concerns": [
            {"claim": "missing edge case for empty input", "severity": "BLOCKING"},
            {"claim": "naming nit on processData", "severity": "MINOR"},
            {"claim": "unhandled timeout exception", "severity": "MAJOR"},
        ],
    }
    s = ld._critic_to_set(critic)
    assert len(s) == 2  # MINOR filtered
    # Tokens should normalize to alphanum sets
    assert any("missing" in token or "edge" in token for token in s)


def test_normalize_claim_token_extraction(ld):
    """Claim normalization extracts >=4 char tokens, lowercased, sorted set."""
    sig = ld._normalize_claim("Missing EDGE CASE for empty input")
    # Should contain "edge", "case", "missing", "empty", "input"
    tokens = sig.split()
    assert "missing" in tokens
    assert "edge" in tokens


# ============================================================================
# Bucket recommendation
# ============================================================================

def test_recommend_action_t1_cap_exhausted(ld):
    bucket, rationale = ld.recommend_action(
        trigger="T1_cap_exhausted",
        catastrophic_signals=[],
        convergence_score=0.3,
    )
    assert bucket == "RETRY"
    assert "Cap" in rationale


def test_recommend_action_t2_convergence(ld):
    bucket, rationale = ld.recommend_action(
        trigger="T2_convergence_trip",
        catastrophic_signals=[],
        convergence_score=0.85,
    )
    assert bucket == "RETRY"
    assert "0.85" in rationale or "convergence" in rationale.lower() or "ambígua" in rationale.lower()


def test_recommend_action_t3_catastrophic_with_b3_hint(ld):
    bucket, rationale = ld.recommend_action(
        trigger="T3_catastrophic",
        catastrophic_signals=[
            {"name": "build_globally_broken", "evidence": "exit 1", "action_hint": "VOID"},
        ],
        convergence_score=0.0,
    )
    assert bucket == "VOID"
    assert "catastrophic" in rationale.lower()


def test_recommend_action_unknown_trigger_raises(ld):
    with pytest.raises(ValueError, match="unknown trigger"):
        ld.recommend_action("T99_invalid", [], 0.0)


# ============================================================================
# Catastrophic detector
# ============================================================================

def test_detect_catastrophic_massive_scope_creep(ld, tmp_path):
    """forensic_files_outside > threshold → signal."""
    signals = ld.detect_catastrophic(
        cwd=tmp_path,
        branch="dummy",
        base_branch="main",
        files_touched_declared=[],
        forensic_files_outside=10,  # > CATASTROPHIC_FILES_OUTSIDE_THRESHOLD (5)
    )
    names = [s["name"] for s in signals]
    assert "massive_scope_creep" in names


def test_detect_catastrophic_no_signals_when_under_threshold(ld, tmp_path):
    """forensic_files_outside <= threshold AND no other signals → empty."""
    signals = ld.detect_catastrophic(
        cwd=tmp_path,
        branch="dummy",
        base_branch="main",
        files_touched_declared=[],
        forensic_files_outside=2,
        build_command=None,
    )
    # No build command + git fail (tmp_path has no git) → no signals beyond
    # massive_scope_creep gate. Tests broken outside scope path may not
    # produce signals due to git fail; either way, no massive_scope_creep
    assert all(s["name"] != "massive_scope_creep" for s in signals)


# ============================================================================
# Surgical brief render
# ============================================================================

def test_render_surgical_brief_top_3_concerns(ld):
    """Brief should pick 3 most-recurring claims across rounds."""
    rounds = [
        {
            "concerns": [
                {"claim": "missing edge case empty", "severity": "BLOCKING",
                 "evidence": "src/foo.py:10", "counterexample": "f([]) crashes"},
                {"claim": "wrong type annotation", "severity": "MAJOR",
                 "evidence": "src/foo.py:25", "counterexample": "Optional[int] expected"},
            ],
        },
        {
            "concerns": [
                {"claim": "missing edge case empty input handling", "severity": "BLOCKING",
                 "evidence": "src/foo.py:10", "counterexample": "f([]) crashes"},
            ],
        },
    ]
    brief = ld.render_surgical_brief(rounds)
    assert "Top concerns" in brief or "concerns" in brief.lower()
    assert "Acceptance delta" in brief


def test_render_surgical_brief_empty_rounds(ld):
    """No rounds → graceful no-recurring message."""
    brief = ld.render_surgical_brief([])
    assert "no recurring" in brief.lower()


# ============================================================================
# diagnose() orchestration smoke
# ============================================================================

def test_diagnose_no_trigger_when_rounds_below_cap(ld, tmp_path):
    """rounds < 3, no convergence, no catastrophic → trigger=None."""
    result = ld.diagnose(
        task_slug="test-task",
        wave_num=1,
        rounds=[
            {"concerns": [{"claim": "x", "severity": "BLOCKING"}]},
            {"concerns": [{"claim": "y", "severity": "BLOCKING"}]},  # different
        ],
        files_touched_declared=[],
        cwd=tmp_path,
        branch="dummy",
        base_branch="main",
        forensic_files_outside=0,
        build_command=None,
        explicit_trigger=None,
    )
    assert result["trigger"] is None
    assert result["action"] is None


def test_diagnose_t2_convergence_trip(ld, tmp_path):
    """2 rounds with same recurring concerns (Jaccard >= 0.7) → T2."""
    same_concerns = [
        {"claim": "missing input validation null check", "severity": "BLOCKING"},
        {"claim": "wrong error type raised in boundary", "severity": "MAJOR"},
    ]
    result = ld.diagnose(
        task_slug="test-task",
        wave_num=1,
        rounds=[
            {"concerns": same_concerns},
            {"concerns": same_concerns},  # Jaccard = 1.0
        ],
        files_touched_declared=[],
        cwd=tmp_path,
        branch="dummy",
        base_branch="main",
        forensic_files_outside=0,
        build_command=None,
        explicit_trigger=None,
    )
    assert result["trigger"] == "T2_convergence_trip"
    assert result["action"] == "RETRY"


def test_diagnose_t3_catastrophic_overrides_other(ld, tmp_path):
    """Catastrophic signal trumps cap/convergence."""
    result = ld.diagnose(
        task_slug="test-task",
        wave_num=1,
        rounds=[{"concerns": []}],
        files_touched_declared=[],
        cwd=tmp_path,
        branch="dummy",
        base_branch="main",
        forensic_files_outside=10,  # > threshold
        build_command=None,
        explicit_trigger=None,
    )
    assert result["trigger"] == "T3_catastrophic"
    assert result["action"] == "VOID"


def test_diagnose_t1_cap_exhausted(ld, tmp_path):
    """3 rounds with completely distinct claims (no token sharing) → T1, not T2."""
    rounds = [
        {"concerns": [{"claim": "missing input validation null check", "severity": "BLOCKING"}]},
        {"concerns": [{"claim": "wrong return type annotation", "severity": "BLOCKING"}]},
        {"concerns": [{"claim": "circular dependency between modules", "severity": "BLOCKING"}]},
    ]
    result = ld.diagnose(
        task_slug="test-task",
        wave_num=1,
        rounds=rounds,
        files_touched_declared=[],
        cwd=tmp_path,
        branch="dummy",
        base_branch="main",
        forensic_files_outside=0,
        build_command=None,
        explicit_trigger=None,
    )
    assert result["trigger"] == "T1_cap_exhausted"
    assert result["action"] == "RETRY"


# ============================================================================
# Render diagnose.md schema sanity
# ============================================================================

def test_render_diagnose_md_b1_includes_surgical_brief(ld):
    md = ld.render_diagnose_md(
        task_slug="test",
        wave_num=1,
        trigger="T2_convergence_trip",
        rounds=[{"concerns": [{"claim": "x", "severity": "BLOCKING"}]}],
        convergence_pairs=[(1, 2, 0.85)],
        catastrophic_signals=[],
        action="RETRY",
        rationale="test rationale",
        surgical_brief="(brief content)",
    )
    assert "# Diagnose" in md
    assert "## Trigger" in md
    assert "## Action recommendation" in md
    assert "## Surgical brief" in md
    assert "(brief content)" in md


def test_render_diagnose_md_b3_no_surgical_brief(ld):
    md = ld.render_diagnose_md(
        task_slug="test",
        wave_num=1,
        trigger="T3_catastrophic",
        rounds=[{"concerns": []}],
        convergence_pairs=[],
        catastrophic_signals=[
            {"name": "build_globally_broken", "evidence": "exit 1", "action_hint": "VOID"},
        ],
        action="VOID",
        rationale="catastrophic",
        surgical_brief=None,
    )
    assert "## Catastrophic signals" in md
    assert "## Surgical brief" not in md
