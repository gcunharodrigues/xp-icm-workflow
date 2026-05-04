"""AGENT-BRIEF render — gera brief estruturado para subagent (T1.2).

Usado pela lead session em stage 04: extrai task do plan.md, monta AGENT-BRIEF
no formato canônico (`references/agent-brief-template.md`) e imprime em stdout
para o lead copy-pastear no prompt do Agent tool.

CLI:
    python scripts/agent-brief-render.py --task <slug> \\
        --plan <workspace>/stages/02_design/output/plan.md \\
        [--adrs <project>/docs/decisions]

Output: AGENT-BRIEF markdown em stdout. Exit 0 se task encontrada, 1 senão.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


# ============================================================================
# Constantes
# ============================================================================

# Anti-pattern detector: paths absolutos / line numbers em acceptance criteria
PATH_ABSOLUTE_RE = re.compile(r"\b(?:/[a-zA-Z0-9_./-]+|[A-Z]:\\[a-zA-Z0-9_\\-]+)")
LINE_NUMBER_RE = re.compile(r":\d+\b")


# ============================================================================
# pick-model integration (v3.9.0)
# ============================================================================

def _load_pick_model_module():
    """Load scripts/pick-model.py as a module via importlib (hyphen workaround)."""
    pm_path = Path(__file__).parent / "pick-model.py"
    spec = importlib.util.spec_from_file_location("pick_model", pm_path)
    if spec is None or spec.loader is None:
        raise AgentBriefError(f"could not load pick-model module at {pm_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AgentBriefError(Exception):
    """Erro de render de AGENT-BRIEF."""


# ============================================================================
# Parse plan.md
# ============================================================================

def extract_task_section(plan_md: str, slug: str) -> str:
    """Extrai seção `## Task <slug>: <título>` até próxima `## Task ` ou EOF.

    Schema canônico v3.4.2: H2 `## Task <SLUG>: <Título>` (não H3 `### Task:`
    como em versões anteriores). Slug é case-sensitive e exato. Retorna
    texto da section (incluindo header). Raise AgentBriefError se não
    encontrada.
    """
    pattern = re.compile(
        rf"^## Task {re.escape(slug)}\b.*?(?=^## Task |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(plan_md)
    if match is None:
        raise AgentBriefError(f"task não encontrada em plan.md: {slug!r}")
    return match.group(0).rstrip() + "\n"


def parse_4block(task_section: str) -> dict[str, str]:
    """Parse 4-block (O QUE / COMO / NÃO QUERO / VALIDAÇÃO) da seção.

    Schema canônico v3.4.2: blocos como H3 (`### O QUE`, `### COMO`,
    `### NÃO QUERO`, `### VALIDAÇÃO`), conteúdo nas linhas seguintes.
    Schema anterior usava bold inline (`**O QUE:**`) — não suportado.

    Retorna dict com chaves: o_que, como, nao_quero, validacao, type, files_touched.
    Strings vazias para chaves ausentes.
    """
    out = {
        "o_que": "",
        "como": "",
        "nao_quero": "",
        "validacao": "",
        "type": "AFK",
        "files_touched": "",
    }

    # Type
    m = re.search(r"\*\*Type:\*\*\s*(HITL|AFK)", task_section)
    if m:
        out["type"] = m.group(1)

    # Files touched
    m = re.search(r"\*\*Files touched:\*\*\s*([^\n]+)", task_section)
    if m:
        out["files_touched"] = m.group(1).strip()

    # 4-block extraction (H3 markers, content até próximo H3 ou H2 ou EOF)
    blocks = {
        "o_que": r"^### O QUE\s*$",
        "como": r"^### COMO\s*$",
        "nao_quero": r"^### N[ÃA]O QUERO\s*$",
        "validacao": r"^### VALIDA[ÇC][ÃA]O\s*$",
    }
    for key, marker in blocks.items():
        m = re.search(
            rf"{marker}\n(.*?)(?=^### |^## |\Z)",
            task_section,
            re.DOTALL | re.MULTILINE,
        )
        if m:
            out[key] = m.group(1).strip()

    return out


# ============================================================================
# Render AGENT-BRIEF
# ============================================================================

def render_brief(
    slug: str,
    parsed: dict[str, str],
    adrs: list[str],
    model_info: dict | None = None,
) -> str:
    """Render AGENT-BRIEF markdown a partir de 4-block parseado + ADRs aplicáveis.

    Mapping: O QUE → Summary + Current/Desired; COMO → Key interfaces;
    NÃO QUERO → Out of scope; VALIDAÇÃO → Acceptance criteria.

    v3.9.0: model_info dict (from pick-model.py) injects writer/critic/score
    no header quando provided.
    """
    adrs_block = ""
    if adrs:
        adrs_lines = "\n".join(f"- {adr}" for adr in adrs)
        adrs_block = f"\n**Applicable ADRs:**\n{adrs_lines}\n"

    model_block = ""
    if model_info:
        model_block = (
            f"**Model recommended (writer):** {model_info['model_recommended_writer']}\n"
            f"**Model recommended (critic):** {model_info['model_recommended_critic']}\n"
            f"**Complexity score:** {model_info['complexity_score']}\n"
        )

    return (
        f"## Agent Brief — {slug}\n"
        "\n"
        f"**Type:** {parsed['type']}\n"
        f"**Files touched:** {parsed['files_touched']}\n"
        f"{model_block}"
        "\n"
        f"**Summary:** {_first_line(parsed['o_que'])}\n"
        "\n"
        "**Desired behavior:**\n"
        f"{parsed['o_que']}\n"
        "\n"
        "**Key interfaces:**\n"
        f"{parsed['como']}\n"
        f"{adrs_block}"
        "\n"
        "**Acceptance criteria:**\n"
        f"{parsed['validacao']}\n"
        "\n"
        "**Out of scope:**\n"
        f"{parsed['nao_quero']}\n"
    )


def _first_line(text: str) -> str:
    """Primeira linha não-vazia, max 200 chars."""
    for line in text.splitlines():
        s = line.strip()
        if s:
            return s[:200]
    return ""


# ============================================================================
# Validação
# ============================================================================

def warn_if_brittle(brief_md: str) -> list[str]:
    """Detecta anti-patterns (paths absolutos, line numbers).

    Retorna lista de warnings. Vazio se OK.
    """
    warnings: list[str] = []
    paths = PATH_ABSOLUTE_RE.findall(brief_md)
    if paths:
        warnings.append(
            f"Paths absolutos detectados ({len(paths)}): {paths[:3]}... "
            "AGENT-BRIEF deve descrever interfaces, não paths (vão stale)."
        )
    line_nums = LINE_NUMBER_RE.findall(brief_md)
    if line_nums:
        warnings.append(
            f"Line numbers detectados ({len(line_nums)}): "
            "AGENT-BRIEF deve ser comportamental, não procedimental."
        )
    return warnings


# ============================================================================
# CLI
# ============================================================================

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agent-brief-render.py")
    parser.add_argument("--task", required=True, help="task slug (kebab-case)")
    parser.add_argument("--plan", type=Path, required=True, help="path do plan.md")
    parser.add_argument(
        "--adrs", type=Path, default=None,
        help="diretório docs/decisions (lista ADRs aplicáveis)",
    )
    parser.add_argument(
        "--strict", action="store_true",
        help="exit 1 se warnings de anti-pattern detectados",
    )
    parser.add_argument(
        "--tier", choices=("experimental", "tool", "development", "production"),
        default=None,
        help="se fornecido, integra pick-model.py e injeta model_recommended_writer/critic no header",
    )
    args = parser.parse_args(argv)

    try:
        plan_text = args.plan.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"erro: não foi possível ler plan.md: {exc}", file=sys.stderr)
        return 1

    try:
        section = extract_task_section(plan_text, args.task)
    except AgentBriefError as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1

    parsed = parse_4block(section)

    adrs: list[str] = []
    if args.adrs and args.adrs.is_dir():
        # Lista todos ADR files; lead pode pré-filtrar manualmente
        adrs = sorted(p.name for p in args.adrs.glob("[0-9]*.md"))

    model_info: dict | None = None
    if args.tier:
        try:
            pm = _load_pick_model_module()
            meta = pm.parse_task_metadata(args.plan, args.task)
            score = pm.compute_score(
                estimated_lines=meta["estimated_lines"],
                files_touched=meta["files_touched"],
                security_sensitive=meta["security_sensitive"],
                public_api_change=meta["public_api_change"],
                algorithm_heavy=meta["algorithm_heavy"],
                doc_only=meta["doc_only"],
                config_only=meta["config_only"],
                css_only=meta["css_only"],
                tier=args.tier,
            )
            writer, critic = pm.pick_models(score, args.tier)
            model_info = {
                "complexity_score": score,
                "model_recommended_writer": writer,
                "model_recommended_critic": critic,
            }
        except (AgentBriefError, OSError) as exc:
            print(f"warning: pick-model integration failed: {exc}", file=sys.stderr)

    brief = render_brief(args.task, parsed, adrs, model_info=model_info)

    warnings = warn_if_brittle(brief)
    if warnings:
        for w in warnings:
            print(f"warning: {w}", file=sys.stderr)
        if args.strict:
            return 1

    print(brief)
    return 0


if __name__ == "__main__":
    sys.exit(main())
