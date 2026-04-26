"""Merge de profile base + override local em profile efetivo + hash deterministico.

Cobre 10 profiles canonicos x 4 tiers, com regras de override seguro
(`confirm_unsafe`) e validacao estrita de schema.
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
# Constantes / matriz canonica
# ============================================================================

CANONICAL_PROFILES: tuple[str, ...] = (
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
    "cap_teammates_per_wave",
    "stop_points_calibration",
})

UNSAFE_KEYS: frozenset[str] = frozenset({
    "tdd_required",
    "security_gate",
    "peer_review_required",
})

ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2})?$")


class ProfileMergeError(Exception):
    """Erro de validacao ou merge de profile."""


# ============================================================================
# Defaults por tier (sem profile override aplicado)
# ============================================================================

def _tier_defaults(tier: str) -> dict[str, Any]:
    """Retorna o dict base para um tier; profile-overrides aplicam por cima."""
    if tier == "experimental":
        return {
            "stages_skipped": [],
            "tdd_required": False,
            "tdd_mode": "optional",
            "security_gate": False,
            "tech_debt_tracking": False,
            "peer_review_required": False,
            "cap_teammates_per_wave": 2,
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
            "cap_teammates_per_wave": 3,
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
            "cap_teammates_per_wave": 5,
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
            "cap_teammates_per_wave": 5,
            "stop_points_calibration": {
                "item_5": {"mode": "hard", "limite_mensal_BRL": 1000},
                "item_7": {"mode": "hard"},
                "item_8": {"mode": "hard+DPO"},
            },
        }
    raise ProfileMergeError(f"tier desconhecido: {tier!r}")


# ============================================================================
# Profile-specific overrides aplicados sobre os defaults de tier
# ============================================================================

def _apply_profile_rules(profile: str, tier: str, base: dict[str, Any]) -> dict[str, Any]:
    """Aplica regras especificas do profile sobre o dict base de tier."""
    out = copy.deepcopy(base)

    if profile == "experiment":
        out["stages_skipped"] = ["03", "05", "06", "08"]

    if profile == "technical_article":
        # Artigo tecnico nao precisa do estagio 03 (testes/qualidade automatizada)
        skipped = set(out["stages_skipped"])
        skipped.add("03")
        out["stages_skipped"] = sorted(skipped)
        out["cap_teammates_per_wave"] = 5

    if profile == "framework_library":
        out["cap_teammates_per_wave"] = 3

    if profile == "ml_project":
        out["cap_teammates_per_wave"] = 3

    # Apps web ligam security_gate em qualquer tier acima de experimental
    if profile in ("app_web_backend", "app_web_frontend") and tier != "experimental":
        out["security_gate"] = True

    return out


# ============================================================================
# Validacao
# ============================================================================

def _validate_profile(profile: str) -> None:
    if profile not in CANONICAL_PROFILES:
        raise ProfileMergeError(
            f"profile invalido: {profile!r} (esperado: {', '.join(CANONICAL_PROFILES)})"
        )


def _validate_tier(tier: str) -> None:
    if tier not in CANONICAL_TIERS:
        raise ProfileMergeError(
            f"tier invalido: {tier!r} (esperado: {', '.join(CANONICAL_TIERS)})"
        )


def _validate_iso_8601(value: str) -> None:
    if not isinstance(value, str) or not ISO_DATE_RE.match(value):
        raise ProfileMergeError(
            f"revisit_after deve ser ISO 8601 (YYYY-MM-DD ou YYYY-MM-DDTHH:MM:SS), recebido: {value!r}"
        )


def _validate_overrides_keys(overrides: dict[str, Any]) -> None:
    unknown = set(overrides) - MATRIX_KEYS
    if unknown:
        raise ProfileMergeError(
            f"overrides contem chaves desconhecidas: {sorted(unknown)} "
            f"(permitidas: {sorted(MATRIX_KEYS)})"
        )


def _validate_custom_stop_points(items: Any) -> None:
    if not isinstance(items, list):
        raise ProfileMergeError("custom_stop_points deve ser lista")
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            raise ProfileMergeError(f"custom_stop_points[{idx}] deve ser dict")
        if not isinstance(item.get("id"), str) or not item["id"]:
            raise ProfileMergeError(f"custom_stop_points[{idx}].id ausente ou nao-string")
        if not isinstance(item.get("description"), str) or not item["description"]:
            raise ProfileMergeError(
                f"custom_stop_points[{idx}].description ausente ou nao-string"
            )
        threshold = item.get("threshold")
        if not isinstance(threshold, dict) or not threshold:
            raise ProfileMergeError(
                f"custom_stop_points[{idx}].threshold deve ser dict nao-vazio"
            )
        for tier_key in threshold:
            if tier_key not in CANONICAL_TIERS:
                raise ProfileMergeError(
                    f"custom_stop_points[{idx}].threshold tier invalido: {tier_key!r}"
                )


# ============================================================================
# Override loading + application
# ============================================================================

def _load_override(path: Path) -> dict[str, Any]:
    """Carrega arquivo .icm-profile.local.yaml em dict; valida existencia."""
    if not path.exists():
        raise ProfileMergeError(f"override path nao existe: {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ProfileMergeError(f"override YAML invalido: {exc}") from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ProfileMergeError("override raiz deve ser mapping/dict")
    return data


def _check_unsafe_overrides(
    base_after_profile: dict[str, Any],
    overrides: dict[str, Any],
    confirm_unsafe: bool,
) -> None:
    """Levanta se override desliga gate critico sem confirm_unsafe=true."""
    for key in UNSAFE_KEYS:
        if key not in overrides:
            continue
        was_on = bool(base_after_profile.get(key))
        will_be = bool(overrides[key])
        if was_on and not will_be and not confirm_unsafe:
            raise ProfileMergeError(
                f"override perigoso requer confirm_unsafe: true (chave: {key})"
            )


# ============================================================================
# API publica
# ============================================================================

def merge_profile(
    profile: str,
    tier: str,
    override_path: Path | str | None = None,
) -> tuple[dict[str, Any], str]:
    """Produz profile efetivo + hash; aplica override se fornecido."""
    _validate_profile(profile)
    _validate_tier(tier)

    base = _tier_defaults(tier)
    effective = _apply_profile_rules(profile, tier, base)
    effective["profile"] = profile
    effective["tier"] = tier

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
    """Valida + aplica override sobre o dict efetivo."""
    extends = override.get("extends")
    if extends is not None:
        _validate_profile(extends)
        if extends != profile:
            raise ProfileMergeError(
                f"override.extends={extends!r} difere do profile passado={profile!r}"
            )

    override_tier = override.get("tier")
    if override_tier is not None:
        _validate_tier(override_tier)
        if override_tier != tier:
            raise ProfileMergeError(
                f"override.tier={override_tier!r} difere do tier passado={tier!r}"
            )

    if "revisit_after" in override:
        _validate_iso_8601(override["revisit_after"])
        effective["revisit_after"] = override["revisit_after"]

    overrides = override.get("overrides") or {}
    if overrides:
        if not isinstance(overrides, dict):
            raise ProfileMergeError("overrides deve ser dict")
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
        description="Merge de profile + tier (+ override opcional) em dict efetivo + hash."
    )
    parser.add_argument("--profile", required=True, help="Profile base (ex.: app_web_backend)")
    parser.add_argument("--tier", required=True, help="Tier (experimental/tool/development/production)")
    parser.add_argument("--override", default=None, help="Path para .icm-profile.local.yaml")
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
        print(f"erro: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"effective": effective, "hash": h}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
