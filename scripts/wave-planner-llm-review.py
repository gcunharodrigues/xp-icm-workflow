#!/usr/bin/env python3
"""Wave Planner LLM Review subagent (companion to wave-planner-script.py).

Receives the DAG draft (wave-plan.md), the original plan.md and
ambiguities-resolved.md, and returns a structured JSON verdict
(APPROVE / PROPOSE_CHANGES / SKIPPED).

Operating modes:
  1. Mock mode (--mock-response): reads JSON from fixture (used in tests).
  2. Prod mode (--llm-response): reads JSON produced by an external LLM (human-in-the-loop
     or CI pipeline that runs the LLM separately).
  3. Prompt mode (no response path): prints a formatted prompt to stdout and
     exits with code 2, waiting for a human/external algorithm to run the LLM and
     resubmit the JSON via --llm-response.

Skip threshold: total_tasks <= 2 or total_waves <= 1 -> do not spawn LLM (cost
does not justify the signal).

CLI:
  python scripts/wave-planner-llm-review.py
      --wave-plan stages/02_design/output/wave-plan.md
      --plan stages/02_design/output/plan.md
      --ambiguities stages/02_design/output/ambiguities-resolved.md
      --output stages/02_design/output/llm-review-verdict.json
      [--mock-response tests/mocks/llm_review_responses/<name>.json]
      [--llm-response path/to/llm_response.json]

Stdout: verdict=<X> issues=<N> proposed_changes=<M> skipped=<true|false>
Exit codes:
  0  success (any verdict, including SKIPPED)
  1  error (missing mock, invalid schema, IO)
  2  prompt emitted (interactive mode / human-in-the-loop)

JSON schema spec:
  {
    "verdict": "APPROVE" | "PROPOSE_CHANGES" | "SKIPPED",
    "issues": [
      {"type": str, "from": str, "to": str, "reason": str, "severity": str}
    ],
    "proposed_dag_changes": [
      {"action": "add_dep" | "split_wave", ...}
    ],
    "skip_reason": "<str>" (only if SKIPPED)
  }
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

# ----------------------------------------------------------------------------
# Constants / enums
# ----------------------------------------------------------------------------
VALID_VERDICTS: frozenset[str] = frozenset({"APPROVE", "PROPOSE_CHANGES", "SKIPPED"})
VALID_ISSUE_TYPES: frozenset[str] = frozenset(
    {"implicit_dep", "ambiguous_footprint", "sub_wave_merge"}
)
VALID_SEVERITIES: frozenset[str] = frozenset({"warning", "error"})
VALID_ACTIONS: frozenset[str] = frozenset({"add_dep", "split_wave"})


# ----------------------------------------------------------------------------
# Errors
# ----------------------------------------------------------------------------
class LLMReviewError(Exception):
    """Parse, validation, or review execution error."""


# ----------------------------------------------------------------------------
# Minimal parser of wave-plan.md (subset of what the companion writes)
# ----------------------------------------------------------------------------
@dataclass
class WavePlanSummary:
    """Minimal subset extracted from wave-plan.md to decide skip."""

    total_tasks: int
    total_waves: int
    total_sub_waves: int


def parse_wave_plan(path: Path) -> WavePlanSummary:
    """Reads wave-plan.md (YAML frontmatter) and returns a summary with totals.

    Possible errors:
      - file not found
      - missing frontmatter
      - required fields missing
    """
    if not path.exists():
        raise LLMReviewError(f"wave-plan file not found: {path}")
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise LLMReviewError(
            f"wave-plan missing YAML frontmatter (expected '---\\n' at start): {path}"
        )
    closing_idx = text.find("\n---\n", 4)
    if closing_idx == -1:
        raise LLMReviewError(f"wave-plan frontmatter not closed: {path}")
    raw_fm = text[4:closing_idx]
    try:
        fm = yaml.safe_load(raw_fm) or {}
    except yaml.YAMLError as exc:
        raise LLMReviewError(f"invalid YAML in wave-plan frontmatter: {exc}") from exc

    for key in ("total_tasks", "total_waves", "total_sub_waves"):
        if key not in fm:
            raise LLMReviewError(f"wave-plan frontmatter missing key {key!r}")
    return WavePlanSummary(
        total_tasks=int(fm["total_tasks"]),
        total_waves=int(fm["total_waves"]),
        total_sub_waves=int(fm["total_sub_waves"]),
    )


# ----------------------------------------------------------------------------
# Skip decision
# ----------------------------------------------------------------------------
def should_skip(summary: WavePlanSummary) -> tuple[bool, str]:
    """Returns (skip?, reason). Skips if total_tasks <= 2 OR total_waves <= 1."""
    if summary.total_tasks <= 2:
        return True, f"total_tasks={summary.total_tasks}"
    if summary.total_waves <= 1:
        return True, f"total_waves={summary.total_waves}"
    return False, ""


# ----------------------------------------------------------------------------
# Build prompt for human-in-the-loop / external LLM
# ----------------------------------------------------------------------------
PROMPT_TEMPLATE: str = """\
You are a wave-planner-reviewer. You receive the DAG draft + plan.md + ambiguities.

Task: read tasks + graph + ambiguities. Verify whether there are:
1. Ambiguous footprints not resolved by the deterministic phase
2. Undeclared implicit deps (e.g. task B needs the schema migrated by task A
   but does not declare the dep)
3. Sub-waves that could re-parallelize (cap unnecessarily reduced)

Structured JSON output:
{
  "verdict": "APPROVE" | "PROPOSE_CHANGES",
  "issues": [
    {"type": "implicit_dep", "from": "task-a", "to": "task-b", "reason": "..."},
    {"type": "ambiguous_footprint", "tasks": ["task-x", "task-y"], "suggestion": "..."}
  ],
  "proposed_dag_changes": [...]   // only if PROPOSE_CHANGES
}
"""


def _build_prompt(wave_plan_text: str, plan_text: str, ambiguities_text: str) -> str:
    """Builds the complete review prompt, including the 3 documents as context."""
    return (
        f"{PROMPT_TEMPLATE}\n"
        "---\n"
        "## Context: wave-plan.md (DAG draft)\n"
        "\n"
        f"{wave_plan_text}\n"
        "---\n"
        "## Context: plan.md (original input)\n"
        "\n"
        f"{plan_text}\n"
        "---\n"
        "## Context: ambiguities-resolved.md\n"
        "\n"
        f"{ambiguities_text}\n"
    )


# ----------------------------------------------------------------------------
# Spawn LLM (mockavel / human-in-the-loop)
# ----------------------------------------------------------------------------
def request_review(
    wave_plan_text: str,
    plan_text: str,
    ambiguities_text: str,
    *,
    response_path: Path | None = None,
) -> dict[str, Any] | str:
    """Requests LLM review.

    - If `response_path` is provided: reads JSON from path (mock or real external
      LLM response) and returns the parsed dict.
    - If `response_path` is absent: builds prompt via `_build_prompt` and returns it
      as a string. The caller should detect type str, print to stdout and
      return exit 2.

    The first three params (`wave_plan_text`/`plan_text`/`ambiguities_text`)
    feed the prompt in interactive mode, or are ignored when a
    `response_path` already exists.
    """
    if response_path is not None:
        if not response_path.exists():
            raise LLMReviewError(f"response file not found: {response_path}")
        try:
            data = json.loads(response_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise LLMReviewError(
                f"invalid JSON in response {response_path}: {exc}"
            ) from exc
        if not isinstance(data, dict):
            raise LLMReviewError(
                f"response JSON must be a dict, got {type(data).__name__}"
            )
        return data
    return _build_prompt(wave_plan_text, plan_text, ambiguities_text)


# ----------------------------------------------------------------------------
# Response validation
# ----------------------------------------------------------------------------
def validate_response(d: Any) -> dict[str, Any]:
    """Validates verdict schema. Aborts with LLMReviewError if invalid.

    Returns the normalized dict (with defaults filled in).
    """
    if not isinstance(d, dict):
        raise LLMReviewError(f"response must be a dict, got {type(d).__name__}")

    verdict = d.get("verdict")
    if verdict not in VALID_VERDICTS:
        raise LLMReviewError(
            f"invalid verdict {verdict!r}; must be one of {sorted(VALID_VERDICTS)}"
        )

    if verdict == "SKIPPED":
        # Legitimate path only when produced by the script itself (skip threshold).
        # We accept SKIPPED from mock for pass-through testing; empty defaults.
        issues = d.get("issues", [])
        proposed = d.get("proposed_dag_changes", [])
    else:
        # APPROVE / PROPOSE_CHANGES require fields issues + proposed_dag_changes.
        if "issues" not in d:
            raise LLMReviewError(
                f"response with verdict={verdict} must have field 'issues'"
            )
        if "proposed_dag_changes" not in d:
            raise LLMReviewError(
                f"response with verdict={verdict} must have field 'proposed_dag_changes'"
            )
        issues = d["issues"]
        proposed = d["proposed_dag_changes"]

    if not isinstance(issues, list):
        raise LLMReviewError(f"'issues' must be a list, got {type(issues).__name__}")
    if not isinstance(proposed, list):
        raise LLMReviewError(
            f"'proposed_dag_changes' must be a list, got {type(proposed).__name__}"
        )

    for idx, issue in enumerate(issues):
        if not isinstance(issue, dict):
            raise LLMReviewError(f"issues[{idx}] must be a dict")
        for key in ("type", "from", "to", "reason", "severity"):
            if key not in issue:
                raise LLMReviewError(f"issues[{idx}] missing key {key!r}")
        if issue["type"] not in VALID_ISSUE_TYPES:
            raise LLMReviewError(
                f"issues[{idx}].type {issue['type']!r} invalid; "
                f"must be one of {sorted(VALID_ISSUE_TYPES)}"
            )
        if issue["severity"] not in VALID_SEVERITIES:
            raise LLMReviewError(
                f"issues[{idx}].severity {issue['severity']!r} invalid; "
                f"must be one of {sorted(VALID_SEVERITIES)}"
            )

    for idx, change in enumerate(proposed):
        if not isinstance(change, dict):
            raise LLMReviewError(f"proposed_dag_changes[{idx}] must be a dict")
        if "action" not in change:
            raise LLMReviewError(
                f"proposed_dag_changes[{idx}] missing key 'action'"
            )
        if change["action"] not in VALID_ACTIONS:
            raise LLMReviewError(
                f"proposed_dag_changes[{idx}].action {change['action']!r} invalid; "
                f"must be one of {sorted(VALID_ACTIONS)}"
            )

    normalized: dict[str, Any] = {
        "verdict": verdict,
        "issues": issues,
        "proposed_dag_changes": proposed,
    }
    if verdict == "SKIPPED" and "skip_reason" in d:
        normalized["skip_reason"] = d["skip_reason"]
    return normalized


# ----------------------------------------------------------------------------
# Build verdict SKIPPED localmente (sem chamar LLM)
# ----------------------------------------------------------------------------
def build_skipped_verdict(skip_reason: str) -> dict[str, Any]:
    """Builds the canonical SKIPPED dict produced by the script itself."""
    return {
        "verdict": "SKIPPED",
        "issues": [],
        "proposed_dag_changes": [],
        "skip_reason": skip_reason,
    }


# ----------------------------------------------------------------------------
# Update wave-plan.md frontmatter
# ----------------------------------------------------------------------------
def _update_wave_plan_llm_review(wave_plan_path: Path, verdict: str) -> None:
    """Updates wave-plan.md frontmatter with llm_review + increments iterations.

    - llm_review -> <verdict>
    - llm_review_iterations -> +1 (or 1 if absent)
    - Preserves markdown body and all other frontmatter fields.
    """
    if not wave_plan_path.exists():
        raise LLMReviewError(f"wave-plan file not found: {wave_plan_path}")
    text = wave_plan_path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise LLMReviewError(
            f"wave-plan missing YAML frontmatter (expected '---\\n' at start): {wave_plan_path}"
        )
    closing_idx = text.find("\n---\n", 4)
    if closing_idx == -1:
        raise LLMReviewError(
            f"wave-plan frontmatter not closed: {wave_plan_path}"
        )
    raw_fm = text[4:closing_idx]
    body = text[closing_idx + 5 :]
    try:
        fm = yaml.safe_load(raw_fm) or {}
    except yaml.YAMLError as exc:
        raise LLMReviewError(
            f"invalid YAML in wave-plan frontmatter: {exc}"
        ) from exc

    if not isinstance(fm, dict):
        raise LLMReviewError(
            f"wave-plan frontmatter must be a dict, got {type(fm).__name__}"
        )

    fm["llm_review"] = verdict
    fm["llm_review_iterations"] = int(fm.get("llm_review_iterations", 0)) + 1

    new_fm = yaml.safe_dump(fm, allow_unicode=True, sort_keys=False)
    new_text = f"---\n{new_fm}---\n{body}"
    wave_plan_path.write_text(new_text, encoding="utf-8")


# ----------------------------------------------------------------------------
# Update L1 llm_review_skipped_count
# ----------------------------------------------------------------------------
def _increment_llm_review_skipped_count(context_path: Path) -> None:
    """Increments `llm_review_skipped_count` in the L1 frontmatter (CONTEXT.md).

    If field is absent, initializes to 1. Preserves markdown body and other fields.
    Returns silently if file does not exist or frontmatter is invalid
    (does not fail the review on L1 error).
    """
    if not context_path.exists():
        return
    text = context_path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return
    closing_idx = text.find("\n---\n", 4)
    if closing_idx == -1:
        return
    raw_fm = text[4:closing_idx]
    body = text[closing_idx + 5 :]
    try:
        fm = yaml.safe_load(raw_fm) or {}
    except yaml.YAMLError:
        return
    if not isinstance(fm, dict):
        return
    fm["llm_review_skipped_count"] = int(fm.get("llm_review_skipped_count", 0)) + 1
    new_fm = yaml.safe_dump(fm, allow_unicode=True, sort_keys=False)
    new_text = f"---\n{new_fm}---\n{body}"
    context_path.write_text(new_text, encoding="utf-8")


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------
def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Wave Planner LLM Review (subagent companion)."
    )
    parser.add_argument(
        "--wave-plan",
        required=True,
        type=Path,
        help="path to wave-plan.md (generated by wave-planner-script.py)",
    )
    parser.add_argument(
        "--plan",
        required=True,
        type=Path,
        help="path to plan.md (original wave planner input)",
    )
    parser.add_argument(
        "--ambiguities",
        required=True,
        type=Path,
        help="path to ambiguities-resolved.md",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="path to llm-review-verdict.json (output)",
    )
    parser.add_argument(
        "--mock-response",
        type=Path,
        default=None,
        help="path to mock JSON (test mode); mutually exclusive with --llm-response",
    )
    parser.add_argument(
        "--llm-response",
        type=Path,
        default=None,
        help="path to JSON produced by external LLM (prod mode); mutually exclusive with --mock-response",
    )
    parser.add_argument(
        "--update-wave-plan",
        type=Path,
        default=None,
        help="path to wave-plan.md to update with llm_review in frontmatter",
    )
    parser.add_argument(
        "--workspace-context",
        type=Path,
        default=None,
        help="path to workspace L1 CONTEXT.md; used to increment llm_review_skipped_count when skip occurs",
    )
    return parser.parse_args(argv)


def _read_text_safe(path: Path, label: str) -> str:
    if not path.exists():
        raise LLMReviewError(f"{label} file not found: {path}")
    return path.read_text(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(list(sys.argv[1:] if argv is None else argv))

    try:
        # 1. Parse wave-plan summary + decide skip.
        summary = parse_wave_plan(args.wave_plan)
        skip, reason = should_skip(summary)

        if skip:
            verdict_dict = build_skipped_verdict(reason)
        else:
            # 2. Read text inputs.
            wave_plan_text = _read_text_safe(args.wave_plan, "wave-plan")
            plan_text = _read_text_safe(args.plan, "plan")
            ambiguities_text = _read_text_safe(args.ambiguities, "ambiguities")

            response_path = args.mock_response or args.llm_response
            raw = request_review(
                wave_plan_text,
                plan_text,
                ambiguities_text,
                response_path=response_path,
            )
            if isinstance(raw, str):
                # Prompt mode: no response path provided.
                print(raw, end="")
                return 2
            verdict_dict = validate_response(raw)

    except LLMReviewError as exc:
        print(f"llm-review error: {exc}", file=sys.stderr)
        return 1

    # 3. Update wave-plan.md frontmatter if requested.
    if args.update_wave_plan is not None:
        if not args.update_wave_plan.exists():
            raise LLMReviewError(
                f"--update-wave-plan file not found: {args.update_wave_plan}"
            )
        _update_wave_plan_llm_review(
            args.update_wave_plan, verdict_dict["verdict"]
        )

    # 3b. If skip occurred and workspace-context provided, increment counter in L1.
    if (
        verdict_dict["verdict"] == "SKIPPED"
        and args.workspace_context is not None
    ):
        _increment_llm_review_skipped_count(args.workspace_context)

    # 4. Write output JSON.
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(verdict_dict, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    # 5. Summarized stdout.
    is_skipped = verdict_dict["verdict"] == "SKIPPED"
    print(
        f"verdict={verdict_dict['verdict']} "
        f"issues={len(verdict_dict.get('issues', []))} "
        f"proposed_changes={len(verdict_dict.get('proposed_dag_changes', []))} "
        f"skipped={'true' if is_skipped else 'false'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
