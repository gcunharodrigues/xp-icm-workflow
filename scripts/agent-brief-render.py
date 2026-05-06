"""AGENT-BRIEF render — generates structured brief for subagent (T1.2).

Used by the lead session in stage 04: extracts task from plan.md, builds
AGENT-BRIEF in canonical format (`references/agent-brief-template.md`) and
prints to stdout for the lead to paste into the Agent tool prompt.

CLI:
    python scripts/agent-brief-render.py --task <slug> \\
        --plan <workspace>/stages/02_design/output/plan.md \\
        --workspace-num <NNN> --wave <N> \\
        --project-root <path> --base-branch <name> \\
        [--adrs <project>/docs/decisions] \\
        [--isolation-mode worktree|manual-worktree|direct]

Isolation modes (v4.0.x):
  worktree         — Agent(isolation: "worktree") when .git is directory
  manual-worktree  — manual git worktree add + Agent(isolation=none, cwd=<wt>)
                     when .git is a FILE (nested worktree model)
  direct           — no isolation, reviewer/critic ONLY (never for code tasks)
  auto (default)   — detects .git file → manual-worktree, else → worktree

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

# ============================================================================
# Nested worktree detection (v4.0.x)
# ============================================================================

def detect_isolation_mode(project_root: str) -> str:
    """Detect isolation mode based on .git type.

    Returns:
        "worktree" — .git is a directory (standard clone) -> Agent(isolation: "worktree")
        "manual-worktree" — .git is a file (linked worktree) -> manual git worktree add
    """
    if not project_root:
        return "worktree"  # safe default
    dot_git = Path(project_root) / ".git"
    if dot_git.is_file():
        return "manual-worktree"
    return "worktree"


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
    isolation_mode: str = "worktree",
) -> str:
    """Render AGENT-BRIEF markdown from parsed 4-block + applicable ADRs.

    Mapping: WHAT -> Summary + Current/Desired; HOW -> Key interfaces;
    OUT OF SCOPE -> Out of scope; VALIDATION -> Acceptance criteria.

    v4.0: model str from heuristic (haiku|sonnet|opus). Lead may override.
    v4.0: project_root + base_branch resolve placeholders in isolation block.
    v4.0.x: isolation_mode controls which isolation rules are rendered:
        worktree — Agent(isolation: "worktree")
        manual-worktree — manual git worktree add + Agent(isolation=none, cwd=<wt>)
        direct — reviewer/critic only, NO isolation (never for code tasks)
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

    isolation_block = _render_isolation_block(
        slug=slug,
        workspace_num=workspace_num,
        wave_num=wave_num,
        project_root=pr,
        base_branch=bb,
        mode=isolation_mode,
    )

    return (
        f"## Agent Brief — {slug}\n"
        "\n"
        f"**Type:** {parsed['type']}\n"
        f"**Files touched:** {parsed['files_touched']}\n"
        f"{model_block}"
        f"**Isolation mode:** {isolation_mode}\n"
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


def _render_isolation_block(
    *,
    slug: str,
    workspace_num: str,
    wave_num: int,
    project_root: str,
    base_branch: str,
    mode: str,
) -> str:
    """Render isolation rules block based on mode.

    Modes (v4.0.x):
      worktree — Agent(isolation: "worktree")
      manual-worktree — manual git worktree add + Agent(isolation=none, cwd=<wt>)
      direct — reviewer/critic only, NO isolation
    """
    if not workspace_num or not wave_num:
        return ""

    branch = f"wave-{workspace_num}-{wave_num}/{slug}"
    pr = project_root

    if mode == "direct":
        return (
            "\n"
            "**Isolation rules — direct mode (MANDATORY — REVIEWER/CRITIC ONLY):**\n"
            "- [ ] You run WITHOUT worktree isolation. CWD = project root on workspace branch.\n"
            "- [ ] You are a REVIEWER/CRITIC only. NEVER write code. NEVER modify `src/` or `tests/`.\n"
            "- [ ] Read code via `git show <branch>:<path>` or `git diff`.\n"
            f"- [ ] Write outputs to workspace state paths only.\n"
            "\n"
        )

    if mode == "manual-worktree":
        return (
            "\n"
            "**Isolation rules — manual-worktree mode (MANDATORY — Agent(isolation=none, cwd=<worktree>)):**\n"
            f"- [ ] You are in a manually-created git worktree on branch `{branch}`.\n"
            "      Your CWD is a path like `.claude/worktrees/icm-wave-<NNN>-<N>/<slug>` — NOT `{{PROJECT_ROOT}}`.\n"
            "      Run `pwd` to confirm your worktree path.\n"
            "- [ ] Your CWD IS the isolation. Write code ONLY in this worktree.\n"
            "      NEVER write via absolute paths to the project.\n"
            f"- [ ] NEVER write to `{pr}/.icm-main/` or any path under it.\n"
            "      It is the base-branch linked worktree — read-only for docs.\n"
            "- [ ] NEVER run `git checkout`, `git switch`, `git rebase`, or `git push`.\n"
            "      Your branch is pre-created and checked out.\n"
            "- [ ] Read base-branch docs (ADRs, lessons, tech_debt) via Read tool with\n"
            f"      absolute path `{pr}/.icm-main/<path>`.\n"
            "- [ ] Verify on startup:\n"
            f"      1. `git branch --show-current` MUST show `{branch}`.\n"
            "      2. `git status --short` — confirm clean working tree.\n"
            "      If wrong -> STOP, report `Status: BLOCKED`.\n"
            "- [ ] Return results in Agent tool output using this format:\n"
            "      ```\n"
            f"      ## Result: {slug}\n"
            "      **Status:** COMPLETE | BLOCKED\n"
            "      **Summary:** <1-3 sentences>\n"
            f"      **Modified files:** <git diff --name-only {base_branch}...HEAD output>\n"
            "      **Tests written:** <count and file paths>\n"
            "      **ADRs applied:** <list or 'none'>\n"
            "      ```\n"
            "      The lead writes all workspace state files (task report, L1 updates).\n"
            "      MUST NOT write to workspace branch paths.\n"
            "\n"
        )

    # Default: worktree mode (Agent isolation)
    return (
        "\n"
        "**Isolation rules — worktree mode (MANDATORY — Agent(isolation: \"worktree\")):**\n"
        f"- [ ] You are in an isolated git worktree on branch `{branch}`.\n"
        "      Your CWD is the worktree root — NOT the project root.\n"
        "      Run `pwd` to confirm your worktree path.\n"
        "- [ ] Write code ONLY in this worktree. NEVER write via absolute paths to the project.\n"
        f"- [ ] NEVER write to `{pr}/.icm-main/` or any path under it.\n"
        "      It is the base-branch linked worktree — read-only for docs.\n"
        "- [ ] NEVER run `git checkout`, `git switch`, `git rebase`, or `git push`.\n"
        "      You are on the correct branch already.\n"
        "- [ ] Read base-branch docs (ADRs, lessons, tech_debt) via Read tool with\n"
        f"      absolute path `{pr}/.icm-main/<path>`.\n"
        "- [ ] Verify on startup:\n"
        f"      1. `git branch --show-current` MUST show `{branch}`.\n"
        "      2. `git status --short` — confirm clean working tree.\n"
        "      If wrong -> STOP, report `Status: BLOCKED`.\n"
        "- [ ] Workspace state (L0/L1/L2) is injected into this brief by the lead.\n"
        "      Do NOT read workspace state files separately.\n"
        "- [ ] Return results in Agent tool output using this format:\n"
        "      ```\n"
        f"      ## Result: {slug}\n"
        "      **Status:** COMPLETE | BLOCKED\n"
        "      **Summary:** <1-3 sentences>\n"
        f"      **Modified files:** <git diff --name-only {base_branch}...HEAD output>\n"
        "      **Tests written:** <count and file paths>\n"
        "      **ADRs applied:** <list or 'none'>\n"
        "      ```\n"
        "      The lead writes all workspace state files (task report, L1 updates).\n"
        "      MUST NOT write to workspace branch paths.\n"
        "\n"
    )


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
    parser.add_argument(
        "--isolation-mode",
        choices=("worktree", "manual-worktree", "direct", "auto"),
        default="auto",
        help=(
            "isolation mode for the subagent: worktree (Agent isolation), "
            "manual-worktree (manual git worktree add), direct (reviewer/critic only), "
            "auto (detect from .git type — default)"
        ),
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

    isolation_mode = args.isolation_mode
    if isolation_mode == "auto":
        isolation_mode = detect_isolation_mode(args.project_root or "")

    brief = render_brief(
        args.task, parsed, adrs, model=model or "",
        workspace_num=args.workspace_num or "",
        wave_num=args.wave or 0,
        project_root=args.project_root or "",
        base_branch=args.base_branch or "",
        isolation_mode=isolation_mode,
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
