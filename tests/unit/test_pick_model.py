"""Unit tests para scripts/pick-model.py (v3.9.0).

Cobertura:
- compute_score determinístico (deterministic per inputs)
- pick_models tier ceiling cap (writer ≤ ceiling, critic = ceiling)
- property-based via Hypothesis: writer ≤ critic; critic = ceiling
- HOT_PATHS bonus
- security_sensitive / public_api_change / algorithm_heavy / doc_only flags
- parse_task_metadata smoke
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from hypothesis import given, strategies as st

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "pick_model", REPO_ROOT / "scripts" / "pick-model.py",
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def pm():
    return _load_module()


# ============================================================================
# compute_score
# ============================================================================

def test_compute_score_minimal_task(pm):
    """Tiny task (no flags): score = 0 (estimated_lines None) - 1 (exp tier) = -1."""
    score = pm.compute_score(
        estimated_lines=None,
        files_touched=[],
        tier="experimental",
    )
    assert score == -1


def test_compute_score_large_task_production(pm):
    """estimated_lines > 200 (+3) + production (+1) = 4."""
    score = pm.compute_score(
        estimated_lines=300,
        files_touched=["src/foo.ts"],
        tier="production",
    )
    assert score == 4


def test_compute_score_security_sensitive_bonus(pm):
    """security_sensitive +3 + medium task +1 = 4."""
    score = pm.compute_score(
        estimated_lines=100,  # > 50
        files_touched=["src/foo.ts"],
        security_sensitive=True,
        tier="development",
    )
    assert score == 4


def test_compute_score_hot_path_match(pm):
    """File in auth/ → +2 hot path bonus."""
    score = pm.compute_score(
        estimated_lines=10,
        files_touched=["src/auth/middleware.ts"],
        tier="development",
    )
    # 0 (lines<50) + 2 (hot) = 2
    assert score == 2


def test_compute_score_doc_only_penalty(pm):
    """doc_only -2."""
    score = pm.compute_score(
        estimated_lines=None,
        files_touched=[],
        doc_only=True,
        tier="development",
    )
    assert score == -2


def test_compute_score_combined_factors(pm):
    """estimated 250 (+3) + hot path (+2) + security (+3) + api change (+2) + production (+1) = 11."""
    score = pm.compute_score(
        estimated_lines=250,
        files_touched=["src/auth/middleware.ts"],
        security_sensitive=True,
        public_api_change=True,
        tier="production",
    )
    assert score == 11


# ============================================================================
# pick_models — tier ceiling cap
# ============================================================================

def test_pick_models_low_score_haiku_writer(pm):
    """score < 2 → writer = haiku."""
    writer, critic = pm.pick_models(score=0, tier="production")
    assert writer == "claude-haiku-4-5"
    assert critic == "claude-opus-4-7"  # tier ceiling


def test_pick_models_medium_score_sonnet_writer(pm):
    """2 <= score < 5 → writer = sonnet."""
    writer, critic = pm.pick_models(score=3, tier="production")
    assert writer == "claude-sonnet-4-6"
    assert critic == "claude-opus-4-7"


def test_pick_models_high_score_opus_writer(pm):
    """score >= 5 → writer = opus (production)."""
    writer, critic = pm.pick_models(score=7, tier="production")
    assert writer == "claude-opus-4-7"
    assert critic == "claude-opus-4-7"


def test_pick_models_experimental_caps_to_haiku(pm):
    """Tier exp ceiling = haiku, even if score high → writer caps at haiku."""
    writer, critic = pm.pick_models(score=10, tier="experimental")
    assert writer == "claude-haiku-4-5"
    assert critic == "claude-haiku-4-5"


def test_pick_models_tool_caps_to_sonnet(pm):
    """Tier tool ceiling = sonnet."""
    writer, critic = pm.pick_models(score=10, tier="tool")
    assert writer == "claude-sonnet-4-6"
    assert critic == "claude-sonnet-4-6"


def test_pick_models_unknown_tier_raises(pm):
    with pytest.raises(ValueError, match="unknown tier"):
        pm.pick_models(score=0, tier="invalid")


# ============================================================================
# Property-based: invariants
# ============================================================================

VALID_TIERS = ("experimental", "tool", "development", "production")


@given(
    score=st.integers(min_value=-10, max_value=20),
    tier=st.sampled_from(VALID_TIERS),
)
def test_property_critic_always_equals_ceiling(score: int, tier: str):
    pm = _load_module()
    writer, critic = pm.pick_models(score, tier)
    assert critic == pm.TIER_CEILING[tier], (
        f"critic {critic} ≠ TIER_CEILING[{tier}] {pm.TIER_CEILING[tier]}"
    )


@given(
    score=st.integers(min_value=-10, max_value=20),
    tier=st.sampled_from(VALID_TIERS),
)
def test_property_writer_le_critic(score: int, tier: str):
    pm = _load_module()
    writer, critic = pm.pick_models(score, tier)
    assert pm.MODEL_RANK[writer] <= pm.MODEL_RANK[critic], (
        f"writer {writer} (rank {pm.MODEL_RANK[writer]}) > "
        f"critic {critic} (rank {pm.MODEL_RANK[critic]})"
    )


@given(
    score=st.integers(min_value=-10, max_value=20),
    tier=st.sampled_from(VALID_TIERS),
)
def test_property_writer_le_tier_ceiling(score: int, tier: str):
    pm = _load_module()
    writer, _ = pm.pick_models(score, tier)
    ceiling = pm.TIER_CEILING[tier]
    assert pm.MODEL_RANK[writer] <= pm.MODEL_RANK[ceiling]


# ============================================================================
# parse_task_metadata smoke
# ============================================================================

def test_parse_task_metadata_basic(pm, tmp_path: Path):
    plan = tmp_path / "plan.md"
    plan.write_text(
        "## Task auth-mw: JWT middleware\n\n"
        "### O QUE\n- Validate JWT in headers (public API change).\n\n"
        "### COMO\n- Use jose lib.\n\n"
        "### NÃO QUERO\n- Decode without verify.\n\n"
        "### VALIDAÇÃO\n- Test missing header → 401.\n\n"
        "### Files touched\n- src/auth/middleware.ts\n- tests/auth/middleware.test.ts\n\n"
        "### Estimated lines\n~150\n\n",
        encoding="utf-8",
    )
    meta = pm.parse_task_metadata(plan, "auth-mw")
    assert meta["estimated_lines"] == 150
    assert "src/auth/middleware.ts" in meta["files_touched"]
    assert meta["security_sensitive"]  # auth/ in path
    assert meta["public_api_change"]   # "public api" in O QUE


def test_parse_task_metadata_doc_only(pm, tmp_path: Path):
    plan = tmp_path / "plan.md"
    plan.write_text(
        "## Task readme-update: Update README\n\n"
        "### O QUE\n- Update docs.\n\n"
        "### COMO\n- Edit README.md.\n\n"
        "### NÃO QUERO\n- Code changes.\n\n"
        "### VALIDAÇÃO\n- README rendered correctly.\n\n"
        "### Files touched\n- README.md\n\n"
        "### Conventions extras\n- doc-only\n\n",
        encoding="utf-8",
    )
    meta = pm.parse_task_metadata(plan, "readme-update")
    assert meta["doc_only"] is True


def test_parse_task_metadata_task_not_found(pm, tmp_path: Path):
    plan = tmp_path / "plan.md"
    plan.write_text("## Task other: unrelated\n", encoding="utf-8")
    with pytest.raises(pm.PlanParseError, match="task slug not found"):
        pm.parse_task_metadata(plan, "missing-slug")


# ============================================================================
# CURRENT_SKILL_VERSION drift sanity
# ============================================================================

def test_current_skill_version_constant_exists(pm):
    """pick-model.py exposes CURRENT_SKILL_VERSION for drift detector."""
    assert hasattr(pm, "CURRENT_SKILL_VERSION")
    assert isinstance(pm.CURRENT_SKILL_VERSION, str)


def test_tier_ceiling_covers_all_valid_tiers(pm):
    """TIER_CEILING dict covers all canonical tiers."""
    for tier in VALID_TIERS:
        assert tier in pm.TIER_CEILING
        assert pm.TIER_CEILING[tier] in pm.MODEL_RANK
