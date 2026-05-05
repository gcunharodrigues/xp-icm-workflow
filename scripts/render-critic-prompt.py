#!/usr/bin/env python3
"""Render critic prompt — fills `templates/critic-prompt.md` placeholders.

Replaces the manual 10-placeholder substitution that was previously done by
the LLM lead. Automates git diff capture, task 4-block extraction from
plan.md, and test output capture.

CLI:
  python scripts/render-critic-prompt.py \\
      --task-slug config-module --wave 1 --tier development \\
      --workspace-num 001 --base-branch main \\
      --plan stages/02_design/output/plan.md \\
      --critic-model claude-sonnet-4-6 \\
      [--test-command "pytest tests/ -x --tb=short"] \\
      [--cwd /path/to/project]

Stdout: rendered prompt ready for Agent tool injection.
Exit 0 = success. Exit 1 = error (missing branch, plan parse failure, etc).
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Plan parsing (lightweight — extracts only what the critic needs)
# ---------------------------------------------------------------------------

def _extract_section(block: str, section_title: str) -> str:
    """Extract body of `### <title>` section from a task block."""
    pattern = re.compile(
        rf"^###\s+{re.escape(section_title)}\s*$",
        re.MULTILINE | re.IGNORECASE,
    )
    match = pattern.search(block)
    if not match:
        return ""
    tail = block[match.end():]
    next_section = re.search(r"^(##\s|###\s)", tail, re.MULTILINE)
    body = tail[: next_section.start()] if next_section else tail
    return body.strip()


def _extract_bullets(block: str, section_title: str) -> list[str]:
    """Extract bullet items from `### <title>` section."""
    body = _extract_section(block, section_title)
    items: list[str] = []
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("- "):
            value = line[2:].strip()
            if value:
                # Strip parenthetical notes (same as wave-planner-script.py)
                value = re.sub(r'\s*\([^)]*\)', '', value).strip()
            if value:
                items.append(value)
    return items


def parse_task_from_plan(plan_path: Path, task_slug: str) -> dict:
    """Extract task 4-block, acceptance criteria, ADRs, and deps from plan.md."""
    text = plan_path.read_text(encoding="utf-8")

    # Find task block: ## Task <slug>:
    pattern = re.compile(
        rf"^##\s+Task\s+{re.escape(task_slug)}\s*:.*$",
        re.MULTILINE | re.IGNORECASE,
    )
    match = pattern.search(text)
    if not match:
        sys.stderr.write(f"render-critic-prompt: task {task_slug!r} not found in plan\n")
        sys.exit(1)

    start = match.start()
    # Find next task block or end of file
    next_task = re.search(r"^##\s+Task\s+", text[match.end():], re.MULTILINE)
    end = match.end() + next_task.start() if next_task else len(text)
    block = text[start:end]

    # Extract 4-block for full context
    what = _extract_section(block, "WHAT")
    how = _extract_section(block, "HOW")
    out_of_scope = _extract_section(block, "OUT OF SCOPE")
    validation = _extract_section(block, "VALIDATION")

    task_4block = f"### WHAT\n{what}\n\n### HOW\n{how}\n\n"
    task_4block += f"### OUT OF SCOPE\n{out_of_scope}\n\n### VALIDATION\n{validation}"

    adrs = _extract_bullets(block, "Applicable ADRs")
    adrs_text = "\n".join(f"- {a}" for a in adrs) if adrs else "(none)"

    return {
        "task_4block": task_4block,
        "acceptance_criteria": validation,
        "adrs_applicable": adrs_text,
        "depends_on": _extract_bullets(block, "Depends on"),
        "files_touched": _extract_bullets(block, "Files touched"),
    }


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def capture_diff(cwd: Path, base_branch: str, branch: str) -> str:
    """Capture full diff between base and task branch."""
    try:
        result = subprocess.run(
            ["git", "diff", f"{base_branch}...{branch}"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        sys.stderr.write("render-critic-prompt: git binary not found\n")
        sys.exit(1)
    if result.returncode != 0:
        sys.stderr.write(
            f"render-critic-prompt: git diff failed: {result.stderr.strip()}\n"
        )
        sys.exit(1)
    return result.stdout


def capture_test_output(cwd: Path, test_command: str) -> str:
    """Run test command and capture stdout+stderr."""
    try:
        result = subprocess.run(
            test_command,
            cwd=str(cwd),
            shell=True,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        return "[TEST RUNNER TIMED OUT AFTER 120s]"
    except FileNotFoundError:
        return f"[TEST COMMAND NOT FOUND: {test_command}]"
    return result.stdout + "\n" + result.stderr


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------

def render(template_text: str, variables: dict[str, str]) -> str:
    """Substitute {{PLACEHOLDERS}} with values."""
    result = template_text
    for key, value in variables.items():
        result = result.replace("{{" + key + "}}", value)
    # Warn about unresolved placeholders
    unresolved = set(re.findall(r"\{\{([A-Z_][A-Z0-9_]*)\}\}", result))
    if unresolved:
        sys.stderr.write(
            f"render-critic-prompt: warning — unresolved placeholders: {unresolved}\n"
        )
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="render-critic-prompt.py",
        description="Render L3 critic prompt from templates/critic-prompt.md",
    )
    parser.add_argument("--task-slug", required=True, help="Task slug (kebab-case)")
    parser.add_argument("--wave", required=True, type=int, help="Wave number")
    parser.add_argument("--tier", required=True, help="Tier (experimental/tool/development/production)")
    parser.add_argument("--workspace-num", required=True, help="Workspace number (e.g. 001)")
    parser.add_argument("--base-branch", required=True, help="Base branch (e.g. main)")
    parser.add_argument("--plan", type=Path, required=True, help="Path to plan.md")
    parser.add_argument("--critic-model", required=True, help="Model for critic (from pick-model.py)")
    parser.add_argument(
        "--test-command",
        default="pytest tests/ -x --tb=short -q",
        help="Test runner command (default: pytest)",
    )
    parser.add_argument("--cwd", type=Path, default=None, help="Project root (default: cwd)")
    parser.add_argument("--output", type=Path, default=None, help="Write to file instead of stdout")

    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    cwd = args.cwd or Path.cwd()
    branch = f"wave-{args.workspace_num}-{args.wave}/{args.task_slug}"

    # 1. Parse task from plan.md
    plan_path = args.plan
    if not plan_path.is_absolute():
        plan_path = cwd / plan_path
    task = parse_task_from_plan(plan_path, args.task_slug)

    # 2. Capture git diff
    diff = capture_diff(cwd, args.base_branch, branch)

    # 3. Capture test output
    test_output = capture_test_output(cwd, args.test_command)

    # 4. Load template
    # Find template relative to this script
    script_dir = Path(__file__).resolve().parent.parent
    template_path = script_dir / "templates" / "critic-prompt.md"
    if not template_path.is_file():
        sys.stderr.write(
            f"render-critic-prompt: template not found: {template_path}\n"
        )
        return 1
    template_text = template_path.read_text(encoding="utf-8")

    # 5. Substitute placeholders
    variables = {
        "TASK_SLUG": args.task_slug,
        "WAVE_NUM": str(args.wave),
        "TIER": args.tier,
        "TASK_4BLOCK": task["task_4block"],
        "ACCEPTANCE_CRITERIA": task["acceptance_criteria"],
        "ADRS_APPLICABLE": task["adrs_applicable"],
        "WORKSPACE_NUM": args.workspace_num,
        "DIFF_COMPLETE": diff if diff else "(empty diff — no commits on branch?)",
        "TEST_OUTPUT_RAW": test_output,
        "CRITIC_MODEL": args.critic_model,
    }
    rendered = render(template_text, variables)

    # 6. Output
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
        print(f"render-critic-prompt: wrote {args.output}")
    else:
        sys.stdout.write(rendered)

    return 0


if __name__ == "__main__":
    sys.exit(main())
