"""Testes unitarios para profile-merge.py."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

# Carrega scripts/profile-merge.py como modulo (hifen no nome impede import direto)
SKILL_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = SKILL_ROOT / "scripts" / "profile-merge.py"

_spec = importlib.util.spec_from_file_location("profile_merge", SCRIPT_PATH)
profile_merge = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules["profile_merge"] = profile_merge
_spec.loader.exec_module(profile_merge)  # type: ignore[union-attr]

ProfileMergeError = profile_merge.ProfileMergeError
merge_profile = profile_merge.merge_profile
compute_hash = profile_merge.compute_hash
CANONICAL_PROFILES = profile_merge.CANONICAL_PROFILES
CANONICAL_TIERS = profile_merge.CANONICAL_TIERS


# ----------------------------------------------------------------------------
# 1. Cobertura completa: 10 profiles x 4 tiers
# ----------------------------------------------------------------------------

def test_canonical_profiles_count():
    assert len(CANONICAL_PROFILES) == 10
    assert set(CANONICAL_PROFILES) == {
        "app_web_backend",
        "app_web_frontend",
        "dashboard",
        "data_analysis",
        "ml_project",
        "agent_ia",
        "cli_tool",
        "framework_library",
        "technical_article",
        "experiment",
    }


def test_canonical_tiers_count():
    assert len(CANONICAL_TIERS) == 4
    assert set(CANONICAL_TIERS) == {"experimental", "tool", "development", "production"}


@pytest.mark.parametrize("profile", [
    "app_web_backend", "app_web_frontend", "dashboard", "data_analysis",
    "ml_project", "agent_ia", "cli_tool", "framework_library",
    "technical_article", "experiment",
])
@pytest.mark.parametrize("tier", ["experimental", "tool", "development", "production"])
def test_all_combos_return_valid_dict(profile, tier):
    effective, _hash = merge_profile(profile=profile, tier=tier)
    assert isinstance(effective, dict)
    assert effective["profile"] == profile
    assert effective["tier"] == tier
    # Chaves obrigatorias da matriz
    for key in (
        "stages_skipped",
        "tdd_required",
        "security_gate",
        "tech_debt_tracking",
        "peer_review_required",
        "cap_teammates_per_wave",
        "stop_points_calibration",
    ):
        assert key in effective, f"chave {key!r} faltando para {profile}/{tier}"


# ----------------------------------------------------------------------------
# 2. Hash determinismo
# ----------------------------------------------------------------------------

def test_hash_is_deterministic_same_input():
    a, hash_a = merge_profile(profile="app_web_backend", tier="development")
    b, hash_b = merge_profile(profile="app_web_backend", tier="development")
    assert hash_a == hash_b
    assert a == b


def test_hash_differs_for_different_profiles():
    _, hash_a = merge_profile(profile="app_web_backend", tier="development")
    _, hash_b = merge_profile(profile="cli_tool", tier="development")
    assert hash_a != hash_b


def test_hash_differs_for_different_tiers():
    _, hash_a = merge_profile(profile="app_web_backend", tier="experimental")
    _, hash_b = merge_profile(profile="app_web_backend", tier="production")
    assert hash_a != hash_b


def test_hash_is_sha256_hex():
    _, h = merge_profile(profile="experiment", tier="experimental")
    assert len(h) == 64
    int(h, 16)  # nao levanta = hex valido


# ----------------------------------------------------------------------------
# 3. Defaults concretos por tier (sem profile override)
# ----------------------------------------------------------------------------

def test_experimental_defaults():
    eff, _ = merge_profile(profile="cli_tool", tier="experimental")
    assert eff["tdd_required"] is False  # optional -> False
    assert eff["security_gate"] is False
    assert eff["tech_debt_tracking"] is False
    assert eff["peer_review_required"] is False
    assert eff["cap_teammates_per_wave"] == 2
    assert eff["stop_points_calibration"]["item_5"]["limite_mensal_BRL"] == 50


def test_tool_defaults():
    eff, _ = merge_profile(profile="cli_tool", tier="tool")
    assert eff["tdd_required"] is False  # recommended -> False
    assert eff["security_gate"] is False
    assert eff["tech_debt_tracking"] is True
    assert eff["peer_review_required"] is False
    assert eff["cap_teammates_per_wave"] == 3
    assert eff["stop_points_calibration"]["item_5"]["limite_mensal_BRL"] == 200


def test_development_defaults():
    eff, _ = merge_profile(profile="cli_tool", tier="development")
    assert eff["tdd_required"] is True
    assert eff["security_gate"] is True
    assert eff["tech_debt_tracking"] is True
    assert eff["peer_review_required"] is False
    assert eff["cap_teammates_per_wave"] == 5
    assert eff["stop_points_calibration"]["item_5"]["limite_mensal_BRL"] == 500


def test_production_defaults():
    eff, _ = merge_profile(profile="cli_tool", tier="production")
    assert eff["tdd_required"] is True
    assert eff["security_gate"] is True
    assert eff["tech_debt_tracking"] is True
    assert eff["peer_review_required"] is True
    assert eff["cap_teammates_per_wave"] == 5
    assert eff["stop_points_calibration"]["item_5"]["limite_mensal_BRL"] == 1000


# ----------------------------------------------------------------------------
# 4. Profile-specific overrides na matriz
# ----------------------------------------------------------------------------

def test_experiment_skips_stages_03_05_06_08():
    for tier in CANONICAL_TIERS:
        eff, _ = merge_profile(profile="experiment", tier=tier)
        assert sorted(eff["stages_skipped"]) == ["03", "05", "06", "08"]


def test_technical_article_skips_stage_03():
    eff, _ = merge_profile(profile="technical_article", tier="development")
    assert "03" in eff["stages_skipped"]


def test_framework_library_cap_is_3():
    for tier in CANONICAL_TIERS:
        eff, _ = merge_profile(profile="framework_library", tier=tier)
        assert eff["cap_teammates_per_wave"] == 3


def test_ml_project_cap_is_3():
    for tier in CANONICAL_TIERS:
        eff, _ = merge_profile(profile="ml_project", tier=tier)
        assert eff["cap_teammates_per_wave"] == 3


def test_technical_article_cap_is_5():
    for tier in CANONICAL_TIERS:
        eff, _ = merge_profile(profile="technical_article", tier=tier)
        assert eff["cap_teammates_per_wave"] == 5


def test_app_web_security_gate_above_experimental():
    # Regra: security_gate True para app_web_* em qualquer tier != experimental
    for profile in ["app_web_backend", "app_web_frontend"]:
        eff_exp, _ = merge_profile(profile=profile, tier="experimental")
        assert eff_exp["security_gate"] is False
        for tier in ["tool", "development", "production"]:
            eff, _ = merge_profile(profile=profile, tier=tier)
            assert eff["security_gate"] is True, f"{profile}/{tier} deveria ter security_gate"


# ----------------------------------------------------------------------------
# 5. Override via .icm-profile.local.yaml
# ----------------------------------------------------------------------------

def test_override_cap_applied(tmp_path):
    override_file = tmp_path / ".icm-profile.local.yaml"
    override_file.write_text(yaml.safe_dump({
        "extends": "app_web_backend",
        "tier": "development",
        "overrides": {"cap_teammates_per_wave": 7},
    }), encoding="utf-8")
    eff, _ = merge_profile(profile="app_web_backend", tier="development", override_path=override_file)
    assert eff["cap_teammates_per_wave"] == 7


def test_override_stages_skipped_applied(tmp_path):
    override_file = tmp_path / ".icm-profile.local.yaml"
    override_file.write_text(yaml.safe_dump({
        "extends": "app_web_backend",
        "tier": "development",
        "overrides": {"stages_skipped": ["08"]},
    }), encoding="utf-8")
    eff, _ = merge_profile(profile="app_web_backend", tier="development", override_path=override_file)
    assert eff["stages_skipped"] == ["08"]


def test_override_changes_hash(tmp_path):
    override_file = tmp_path / ".icm-profile.local.yaml"
    override_file.write_text(yaml.safe_dump({
        "extends": "app_web_backend",
        "tier": "development",
        "overrides": {"cap_teammates_per_wave": 7},
    }), encoding="utf-8")
    _, hash_default = merge_profile(profile="app_web_backend", tier="development")
    _, hash_override = merge_profile(profile="app_web_backend", tier="development", override_path=override_file)
    assert hash_default != hash_override


def test_override_custom_stop_points(tmp_path):
    override_file = tmp_path / ".icm-profile.local.yaml"
    override_file.write_text(yaml.safe_dump({
        "extends": "app_web_backend",
        "tier": "development",
        "custom_stop_points": [
            {"id": "custom_1", "description": "checagem extra", "threshold": {"development": "hard"}}
        ],
    }), encoding="utf-8")
    eff, _ = merge_profile(profile="app_web_backend", tier="development", override_path=override_file)
    assert "custom_stop_points" in eff
    assert eff["custom_stop_points"][0]["id"] == "custom_1"


def test_override_revisit_after_iso_date(tmp_path):
    override_file = tmp_path / ".icm-profile.local.yaml"
    override_file.write_text(yaml.safe_dump({
        "extends": "app_web_backend",
        "tier": "development",
        "revisit_after": "2026-08-01",
    }), encoding="utf-8")
    eff, _ = merge_profile(profile="app_web_backend", tier="development", override_path=override_file)
    assert eff["revisit_after"] == "2026-08-01"


def test_override_revisit_after_iso_datetime(tmp_path):
    override_file = tmp_path / ".icm-profile.local.yaml"
    override_file.write_text(yaml.safe_dump({
        "extends": "app_web_backend",
        "tier": "development",
        "revisit_after": "2026-08-01T10:00:00",
    }), encoding="utf-8")
    eff, _ = merge_profile(profile="app_web_backend", tier="development", override_path=override_file)
    assert eff["revisit_after"] == "2026-08-01T10:00:00"


# ----------------------------------------------------------------------------
# 6. confirm_unsafe guard rails
# ----------------------------------------------------------------------------

def test_unsafe_disable_tdd_without_confirm_raises(tmp_path):
    override_file = tmp_path / ".icm-profile.local.yaml"
    override_file.write_text(yaml.safe_dump({
        "extends": "app_web_backend",
        "tier": "development",
        "overrides": {"tdd_required": False},
    }), encoding="utf-8")
    with pytest.raises(ProfileMergeError, match="confirm_unsafe"):
        merge_profile(profile="app_web_backend", tier="development", override_path=override_file)


def test_unsafe_disable_security_without_confirm_raises(tmp_path):
    override_file = tmp_path / ".icm-profile.local.yaml"
    override_file.write_text(yaml.safe_dump({
        "extends": "app_web_backend",
        "tier": "development",
        "overrides": {"security_gate": False},
    }), encoding="utf-8")
    with pytest.raises(ProfileMergeError, match="confirm_unsafe"):
        merge_profile(profile="app_web_backend", tier="development", override_path=override_file)


def test_unsafe_disable_peer_review_without_confirm_raises(tmp_path):
    override_file = tmp_path / ".icm-profile.local.yaml"
    override_file.write_text(yaml.safe_dump({
        "extends": "app_web_backend",
        "tier": "production",
        "overrides": {"peer_review_required": False},
    }), encoding="utf-8")
    with pytest.raises(ProfileMergeError, match="confirm_unsafe"):
        merge_profile(profile="app_web_backend", tier="production", override_path=override_file)


def test_unsafe_disable_with_confirm_unsafe_succeeds(tmp_path):
    override_file = tmp_path / ".icm-profile.local.yaml"
    override_file.write_text(yaml.safe_dump({
        "extends": "app_web_backend",
        "tier": "development",
        "overrides": {"tdd_required": False, "security_gate": False},
        "confirm_unsafe": True,
    }), encoding="utf-8")
    eff, _ = merge_profile(profile="app_web_backend", tier="development", override_path=override_file)
    assert eff["tdd_required"] is False
    assert eff["security_gate"] is False


def test_safe_override_does_not_require_confirm(tmp_path):
    # Mudar cap nao e perigoso; nao precisa confirm_unsafe
    override_file = tmp_path / ".icm-profile.local.yaml"
    override_file.write_text(yaml.safe_dump({
        "extends": "app_web_backend",
        "tier": "development",
        "overrides": {"cap_teammates_per_wave": 2},
    }), encoding="utf-8")
    eff, _ = merge_profile(profile="app_web_backend", tier="development", override_path=override_file)
    assert eff["cap_teammates_per_wave"] == 2


def test_enabling_gate_does_not_require_confirm(tmp_path):
    # Ligar tdd_required (False -> True) nao e perigoso
    override_file = tmp_path / ".icm-profile.local.yaml"
    override_file.write_text(yaml.safe_dump({
        "extends": "experiment",
        "tier": "experimental",
        "overrides": {"tdd_required": True},
    }), encoding="utf-8")
    eff, _ = merge_profile(profile="experiment", tier="experimental", override_path=override_file)
    assert eff["tdd_required"] is True


# ----------------------------------------------------------------------------
# 7. Validacao de schema
# ----------------------------------------------------------------------------

def test_invalid_profile_raises():
    with pytest.raises(ProfileMergeError, match="profile"):
        merge_profile(profile="not_a_profile", tier="development")


def test_invalid_tier_raises():
    with pytest.raises(ProfileMergeError, match="tier"):
        merge_profile(profile="app_web_backend", tier="not_a_tier")


def test_extends_mismatch_raises(tmp_path):
    # Override declara extends diferente do profile passado: deve falhar
    override_file = tmp_path / ".icm-profile.local.yaml"
    override_file.write_text(yaml.safe_dump({
        "extends": "cli_tool",
        "tier": "development",
    }), encoding="utf-8")
    with pytest.raises(ProfileMergeError, match="extends"):
        merge_profile(profile="app_web_backend", tier="development", override_path=override_file)


def test_invalid_extends_raises(tmp_path):
    override_file = tmp_path / ".icm-profile.local.yaml"
    override_file.write_text(yaml.safe_dump({
        "extends": "no_such_profile",
        "tier": "development",
    }), encoding="utf-8")
    with pytest.raises(ProfileMergeError):
        merge_profile(profile="no_such_profile", tier="development", override_path=override_file)


def test_unknown_override_key_raises(tmp_path):
    override_file = tmp_path / ".icm-profile.local.yaml"
    override_file.write_text(yaml.safe_dump({
        "extends": "app_web_backend",
        "tier": "development",
        "overrides": {"chave_inexistente": True},
    }), encoding="utf-8")
    with pytest.raises(ProfileMergeError, match="overrides"):
        merge_profile(profile="app_web_backend", tier="development", override_path=override_file)


def test_revisit_after_malformed_raises(tmp_path):
    override_file = tmp_path / ".icm-profile.local.yaml"
    override_file.write_text(yaml.safe_dump({
        "extends": "app_web_backend",
        "tier": "development",
        "revisit_after": "agosto de 2026",
    }), encoding="utf-8")
    with pytest.raises(ProfileMergeError, match="revisit_after"):
        merge_profile(profile="app_web_backend", tier="development", override_path=override_file)


def test_revisit_after_partial_date_raises(tmp_path):
    override_file = tmp_path / ".icm-profile.local.yaml"
    override_file.write_text(yaml.safe_dump({
        "extends": "app_web_backend",
        "tier": "development",
        "revisit_after": "2026-08",
    }), encoding="utf-8")
    with pytest.raises(ProfileMergeError, match="revisit_after"):
        merge_profile(profile="app_web_backend", tier="development", override_path=override_file)


def test_custom_stop_point_missing_id_raises(tmp_path):
    override_file = tmp_path / ".icm-profile.local.yaml"
    override_file.write_text(yaml.safe_dump({
        "extends": "app_web_backend",
        "tier": "development",
        "custom_stop_points": [
            {"description": "sem id", "threshold": {"development": "hard"}}
        ],
    }), encoding="utf-8")
    with pytest.raises(ProfileMergeError, match="custom_stop_points"):
        merge_profile(profile="app_web_backend", tier="development", override_path=override_file)


def test_custom_stop_point_missing_description_raises(tmp_path):
    override_file = tmp_path / ".icm-profile.local.yaml"
    override_file.write_text(yaml.safe_dump({
        "extends": "app_web_backend",
        "tier": "development",
        "custom_stop_points": [
            {"id": "custom_1", "threshold": {"development": "hard"}}
        ],
    }), encoding="utf-8")
    with pytest.raises(ProfileMergeError, match="custom_stop_points"):
        merge_profile(profile="app_web_backend", tier="development", override_path=override_file)


def test_custom_stop_point_empty_threshold_raises(tmp_path):
    override_file = tmp_path / ".icm-profile.local.yaml"
    override_file.write_text(yaml.safe_dump({
        "extends": "app_web_backend",
        "tier": "development",
        "custom_stop_points": [
            {"id": "custom_1", "description": "x", "threshold": {}}
        ],
    }), encoding="utf-8")
    with pytest.raises(ProfileMergeError, match="custom_stop_points"):
        merge_profile(profile="app_web_backend", tier="development", override_path=override_file)


def test_custom_stop_point_invalid_threshold_tier_raises(tmp_path):
    override_file = tmp_path / ".icm-profile.local.yaml"
    override_file.write_text(yaml.safe_dump({
        "extends": "app_web_backend",
        "tier": "development",
        "custom_stop_points": [
            {"id": "custom_1", "description": "x", "threshold": {"unknown_tier": "hard"}}
        ],
    }), encoding="utf-8")
    with pytest.raises(ProfileMergeError, match="custom_stop_points"):
        merge_profile(profile="app_web_backend", tier="development", override_path=override_file)


def test_override_path_missing_raises(tmp_path):
    missing = tmp_path / "nao_existe.yaml"
    with pytest.raises(ProfileMergeError):
        merge_profile(profile="app_web_backend", tier="development", override_path=missing)


# ----------------------------------------------------------------------------
# 8. compute_hash function isolada
# ----------------------------------------------------------------------------

def test_compute_hash_stable_against_key_order():
    a = {"a": 1, "b": 2, "c": [3, 4]}
    b = {"c": [3, 4], "b": 2, "a": 1}
    assert compute_hash(a) == compute_hash(b)


def test_compute_hash_changes_on_value_change():
    a = {"a": 1}
    b = {"a": 2}
    assert compute_hash(a) != compute_hash(b)


# ----------------------------------------------------------------------------
# 9. CLI mode
# ----------------------------------------------------------------------------

def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_cli_outputs_parseable_json():
    result = _run_cli("--profile", "app_web_backend", "--tier", "development")
    assert result.returncode == 0, f"stderr={result.stderr}"
    payload = json.loads(result.stdout)
    assert "effective" in payload
    assert "hash" in payload
    assert payload["effective"]["profile"] == "app_web_backend"
    assert payload["effective"]["tier"] == "development"
    assert len(payload["hash"]) == 64


def test_cli_with_override(tmp_path):
    override_file = tmp_path / ".icm-profile.local.yaml"
    override_file.write_text(yaml.safe_dump({
        "extends": "framework_library",
        "tier": "tool",
        "overrides": {"cap_teammates_per_wave": 4},
    }), encoding="utf-8")
    result = _run_cli(
        "--profile", "framework_library",
        "--tier", "tool",
        "--override", str(override_file),
    )
    assert result.returncode == 0, f"stderr={result.stderr}"
    payload = json.loads(result.stdout)
    assert payload["effective"]["cap_teammates_per_wave"] == 4


def test_cli_invalid_profile_exits_nonzero():
    result = _run_cli("--profile", "nope", "--tier", "development")
    assert result.returncode == 1
    assert result.stderr.strip() != ""


def test_cli_invalid_tier_exits_nonzero():
    result = _run_cli("--profile", "app_web_backend", "--tier", "nope")
    assert result.returncode == 1
    assert result.stderr.strip() != ""
