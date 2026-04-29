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
import re
import sys
from pathlib import Path


# ============================================================================
# Constantes
# ============================================================================

# Anti-pattern detector: paths absolutos / line numbers em acceptance criteria
PATH_ABSOLUTE_RE = re.compile(r"\b(?:/[a-zA-Z0-9_./-]+|[A-Z]:\\[a-zA-Z0-9_\\-]+)")
LINE_NUMBER_RE = re.compile(r":\d+\b")


class AgentBriefError(Exception):
    """Erro de render de AGENT-BRIEF."""


# ============================================================================
# Parse plan.md
# ============================================================================

def extract_task_section(plan_md: str, slug: str) -> str:
    """Extrai seção `### Task: {slug}` até próxima `### Task:` ou EOF.

    Slug é case-sensitive e exato. Retorna texto da section (incluindo header).
    Raise AgentBriefError se não encontrada.
    """
    pattern = re.compile(
        rf"^### Task: {re.escape(slug)}\b.*?(?=^### Task: |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(plan_md)
    if match is None:
        raise AgentBriefError(f"task não encontrada em plan.md: {slug!r}")
    return match.group(0).rstrip() + "\n"


def parse_4block(task_section: str) -> dict[str, str]:
    """Parse 4-block (O QUE / COMO / NÃO QUERO / VALIDAÇÃO) da seção.

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

    # 4-block extraction
    blocks = {
        "o_que": r"\*\*O QUE:\*\*",
        "como": r"\*\*COMO:\*\*",
        "nao_quero": r"\*\*N[ÃA]O QUERO:\*\*",
        "validacao": r"\*\*VALIDA[ÇC][ÃA]O:\*\*",
    }
    for key, marker in blocks.items():
        m = re.search(rf"{marker}\s*(.*?)(?=\n\*\*[A-ZÃÇ]|\Z)", task_section, re.DOTALL)
        if m:
            out[key] = m.group(1).strip()

    return out


# ============================================================================
# Render AGENT-BRIEF
# ============================================================================

def render_brief(slug: str, parsed: dict[str, str], adrs: list[str]) -> str:
    """Render AGENT-BRIEF markdown a partir de 4-block parseado + ADRs aplicáveis.

    Mapping: O QUE → Summary + Current/Desired; COMO → Key interfaces;
    NÃO QUERO → Out of scope; VALIDAÇÃO → Acceptance criteria.
    """
    adrs_block = ""
    if adrs:
        adrs_lines = "\n".join(f"- {adr}" for adr in adrs)
        adrs_block = f"\n**Applicable ADRs:**\n{adrs_lines}\n"

    return (
        f"## Agent Brief — {slug}\n"
        "\n"
        f"**Type:** {parsed['type']}\n"
        f"**Files touched:** {parsed['files_touched']}\n"
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

    brief = render_brief(args.task, parsed, adrs)

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
