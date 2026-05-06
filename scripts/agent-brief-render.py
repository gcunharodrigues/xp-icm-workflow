"""AGENT-BRIEF render — generates structured brief for subagent (T1.2).

Used by the lead session in stage 04: extracts task from plan.md, builds
AGENT-BRIEF in canonical format (`references/agent-brief-template.md`) and
prints to stdout for the lead to paste into the Agent tool prompt.

CLI:
    python scripts/agent-brief-render.py --task <slug> \\
        --plan <workspace>/stages/02_design/output/plan.md \\
        [--adrs <project>/docs/decisions]

Output: AGENT-BRIEF markdown on stdout. Exit 0 if task found, 1 otherwise.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


# ============================================================================
# Constants
# ============================================================================

# Anti-pattern detector: absolute paths / line numbers in acceptance criteria
PATH_ABSOLUTE_RE = re.compile(r"\b(?:/[a-zA-Z0-9_./-]+|[A-Z]:\\[a-zA-Z0-9_\\-]+)")
LINE_NUMBER_RE = re.compile(r":\d+\b")


# ============================================================================
# Model selection heuristic (v4.0 — replaces pick-model.py)
# ============================================================================

def _recommend_model(task_section: str) -> str:
    """Heuristic model recommendation based on task signals.

    haiku: doc_only, config_only, css_only, or estimated_lines < 50
    opus:  security_sensitive, public_api_change, algorithm_heavy, or estimated_lines > 200
    sonnet: default (catch-all)
    """
    lowered = task_section.lower()

    # Light tasks → haiku
    if any(marker in lowered for marker in (
        "doc_only: true",
        "config_only: true",
        "css_only: true",
    )):
        return "haiku"

    # Heavy/sensitive tasks → opus
    if any(marker in lowered for marker in (
        "security_sensitive: true",
        "public_api_change: true",
        "algorithm_heavy: true",
    )):
        return "opus"

    # Fallback: check estimated_lines for explicit >200
    import re
    m = re.search(r"\*\*Estimated lines:\*\*\s*(\d+)", task_section)
    if m and int(m.group(1)) > 200:
        return "opus"

    return "sonnet"


class AgentBriefError(Exception):
    """AGENT-BRIEF render error."""


# ============================================================================
# Parse plan.md
# ============================================================================

def extract_task_section(plan_md: str, slug: str) -> str:
    """Extract section `## Task <slug>: <title>` until next `## Task ` or EOF.

    Canonical schema v3.4.2: H2 `## Task <SLUG>: <Title>` (not H3 `### Task:`
    as in older versions). Slug is case-sensitive and exact. Returns
    section text (including header). Raises AgentBriefError if not found.
    """
    pattern = re.compile(
        rf"^## Task {re.escape(slug)}\b.*?(?=^## Task |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(plan_md)
    if match is None:
        raise AgentBriefError(f"task not found in plan.md: {slug!r}")
    return match.group(0).rstrip() + "\n"


def parse_4block(task_section: str) -> dict[str, str]:
    """Parse 4-block (WHAT / HOW / OUT OF SCOPE / VALIDATION) from section.

    Canonical schema v3.12.0: blocks as H3 (`### WHAT`, `### HOW`,
    `### OUT OF SCOPE`, `### VALIDATION`), content on following lines.
    Legacy schema used pt-BR headers (pre-v3.12.0) — not supported.

    Returns dict with keys: what, how, out_of_scope, validation, type, files_touched.
    Empty strings for absent keys.
    """
    out = {
        "what": "",
        "how": "",
        "out_of_scope": "",
        "validation": "",
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

    # 4-block extraction (H3 markers, content until next H3 or H2 or EOF)
    blocks = {
        "what": r"^### WHAT\s*$",
        "how": r"^### HOW\s*$",
        "out_of_scope": r"^### OUT OF SCOPE\s*$",
        "validation": r"^### VALIDATION\s*$",
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
    model: str = "",
    *,
    workspace_num: str = "",
    wave_num: int = 0,
    project_root: str = "",
    base_branch: str = "",
) -> str:
    """Render AGENT-BRIEF markdown from parsed 4-block + applicable ADRs.

    Mapping: WHAT -> Summary + Current/Desired; HOW -> Key interfaces;
    OUT OF SCOPE -> Out of scope; VALIDATION -> Acceptance criteria.

    v4.0: model str from heuristic (haiku|sonnet|opus). Lead may override.
    v4.0: project_root + base_branch resolve placeholders in isolation block.
    """
    pr = project_root or "<project_root>"
    bb = base_branch or "main"
    adrs_block = ""
    if adrs:
        adrs_lines = "\n".join(f"- {adr}" for adr in adrs)
        adrs_block = f"\n**Applicable ADRs:**\n{adrs_lines}\n"

    model_block = ""
    if model:
        model_block = f"**Model recommended (writer):** {model}\n"

    isolation_block = ""
    if workspace_num and wave_num:
        branch = f"wave-{workspace_num}-{wave_num}/{slug}"
        isolation_block = (
            "\n"
            "**Isolation rules (MANDATORY — you are in an isolated worktree):**\n"
            f"- [ ] You are in an isolated git worktree on branch `{branch}`.\n"
            "      Your CWD is the worktree root — NOT the project root.\n"
            "      Run `pwd` to confirm your worktree path.\n"
            "- [ ] Write code ONLY in this worktree. NEVER write via absolute paths to the project.\n"
            f"- [ ] NEVER write to `{pr}/.icm-main/` or any path under it. It is the\n"
            "      base-branch linked worktree — read-only for docs.\n"
            "- [ ] NEVER run `git checkout`, `git switch`, `git rebase`, or\n"
            "      `git push`. You are on the correct branch already.\n"
            "- [ ] Read base-branch docs (ADRs, lessons, tech_debt) from `.icm-main/` via\n"
            f"      Read tool with absolute path `{pr}/.icm-main/<path>`.\n"
            "- [ ] Verify on startup:\n"
            "      1. `git branch --show-current` MUST show `{branch}`.\n"
            "      2. `git status --short` — confirm clean working tree.\n"
            "      If wrong -> STOP, report `Status: BLOCKED`.\n"
            "- [ ] Workspace state (L0/L1/L2) is injected into this brief by the lead.\n"
            "      Do NOT read workspace state files separately.\n"
            "- [ ] Return results in Agent tool output using this format:\n"
            "      ```\n"
            "      ## Result: {slug}\n"
            "      **Status:** COMPLETE | BLOCKED\n"
            "      **Summary:** <1-3 sentences>\n"
            "      **Modified files:** <git diff --name-only {bb}...HEAD output>\n"
            "      **Tests written:** <count and file paths>\n"
            "      **ADRs applied:** <list or 'none'>\n"
            "      ```\n"
            "      The lead writes all workspace state files (task report, L1 updates).\n"
            "      MUST NOT write to workspace branch paths.\n"
            "\n"
        )

    return (
        f"## Agent Brief — {slug}\n"
        "\n"
        f"**Type:** {parsed['type']}\n"
        f"**Files touched:** {parsed['files_touched']}\n"
        f"{model_block}"
        "\n"
        f"**Summary:** {_first_line(parsed["what"])}\n"
        "\n"
        "**Desired behavior:**\n"
        f"{parsed["what"]}\n"
        "\n"
        "**Key interfaces:**\n"
        f"{parsed["how"]}\n"
        f"{adrs_block}"
        "\n"
        "**Acceptance criteria:**\n"
        f"{parsed['validation']}\n"
        "\n"
        "**Out of scope:**\n"
        f"{parsed['out_of_scope']}\n"
        f"{isolation_block}"
    )


def _first_line(text: str) -> str:
    """First non-empty line, max 200 chars."""
    for line in text.splitlines():
        s = line.strip()
        if s:
            return s[:200]
    return ""


# ============================================================================
# Validation
# ============================================================================

def warn_if_brittle(brief_md: str) -> list[str]:
    """Detect anti-patterns (absolute paths, line numbers).

    Returns list of warnings. Empty if OK.
    """
    warnings: list[str] = []
    paths = PATH_ABSOLUTE_RE.findall(brief_md)
    if paths:
        warnings.append(
            f"Absolute paths detected ({len(paths)}): {paths[:3]}... "
            "AGENT-BRIEF should describe interfaces, not paths (they go stale)."
        )
    line_nums = LINE_NUMBER_RE.findall(brief_md)
    if line_nums:
        warnings.append(
            f"Line numbers detected ({len(line_nums)}): "
            "AGENT-BRIEF should be behavioral, not procedural."
        )
    return warnings


# ============================================================================
# CLI
# ============================================================================

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agent-brief-render.py")
    parser.add_argument("--task", required=True, help="task slug (kebab-case)")
    parser.add_argument("--plan", type=Path, required=True, help="path to plan.md")
    parser.add_argument(
        "--adrs", type=Path, default=None,
        help="docs/decisions directory (lists applicable ADRs)",
    )
    parser.add_argument(
        "--strict", action="store_true",
        help="exit 1 if anti-pattern warnings detected",
    )
    parser.add_argument(
        "--tier", choices=("experimental", "tool", "development", "production"),
        default=None,
        help="if provided, uses heuristic to recommend model (haiku|sonnet|opus) based on task signals",
    )
    parser.add_argument(
        "--workspace-num", default=None,
        help="workspace number (e.g. 001) — enables isolation rules block",
    )
    parser.add_argument(
        "--wave", type=int, default=None,
        help="wave number — enables isolation rules block",
    )
    parser.add_argument(
        "--project-root", default=None,
        help="project root absolute path — resolves <project_root> in isolation block",
    )
    parser.add_argument(
        "--base-branch", default=None,
        help="base branch name — resolves <BASE> in git diff command",
    )
    args = parser.parse_args(argv)

    try:
        plan_text = args.plan.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"error: could not read plan.md: {exc}", file=sys.stderr)
        return 1

    try:
        section = extract_task_section(plan_text, args.task)
    except AgentBriefError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    parsed = parse_4block(section)

    adrs: list[str] = []
    if args.adrs and args.adrs.is_dir():
        # List all ADR files; lead can pre-filter manually
        adrs = sorted(p.name for p in args.adrs.glob("[0-9]*.md"))

    model: str | None = None
    if args.tier:
        model = _recommend_model(section)

    brief = render_brief(
        args.task, parsed, adrs, model=model or "",
        workspace_num=args.workspace_num or "",
        wave_num=args.wave or 0,
        project_root=args.project_root or "",
        base_branch=args.base_branch or "",
    )

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
