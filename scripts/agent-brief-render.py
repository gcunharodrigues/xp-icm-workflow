"""AGENT-BRIEF render — generates structured brief for subagent (T1.2).

Used by the lead session in stage 04: extracts task from plan.md, builds
AGENT-BRIEF in canonical format (`references/agent-brief-template.md`) and
prints to stdout for the lead to paste into the Agent tool prompt.

CLI:
    python scripts/agent-brief-render.py --task <slug> \\
        --plan <workspace>/stages/02_design/output/plan.md \\
        --workspace-num <NNN> --wave <N> \\
        --project-root <path> --base-branch <name> \\
        [--adrs <project>/docs/decisions]

Single isolation mode — all subagents use manual worktrees in
.claude/worktrees/icm-wave-<NNN>-<N>-<slug>/ on branch
wave-<NNN>-<N>/<slug>.

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

PATH_ABSOLUTE_RE = re.compile(r"\b(?:/[a-zA-Z0-9_./-]+|[A-Z]:\\[a-zA-Z0-9_\\-]+)")
LINE_NUMBER_RE = re.compile(r":\d+\b")


# ============================================================================
# Model selection heuristic (v4.0 — replaces pick-model.py)
# ============================================================================

def _recommend_model(task_section: str) -> str:
    """Heuristic model recommendation based on task signals.

    haiku: doc_only, config_only, css_only
    opus:  security_sensitive, public_api_change, algorithm_heavy, or >200 lines
    sonnet: default (catch-all)
    """
    lowered = task_section.lower()

    if any(marker in lowered for marker in (
        "doc_only: true",
        "config_only: true",
        "css_only: true",
    )):
        return "haiku"

    if any(marker in lowered for marker in (
        "security_sensitive: true",
        "public_api_change: true",
        "algorithm_heavy: true",
    )):
        return "opus"

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
    """Extract section `## Task <slug>: <title>` until next `## Task ` or EOF."""
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

    Returns dict with keys: what, how, out_of_scope, validation, type, files_touched.
    """
    out = {
        "what": "",
        "how": "",
        "out_of_scope": "",
        "validation": "",
        "type": "AFK",
        "files_touched": "",
    }

    m = re.search(r"\*\*Type:\*\*\s*(HITL|AFK)", task_section)
    if m:
        out["type"] = m.group(1)

    m = re.search(r"\*\*Files touched:\*\*\s*([^\n]+)", task_section)
    if m:
        out["files_touched"] = m.group(1).strip()

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

def _render_hard_gates(
    *,
    slug: str,
    workspace_num: str,
    wave_num: int,
    base_branch: str,
) -> str:
    """Emit 3 mandatory HARD GATES at the top of every AGENT-BRIEF."""
    branch = f"wave-{workspace_num}-{wave_num}/{slug}"
    return (
        "### HARD GATES — execute in order. Skip any = task BLOCKED.\n"
        "\n"
        f"**GATE 1 — Branch verification (first action after spawn):**\n"
        "```bash\n"
        "git branch --show-current\n"
        "```\n"
        f"Expected: `{branch}`\n"
        "If wrong → STOP. Return `Status: BLOCKED, Reason: branch mismatch`.\n"
        "Do NOT run `git checkout`. Do NOT create a branch. Just STOP.\n"
        "\n"
        "**GATE 2 — Synchronous-first (every test/lint/typecheck):**\n"
        "Use: `Bash: \"<test-runner> <test-files>\"` — synchronous, blocks, returns exit code.\n"
        "NEVER: `Bash(run_in_background=true)` + `Monitor` for commands under 5 minutes.\n"
        "If the command returned an exit code directly → GATE PASSED.\n"
        "If you used Monitor → GATE FAILED. Re-run synchronously.\n"
        "\n"
        f"**GATE 3 — Commit verify (before declaring COMPLETE):**\n"
        "```bash\n"
        f"git log --oneline {base_branch}..HEAD\n"
        "```\n"
        "Must show >= 1 commit. Zero commits → return to TDD loop.\n"
        "Then: `git status --short` must be clean. Dirty → commit or stash, retry gate.\n"
    )


def _render_isolation_block(
    *,
    slug: str,
    workspace_num: str,
    wave_num: int,
    project_root: str,
    base_branch: str,
) -> str:
    """Render single isolation block — always manual worktree."""
    branch = f"wave-{workspace_num}-{wave_num}/{slug}"
    wrk = f".claude/worktrees/icm-wave-{workspace_num}-{wave_num}-{slug}"
    pr = project_root

    return (
        "### Isolation rules (MANDATORY)\n"
        "\n"
        f"- [ ] Your CWD is `{wrk}/` — a git worktree on branch `{branch}`.\n"
        f"      Run `pwd` to confirm. NOT the project root.\n"
        "- [ ] Write code ONLY in this worktree. NEVER write via absolute paths to the project.\n"
        f"- [ ] NEVER write to `{pr}/.icm-main/` or any path under it.\n"
        "      It is the base-branch linked worktree — read-only for docs.\n"
        "- [ ] NEVER run `git checkout`, `git switch`, `git rebase`, or `git push`.\n"
        "      Your branch is pre-created and checked out.\n"
        "- [ ] Read base-branch docs (ADRs, lessons, tech_debt) with absolute path:\n"
        f"      `{pr}/.icm-main/<path>`\n"
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
    )


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

    Output order: HARD GATES → isolation rules → Summary → Behavior →
    Key interfaces → Acceptance criteria → Out of scope.
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

    gates = _render_hard_gates(
        slug=slug,
        workspace_num=workspace_num,
        wave_num=wave_num,
        base_branch=bb,
    )

    isolation = _render_isolation_block(
        slug=slug,
        workspace_num=workspace_num,
        wave_num=wave_num,
        project_root=pr,
        base_branch=bb,
    )

    return (
        f"## Agent Brief — {slug}\n"
        "\n"
        f"{gates}\n"
        f"{isolation}\n"
        f"**Type:** {parsed['type']}\n"
        f"**Files touched:** {parsed['files_touched']}\n"
        f"{model_block}"
        f"**Summary:** {_first_line(parsed['what'])}\n"
        "\n"
        "**Desired behavior:**\n"
        f"{parsed['what']}\n"
        "\n"
        "**Key interfaces:**\n"
        f"{parsed['how']}\n"
        f"{adrs_block}"
        "\n"
        "**Acceptance criteria:**\n"
        f"{parsed['validation']}\n"
        "\n"
        "**Out of scope:**\n"
        f"{parsed['out_of_scope']}\n"
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
    """Detect anti-patterns (absolute paths, line numbers)."""
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
        help="if provided, uses heuristic to recommend model (haiku|sonnet|opus)",
    )
    parser.add_argument(
        "--workspace-num", required=True,
        help="workspace number (e.g. 001)",
    )
    parser.add_argument(
        "--wave", type=int, required=True,
        help="wave number",
    )
    parser.add_argument(
        "--project-root", required=True,
        help="project root absolute path",
    )
    parser.add_argument(
        "--base-branch", default="main",
        help="base branch name (default: main)",
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
        adrs = sorted(p.name for p in args.adrs.glob("[0-9]*.md"))

    model: str | None = None
    if args.tier:
        model = _recommend_model(section)

    brief = render_brief(
        args.task, parsed, adrs, model=model or "",
        workspace_num=args.workspace_num,
        wave_num=args.wave,
        project_root=args.project_root,
        base_branch=args.base_branch,
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
