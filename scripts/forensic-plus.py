#!/usr/bin/env python3
"""Forensic+ — anti-fraud structural audit per task in stage 04 wave-reviewer.

Reads CLI args + plan.md + git state. Runs 4 checks. Emits JSON to stdout.
Exit 0 always when script completes normally (regardless of violations).
Exit 1 on script crash (git missing, plan malformed, etc.).

Spec: docs/superpowers/specs/2026-05-03-forensic-plus-wave-reviewer-design.md
Canonical: references/forensic-plus-protocol.md
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


# ============================================================================
# Constants
# ============================================================================

VALID_TIERS = ("experimental", "tool", "development", "production")


# ============================================================================
# Constants — Check 1 language-aware regex
# ============================================================================

ASSERT_PATTERNS_BY_EXT: dict[str, str] = {
    ".py":   r"\bassert\b|pytest\.raises|self\.assert\w+",
    ".ts":   r"\b(expect|assert|should|it\(|test\()\b",
    ".tsx":  r"\b(expect|assert|should|it\(|test\()\b",
    ".js":   r"\b(expect|assert|should|it\(|test\()\b",
    ".jsx":  r"\b(expect|assert|should|it\(|test\()\b",
    ".go":   r"\bt\.(Errorf|Fatal|Run)\b",
    ".rb":   r"\b(expect|assert|should)\b",
    ".rs":   r"\bassert(_eq|_ne)?!\b",
    ".java": r"\b(assert|@Test|assertEquals)",
    ".kt":   r"\b(assert|@Test|assertEquals)",
    ".cs":   r"\b(Assert\.|\[Test\]|\[Fact\]|\[Theory\])",
}

ASSERT_THRESHOLD = 2

# Test file path patterns (mirror wave-planner-algorithm.md §2)
TEST_PATH_PATTERNS = [
    re.compile(r"(^|/)tests?/"),
    re.compile(r"(^|/)__tests__/"),
    re.compile(r"(^|/)spec/"),
    re.compile(r"_test\.[a-z]+$"),
    re.compile(r"\.test\.[a-z]+$"),
    re.compile(r"\.spec\.[a-z]+$"),
    re.compile(r"^test_.*\.py$"),
]


def _is_test_file(path: str) -> bool:
    """True if path matches any TEST_PATH_PATTERNS."""
    return any(p.search(path) for p in TEST_PATH_PATTERNS)


# ============================================================================
# Plan parser
# ============================================================================

class PlanParseError(Exception):
    """Raised when plan.md cannot be read or task slug not found."""
    pass


def parse_plan_for_task(plan_path: Path, task_slug: str) -> dict:
    """Extract task metadata from plan.md.

    Returns dict with keys: files_touched, conventions_extras, estimated_lines, type.
    Raises PlanParseError if plan unreadable or task slug not found.
    """
    if not plan_path.is_file():
        raise PlanParseError(f"plan.md not found: {plan_path}")
    text = plan_path.read_text(encoding="utf-8")

    # Find task header
    header_re = re.compile(rf"^## Task {re.escape(task_slug)}:", re.MULTILINE)
    m = header_re.search(text)
    if not m:
        raise PlanParseError(f"task slug not found in plan: {task_slug}")

    # Slice from this header to next ## or EOF
    start = m.start()
    next_m = re.search(r"^## ", text[m.end():], re.MULTILINE)
    end = m.end() + next_m.start() if next_m else len(text)
    section = text[start:end]

    def _bullets_under(heading: str) -> list[str]:
        """Return bullet items under a `### {heading}` block, stripped of `- ` prefix."""
        h_re = re.compile(rf"^### {re.escape(heading)}\s*\n", re.MULTILINE)
        h_m = h_re.search(section)
        if not h_m:
            return []
        rest = section[h_m.end():]
        next_h = re.search(r"^### ", rest, re.MULTILINE)
        block = rest[: next_h.start()] if next_h else rest
        return [
            re.sub(r"^-\s+", "", ln).strip()
            for ln in block.splitlines()
            if ln.strip().startswith("-")
        ]

    files_touched = _bullets_under("Files touched")
    conventions = _bullets_under("Conventions extras")
    type_field = _bullets_under("Type")

    # Estimated lines: parse "~250" or "250" from block (not bullet)
    est_lines = None
    est_h = re.search(r"^### Estimated lines\s*\n", section, re.MULTILINE)
    if est_h:
        rest = section[est_h.end():]
        next_h = re.search(r"^### ", rest, re.MULTILINE)
        block = rest[: next_h.start()] if next_h else rest
        # Extract first int from block
        num_m = re.search(r"\d+", block)
        if num_m:
            est_lines = int(num_m.group(0))

    return {
        "files_touched": files_touched,
        "conventions_extras": conventions,
        "estimated_lines": est_lines,
        "type": type_field[0].upper() if type_field else "AFK",
    }


# ============================================================================
# Git subprocess wrapper
# ============================================================================

class GitError(Exception):
    """Raised when a git subprocess invocation fails."""
    pass


def _git_run(cwd: Path, *args: str) -> str:
    """Run git command. Returns stdout. Raises GitError on non-zero exit."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as e:
        raise GitError(f"git binary not found: {e}") from e
    if result.returncode != 0:
        raise GitError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def _git_show_file(cwd: Path, ref: str, path: str) -> str | None:
    """Return file content at ref, or None if missing/binary."""
    try:
        return _git_run(cwd, "show", f"{ref}:{path}")
    except GitError:
        return None


# ============================================================================
# Check 1 — test assertions
# ============================================================================

def check_test_assertions(
    cwd: Path,
    branch: str,
    files_touched: list[str],
    conventions_extras: list[str],
) -> list[dict]:
    """Verify each declared test file has >= ASSERT_THRESHOLD assertion-shaped tokens.

    The check is purely count-based — it does not distinguish `assert True` from
    `assert x == y`. Rationale (spec §4.1): a single assertion is too easily a
    placeholder; >=2 indicates a minimal real suite. Quality of the assertion is
    out of scope for forensic+; the wave-reviewer's acceptance audit (step 8c)
    catches semantic emptiness.

    Severity is HARD across all tiers (spec §4.1), so this check does not take
    a tier parameter — unlike future checks (files_outside_declared, scope_creep,
    todo_added) which vary severity by tier.

    Returns list of violation dicts (empty if pass).
    """
    if any(c.lower().strip() in ("doc-only", "config-only") for c in conventions_extras):
        return []

    violations: list[dict] = []
    for path in files_touched:
        if not _is_test_file(path):
            continue
        ext_idx = path.rfind(".")
        ext = path[ext_idx:] if ext_idx >= 0 else ""
        pattern = ASSERT_PATTERNS_BY_EXT.get(ext)
        if pattern is None:
            continue  # unsupported extension, skip silently
        content = _git_show_file(cwd, branch, path)
        if content is None:
            violations.append({
                "check": "test_assertions_too_few",
                "severity": "HARD",
                "evidence": f"test file missing on branch: {path}",
            })
            continue
        count = len(re.findall(pattern, content))
        if count < ASSERT_THRESHOLD:
            violations.append({
                "check": "test_assertions_too_few",
                "severity": "HARD",
                "evidence": f"{path}: {count} non-trivial assertion(s) found, need >={ASSERT_THRESHOLD}",
            })
    return violations


# ============================================================================
# Tier × violation severity matrix (spec §4.2)
# ============================================================================

TIER_SEVERITY: dict[str, dict[str, str]] = {
    "test_assertions_too_few":   {"experimental": "HARD", "tool": "HARD", "development": "HARD", "production": "HARD"},
    "files_outside_declared":    {"experimental": "SOFT", "tool": "SOFT", "development": "HARD", "production": "HARD"},
    "scope_creep":               {"experimental": "SOFT", "tool": "SOFT", "development": "SOFT", "production": "HARD"},
    "todo_added":                {"experimental": "SOFT", "tool": "SOFT", "development": "SOFT", "production": "HARD"},
}


def _severity_for(check: str, tier: str) -> str:
    return TIER_SEVERITY[check][tier]


# ============================================================================
# Allowlists — Check 2
# ============================================================================

LOCKFILE_ALLOWLIST = frozenset({
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "bun.lockb",
    "Cargo.lock",
    "Gemfile.lock",
    "poetry.lock",
    "go.sum",
    ".prettierrc.cache",
    ".eslintcache",
})


def _basename(path: str) -> str:
    return path.rsplit("/", 1)[-1]


# ============================================================================
# Check 2 — files outside declared
# ============================================================================

def check_files_outside_declared(
    cwd: Path,
    branch: str,
    base_branch: str,
    files_touched: list[str],
    tier: str,
) -> list[dict]:
    """Compare actual git diff filenames against declared files_touched.

    Files in actual but not declared (excluding lockfile allowlist) → violation.
    """
    declared = set(files_touched)
    raw = _git_run(cwd, "diff", "--name-only", f"{base_branch}...{branch}")
    actual = {ln.strip() for ln in raw.splitlines() if ln.strip()}
    extras = {p for p in actual - declared if _basename(p) not in LOCKFILE_ALLOWLIST}
    if not extras:
        return []
    sev = _severity_for("files_outside_declared", tier)
    return [{
        "check": "files_outside_declared",
        "severity": sev,
        "evidence": f"{len(extras)} undeclared file(s): {', '.join(sorted(extras))}",
    }]


# ============================================================================
# CLI
# ============================================================================

def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Forensic+ structural audit for stage 04 wave-reviewer."
    )
    p.add_argument("--workspace-num", required=True, help="Workspace number (NNN).")
    p.add_argument("--wave", required=True, type=int, help="Wave index (1-based).")
    p.add_argument("--task-slug", required=True, help="Task slug (kebab-case).")
    p.add_argument("--base-branch", required=True, help="Base branch (e.g. main).")
    p.add_argument("--plan", required=True, help="Path to plan.md.")
    p.add_argument("--tier", required=True, choices=VALID_TIERS, help="Workspace tier.")
    p.add_argument("--output", default="json", choices=("json",), help="Output format.")
    return p.parse_args(argv)


# ============================================================================
# Main
# ============================================================================

def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])

    cwd = Path.cwd()
    branch = f"wave-{args.workspace_num}-{args.wave}/{args.task_slug}"
    plan_path = Path(args.plan)

    try:
        task_meta = parse_plan_for_task(plan_path, args.task_slug)
    except PlanParseError as e:
        sys.stderr.write(f"forensic-plus: {e}\n")
        return 1

    # HITL skip: spec §6.5 EC4 / Q4=A
    if task_meta["type"] == "HITL":
        result = {
            "task_slug": args.task_slug,
            "violations": [],
            "forensic_passed": None,
            "max_severity": None,
            "skipped_reason": "task type=HITL",
        }
        sys.stdout.write(json.dumps(result, indent=2) + "\n")
        return 0

    violations: list[dict] = []
    try:
        violations.extend(check_test_assertions(
            cwd, branch, task_meta["files_touched"], task_meta["conventions_extras"]
        ))
    except GitError as e:
        sys.stderr.write(f"forensic-plus: {e}\n")
        return 1

    try:
        violations.extend(check_files_outside_declared(
            cwd, branch, args.base_branch, task_meta["files_touched"], args.tier,
        ))
    except GitError as e:
        sys.stderr.write(f"forensic-plus: {e}\n")
        return 1

    # Reduce to result schema
    has_hard = any(v["severity"] == "HARD" for v in violations)
    has_soft = any(v["severity"] == "SOFT" for v in violations)
    max_severity = "HARD" if has_hard else ("SOFT" if has_soft else "NONE")

    result: dict[str, Any] = {
        "task_slug": args.task_slug,
        "violations": violations,
        "forensic_passed": not has_hard,
        "max_severity": max_severity,
    }
    sys.stdout.write(json.dumps(result, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
