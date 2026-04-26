#!/usr/bin/env python3
"""Wave Planner LLM Review subagent (companion do wave-planner-script.py).

Recebe o DAG draft (wave-plan.md), o plan.md original e o ambiguities-resolved.md,
spawna subagent de review (Task tool em prod, mock em test) e devolve um
veredicto json estruturado (APPROVE / PROPOSE_CHANGES / SKIPPED).

Skip threshold: total_tasks <= 2 ou total_waves <= 1 -> nao spawna LLM (custo
nao justifica sinal).

CLI:
  python scripts/wave-planner-llm-review.py
      --wave-plan stages/03_wave_planner/output/wave-plan.md
      --plan stages/02_design/output/plan.md
      --ambiguities stages/03_wave_planner/output/ambiguities-resolved.md
      --output stages/03_wave_planner/output/llm-review-verdict.json
      [--mock-response tests/mocks/llm_review_responses/<name>.json]

Stdout: verdict=<X> issues=<N> proposed_changes=<M> skipped=<true|false>
Exit codes:
  0  sucesso (qualquer verdict, inclusive SKIPPED)
  1  erro (mock ausente, schema invalido, IO, NotImplementedError em prod)

Spec do schema (json):
  {
    "verdict": "APPROVE" | "PROPOSE_CHANGES" | "SKIPPED",
    "issues": [
      {"type": str, "from": str, "to": str, "reason": str, "severity": str}
    ],
    "proposed_dag_changes": [
      {"action": "add_dep" | "split_wave", ...}
    ],
    "skip_reason": "<str>" (apenas se SKIPPED)
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
# Constantes / enums
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
    """Erro de parse, validacao ou execucao do review."""


# ----------------------------------------------------------------------------
# Parser minimal do wave-plan.md (subset do que o companion escreve)
# ----------------------------------------------------------------------------
@dataclass
class WavePlanSummary:
    """Subset minimal extraido do wave-plan.md para decidir skip."""

    total_tasks: int
    total_waves: int
    total_sub_waves: int


def parse_wave_plan(path: Path) -> WavePlanSummary:
    """Le wave-plan.md (frontmatter YAML) e retorna summary com totals.

    Erros possiveis:
      - arquivo inexistente
      - frontmatter ausente
      - campos obrigatorios faltando
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
# Decisao de skip
# ----------------------------------------------------------------------------
def should_skip(summary: WavePlanSummary) -> tuple[bool, str]:
    """Retorna (skip?, reason). Skip se total_tasks <= 2 OU total_waves <= 1."""
    if summary.total_tasks <= 2:
        return True, f"total_tasks={summary.total_tasks}"
    if summary.total_waves <= 1:
        return True, f"total_waves={summary.total_waves}"
    return False, ""


# ----------------------------------------------------------------------------
# Spawn LLM (mockavel)
# ----------------------------------------------------------------------------
def request_review(
    wave_plan_text: str,
    plan_text: str,
    ambiguities_text: str,
    *,
    mock_response_path: Path | None = None,
) -> dict[str, Any]:
    """Solicita review do LLM.

    - Em test: le `mock_response_path` (json) e retorna parse.
    - Em prod: levanta NotImplementedError (Task tool integration e Wave 5+).

    Os tres primeiros params (`wave_plan_text`/`plan_text`/`ambiguities_text`)
    serao consumidos pelo prompt do Task tool em Wave 5+; em mock mode sao
    ignorados deliberadamente.
    """
    del wave_plan_text, plan_text, ambiguities_text  # used by prod (Wave 5+)
    if mock_response_path is not None:
        if not mock_response_path.exists():
            raise LLMReviewError(f"mock response file not found: {mock_response_path}")
        try:
            return json.loads(mock_response_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise LLMReviewError(
                f"invalid JSON in mock response {mock_response_path}: {exc}"
            ) from exc
    raise NotImplementedError(
        "Task tool integration is Wave 5+. Use --mock-response for now."
    )


# ----------------------------------------------------------------------------
# Validacao do response
# ----------------------------------------------------------------------------
def validate_response(d: Any) -> dict[str, Any]:
    """Valida schema do veredicto. Aborta com LLMReviewError se invalido.

    Retorna o dict normalizado (com defaults preenchidos).
    """
    if not isinstance(d, dict):
        raise LLMReviewError(f"response must be a dict, got {type(d).__name__}")

    verdict = d.get("verdict")
    if verdict not in VALID_VERDICTS:
        raise LLMReviewError(
            f"invalid verdict {verdict!r}; must be one of {sorted(VALID_VERDICTS)}"
        )

    if verdict == "SKIPPED":
        # Caminho legitimo apenas quando produzido pelo proprio script (skip threshold).
        # Aceitamos SKIPPED do mock para teste de pass-through; defaults vazios.
        issues = d.get("issues", [])
        proposed = d.get("proposed_dag_changes", [])
    else:
        # APPROVE / PROPOSE_CHANGES exigem campos issues + proposed_dag_changes.
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
    """Monta o dict canonico de SKIPPED produzido pelo proprio script."""
    return {
        "verdict": "SKIPPED",
        "issues": [],
        "proposed_dag_changes": [],
        "skip_reason": skip_reason,
    }


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
        help="path para wave-plan.md (gerado pelo wave-planner-script.py)",
    )
    parser.add_argument(
        "--plan",
        required=True,
        type=Path,
        help="path para plan.md (input original do wave planner)",
    )
    parser.add_argument(
        "--ambiguities",
        required=True,
        type=Path,
        help="path para ambiguities-resolved.md",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="path para llm-review-verdict.json (saida)",
    )
    parser.add_argument(
        "--mock-response",
        type=Path,
        default=None,
        help="path para json de mock (test mode); ausente = prod (NotImplementedError)",
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
            # 2. Le inputs textuais (sera enviado ao subagent prod, ou ignorado em mock).
            wave_plan_text = _read_text_safe(args.wave_plan, "wave-plan")
            plan_text = _read_text_safe(args.plan, "plan")
            ambiguities_text = _read_text_safe(args.ambiguities, "ambiguities")

            raw = request_review(
                wave_plan_text,
                plan_text,
                ambiguities_text,
                mock_response_path=args.mock_response,
            )
            verdict_dict = validate_response(raw)

    except NotImplementedError as exc:
        print(f"llm-review error: prod mode not implemented: {exc}", file=sys.stderr)
        return 1
    except LLMReviewError as exc:
        print(f"llm-review error: {exc}", file=sys.stderr)
        return 1

    # 3. Escreve output json.
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(verdict_dict, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    # 4. Stdout sumarizado.
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
