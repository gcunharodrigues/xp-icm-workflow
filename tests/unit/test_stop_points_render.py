"""Testes unitarios para render do template `_config/stop-points.md`.

Cobre:
- `derive_stop_point_placeholders` — extracao de TIER_PAID_MODE/etc do
  profile efetivo, por tier.
- `render_custom_stop_points_block` — renderizacao do bloco markdown de
  custom stop points (lista vazia, lista com 1+ items, threshold por tier).
- Render integrado do template `templates/_config/stop-points.md` via
  `render_template`, com property: nenhum `{{X}}` remanescente no output
  para cada tier canonico.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

# Carrega scripts/bootstrap.py como modulo (mesmo padrao de test_bootstrap.py)
SKILL_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = SKILL_ROOT / "scripts" / "bootstrap.py"
TEMPLATE_PATH = SKILL_ROOT / "templates" / "_config" / "stop-points.md"

_spec = importlib.util.spec_from_file_location("bootstrap", SCRIPT_PATH)
bootstrap = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules["bootstrap"] = bootstrap
_spec.loader.exec_module(bootstrap)  # type: ignore[union-attr]

BootstrapError = bootstrap.BootstrapError
render_template = bootstrap.render_template
derive_stop_point_placeholders = bootstrap.derive_stop_point_placeholders
render_custom_stop_points_block = bootstrap.render_custom_stop_points_block
PLACEHOLDER_RE = bootstrap.PLACEHOLDER_RE

# Tiers canonicos (espelha profile-merge.py)
TIERS: tuple[str, ...] = ("experimental", "tool", "development", "production")

# Calibracao canonica (espelha profile-merge.py defaults sem override)
TIER_CALIBRATION: dict[str, dict[str, Any]] = {
    "experimental": {
        "item_5": {"mode": "warning", "limite_mensal_BRL": 50},
        "item_7": {"mode": "warning"},
        "item_8": {"mode": "warning"},
    },
    "tool": {
        "item_5": {"mode": "hard", "limite_mensal_BRL": 200},
        "item_7": {"mode": "warning"},
        "item_8": {"mode": "hard"},
    },
    "development": {
        "item_5": {"mode": "hard", "limite_mensal_BRL": 500},
        "item_7": {"mode": "hard"},
        "item_8": {"mode": "hard"},
    },
    "production": {
        "item_5": {"mode": "hard", "limite_mensal_BRL": 1000},
        "item_7": {"mode": "hard"},
        "item_8": {"mode": "hard+DPO"},
    },
}


def _effective(tier: str, custom: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Constroi profile efetivo minimo para o tier dado."""
    eff: dict[str, Any] = {
        "profile": "cli_tool",
        "tier": tier,
        "stop_points_calibration": TIER_CALIBRATION[tier],
    }
    if custom is not None:
        eff["custom_stop_points"] = custom
    return eff


def _full_render_vars(tier: str, custom_block: str) -> dict[str, str]:
    """Vars completas para renderizar o template stop-points.md."""
    sp = derive_stop_point_placeholders(_effective(tier))
    return {
        "WORKSPACE": "001-test-ws",
        "PROFILE": "cli_tool",
        "TIER": tier,
        "PROJECT_ROOT": "/tmp/proj",
        "BASE_BRANCH": "main",
        "LOGS_ROOT": "null",
        "PROFILE_EFFECTIVE_HASH": "abc123",
        "CREATED_AT": "2026-04-25T10:00:00Z",
        "SKILL_VERSION": "3.3.0",
        "BOOTSTRAP_COMMIT_SHA": "deadbeef",
        "CUSTOM_STOP_POINTS_BLOCK": custom_block,
        **sp,
    }


# ============================================================================
# derive_stop_point_placeholders
# ============================================================================

class TestDeriveStopPointPlaceholders:
    def test_experimental_tier(self) -> None:
        out = derive_stop_point_placeholders(_effective("experimental"))
        assert out["TIER_PAID_MODE"] == "warning"
        assert out["TIER_PAID_THRESHOLD_BRL"] == "50"
        assert out["TIER_OVER_ENG_MODE"] == "warning"
        assert out["TIER_PII_MODE"] == "warning"

    def test_tool_tier(self) -> None:
        out = derive_stop_point_placeholders(_effective("tool"))
        assert out["TIER_PAID_MODE"] == "hard"
        assert out["TIER_PAID_THRESHOLD_BRL"] == "200"
        assert out["TIER_OVER_ENG_MODE"] == "warning"
        assert out["TIER_PII_MODE"] == "hard"

    def test_development_tier(self) -> None:
        out = derive_stop_point_placeholders(_effective("development"))
        assert out["TIER_PAID_MODE"] == "hard"
        assert out["TIER_PAID_THRESHOLD_BRL"] == "500"
        assert out["TIER_OVER_ENG_MODE"] == "hard"
        assert out["TIER_PII_MODE"] == "hard"

    def test_production_tier_dpo(self) -> None:
        out = derive_stop_point_placeholders(_effective("production"))
        assert out["TIER_PAID_MODE"] == "hard"
        assert out["TIER_PAID_THRESHOLD_BRL"] == "1000"
        assert out["TIER_OVER_ENG_MODE"] == "hard"
        assert out["TIER_PII_MODE"] == "hard+DPO"

    def test_returns_strings_only(self) -> None:
        # important: render_template requires str values
        out = derive_stop_point_placeholders(_effective("development"))
        for k, v in out.items():
            assert isinstance(k, str)
            assert isinstance(v, str), f"{k} must be str, got {type(v)}"

    def test_raises_when_calibration_missing(self) -> None:
        with pytest.raises(BootstrapError, match="stop_points_calibration"):
            derive_stop_point_placeholders({"profile": "cli_tool"})

    def test_raises_when_calibration_not_dict(self) -> None:
        with pytest.raises(BootstrapError, match="stop_points_calibration"):
            derive_stop_point_placeholders({"stop_points_calibration": "string"})

    def test_raises_when_item_5_missing(self) -> None:
        eff = {"stop_points_calibration": {"item_7": {"mode": "hard"}, "item_8": {"mode": "hard"}}}
        with pytest.raises(BootstrapError, match="item_5"):
            derive_stop_point_placeholders(eff)

    def test_raises_when_subkey_missing(self) -> None:
        eff = {
            "stop_points_calibration": {
                "item_5": {"mode": "hard"},  # falta limite_mensal_BRL
                "item_7": {"mode": "hard"},
                "item_8": {"mode": "hard"},
            }
        }
        with pytest.raises(BootstrapError, match="limite_mensal_BRL"):
            derive_stop_point_placeholders(eff)


# ============================================================================
# render_custom_stop_points_block
# ============================================================================

class TestRenderCustomStopPointsBlock:
    def test_empty_list_returns_nenhum(self) -> None:
        out = render_custom_stop_points_block([], tier="development")
        assert "nenhum" in out

    def test_none_returns_nenhum(self) -> None:
        out = render_custom_stop_points_block(None, tier="development")
        assert "nenhum" in out

    def test_single_custom_stop_renders(self) -> None:
        custom = [
            {
                "id": "lgpd_health",
                "description": "checagem extra para dados de saude",
                "threshold": {"experimental": "warning", "development": "hard"},
            }
        ]
        out = render_custom_stop_points_block(custom, tier="development")
        assert "### custom: lgpd_health" in out
        assert "checagem extra para dados de saude" in out
        assert "Threshold tier `development`: `hard`" in out

    def test_multiple_custom_stops_render_both(self) -> None:
        custom = [
            {
                "id": "stop_one",
                "description": "primeiro stop",
                "threshold": {"development": "hard"},
            },
            {
                "id": "stop_two",
                "description": "segundo stop",
                "threshold": {"development": "warning"},
            },
        ]
        out = render_custom_stop_points_block(custom, tier="development")
        assert "### custom: stop_one" in out
        assert "### custom: stop_two" in out
        assert "primeiro stop" in out
        assert "segundo stop" in out
        assert "Threshold tier `development`: `hard`" in out
        assert "Threshold tier `development`: `warning`" in out

    def test_threshold_missing_for_tier_returns_na(self) -> None:
        custom = [
            {
                "id": "only_prod",
                "description": "so vale em production",
                "threshold": {"production": "hard"},
            }
        ]
        out = render_custom_stop_points_block(custom, tier="experimental")
        assert "Threshold tier `experimental`: `n/a`" in out

    def test_raises_on_missing_id(self) -> None:
        custom = [{"description": "x", "threshold": {"development": "hard"}}]
        with pytest.raises(BootstrapError, match="id"):
            render_custom_stop_points_block(custom, tier="development")

    def test_raises_on_missing_description(self) -> None:
        custom = [{"id": "foo", "threshold": {"development": "hard"}}]
        with pytest.raises(BootstrapError, match="description"):
            render_custom_stop_points_block(custom, tier="development")

    def test_raises_on_non_dict_item(self) -> None:
        with pytest.raises(BootstrapError, match="nao-dict"):
            render_custom_stop_points_block(["nope"], tier="development")  # type: ignore[list-item]


# ============================================================================
# Render integrado do template stop-points.md
# ============================================================================

class TestRenderStopPointsTemplate:
    def test_template_file_exists(self) -> None:
        assert TEMPLATE_PATH.exists(), f"template ausente: {TEMPLATE_PATH}"

    def test_render_stop_points_experimental_tier(self) -> None:
        custom = render_custom_stop_points_block(None, tier="experimental")
        out = render_template(TEMPLATE_PATH, _full_render_vars("experimental", custom))
        # placeholders resolvidos
        assert "warning" in out  # TIER_PAID_MODE
        assert "R$ 50" in out  # TIER_PAID_THRESHOLD_BRL
        # frontmatter resolvido
        assert "tier_resolved: \"experimental\"" in out
        assert "001-test-ws" in out  # WORKSPACE
        # custom stops vazio
        assert "nenhum custom stop point" in out

    def test_render_stop_points_production_tier(self) -> None:
        custom = render_custom_stop_points_block(None, tier="production")
        out = render_template(TEMPLATE_PATH, _full_render_vars("production", custom))
        assert "hard+DPO" in out  # TIER_PII_MODE
        assert "R$ 1000" in out
        assert "tier_resolved: \"production\"" in out

    def test_render_stop_points_with_custom_sps(self) -> None:
        custom_list = [
            {
                "id": "alpha",
                "description": "alpha desc",
                "threshold": {"development": "hard"},
            },
            {
                "id": "beta",
                "description": "beta desc",
                "threshold": {"development": "warning"},
            },
        ]
        custom = render_custom_stop_points_block(custom_list, tier="development")
        out = render_template(TEMPLATE_PATH, _full_render_vars("development", custom))
        assert "### custom: alpha" in out
        assert "### custom: beta" in out
        assert "alpha desc" in out
        assert "beta desc" in out

    def test_render_stop_points_no_custom_writes_nenhum(self) -> None:
        custom = render_custom_stop_points_block(None, tier="tool")
        out = render_template(TEMPLATE_PATH, _full_render_vars("tool", custom))
        assert "nenhum custom stop point" in out

    @pytest.mark.parametrize("tier", TIERS)
    def test_no_unresolved_placeholders_for_any_tier(self, tier: str) -> None:
        """Property: para cada tier canonico, render produz output limpo
        (zero `{{X}}` leftover)."""
        custom = render_custom_stop_points_block(None, tier=tier)
        out = render_template(TEMPLATE_PATH, _full_render_vars(tier, custom))
        leftover = PLACEHOLDER_RE.search(out)
        assert leftover is None, (
            f"placeholder nao-resolvido em tier={tier}: {leftover.group(0) if leftover else None}"
        )

    @pytest.mark.parametrize("tier", TIERS)
    def test_no_unresolved_placeholders_with_custom_sps(self, tier: str) -> None:
        """Property: idem, agora com custom stops declarados."""
        custom_list = [
            {
                "id": "x_check",
                "description": "extra check",
                "threshold": {tier: "hard"},
            }
        ]
        custom = render_custom_stop_points_block(custom_list, tier=tier)
        out = render_template(TEMPLATE_PATH, _full_render_vars(tier, custom))
        leftover = PLACEHOLDER_RE.search(out)
        assert leftover is None, (
            f"placeholder nao-resolvido em tier={tier}: {leftover.group(0) if leftover else None}"
        )

    def test_render_includes_canonical_12_items(self) -> None:
        """Sanity: output lista todos os 12 stops canonicos."""
        custom = render_custom_stop_points_block(None, tier="development")
        out = render_template(TEMPLATE_PATH, _full_render_vars("development", custom))
        for sp_id in (
            "stack",
            "db",
            "external_api",
            "new_dep",
            "paid_service",
            "irreversible",
            "over_eng",
            "pii",
            "prod_migration",
            "adr_drift",
            "wave_branch_missing",
            "profile_mismatch",
        ):
            assert sp_id in out, f"stop point canonico ausente: {sp_id}"

    def test_render_includes_menu_template_inline(self) -> None:
        """Workspace e self-contained: template do menu A/B/C deve estar inline."""
        custom = render_custom_stop_points_block(None, tier="development")
        out = render_template(TEMPLATE_PATH, _full_render_vars("development", custom))
        assert "STOP POINT" in out
        assert "Trade-offs" in out
        assert "Recomendação do agente" in out
