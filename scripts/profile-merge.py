"""Merge of base profile + local override into effective profile + deterministic hash.

Covers 11 canonical profiles x 4 tiers, with safe override rules
(`confirm_unsafe`) and strict schema validation.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

# ============================================================================
# Constants / canonical matrix
# ============================================================================

CANONICAL_PROFILES: tuple[str, ...] = (
    "app_web_backend",
    "app_web_frontend",
    "fullstack",
    "dashboard",
    "data_analysis",
    "ml_project",
    "agent_ia",
    "cli_tool",
    "framework_library",
    "technical_article",
    "experiment",
)

CANONICAL_TIERS: tuple[str, ...] = (
    "experimental",
    "tool",
    "development",
    "production",
)

MATRIX_KEYS: frozenset[str] = frozenset({
    "stages_skipped",
    "tdd_required",
    "security_gate",
    "tech_debt_tracking",
    "peer_review_required",
    "cap_subagents_per_wave",
    "stop_points_calibration",
})

UNSAFE_KEYS: frozenset[str] = frozenset({
    "tdd_required",
    "security_gate",
    "peer_review_required",
})

ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2})?$")


class ProfileMergeError(Exception):
    """Profile validation or merge error."""


# ============================================================================
# Tier defaults (before profile overrides applied)
# ============================================================================

def _tier_defaults(tier: str) -> dict[str, Any]:
    """Returns the base dict for a tier; profile-overrides are applied on top."""
    if tier == "experimental":
        return {
            "stages_skipped": [],
            "tdd_required": False,
            "tdd_mode": "optional",
            "security_gate": False,
            "tech_debt_tracking": False,
            "peer_review_required": False,
            "cap_subagents_per_wave": 2,
            "stop_points_calibration": {
                "item_5": {"mode": "warning", "limite_mensal_BRL": 50},
                "item_7": {"mode": "warning"},
                "item_8": {"mode": "warning"},
            },
        }
    if tier == "tool":
        return {
            "stages_skipped": [],
            "tdd_required": False,
            "tdd_mode": "recommended",
            "security_gate": False,
            "tech_debt_tracking": True,
            "peer_review_required": False,
            "cap_subagents_per_wave": 3,
            "stop_points_calibration": {
                "item_5": {"mode": "hard", "limite_mensal_BRL": 200},
                "item_7": {"mode": "warning"},
                "item_8": {"mode": "hard"},
            },
        }
    if tier == "development":
        return {
            "stages_skipped": [],
            "tdd_required": True,
            "tdd_mode": "required",
            "security_gate": True,
            "security_mode": "on",
            "tech_debt_tracking": True,
            "peer_review_required": False,
            "cap_subagents_per_wave": 5,
            "stop_points_calibration": {
                "item_5": {"mode": "hard", "limite_mensal_BRL": 500},
                "item_7": {"mode": "hard"},
                "item_8": {"mode": "hard"},
            },
        }
    if tier == "production":
        return {
            "stages_skipped": [],
            "tdd_required": True,
            "tdd_mode": "required",
            "security_gate": True,
            "security_mode": "on+LGPD",
            "tech_debt_tracking": True,
            "peer_review_required": True,
            "cap_subagents_per_wave": 5,
            "stop_points_calibration": {
                "item_5": {"mode": "hard", "limite_mensal_BRL": 1000},
                "item_7": {"mode": "hard"},
                "item_8": {"mode": "hard+DPO"},
            },
        }
    raise ProfileMergeError(f"unknown tier: {tier!r}")


# ============================================================================
# test_specs per profile+tier (derived; not configurable via override)
# ============================================================================

def _test_specs(profile: str, tier: str) -> dict[str, Any]:
    """Returns computed test_specs for the profile+tier pair.

    Not configurable via overrides — derived deterministically.
    Stage 02 design uses these values to define the Test Strategy in plan.md.
    Stage 05 verification uses coverage_threshold and test_types_required to audit.
    """
    threshold_by_tier = {
        "experimental": 0,
        "tool": 60,
        "development": 80,
        "production": 90,
    }
    base_threshold = threshold_by_tier[tier]

    if profile == "experiment":
        return {
            "test_types_required": [],
            "coverage_threshold": 0,
            "test_location": "tests/",
            "note": "experiment — no test requirements enforced",
        }

    if profile == "technical_article":
        return {
            "test_types_required": ["unit"] if tier != "experimental" else [],
            "coverage_threshold": 0,
            "test_location": "tests/",
            "note": "article — unit tests for embedded code snippets only if executable",
        }

    if profile == "app_web_backend":
        return {
            "test_types_required": ["unit", "integration"],
            "coverage_threshold": base_threshold,
            "test_location": "tests/",
            "http_integration": True,
            "db_integration": True,
        }

    if profile == "app_web_frontend":
        e2e_required = tier in ("development", "production")
        visual_regression = tier == "production"
        a11y_testing = tier in ("development", "production")
        return {
            "test_types_required": (
                ["unit", "component", "e2e"] if e2e_required else ["unit", "component"]
            ),
            "coverage_threshold": base_threshold,
            "test_location": "src/",
            "component_testing": True,
            "e2e_required": e2e_required,
            "visual_regression": visual_regression,
            "a11y_testing": a11y_testing,
            "design_system_required": True,
        }

    if profile == "fullstack":
        # Superset of backend + frontend. E.g.: Next.js with API routes,
        # Remix + Prisma, T3 stack, Django + React colocated.
        e2e_required = tier in ("development", "production")
        visual_regression = tier == "production"
        a11y_testing = tier in ("development", "production")
        return {
            "test_types_required": (
                ["unit", "integration", "component", "e2e"]
                if e2e_required
                else ["unit", "integration", "component"]
            ),
            "coverage_threshold": base_threshold,
            "test_location": "tests/",
            "http_integration": True,
            "db_integration": True,
            "component_testing": True,
            "e2e_required": e2e_required,
            "visual_regression": visual_regression,
            "a11y_testing": a11y_testing,
            "design_system_required": True,
            "note": (
                "fullstack — backend + frontend coexist in the same repo "
                "(Next.js with API routes, Remix+Prisma, T3 stack, etc). "
                "For monorepo apps/web + apps/api separated, prefer "
                "2 workspaces (1 app_web_backend + 1 app_web_frontend)."
            ),
        }

    if profile == "dashboard":
        return {
            "test_types_required": ["unit", "integration"],
            "coverage_threshold": base_threshold,
            "test_location": "tests/",
            "http_integration": True,
            "db_integration": True,
        }

    if profile == "data_analysis":
        return {
            "test_types_required": ["unit"],
            "coverage_threshold": min(base_threshold, 70),
            "test_location": "tests/",
            "note": "transformation functions unit-tested; notebooks excluded from coverage",
        }

    if profile == "ml_project":
        model_regression = tier in ("development", "production")
        return {
            "test_types_required": (
                ["unit", "pipeline", "model_eval"] if model_regression else ["unit", "pipeline"]
            ),
            "coverage_threshold": min(base_threshold, 70),
            "test_location": "tests/",
            "pipeline_testing": True,
            "model_regression": model_regression,
        }

    if profile == "agent_ia":
        eval_required = tier in ("development", "production")
        return {
            "test_types_required": (
                ["unit_tools", "integration_prompt", "eval"]
                if eval_required
                else ["unit_tools", "integration_prompt"]
            ),
            "coverage_threshold": min(base_threshold, 70),
            "test_location": "tests/",
            "deterministic_tools_only": True,
            "eval_strategy": "golden_output_similarity" if eval_required else None,
            "eval_threshold": 0.85 if eval_required else None,
            "note": "LLM outputs non-deterministic; tool calls are unit-testable; prompts tested via eval",
        }

    if profile == "cli_tool":
        return {
            "test_types_required": ["unit", "integration"],
            "coverage_threshold": base_threshold,
            "test_location": "tests/",
            "subprocess_testing": True,
            "note": "integration = subprocess calls with stdin/stdout capture and tempdir fixtures",
        }

    if profile == "framework_library":
        # Libraries need higher coverage: they are reused by unknown consumers.
        lib_threshold = min(base_threshold + 10, 100)
        return {
            "test_types_required": ["unit", "integration"],
            "coverage_threshold": lib_threshold,
            "test_location": "tests/",
            "public_api_coverage": True,
            "note": "coverage +10% vs tier default; public API 100% unit required",
        }

    # Generic fallback (should not occur with canonical profiles)
    return {
        "test_types_required": ["unit"],
        "coverage_threshold": base_threshold,
        "test_location": "tests/",
    }


# ============================================================================
# Profile-specific overrides applied on top of tier defaults
# ============================================================================

def _apply_profile_rules(profile: str, tier: str, base: dict[str, Any]) -> dict[str, Any]:
    """Applies profile-specific rules on top of the tier base dict."""
    out = copy.deepcopy(base)

    if profile == "experiment":
        out["stages_skipped"] = ["03", "05", "06", "08"]

    if profile == "technical_article":
        # Technical article does not need stage 03 (automated tests/quality)
        skipped = set(out["stages_skipped"])
        skipped.add("03")
        out["stages_skipped"] = sorted(skipped)
        out["cap_subagents_per_wave"] = 5

    if profile == "framework_library":
        out["cap_subagents_per_wave"] = 3

    if profile == "ml_project":
        out["cap_subagents_per_wave"] = 3

    # Web apps enable security_gate on any tier above experimental
    # (fullstack too — backend + frontend both exposed to network)
    if (
        profile in ("app_web_backend", "app_web_frontend", "fullstack")
        and tier != "experimental"
    ):
        out["security_gate"] = True

    return out


# ============================================================================
# Validacao
# ============================================================================

def _validate_profile(profile: str) -> None:
    if profile not in CANONICAL_PROFILES:
        raise ProfileMergeError(
            f"invalid profile: {profile!r} (expected: {', '.join(CANONICAL_PROFILES)})"
        )


def _validate_tier(tier: str) -> None:
    if tier not in CANONICAL_TIERS:
        raise ProfileMergeError(
            f"invalid tier: {tier!r} (expected: {', '.join(CANONICAL_TIERS)})"
        )


def _validate_iso_8601(value: str) -> None:
    if not isinstance(value, str) or not ISO_DATE_RE.match(value):
        raise ProfileMergeError(
            f"revisit_after must be ISO 8601 (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS), got: {value!r}"
        )


def _validate_overrides_keys(overrides: dict[str, Any]) -> None:
    unknown = set(overrides) - MATRIX_KEYS
    if unknown:
        raise ProfileMergeError(
            f"overrides contains unknown keys: {sorted(unknown)} "
            f"(allowed: {sorted(MATRIX_KEYS)})"
        )


def _validate_custom_stop_points(items: Any) -> None:
    if not isinstance(items, list):
        raise ProfileMergeError("custom_stop_points must be a list")
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            raise ProfileMergeError(f"custom_stop_points[{idx}] must be a dict")
        if not isinstance(item.get("id"), str) or not item["id"]:
            raise ProfileMergeError(f"custom_stop_points[{idx}].id missing or not a string")
        if not isinstance(item.get("description"), str) or not item["description"]:
            raise ProfileMergeError(
                f"custom_stop_points[{idx}].description missing or not a string"
            )
        threshold = item.get("threshold")
        if not isinstance(threshold, dict) or not threshold:
            raise ProfileMergeError(
                f"custom_stop_points[{idx}].threshold must be a non-empty dict"
            )
        for tier_key in threshold:
            if tier_key not in CANONICAL_TIERS:
                raise ProfileMergeError(
                    f"custom_stop_points[{idx}].threshold invalid tier: {tier_key!r}"
                )


# ============================================================================
# Override loading + application
# ============================================================================

def _load_override(path: Path) -> dict[str, Any]:
    """Loads .icm-profile.local.yaml file into a dict; validates existence."""
    if not path.exists():
        raise ProfileMergeError(f"override path does not exist: {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ProfileMergeError(f"invalid override YAML: {exc}") from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ProfileMergeError("override root must be a mapping/dict")
    return data


def _check_unsafe_overrides(
    base_after_profile: dict[str, Any],
    overrides: dict[str, Any],
    confirm_unsafe: bool,
) -> None:
    """Raises if override disables a critical gate without confirm_unsafe=true."""
    for key in UNSAFE_KEYS:
        if key not in overrides:
            continue
        was_on = bool(base_after_profile.get(key))
        will_be = bool(overrides[key])
        if was_on and not will_be and not confirm_unsafe:
            raise ProfileMergeError(
                f"dangerous override requires confirm_unsafe: true (key: {key})"
            )


# ============================================================================
# Public API
# ============================================================================

def _preview_loop_config(profile: str, tier: str) -> dict[str, Any] | None:
    """Returns preview_loop config for frontend/fullstack profiles.

    None for profiles without `design_system_required`. v3.6.0+.
    Canonical doc: references/preview-loop-protocol.md.
    """
    if profile not in ("app_web_frontend", "fullstack"):
        return None
    mock_data_by_tier = {
        "experimental": "fixtures",
        "tool": "fixtures",
        "development": "msw_faker",
        "production": "msw_faker_zod",
    }
    return {
        "preview_loop_enabled": True,
        "mock_data_strategy": mock_data_by_tier[tier],
        "cdp_live_enabled": True,
        "visual_iter_cap": None,
        "design_cascade_threshold": 5,
        "preview_pages_path": "preview/",
    }


def merge_profile(
    profile: str,
    tier: str,
    override_path: Path | str | None = None,
) -> tuple[dict[str, Any], str]:
    """Produces effective profile + hash; applies override if provided."""
    _validate_profile(profile)
    _validate_tier(tier)

    base = _tier_defaults(tier)
    effective = _apply_profile_rules(profile, tier, base)
    effective["profile"] = profile
    effective["tier"] = tier
    effective["test_specs"] = _test_specs(profile, tier)
    preview_loop = _preview_loop_config(profile, tier)
    if preview_loop is not None:
        effective["preview_loop"] = preview_loop

    if override_path is not None:
        override = _load_override(Path(override_path))
        effective = _apply_override(profile, tier, effective, override)

    return effective, compute_hash(effective)


def _apply_override(
    profile: str,
    tier: str,
    effective: dict[str, Any],
    override: dict[str, Any],
) -> dict[str, Any]:
    """Validates + applies override on top of the effective dict."""
    extends = override.get("extends")
    if extends is not None:
        _validate_profile(extends)
        if extends != profile:
            raise ProfileMergeError(
                f"override.extends={extends!r} differs from profile passed={profile!r}"
            )

    override_tier = override.get("tier")
    if override_tier is not None:
        _validate_tier(override_tier)
        if override_tier != tier:
            raise ProfileMergeError(
                f"override.tier={override_tier!r} differs from tier passed={tier!r}"
            )

    if "revisit_after" in override:
        _validate_iso_8601(override["revisit_after"])
        effective["revisit_after"] = override["revisit_after"]

    overrides = override.get("overrides") or {}
    if overrides:
        if not isinstance(overrides, dict):
            raise ProfileMergeError("overrides must be a dict")
        _validate_overrides_keys(overrides)
        confirm_unsafe = bool(override.get("confirm_unsafe", False))
        _check_unsafe_overrides(effective, overrides, confirm_unsafe)
        for key, value in overrides.items():
            effective[key] = value

    if "custom_stop_points" in override:
        _validate_custom_stop_points(override["custom_stop_points"])
        effective["custom_stop_points"] = override["custom_stop_points"]

    return effective


def compute_hash(effective: dict[str, Any]) -> str:
    """SHA256 hex do dict serializado em YAML canonico (sort_keys, block style)."""
    serialized = yaml.safe_dump(
        effective,
        sort_keys=True,
        default_flow_style=False,
        allow_unicode=True,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


# ============================================================================
# CLI
# ============================================================================

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Merge of profile + tier (+ optional override) into effective dict + hash."
    )
    parser.add_argument("--profile", required=True, help="Base profile (e.g.: app_web_backend)")
    parser.add_argument("--tier", required=True, help="Tier (experimental/tool/development/production)")
    parser.add_argument("--override", default=None, help="Path to .icm-profile.local.yaml")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        effective, h = merge_profile(
            profile=args.profile,
            tier=args.tier,
            override_path=Path(args.override) if args.override else None,
        )
    except ProfileMergeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"effective": effective, "hash": h}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
