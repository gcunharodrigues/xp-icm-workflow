#!/usr/bin/env python3
"""Forensic+ — anti-fraud structural audit per task in stage 04 wave-reviewer.

Reads CLI args + plan.md + git state. Runs 4 checks. Emits JSON to stdout.
Exit 0 always when script completes normally (regardless of violations).
Exit 1 on script crash (git missing, plan malformed, etc.).

Spec: docs/superpowers/specs/2026-05-03-forensic-plus-wave-reviewer-design.md
Canonical: references/forensic-plus-protocol.md
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any


# ============================================================================
# Constants
# ============================================================================

VALID_TIERS = ("experimental", "tool", "development", "production")


# ============================================================================
# CLI
# ============================================================================

def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Forensic+ structural audit for stage 04 wave-reviewer."
    )
    p.add_argument("--workspace-num", required=True, help="Workspace number (NNN).")
    p.add_argument("--wave", required=True, type=int, help="Wave index (1-based).")
    p.add_argument("--task-slug", required=True, help="Task slug (kebab-case).")
    p.add_argument("--base-branch", required=True, help="Base branch (e.g. main).")
    p.add_argument("--plan", required=True, help="Path to plan.md.")
    p.add_argument("--tier", required=True, choices=VALID_TIERS, help="Workspace tier.")
    p.add_argument("--output", default="json", choices=("json",), help="Output format.")
    return p.parse_args(argv)


# ============================================================================
# Main
# ============================================================================

def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])

    # Skeleton: emit empty result. Will be filled in Tasks 2-7.
    result: dict[str, Any] = {
        "task_slug": args.task_slug,
        "violations": [],
        "forensic_passed": True,
        "max_severity": "NONE",
    }
    sys.stdout.write(json.dumps(result, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
