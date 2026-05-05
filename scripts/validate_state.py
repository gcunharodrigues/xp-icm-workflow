#!/usr/bin/env python3
"""L1 (state machine) validator for the root CONTEXT.md schema of a workspace.

Python backend called by scripts/validate-state.sh. Separated from the bash
wrapper for testability — property-based tests in tests/unit/test_state_machine.py.

CLI: python scripts/validate_state.py --workspace <path>

Canonical schema documented in references/state-machine-schema.md.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import yaml


# Canonical enums -------------------------------------------------------------

VALID_TIERS: frozenset[str] = frozenset(
    {"experimental", "tool", "development", "production"}
)

VALID_STATUSES: frozenset[str] = frozenset(
    {
        "IN_PROGRESS",
        "COMPLETED_AWAITING_HUMAN",
        "BLOCKED_STOP_POINT",
        "BLOCKED_ERROR",
        "BLOCKED_HITL",
        "LEAD_RESOLUTION_IN_PROGRESS",  # v3.9.0
        "COMPLETED",
    }
)

# Stable public alias (v3.5.0+) — single source of truth for drift detector
# (test_no_drift.py imports this symbol). Do not rename without updating drift test.
ALLOWED_STATUSES: frozenset[str] = VALID_STATUSES

VALID_STAGES: frozenset[str] = frozenset(
    {"00", "01", "02", "03", "04", "05", "06", "07", "08"}
)

# Simple sub-stage enums (stages without variable N)
SIMPLE_SUB_STAGE_ENUMS: dict[str, frozenset[str]] = {
    "00": frozenset({"00_in_progress", "00_completed"}),
    "01": frozenset({"01_in_progress", "01_completed"}),
    "02": frozenset({"02_in_progress", "02_completed"}),
    "03": frozenset({"03_in_progress", "03_completed"}),
    "05": frozenset({"05_in_progress", "05_completed"}),
    "06": frozenset({"06_in_progress", "06_completed"}),
    "07": frozenset({"07_in_progress", "07_completed"}),
    "08": frozenset(
        {
            "08_in_progress",
            "08_decided_A",
            "08_decided_B",
            "08_decided_C",
        }
    ),
}

# Stage 04 has variable N — regex
SUB_STAGE_04_PATTERN = re.compile(r"^04_wave_(\d+)_(in_progress|completed)$")

REQUIRED_FIELDS: tuple[str, ...] = (
    "workspace",
    "profile_base",
    "profile_effective_hash",
    "tier",
    "project_root",
    "base_branch",
    "workspace_branch",
    "stage_atual",
    "sub_stage",
    "status",
    "iteration",
    "history",
    "last_action",
    "last_action_at",
    "next_action",
    "last_transition",
)

LAST_TRANSITION_REQUIRED_KEYS: tuple[str, ...] = ("from", "to", "at", "commit_sha")


class StateValidationError(Exception):
    """L1 state validation error."""


# Parsing ---------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(
    r"^---\s*\n(?P<body>.*?)\n---\s*(?:\n|$)", re.DOTALL
)


def parse_frontmatter(content: str) -> dict[str, Any]:
    """Extracts and parses the YAML frontmatter from a CONTEXT.md.

    Raises StateValidationError if there is no frontmatter or if the YAML is
    invalid.
    """
    match = _FRONTMATTER_RE.match(content)
    if match is None:
        raise StateValidationError(
            "CONTEXT.md does not have YAML frontmatter delimited by '---'"
        )
    raw = match.group("body")
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise StateValidationError(f"Invalid YAML frontmatter: {exc}") from exc
    if not isinstance(data, dict):
        raise StateValidationError(
            "YAML frontmatter must be a top-level mapping (dict), received: "
            f"{type(data).__name__}"
        )
    return data


# Validation ------------------------------------------------------------------

def _validate_required_fields(state: dict[str, Any]) -> None:
    missing = [f for f in REQUIRED_FIELDS if f not in state]
    if missing:
        raise StateValidationError(
            f"Required fields missing in CONTEXT.md: {', '.join(missing)}"
        )


def _validate_tier(state: dict[str, Any]) -> None:
    tier = state["tier"]
    if tier not in VALID_TIERS:
        raise StateValidationError(
            f"Invalid tier: '{tier}'. Expected one of: "
            f"{sorted(VALID_TIERS)}"
        )


def _validate_status(state: dict[str, Any]) -> None:
    status = state["status"]
    if status not in VALID_STATUSES:
        raise StateValidationError(
            f"Invalid status: '{status}'. Expected one of: "
            f"{sorted(VALID_STATUSES)}"
        )


def _validate_stage_atual(state: dict[str, Any]) -> None:
    stage = state["stage_atual"]
    if not isinstance(stage, str) or stage not in VALID_STAGES:
        raise StateValidationError(
            f"Invalid stage_atual: '{stage}'. Expected string in "
            f"{sorted(VALID_STAGES)}"
        )


def _validate_sub_stage(state: dict[str, Any]) -> None:
    """sub_stage must start with prefix `<stage_atual>_` AND match enum."""
    stage = state["stage_atual"]
    sub_stage = state["sub_stage"]
    if not isinstance(sub_stage, str):
        raise StateValidationError(
            f"sub_stage must be a string, received {type(sub_stage).__name__}"
        )
    expected_prefix = f"{stage}_"
    if not sub_stage.startswith(expected_prefix):
        raise StateValidationError(
            f"sub_stage '{sub_stage}' does not start with prefix "
            f"'{expected_prefix}' (stage_atual='{stage}')"
        )

    if stage == "04":
        if not SUB_STAGE_04_PATTERN.match(sub_stage):
            raise StateValidationError(
                f"sub_stage '{sub_stage}' does not match pattern "
                "'04_wave_<N>_in_progress|completed'"
            )
        return

    valid = SIMPLE_SUB_STAGE_ENUMS.get(stage)
    if valid is None or sub_stage not in valid:
        raise StateValidationError(
            f"sub_stage '{sub_stage}' is not in the valid enum for stage "
            f"'{stage}': {sorted(valid) if valid else '<none>'}"
        )


def _validate_iteration(state: dict[str, Any]) -> None:
    iteration = state["iteration"]
    # bool is int in Python; reject bool explicitly
    if isinstance(iteration, bool) or not isinstance(iteration, int):
        raise StateValidationError(
            f"iteration must be an integer, received {type(iteration).__name__}"
        )
    if iteration < 0:
        raise StateValidationError(
            f"iteration must be >= 0, received {iteration}"
        )

    history = state.get("history") or []
    increment_events = sum(
        1
        for item in history
        if isinstance(item, dict) and item.get("event") == "iteration_increment"
    )
    if increment_events != iteration:
        raise StateValidationError(
            f"iteration ({iteration}) does not match number of "
            f"'iteration_increment' events in history ({increment_events}). "
            "iteration must be monotonic vs history."
        )


def _validate_history(state: dict[str, Any]) -> None:
    history = state["history"]
    if not isinstance(history, list):
        raise StateValidationError(
            f"history must be a list, received {type(history).__name__}"
        )
    for idx, item in enumerate(history):
        if not isinstance(item, dict):
            raise StateValidationError(
                f"history[{idx}] must be a mapping, received "
                f"{type(item).__name__}"
            )
        if "at" not in item:
            raise StateValidationError(
                f"history[{idx}] missing required field 'at'"
            )
        if "event" not in item:
            raise StateValidationError(
                f"history[{idx}] missing required field 'event'"
            )


def _validate_waves(state: dict[str, Any]) -> None:
    """waves absent/null iff stage_atual < '04'; present iff >= '04'."""
    stage = state["stage_atual"]
    waves_present = "waves" in state and state["waves"] is not None

    stage_ge_04 = stage >= "04"

    if stage_ge_04 and not waves_present:
        raise StateValidationError(
            f"stage_atual='{stage}' (>=04) requires 'waves' field present "
            "(non-null) with keys 'current' and 'completed'"
        )
    if not stage_ge_04 and waves_present:
        raise StateValidationError(
            f"stage_atual='{stage}' (<04) CANNOT have 'waves' field "
            "present — must be absent or null"
        )

    if not waves_present:
        return

    waves = state["waves"]
    if not isinstance(waves, dict):
        raise StateValidationError(
            f"waves must be a mapping, received {type(waves).__name__}"
        )
    for key in ("current", "completed"):
        if key not in waves:
            raise StateValidationError(
                f"waves missing required field '{key}'"
            )
    if isinstance(waves["current"], bool) or not isinstance(
        waves["current"], int
    ):
        raise StateValidationError(
            f"waves.current must be an integer, received "
            f"{type(waves['current']).__name__}"
        )
    if not isinstance(waves["completed"], list):
        raise StateValidationError(
            f"waves.completed must be a list, received "
            f"{type(waves['completed']).__name__}"
        )


def _validate_last_transition(state: dict[str, Any]) -> None:
    lt = state["last_transition"]
    if not isinstance(lt, dict):
        raise StateValidationError(
            f"last_transition must be a mapping, received {type(lt).__name__}"
        )
    missing = [k for k in LAST_TRANSITION_REQUIRED_KEYS if k not in lt]
    if missing:
        raise StateValidationError(
            f"last_transition missing required fields: {', '.join(missing)}"
        )


def validate_state(state: dict[str, Any]) -> None:
    """Validates an L1 state dict.

    Raises StateValidationError with a specific message on failure.
    """
    _validate_required_fields(state)
    _validate_tier(state)
    _validate_status(state)
    _validate_stage_atual(state)
    _validate_sub_stage(state)
    _validate_history(state)  # before iteration because iteration uses history
    _validate_iteration(state)
    _validate_waves(state)
    _validate_last_transition(state)


def validate_workspace(workspace_path: Path) -> None:
    """Validates the root CONTEXT.md of a workspace.

    Raises StateValidationError or FileNotFoundError.
    """
    context_md = workspace_path / "CONTEXT.md"
    if not context_md.is_file():
        raise StateValidationError(
            f"CONTEXT.md not found in workspace: {context_md}"
        )
    content = context_md.read_text(encoding="utf-8")
    state = parse_frontmatter(content)
    validate_state(state)


# CLI entrypoint ---------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="validate_state.py",
        description="Validates the L1 state (root CONTEXT.md) of a workspace.",
    )
    parser.add_argument(
        "--workspace",
        required=True,
        help="Path to the workspace directory (contains CONTEXT.md)",
    )
    args = parser.parse_args(argv)

    workspace = Path(args.workspace)
    try:
        validate_workspace(workspace)
    except StateValidationError as exc:
        print(f"StateValidationError: {exc}", file=sys.stderr)
        return 1
    except FileNotFoundError as exc:
        print(f"FileNotFoundError: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
