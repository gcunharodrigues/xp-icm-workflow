"""Backend Python do protocolo de session handoff (1 stage = 1 sessao).

Renderiza `_kickoff.md` no diretorio do proximo stage usando template em
`templates/workspace/stages/_kickoff.md.tpl`. Helpers determinsticos sao
testados em `tests/unit/test_handoff.py`. Doc canonico em
`references/session-handoff-protocol.md`.

CLI mode (debug): `python scripts/handoff.py render --workspace-root <path>
  --prev-stage 02 --prev-stage-name design
  --stage-target 03 --stage-target-name wave_planner --commit-sha abc123`.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

import yaml


# ============================================================================
# Constantes
# ============================================================================

PLACEHOLDER_RE = re.compile(r"\{\{([A-Z_][A-Z0-9_]*)\}\}")

# Mapping fixo stage_id -> nome do diretorio (id + name canonico)
STAGE_DIR_BY_ID: dict[str, str] = {
    "00": "00_recon",
    "01": "01_discovery",
    "02": "02_design",
    "03": "03_wave_planner",
    "04": "04_implementation_waves",
    "05": "05_verification",
    "06": "06_review",
    "07": "07_merge",
    "08": "08_feedback_intake",
}

# Indent canonico do bloco YAML literal `prev_decisions_summary: |`
DECISIONS_INDENT = "  "


# ============================================================================
# Tipos
# ============================================================================

class HandoffError(Exception):
    """Erro de protocolo de handoff (template, render, parse, IO)."""


@dataclass(frozen=True)
class PrevOutput:
    """Output declarado pela sessao anterior, listado em prev_outputs."""
    path: str       # path relativo ao workspace, ex "stages/02_design/output/plan.md"
    summary: str    # 1-2 linhas


@dataclass(frozen=True)
class HandoffData:
    """Dados completos para renderizar `_kickoff.md`."""
    workspace: str           # "042-feat-auth"
    project_root: str        # absolute path
    prev_stage: str          # "02"
    prev_stage_name: str     # "design"
    stage_target: str        # "03"
    stage_target_name: str   # "wave_planner"
    stage_target_dir: str    # "03_wave_planner"
    generated_at: str        # ISO 8601 UTC
    generator_commit_sha: str
    prev_outputs: Sequence[PrevOutput] = field(default_factory=tuple)
    prev_decisions_summary: str = ""
    pending_for_this_stage: Sequence[str] = field(default_factory=tuple)
    prev_state_prose: str = ""
    next_tasks_prose: str = ""


# ============================================================================
# Helpers determinsticos
# ============================================================================

def stage_target_dir(stage_id: str, stage_name: str) -> str:
    """Resolve nome canonico do diretorio (`<id>_<name>`).

    Valida que `stage_id` esta no mapping e que `stage_name` bate o canonico.
    """
    if stage_id not in STAGE_DIR_BY_ID:
        raise HandoffError(
            f"stage_id desconhecido: {stage_id!r} (validos: "
            f"{sorted(STAGE_DIR_BY_ID)})"
        )
    canonical = STAGE_DIR_BY_ID[stage_id]
    expected_name = canonical[3:]  # strip "NN_"
    if stage_name != expected_name:
        raise HandoffError(
            f"stage_name {stage_name!r} nao bate canonico {expected_name!r} "
            f"para stage_id {stage_id}"
        )
    return canonical


def utc_now_iso() -> str:
    """Timestamp UTC ISO 8601 com sufixo Z."""
    return _dt.datetime.now(_dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _yaml_inline_list(items: Sequence[str]) -> str:
    """Lista YAML inline. Vazio -> `[]`. Strings entre aspas duplas."""
    if not items:
        return "[]"
    quoted = ", ".join(f'"{_yaml_escape(s)}"' for s in items)
    return f"[{quoted}]"


def _yaml_escape(s: str) -> str:
    """Escape minimo para string YAML entre aspas duplas."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _prev_outputs_yaml(outputs: Sequence[PrevOutput]) -> str:
    """Serializa prev_outputs como bloco YAML.

    Vazio -> `[]` inline. Caso contrario, lista de objetos em linhas
    seguintes, com indent zero porque a chave ja foi escrita no template.
    """
    if not outputs:
        return "[]"
    lines: list[str] = [""]  # quebra logo apos `prev_outputs:`
    for item in outputs:
        lines.append(f'  - path: "{_yaml_escape(item.path)}"')
        lines.append(f'    summary: "{_yaml_escape(item.summary)}"')
    return "\n".join(lines)


def _indent_multiline(text: str, indent: str) -> str:
    """Aplica indent em cada linha (para YAML literal block)."""
    if not text:
        return ""
    lines = text.split("\n")
    return ("\n" + indent).join(lines)


def _build_placeholders(data: HandoffData) -> dict[str, str]:
    """Mapeia HandoffData -> dict de placeholders para o template."""
    return {
        "WORKSPACE": data.workspace,
        "PROJECT_ROOT": data.project_root,
        "PREV_STAGE": data.prev_stage,
        "PREV_STAGE_NAME": data.prev_stage_name,
        "STAGE_TARGET": data.stage_target,
        "STAGE_TARGET_NAME": data.stage_target_name,
        "STAGE_TARGET_DIR": data.stage_target_dir,
        "GENERATED_AT": data.generated_at,
        "GENERATOR_COMMIT_SHA": data.generator_commit_sha,
        "PREV_OUTPUTS_YAML": _prev_outputs_yaml(data.prev_outputs),
        "PREV_DECISIONS_SUMMARY_INDENTED": _indent_multiline(
            data.prev_decisions_summary, DECISIONS_INDENT
        ),
        "PENDING_YAML": _yaml_inline_list(data.pending_for_this_stage),
        "PREV_STATE_PROSE": data.prev_state_prose,
        "NEXT_TASKS_PROSE": data.next_tasks_prose,
    }


# ============================================================================
# API publica
# ============================================================================

def render_kickoff(template_path: Path, data: HandoffData) -> str:
    """Substitui placeholders `{{KEY}}` pelos valores derivados de `data`.

    Raise `HandoffError` se template ausente ou se sobra placeholder
    nao resolvido.
    """
    if not template_path.exists():
        raise HandoffError(f"template ausente: {template_path}")

    placeholders = _build_placeholders(data)
    content = template_path.read_text(encoding="utf-8")

    def _sub(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in placeholders:
            raise HandoffError(
                f"placeholder nao resolvido: {{{{{key}}}}} em {template_path.name}"
            )
        return placeholders[key]

    rendered = PLACEHOLDER_RE.sub(_sub, content)
    leftover = PLACEHOLDER_RE.search(rendered)
    if leftover:
        raise HandoffError(
            f"placeholder nao resolvido: {leftover.group(0)} em {template_path.name}"
        )
    return rendered


def write_kickoff(
    workspace_root: Path,
    data: HandoffData,
    *,
    template_path: Path | None = None,
) -> Path:
    """Escreve `<workspace_root>/stages/<stage_target_dir>/_kickoff.md`.

    Cria dir se ausente. Idempotente (sobrescreve com mesmo conteudo).
    Retorna path absoluto escrito.
    """
    tpl = template_path or _default_template_path()
    rendered = render_kickoff(tpl, data)
    target_dir = workspace_root / "stages" / data.stage_target_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    out_path = (target_dir / "_kickoff.md").resolve()
    out_path.write_text(rendered, encoding="utf-8")
    return out_path


def extract_kickoff_metadata(kickoff_path: Path) -> dict:
    """Parse YAML frontmatter de `_kickoff.md`. Retorna dict.

    Raise `HandoffError` se arquivo ausente, frontmatter ausente ou YAML invalido.
    """
    if not kickoff_path.exists():
        raise HandoffError(f"kickoff ausente: {kickoff_path}")
    text = kickoff_path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise HandoffError(f"frontmatter ausente em {kickoff_path}")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise HandoffError(f"frontmatter mal formado (sem fim) em {kickoff_path}")
    fm_text = text[4:end]
    try:
        meta = yaml.safe_load(fm_text)
    except yaml.YAMLError as exc:
        raise HandoffError(f"YAML invalido em {kickoff_path}: {exc}") from exc
    if not isinstance(meta, dict):
        raise HandoffError(f"frontmatter nao e dict em {kickoff_path}")
    return meta


def validate_kickoff_present(workspace_root: Path, stage_atual: str) -> bool:
    """Pre-flight de sessao nova: verifica se `_kickoff.md` existe.

    Retorna True se OK, False se ausente. Stage_id desconhecido -> raise.
    """
    if stage_atual not in STAGE_DIR_BY_ID:
        raise HandoffError(
            f"stage_atual desconhecido: {stage_atual!r}"
        )
    kickoff = (
        workspace_root
        / "stages"
        / STAGE_DIR_BY_ID[stage_atual]
        / "_kickoff.md"
    )
    return kickoff.is_file()


# ============================================================================
# Internals
# ============================================================================

def _default_template_path() -> Path:
    return (
        Path(__file__).resolve().parent.parent
        / "templates"
        / "workspace"
        / "stages"
        / "_kickoff.md.tpl"
    )


# ============================================================================
# CLI
# ============================================================================

def _parse_prev_outputs_arg(raw: str | None) -> tuple[PrevOutput, ...]:
    """Parse `path1:summary1,path2:summary2` -> tuple[PrevOutput]."""
    if not raw:
        return ()
    items: list[PrevOutput] = []
    for chunk in raw.split(","):
        if ":" not in chunk:
            raise HandoffError(f"prev-outputs chunk sem ':' -> {chunk!r}")
        path, summary = chunk.split(":", 1)
        items.append(PrevOutput(path=path.strip(), summary=summary.strip()))
    return tuple(items)


def _parse_pending_arg(raw: str | None) -> tuple[str, ...]:
    """Parse `p1|p2|p3` -> tuple[str]."""
    if not raw:
        return ()
    return tuple(p.strip() for p in raw.split("|") if p.strip())


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="handoff.py")
    sub = parser.add_subparsers(dest="cmd", required=True)

    render = sub.add_parser("render", help="Renderiza e escreve _kickoff.md")
    render.add_argument("--workspace-root", type=Path, required=True)
    render.add_argument("--prev-stage", required=True)
    render.add_argument("--prev-stage-name", required=True)
    render.add_argument("--stage-target", required=True)
    render.add_argument("--stage-target-name", required=True)
    render.add_argument("--commit-sha", required=True)
    render.add_argument("--prev-outputs", default=None,
                        help="path1:summary1,path2:summary2")
    render.add_argument("--pending", default=None, help="p1|p2|p3")
    render.add_argument("--decisions-summary", default="")
    render.add_argument("--prev-state-prose", default="")
    render.add_argument("--next-tasks-prose", default="")
    render.add_argument("--project-root", type=Path, default=None,
                        help="default = workspace_root.parent.parent")

    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.cmd == "render":
        ws_root: Path = args.workspace_root.resolve()
        workspace_id = ws_root.name
        project_root = (
            args.project_root.resolve()
            if args.project_root
            else ws_root.parent.parent
        )
        data = HandoffData(
            workspace=workspace_id,
            project_root=str(project_root),
            prev_stage=args.prev_stage,
            prev_stage_name=args.prev_stage_name,
            stage_target=args.stage_target,
            stage_target_name=args.stage_target_name,
            stage_target_dir=stage_target_dir(
                args.stage_target, args.stage_target_name
            ),
            generated_at=utc_now_iso(),
            generator_commit_sha=args.commit_sha,
            prev_outputs=_parse_prev_outputs_arg(args.prev_outputs),
            prev_decisions_summary=args.decisions_summary,
            pending_for_this_stage=_parse_pending_arg(args.pending),
            prev_state_prose=args.prev_state_prose,
            next_tasks_prose=args.next_tasks_prose,
        )
        out = write_kickoff(ws_root, data)
        print(out)
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
