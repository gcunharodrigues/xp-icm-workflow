#!/usr/bin/env python3
"""Wave Planner LLM Review subagent (companion do wave-planner-script.py).

Recebe o DAG draft (wave-plan.md), o plan.md original e o ambiguities-resolved.md,
devolve um veredicto json estruturado (APPROVE / PROPOSE_CHANGES / SKIPPED).

Modos de operacao:
  1. Mock mode (--mock-response): le JSON de fixture (usado em testes).
  2. Prod mode (--llm-response): le JSON gerado por LLM externo (human-in-the-loop
     ou pipeline CI que roda LLM separadamente).
  3. Prompt mode (nenhum response path): imprime prompt formatado para stdout e
     sai com exit 2, aguardando que humano/algoritmo externo rode LLM e
     reenvie o JSON via --llm-response.

Skip threshold: total_tasks <= 2 ou total_waves <= 1 -> nao spawna LLM (custo
nao justifica sinal).

CLI:
  python scripts/wave-planner-llm-review.py
      --wave-plan stages/03_wave_planner/output/wave-plan.md
      --plan stages/02_design/output/plan.md
      --ambiguities stages/03_wave_planner/output/ambiguities-resolved.md
      --output stages/03_wave_planner/output/llm-review-verdict.json
      [--mock-response tests/mocks/llm_review_responses/<name>.json]
      [--llm-response path/to/llm_response.json]

Stdout: verdict=<X> issues=<N> proposed_changes=<M> skipped=<true|false>
Exit codes:
  0  sucesso (qualquer verdict, inclusive SKIPPED)
  1  erro (mock ausente, schema invalido, IO)
  2  prompt emitido (modo interativo / human-in-the-loop)

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
# Build prompt for human-in-the-loop / external LLM
# ----------------------------------------------------------------------------
PROMPT_TEMPLATE: str = """\
Você é um wave-planner-reviewer. Recebe o DAG draft + plan.md + ambiguities.

Tarefa: ler tasks + grafo + ambiguidades. Verificar se há:
1. Footprints ambíguos não resolvidos pelo determinístico
2. Deps implícitas não declaradas (ex: task B precisa do schema migrado por task A
   mas não declara dep)
3. Sub-waves que poderiam re-paralelizar (cap reduzido por engano)

Output JSON estruturado:
{
  "verdict": "APPROVE" | "PROPOSE_CHANGES",
  "issues": [
    {"type": "implicit_dep", "from": "task-a", "to": "task-b", "reason": "..."},
    {"type": "ambiguous_footprint", "tasks": ["task-x", "task-y"], "suggestion": "..."}
  ],
  "proposed_dag_changes": [...]   // só se PROPOSE_CHANGES
}
"""


def _build_prompt(wave_plan_text: str, plan_text: str, ambiguities_text: str) -> str:
    """Monta prompt completo para review, incluindo os 3 documentos como contexto."""
    return (
        f"{PROMPT_TEMPLATE}\n"
        "---\n"
        "## Contexto: wave-plan.md (DAG draft)\n"
        "\n"
        f"{wave_plan_text}\n"
        "---\n"
        "## Contexto: plan.md (input original)\n"
        "\n"
        f"{plan_text}\n"
        "---\n"
        "## Contexto: ambiguities-resolved.md\n"
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
    """Solicita review do LLM.

    - Se `response_path` fornecido: le JSON do path (mock ou resposta real de LLM
      externo) e retorna parse.
    - Se `response_path` ausente: monta prompt via `_build_prompt` e retorna-o
      como string. O caller deve detectar tipo str, imprimir para stdout e
      retornar exit 2.

    Os tres primeiros params (`wave_plan_text`/`plan_text`/`ambiguities_text`)
    alimentam o prompt em modo interativo, ou sao ignorados quando um
    `response_path` ja existe.
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
# Update wave-plan.md frontmatter
# ----------------------------------------------------------------------------
def _update_wave_plan_llm_review(wave_plan_path: Path, verdict: str) -> None:
    """Atualiza frontmatter do wave-plan.md com llm_review + incrementa iteracoes.

    - llm_review -> <verdict>
    - llm_review_iterations -> +1 (ou 1 se ausente)
    - Preserva corpo markdown e todos os outros campos do frontmatter.
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
    """Incrementa `llm_review_skipped_count` no frontmatter de L1 (CONTEXT.md).

    Se campo ausente, inicializa em 1. Preserva corpo markdown e demais campos.
    Silenciosamente retorna se arquivo inexistente ou frontmatter inválido
    (não falha o review por erro de L1).
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
        help="path para json de mock (test mode); mutuamente exclusivo com --llm-response",
    )
    parser.add_argument(
        "--llm-response",
        type=Path,
        default=None,
        help="path para json gerado por LLM externo (prod mode); mutuamente exclusivo com --mock-response",
    )
    parser.add_argument(
        "--update-wave-plan",
        type=Path,
        default=None,
        help="path do wave-plan.md a ser atualizado com llm_review no frontmatter",
    )
    parser.add_argument(
        "--workspace-context",
        type=Path,
        default=None,
        help="path do L1 CONTEXT.md do workspace; usado para incrementar llm_review_skipped_count quando skip ocorre",
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
            # 2. Le inputs textuais.
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
                # Prompt mode: nenhum response path fornecido.
                print(raw, end="")
                return 2
            verdict_dict = validate_response(raw)

    except LLMReviewError as exc:
        print(f"llm-review error: {exc}", file=sys.stderr)
        return 1

    # 3. Atualiza wave-plan.md frontmatter se solicitado.
    if args.update_wave_plan is not None:
        if not args.update_wave_plan.exists():
            raise LLMReviewError(
                f"--update-wave-plan file not found: {args.update_wave_plan}"
            )
        _update_wave_plan_llm_review(
            args.update_wave_plan, verdict_dict["verdict"]
        )

    # 3b. Se skip ocorreu e workspace-context fornecido, incrementa counter em L1.
    if (
        verdict_dict["verdict"] == "SKIPPED"
        and args.workspace_context is not None
    ):
        _increment_llm_review_skipped_count(args.workspace_context)

    # 4. Escreve output json.
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(verdict_dict, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    # 5. Stdout sumarizado.
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
