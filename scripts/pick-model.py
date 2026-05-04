#!/usr/bin/env python3
"""Pick-model — heurística determinística pra escolher (writer, critic) por task.

Compute complexity score from task metadata + tier ceiling cap. Emit JSON to
stdout. Consumido por agent-brief-render.py em fase 04 stage subagent dispatch.

Spec: references/critic-protocol.md (critic always tier ceiling),
plan v3.9.0 §7 (compute_score formula + TIER_CEILING + pick_models split).

Canonical script — drift-checked against bootstrap CURRENT_SKILL_VERSION.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


# ============================================================================
# Constants — keep aligned with plan v3.9.0 §7 + critic-protocol.md
# ============================================================================

CURRENT_SKILL_VERSION = "3.9.0"

# Models ordered worst → best (used for `min()` cap on writer).
MODEL_RANK: dict[str, int] = {
    "claude-haiku-4-5": 1,
    "claude-sonnet-4-6": 2,
    "claude-opus-4-7": 3,
}
RANK_TO_MODEL: dict[int, str] = {v: k for k, v in MODEL_RANK.items()}

TIER_CEILING: dict[str, str] = {
    "experimental": "claude-haiku-4-5",
    "tool":         "claude-sonnet-4-6",
    "development":  "claude-opus-4-7",
    "production":   "claude-opus-4-7",
}

VALID_TIERS = tuple(TIER_CEILING.keys())

DEFAULT_HOT_PATHS = (
    "auth/",
    "payments/",
    "crypto/",
    "migrations/",
)


# ============================================================================
# Score computation
# ============================================================================

def _path_matches_hot(files: list[str], hot_paths: tuple[str, ...]) -> bool:
    """True if any file in `files` contains any hot path substring."""
    return any(any(hp in f for hp in hot_paths) for f in files)


def compute_score(
    estimated_lines: int | None,
    files_touched: list[str],
    *,
    security_sensitive: bool = False,
    public_api_change: bool = False,
    algorithm_heavy: bool = False,
    doc_only: bool = False,
    config_only: bool = False,
    css_only: bool = False,
    tier: str = "development",
    hot_paths: tuple[str, ...] = DEFAULT_HOT_PATHS,
) -> int:
    """Compute integer complexity score. Higher = more complex.

    Spec (plan v3.9.0 §7):
      +3 if estimated_lines > 200
      +1 if estimated_lines > 50
      +2 if any file in HOT_PATHS
      +3 if security_sensitive
      +2 if public_api_change
      +2 if algorithm_heavy
      -2 if doc_only or config_only
      -1 if css_only
      +1 if tier == production
      -1 if tier == experimental
    """
    score = 0
    if estimated_lines is not None:
        if estimated_lines > 200:
            score += 3
        elif estimated_lines > 50:
            score += 1
    if _path_matches_hot(files_touched, hot_paths):
        score += 2
    if security_sensitive:
        score += 3
    if public_api_change:
        score += 2
    if algorithm_heavy:
        score += 2
    if doc_only or config_only:
        score -= 2
    if css_only:
        score -= 1
    if tier == "production":
        score += 1
    elif tier == "experimental":
        score -= 1
    return score


# ============================================================================
# Model picking
# ============================================================================

def _model_min(a: str, b: str) -> str:
    """Return the lower-ranked model between a and b."""
    return a if MODEL_RANK[a] <= MODEL_RANK[b] else b


def pick_models(score: int, tier: str) -> tuple[str, str]:
    """Return (writer, critic) tuple per heurística + tier ceiling.

    - writer = haiku if score < 2, sonnet if score < 5, else opus
    - writer = min(writer, TIER_CEILING[tier])  # ceiling cap
    - critic = TIER_CEILING[tier]  # always
    """
    if tier not in TIER_CEILING:
        raise ValueError(f"unknown tier: {tier}")

    if score < 2:
        writer = "claude-haiku-4-5"
    elif score < 5:
        writer = "claude-sonnet-4-6"
    else:
        writer = "claude-opus-4-7"

    ceiling = TIER_CEILING[tier]
    writer = _model_min(writer, ceiling)
    critic = ceiling
    return writer, critic


# ============================================================================
# Plan parser (lightweight — reuse forensic-plus.py style)
# ============================================================================

class PlanParseError(Exception):
    pass


def _extract_task_section(plan_path: Path, task_slug: str) -> str:
    if not plan_path.is_file():
        raise PlanParseError(f"plan.md not found: {plan_path}")
    text = plan_path.read_text(encoding="utf-8")
    header_re = re.compile(rf"^## Task {re.escape(task_slug)}:", re.MULTILINE)
    m = header_re.search(text)
    if not m:
        raise PlanParseError(f"task slug not found in plan: {task_slug}")
    next_m = re.search(r"^## ", text[m.end():], re.MULTILINE)
    end = m.end() + next_m.start() if next_m else len(text)
    return text[m.start():end]


def _bullets_under(section: str, heading: str) -> list[str]:
    h_re = re.compile(rf"^### {re.escape(heading)}\s*\n", re.MULTILINE)
    h_m = h_re.search(section)
    if not h_m:
        return []
    rest = section[h_m.end():]
    next_h = re.search(r"^### ", rest, re.MULTILINE)
    block = rest[: next_h.start()] if next_h else rest
    return [
        re.sub(r"^-\s+", "", ln).strip()
        for ln in block.splitlines()
        if ln.strip().startswith("-")
    ]


def parse_task_metadata(plan_path: Path, task_slug: str) -> dict:
    """Extract task metadata for score computation.

    Heurísticas para flags (security_sensitive, public_api_change, etc.):
    - security_sensitive: paths em `Files touched` matching auth|crypto|payments|secret|token + tier
    - public_api_change: bullet contains "public API" / "exported" / "interface change" in O QUE/COMO
    - algorithm_heavy: bullets contain state machine|concurrent|dag|algorithm|graph|tree
    - doc_only / config_only: declared em `Conventions extras`
    - css_only: all files_touched end .css/.scss/.sass
    """
    section = _extract_task_section(plan_path, task_slug)

    files_touched = _bullets_under(section, "Files touched")
    conventions = _bullets_under(section, "Conventions extras")
    o_que = _bullets_under(section, "O QUE")
    como = _bullets_under(section, "COMO")

    # estimated_lines
    est_lines = None
    est_h = re.search(r"^### Estimated lines\s*\n", section, re.MULTILINE)
    if est_h:
        rest = section[est_h.end():]
        next_h = re.search(r"^### ", rest, re.MULTILINE)
        block = rest[: next_h.start()] if next_h else rest
        num_m = re.search(r"\d+", block)
        if num_m:
            est_lines = int(num_m.group(0))

    conv_lower = " ".join(c.lower() for c in conventions)
    doc_only = "doc-only" in conv_lower
    config_only = "config-only" in conv_lower

    css_only = (
        bool(files_touched)
        and all(re.search(r"\.(css|scss|sass)$", f) for f in files_touched)
    )

    sec_paths = ("auth/", "crypto/", "payments/", "secret", "token", "/jwt", "migrations/")
    security_sensitive = any(
        any(s in f.lower() for s in sec_paths) for f in files_touched
    )

    api_phrases = ("public api", "exported", "interface change", "breaking change")
    qa_text = " ".join((o_que + como)).lower()
    public_api_change = any(p in qa_text for p in api_phrases)

    algo_phrases = ("state machine", "concurrent", "dag", "algorithm", "graph", "tree", "scheduler", "topological")
    algorithm_heavy = any(p in qa_text for p in algo_phrases)

    return {
        "estimated_lines": est_lines,
        "files_touched": files_touched,
        "security_sensitive": security_sensitive,
        "public_api_change": public_api_change,
        "algorithm_heavy": algorithm_heavy,
        "doc_only": doc_only,
        "config_only": config_only,
        "css_only": css_only,
    }


# ============================================================================
# CLI
# ============================================================================

def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Pick (writer, critic) models per task complexity + tier ceiling."
    )
    p.add_argument("--plan", required=True, help="Path to plan.md")
    p.add_argument("--task-slug", required=True, help="Task slug (kebab-case)")
    p.add_argument("--tier", required=True, choices=VALID_TIERS, help="Workspace tier")
    p.add_argument(
        "--hot-paths", default=",".join(DEFAULT_HOT_PATHS),
        help="Comma-separated hot path substrings (default: auth/,payments/,crypto/,migrations/)",
    )
    p.add_argument("--output", default="json", choices=("json",))
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    plan_path = Path(args.plan)
    hot_paths = tuple(p.strip() for p in args.hot_paths.split(",") if p.strip())

    try:
        meta = parse_task_metadata(plan_path, args.task_slug)
    except PlanParseError as e:
        sys.stderr.write(f"pick-model: {e}\n")
        return 1

    score = compute_score(
        estimated_lines=meta["estimated_lines"],
        files_touched=meta["files_touched"],
        security_sensitive=meta["security_sensitive"],
        public_api_change=meta["public_api_change"],
        algorithm_heavy=meta["algorithm_heavy"],
        doc_only=meta["doc_only"],
        config_only=meta["config_only"],
        css_only=meta["css_only"],
        tier=args.tier,
        hot_paths=hot_paths,
    )
    writer, critic = pick_models(score, args.tier)

    result: dict[str, Any] = {
        "task_slug": args.task_slug,
        "tier": args.tier,
        "complexity_score": score,
        "model_recommended_writer": writer,
        "model_recommended_critic": critic,
        "tier_ceiling": TIER_CEILING[args.tier],
        "factors": {
            "estimated_lines": meta["estimated_lines"],
            "hot_path_match": _path_matches_hot(meta["files_touched"], hot_paths),
            "security_sensitive": meta["security_sensitive"],
            "public_api_change": meta["public_api_change"],
            "algorithm_heavy": meta["algorithm_heavy"],
            "doc_only": meta["doc_only"],
            "config_only": meta["config_only"],
            "css_only": meta["css_only"],
        },
    }
    sys.stdout.write(json.dumps(result, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
