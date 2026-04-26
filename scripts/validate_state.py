#!/usr/bin/env python3
"""Validador L1 (state machine) do schema CONTEXT.md raiz de um workspace.

Backend Python chamado por scripts/validate-state.sh. Separado do wrapper bash
para testabilidade — testes property-based em tests/unit/test_state_machine.py.

CLI: python scripts/validate_state.py --workspace <path>

Schema canonico documentado em references/state-machine-schema.md.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import yaml


# Enums canonicos --------------------------------------------------------------

VALID_TIERS: frozenset[str] = frozenset(
    {"experimental", "tool", "development", "production"}
)

VALID_STATUSES: frozenset[str] = frozenset(
    {
        "IN_PROGRESS",
        "COMPLETED_AWAITING_HUMAN",
        "BLOCKED_STOP_POINT",
        "BLOCKED_ERROR",
        "COMPLETED",
    }
)

VALID_STAGES: frozenset[str] = frozenset(
    {"00", "01", "02", "03", "04", "05", "06", "07", "08"}
)

# Sub-stage enums simples (estagios sem N variavel)
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

# Estagio 04 tem N variavel — regex
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
    """Erro de validacao do estado L1."""


# Parsing ---------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(
    r"^---\s*\n(?P<body>.*?)\n---\s*(?:\n|$)", re.DOTALL
)


def parse_frontmatter(content: str) -> dict[str, Any]:
    """Extrai e parseia o YAML frontmatter de um CONTEXT.md.

    Levanta StateValidationError se nao houver frontmatter ou se o YAML for
    invalido.
    """
    match = _FRONTMATTER_RE.match(content)
    if match is None:
        raise StateValidationError(
            "CONTEXT.md nao tem YAML frontmatter delimitado por '---'"
        )
    raw = match.group("body")
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise StateValidationError(f"YAML frontmatter invalido: {exc}") from exc
    if not isinstance(data, dict):
        raise StateValidationError(
            "YAML frontmatter deve ser um mapping no topo (dict), recebido: "
            f"{type(data).__name__}"
        )
    return data


# Validacao -------------------------------------------------------------------

def _validate_required_fields(state: dict[str, Any]) -> None:
    missing = [f for f in REQUIRED_FIELDS if f not in state]
    if missing:
        raise StateValidationError(
            f"Campos obrigatorios ausentes em CONTEXT.md: {', '.join(missing)}"
        )


def _validate_tier(state: dict[str, Any]) -> None:
    tier = state["tier"]
    if tier not in VALID_TIERS:
        raise StateValidationError(
            f"tier invalido: '{tier}'. Esperado um de: "
            f"{sorted(VALID_TIERS)}"
        )


def _validate_status(state: dict[str, Any]) -> None:
    status = state["status"]
    if status not in VALID_STATUSES:
        raise StateValidationError(
            f"status invalido: '{status}'. Esperado um de: "
            f"{sorted(VALID_STATUSES)}"
        )


def _validate_stage_atual(state: dict[str, Any]) -> None:
    stage = state["stage_atual"]
    if not isinstance(stage, str) or stage not in VALID_STAGES:
        raise StateValidationError(
            f"stage_atual invalido: '{stage}'. Esperado string em "
            f"{sorted(VALID_STAGES)}"
        )


def _validate_sub_stage(state: dict[str, Any]) -> None:
    """Sub_stage deve comecar com prefixo `<stage_atual>_` E bater enum."""
    stage = state["stage_atual"]
    sub_stage = state["sub_stage"]
    if not isinstance(sub_stage, str):
        raise StateValidationError(
            f"sub_stage deve ser string, recebido {type(sub_stage).__name__}"
        )
    expected_prefix = f"{stage}_"
    if not sub_stage.startswith(expected_prefix):
        raise StateValidationError(
            f"sub_stage '{sub_stage}' nao comeca com prefixo "
            f"'{expected_prefix}' (stage_atual='{stage}')"
        )

    if stage == "04":
        if not SUB_STAGE_04_PATTERN.match(sub_stage):
            raise StateValidationError(
                f"sub_stage '{sub_stage}' nao bate padrao "
                "'04_wave_<N>_in_progress|completed'"
            )
        return

    valid = SIMPLE_SUB_STAGE_ENUMS.get(stage)
    if valid is None or sub_stage not in valid:
        raise StateValidationError(
            f"sub_stage '{sub_stage}' nao esta no enum valido para stage "
            f"'{stage}': {sorted(valid) if valid else '<nenhum>'}"
        )


def _validate_iteration(state: dict[str, Any]) -> None:
    iteration = state["iteration"]
    # bool e int em Python; rejeitar bool explicitamente
    if isinstance(iteration, bool) or not isinstance(iteration, int):
        raise StateValidationError(
            f"iteration deve ser inteiro, recebido {type(iteration).__name__}"
        )
    if iteration < 0:
        raise StateValidationError(
            f"iteration deve ser >= 0, recebido {iteration}"
        )

    history = state.get("history") or []
    increment_events = sum(
        1
        for item in history
        if isinstance(item, dict) and item.get("event") == "iteration_increment"
    )
    if increment_events != iteration:
        raise StateValidationError(
            f"iteration ({iteration}) nao bate com numero de eventos "
            f"'iteration_increment' em history ({increment_events}). "
            "iteration deve ser monotonico vs history."
        )


def _validate_history(state: dict[str, Any]) -> None:
    history = state["history"]
    if not isinstance(history, list):
        raise StateValidationError(
            f"history deve ser lista, recebido {type(history).__name__}"
        )
    for idx, item in enumerate(history):
        if not isinstance(item, dict):
            raise StateValidationError(
                f"history[{idx}] deve ser mapping, recebido "
                f"{type(item).__name__}"
            )
        if "at" not in item:
            raise StateValidationError(
                f"history[{idx}] sem campo obrigatorio 'at'"
            )
        if "event" not in item:
            raise StateValidationError(
                f"history[{idx}] sem campo obrigatorio 'event'"
            )


def _validate_waves(state: dict[str, Any]) -> None:
    """waves ausente/null sse stage_atual < '04'; presente sse >= '04'."""
    stage = state["stage_atual"]
    waves_present = "waves" in state and state["waves"] is not None

    stage_ge_04 = stage >= "04"

    if stage_ge_04 and not waves_present:
        raise StateValidationError(
            f"stage_atual='{stage}' (>=04) requer campo 'waves' presente "
            "(nao-null) com keys 'current' e 'completed'"
        )
    if not stage_ge_04 and waves_present:
        raise StateValidationError(
            f"stage_atual='{stage}' (<04) NAO pode ter campo 'waves' "
            "presente — deve ser ausente ou null"
        )

    if not waves_present:
        return

    waves = state["waves"]
    if not isinstance(waves, dict):
        raise StateValidationError(
            f"waves deve ser mapping, recebido {type(waves).__name__}"
        )
    for key in ("current", "completed"):
        if key not in waves:
            raise StateValidationError(
                f"waves sem campo obrigatorio '{key}'"
            )
    if isinstance(waves["current"], bool) or not isinstance(
        waves["current"], int
    ):
        raise StateValidationError(
            f"waves.current deve ser inteiro, recebido "
            f"{type(waves['current']).__name__}"
        )
    if not isinstance(waves["completed"], list):
        raise StateValidationError(
            f"waves.completed deve ser lista, recebido "
            f"{type(waves['completed']).__name__}"
        )


def _validate_last_transition(state: dict[str, Any]) -> None:
    lt = state["last_transition"]
    if not isinstance(lt, dict):
        raise StateValidationError(
            f"last_transition deve ser mapping, recebido {type(lt).__name__}"
        )
    missing = [k for k in LAST_TRANSITION_REQUIRED_KEYS if k not in lt]
    if missing:
        raise StateValidationError(
            f"last_transition sem campos obrigatorios: {', '.join(missing)}"
        )


def validate_state(state: dict[str, Any]) -> None:
    """Valida um dict de estado L1.

    Levanta StateValidationError com mensagem especifica em caso de falha.
    """
    _validate_required_fields(state)
    _validate_tier(state)
    _validate_status(state)
    _validate_stage_atual(state)
    _validate_sub_stage(state)
    _validate_history(state)  # antes de iteration porque iteration usa history
    _validate_iteration(state)
    _validate_waves(state)
    _validate_last_transition(state)


def validate_workspace(workspace_path: Path) -> None:
    """Valida o CONTEXT.md raiz de um workspace.

    Levanta StateValidationError ou FileNotFoundError.
    """
    context_md = workspace_path / "CONTEXT.md"
    if not context_md.is_file():
        raise StateValidationError(
            f"CONTEXT.md nao encontrado em workspace: {context_md}"
        )
    content = context_md.read_text(encoding="utf-8")
    state = parse_frontmatter(content)
    validate_state(state)


# CLI entrypoint ---------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="validate_state.py",
        description="Valida o estado L1 (CONTEXT.md raiz) de um workspace.",
    )
    parser.add_argument(
        "--workspace",
        required=True,
        help="Caminho para o diretorio do workspace (contem CONTEXT.md)",
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
