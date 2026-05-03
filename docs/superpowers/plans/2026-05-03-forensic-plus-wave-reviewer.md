# Forensic+ Wave Reviewer Implementation Plan (v3.8.0)

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add structural anti-fraud checks to the stage 04 wave-reviewer (xp-icm-workflow skill) by introducing a deterministic `forensic-plus.py` script that audits each task's git diff for 4 violation classes (test asserções, files outside declared, scope creep, TODO/FIXME), with tier-aware HARD/SOFT severity and re-spawn loop integration.

**Architecture:** Standalone Python script invoked per task by the wave-reviewer Agent. Pure I/O contract: reads CLI args + git/plan.md, writes JSON to stdout. Reviewer parses JSON, populates `task-<slug>.md` frontmatter, decides re-spawn (HARD) vs warn (SOFT). Three new fields in task-md frontmatter (`forensic_violations`, `forensic_passed`, `forensic_max_severity`, `forensic_respawn_count`); new optional `### Estimated lines` block in `plan.md` task schema; new section in `wave-summary.md`. New canonical doc `references/forensic-plus-protocol.md`. Step 8 of `references/wave-execution-protocol.md` expanded into 8a/8b/8c/8d. Cap `MAX_FORENSIC_RETRIES = 2` before BLOCKED_ERROR escalation.

**Tech Stack:** Python 3.11+ (existing skill runtime), pytest + Hypothesis (existing test framework), pygit2 NOT used (subprocess.run on `git` binary — matches repo pattern), bats (existing CI-only integration).

**Spec reference:** `docs/superpowers/specs/2026-05-03-forensic-plus-wave-reviewer-design.md`

---

## File Structure

### New files

| Path | Responsibility |
|------|----------------|
| `scripts/forensic-plus.py` | Runtime: parse CLI, run 4 checks via git subprocess, emit JSON. Pure function modulo git state. |
| `references/forensic-plus-protocol.md` | Canonical doc: 4 checks, tier matrix, HARD/SOFT actions, re-spawn cap, edge cases, JSON schema. |
| `tests/unit/test_forensic_plus.py` | Unit coverage for the script (~25 tests), incl. Hypothesis property tests. |
| `tests/unit/test_wave_reviewer_forensic_integration.py` | Mocks Agent tool; tests reviewer's parser + re-spawn loop logic. |
| `tests/integration/test_forensic_plus_e2e.bats` | Bats CI-only: real git + real script + assertion on output files. |
| `tests/fixtures/forensic-plus-expected/*.json` | 6 snapshot fixtures: (plan.md, git diff, tier) → expected JSON. |

### Edited files

| Path | Change |
|------|--------|
| `scripts/bootstrap.py` | `SKILL_VERSION = "3.8.0"` + add `forensic-plus-protocol.md` to `runtime_refs`. |
| `scripts/wave-planner-script.py` | Rename `skip_wave_reviewer` flag → `skip_cross_task_audit` with backward-compat alias. |
| `scripts/migrate-workspace.py` | `CURRENT_SKILL_VERSION = "3.8.0"`, append tuple, new `migrate_3_7_2_to_3_8_0` (bump-only), `STEP_FUNCTIONS` entry. |
| `tests/unit/test_no_drift.py` | 4 new drift detectors. |
| `tests/unit/test_migrate_workspace.py` | Smoke + idempotency for new step. |
| `templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl` | Step 8 expanded, new error_type, re-spawn brief. |
| `references/wave-execution-protocol.md` | Step 8 expanded into 8a/8b/8c/8d, cross-ref forensic-plus-protocol. |
| `references/wave-planner-algorithm.md` | Flag rename owner doc. |
| `references/4-block-contract-template.md` | Optional `### Estimated lines` after `### Files touched`. |
| `references/state-machine-schema.md` | Comment about new `error_type` values (no enum change). |
| `SKILL.md` | Header `v3.8.0`. |
| `README.md` | Badge `version-v3.8.0` + new section `## v3.8.0`. |
| `references/design-system.md` | Frontmatter version + line. |
| `references/preview-loop-protocol.md` | Title + version line. |
| `references/changelog.md` | New entry `## v3.8.0 — Forensic+ wave reviewer (2026-05-03)`. |

### Decomposition rationale

- `forensic-plus.py` is one focused unit (4 checks share git fetch + plan parsing). Splitting per check would add IPC overhead with no benefit. Internal organization splits parse/check/emit into clear functions, each testable.
- Canonical doc separated from L2 template so future stage 04 changes don't conflict with forensic doc evolution.
- Drift detectors live in existing `test_no_drift.py` (single source of truth for cross-file consistency, per CLAUDE.md).

---

## Chunk 1: forensic-plus.py core (TDD per check)

Goal: ship a working, fully-tested `scripts/forensic-plus.py` that handles all 4 checks, the tier matrix, JSON output, and edge cases EC1/EC4. The wave-reviewer will not call it yet (that comes in Chunk 3).

### Task 1: Scaffold forensic-plus.py + CLI parser + JSON output skeleton

**Files:**
- Create: `scripts/forensic-plus.py`
- Test: `tests/unit/test_forensic_plus.py`

- [ ] **Step 1: Write the failing test for CLI argument parsing**

```python
# tests/unit/test_forensic_plus.py
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "forensic-plus.py"


def _run(args, cwd=None):
    """Helper: run forensic-plus.py and return (returncode, stdout, stderr)."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    return result.returncode, result.stdout, result.stderr


def test_cli_requires_all_args():
    """Missing required args → exit 2 (argparse default for missing args)."""
    rc, _, stderr = _run([])
    assert rc == 2
    assert "required" in stderr.lower() or "the following arguments" in stderr.lower()


def test_cli_outputs_valid_json_skeleton(tmp_path):
    """Smoke: with minimal valid args + nonexistent branch (causes graceful 0 with empty violations not yet implemented), CLI runs."""
    # plan stub
    plan = tmp_path / "plan.md"
    plan.write_text("## Task add-foo:\n### Files touched\n- src/foo.py\n- tests/test_foo.py\n", encoding="utf-8")

    rc, stdout, stderr = _run(
        [
            "--workspace-num", "001",
            "--wave", "1",
            "--task-slug", "add-foo",
            "--base-branch", "main",
            "--plan", str(plan),
            "--tier", "development",
            "--output", "json",
        ],
        cwd=tmp_path,
    )
    # In skeleton stage, exit 1 acceptable (git command fails on no repo).
    # Verify JSON structure on stdout when exit 0; verify stderr non-empty on exit 1.
    assert rc in (0, 1)
    if rc == 0:
        data = json.loads(stdout)
        assert data["task_slug"] == "add-foo"
        assert "violations" in data
        assert "forensic_passed" in data
        assert "max_severity" in data
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/unit/test_forensic_plus.py::test_cli_requires_all_args -v
```
Expected: FAIL with "No such file or directory: scripts/forensic-plus.py" or similar.

- [ ] **Step 3: Create script skeleton with argparse + JSON output stub**

```python
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
import sys
from typing import Any


# ============================================================================
# Constants
# ============================================================================

VALID_TIERS = ("experimental", "tool", "development", "production")


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

    # Skeleton: emit empty result. Will be filled in Tasks 2-7.
    result: dict[str, Any] = {
        "task_slug": args.task_slug,
        "violations": [],
        "forensic_passed": True,
        "max_severity": "NONE",
    }
    sys.stdout.write(json.dumps(result, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/unit/test_forensic_plus.py::test_cli_requires_all_args -v
pytest tests/unit/test_forensic_plus.py::test_cli_outputs_valid_json_skeleton -v
```
Expected: both PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/forensic-plus.py tests/unit/test_forensic_plus.py
git commit -m "feat(forensic-plus): scaffold script + CLI parser (skeleton)"
```

---

### Task 2: Check 1 — test file with non-trivial assertions

**Files:**
- Modify: `scripts/forensic-plus.py` (add Check 1 + plan parser + git subprocess wrapper)
- Modify: `tests/unit/test_forensic_plus.py` (Check 1 cases)

- [ ] **Step 1: Write the failing tests for Check 1**

```python
# Append to tests/unit/test_forensic_plus.py

import os
import subprocess as _sp


def _git(cwd, *args):
    """Run git command in cwd; return stdout."""
    return _sp.check_output(["git", *args], cwd=cwd, text=True).strip()


def _make_repo_with_branch(tmp_path, base_files: dict, branch_files: dict, branch_name: str):
    """Initialize a git repo with base commit + a feature branch with extra files."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    for path, content in base_files.items():
        full = repo / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "base")

    _git(repo, "checkout", "-b", branch_name)
    for path, content in branch_files.items():
        full = repo / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "branch work")
    _git(repo, "checkout", "main")
    return repo


def _make_plan(repo, task_slug, files_touched, conventions_extras=None, estimated_lines=None):
    """Write a minimal plan.md with one task."""
    plan = repo / "plan.md"
    body = f"## Task {task_slug}:\n\n### O QUE\n- placeholder\n\n### Files touched\n"
    for f in files_touched:
        body += f"- {f}\n"
    if estimated_lines is not None:
        body += f"\n### Estimated lines\n~{estimated_lines}\n"
    if conventions_extras:
        body += f"\n### Conventions extras\n- {conventions_extras}\n"
    plan.write_text(body, encoding="utf-8")
    return plan


def test_check1_python_passes_with_three_asserts(tmp_path):
    """Test file with 3 non-trivial asserts → no violation."""
    test_content = (
        "def test_a():\n"
        "    assert 1 + 1 == 2\n"
        "    assert 'x' in 'xy'\n"
        "    assert len([1, 2]) == 2\n"
    )
    repo = _make_repo_with_branch(
        tmp_path,
        base_files={"src/foo.py": "def foo(): return 1\n"},
        branch_files={
            "src/foo.py": "def foo(): return 2\n",
            "tests/test_foo.py": test_content,
        },
        branch_name="wave-001-1/add-foo",
    )
    plan = _make_plan(repo, "add-foo", ["src/foo.py", "tests/test_foo.py"])

    rc, stdout, _ = _run(
        [
            "--workspace-num", "001",
            "--wave", "1",
            "--task-slug", "add-foo",
            "--base-branch", "main",
            "--plan", str(plan),
            "--tier", "development",
            "--output", "json",
        ],
        cwd=repo,
    )
    assert rc == 0
    data = json.loads(stdout)
    check1_violations = [v for v in data["violations"] if v["check"] == "test_assertions_too_few"]
    assert len(check1_violations) == 0


def test_check1_python_fails_with_assert_true_only(tmp_path):
    """Test file with only `assert True` → HARD violation in all tiers."""
    test_content = "def test_a():\n    assert True\n"
    repo = _make_repo_with_branch(
        tmp_path,
        base_files={"src/foo.py": "def foo(): return 1\n"},
        branch_files={
            "src/foo.py": "def foo(): return 2\n",
            "tests/test_foo.py": test_content,
        },
        branch_name="wave-001-1/add-foo",
    )
    plan = _make_plan(repo, "add-foo", ["src/foo.py", "tests/test_foo.py"])

    rc, stdout, _ = _run(
        [
            "--workspace-num", "001",
            "--wave", "1",
            "--task-slug", "add-foo",
            "--base-branch", "main",
            "--plan", str(plan),
            "--tier", "experimental",  # HARD even at lowest tier
            "--output", "json",
        ],
        cwd=repo,
    )
    assert rc == 0
    data = json.loads(stdout)
    check1 = [v for v in data["violations"] if v["check"] == "test_assertions_too_few"]
    assert len(check1) == 1
    assert check1[0]["severity"] == "HARD"
    assert "tests/test_foo.py" in check1[0]["evidence"]
    assert data["forensic_passed"] is False
    assert data["max_severity"] == "HARD"


def test_check1_skip_doc_only(tmp_path):
    """Task with `Conventions extras: doc-only` skips Check 1."""
    repo = _make_repo_with_branch(
        tmp_path,
        base_files={"README.md": "# old\n"},
        branch_files={"README.md": "# new\n"},
        branch_name="wave-001-1/update-readme",
    )
    plan = _make_plan(
        repo, "update-readme", ["README.md"], conventions_extras="doc-only"
    )

    rc, stdout, _ = _run(
        [
            "--workspace-num", "001",
            "--wave", "1",
            "--task-slug", "update-readme",
            "--base-branch", "main",
            "--plan", str(plan),
            "--tier", "production",
            "--output", "json",
        ],
        cwd=repo,
    )
    assert rc == 0
    data = json.loads(stdout)
    check1 = [v for v in data["violations"] if v["check"] == "test_assertions_too_few"]
    assert len(check1) == 0


def test_check1_typescript_pass_and_fail(tmp_path):
    """Language-aware regex: .ts test file with 2+ expect calls passes; with 1 fails."""
    pass_ts = "test('x', () => { expect(1).toBe(1); expect(2).toBe(2); });\n"
    fail_ts = "test('x', () => { /* no expect */ });\n"
    # Pass case
    repo_pass = _make_repo_with_branch(
        tmp_path / "p",
        base_files={"src/x.ts": "export const x = 1;\n"},
        branch_files={
            "src/x.ts": "export const x = 2;\n",
            "tests/x.test.ts": pass_ts,
        },
        branch_name="wave-001-1/add-x",
    )
    plan_pass = _make_plan(repo_pass, "add-x", ["src/x.ts", "tests/x.test.ts"])
    rc, stdout, _ = _run(
        ["--workspace-num", "001", "--wave", "1", "--task-slug", "add-x",
         "--base-branch", "main", "--plan", str(plan_pass), "--tier", "development",
         "--output", "json"],
        cwd=repo_pass,
    )
    assert rc == 0
    assert not [v for v in json.loads(stdout)["violations"] if v["check"] == "test_assertions_too_few"]

    # Fail case
    repo_fail = _make_repo_with_branch(
        tmp_path / "f",
        base_files={"src/x.ts": "export const x = 1;\n"},
        branch_files={
            "src/x.ts": "export const x = 2;\n",
            "tests/x.test.ts": fail_ts,
        },
        branch_name="wave-001-1/add-x",
    )
    plan_fail = _make_plan(repo_fail, "add-x", ["src/x.ts", "tests/x.test.ts"])
    rc, stdout, _ = _run(
        ["--workspace-num", "001", "--wave", "1", "--task-slug", "add-x",
         "--base-branch", "main", "--plan", str(plan_fail), "--tier", "development",
         "--output", "json"],
        cwd=repo_fail,
    )
    assert rc == 0
    check1 = [v for v in json.loads(stdout)["violations"] if v["check"] == "test_assertions_too_few"]
    assert len(check1) == 1
    assert check1[0]["severity"] == "HARD"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/test_forensic_plus.py -v -k check1
```
Expected: 4 FAIL (Check 1 not yet implemented).

- [ ] **Step 3: Implement Check 1 + supporting infrastructure**

Add to `scripts/forensic-plus.py`:

```python
import re
import subprocess
from pathlib import Path

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
        h_re = re.compile(rf"^### {re.escape(heading)}\s*\n", re.MULTILINE)
        h_m = h_re.search(section)
        if not h_m:
            return []
        rest = section[h_m.end():]
        next_h = re.search(r"^### ", rest, re.MULTILINE)
        block = rest[: next_h.start()] if next_h else rest
        return [ln.lstrip("- ").strip() for ln in block.splitlines() if ln.strip().startswith("-")]

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
    tier: str,
) -> list[dict]:
    """Verify each declared test file has ≥ ASSERT_THRESHOLD non-trivial assertions.

    Returns list of violation dicts (empty if pass). Severity HARD all tiers.
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
                "evidence": f"{path}: {count} non-trivial assertion(s) found, need ≥{ASSERT_THRESHOLD}",
            })
    return violations
```

Wire into `main()`:

```python
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
            cwd, branch, task_meta["files_touched"], task_meta["conventions_extras"], args.tier
        ))
    except GitError as e:
        sys.stderr.write(f"forensic-plus: {e}\n")
        return 1

    # Reduce to result schema
    has_hard = any(v["severity"] == "HARD" for v in violations)
    has_soft = any(v["severity"] == "SOFT" for v in violations)
    max_severity = "HARD" if has_hard else ("SOFT" if has_soft else "NONE")

    result = {
        "task_slug": args.task_slug,
        "violations": violations,
        "forensic_passed": not has_hard,
        "max_severity": max_severity,
    }
    sys.stdout.write(json.dumps(result, indent=2) + "\n")
    return 0
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/unit/test_forensic_plus.py -v -k check1
```
Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/forensic-plus.py tests/unit/test_forensic_plus.py
git commit -m "feat(forensic-plus): implement Check 1 — test assertions threshold"
```

---

### Task 3: Check 2 — files outside declared `files_touched`

**Files:**
- Modify: `scripts/forensic-plus.py` (add Check 2 + lockfile allowlist + tier matrix helper)
- Modify: `tests/unit/test_forensic_plus.py` (Check 2 cases)

- [ ] **Step 1: Write failing tests for Check 2**

```python
# Append to tests/unit/test_forensic_plus.py

def test_check2_files_outside_dev_hard(tmp_path):
    """Diff touches undeclared file, tier=development → HARD violation."""
    repo = _make_repo_with_branch(
        tmp_path,
        base_files={"src/foo.py": "def foo(): return 1\n"},
        branch_files={
            "src/foo.py": "def foo(): return 2\n",
            "tests/test_foo.py": "def test_a():\n    assert 1 == 1\n    assert 2 == 2\n",
            "src/utils/helper.py": "def help(): pass\n",  # NOT declared
        },
        branch_name="wave-001-1/add-foo",
    )
    plan = _make_plan(repo, "add-foo", ["src/foo.py", "tests/test_foo.py"])

    rc, stdout, _ = _run(
        ["--workspace-num", "001", "--wave", "1", "--task-slug", "add-foo",
         "--base-branch", "main", "--plan", str(plan), "--tier", "development",
         "--output", "json"],
        cwd=repo,
    )
    assert rc == 0
    data = json.loads(stdout)
    c2 = [v for v in data["violations"] if v["check"] == "files_outside_declared"]
    assert len(c2) == 1
    assert c2[0]["severity"] == "HARD"
    assert "src/utils/helper.py" in c2[0]["evidence"]


def test_check2_files_outside_experimental_soft(tmp_path):
    """Same scenario but tier=experimental → SOFT (warn only)."""
    repo = _make_repo_with_branch(
        tmp_path,
        base_files={"src/foo.py": "x = 1\n"},
        branch_files={
            "src/foo.py": "x = 2\n",
            "tests/test_foo.py": "def test_a():\n    assert 1 == 1\n    assert 2 == 2\n",
            "src/utils/extra.py": "y = 1\n",
        },
        branch_name="wave-001-1/add-foo",
    )
    plan = _make_plan(repo, "add-foo", ["src/foo.py", "tests/test_foo.py"])

    rc, stdout, _ = _run(
        ["--workspace-num", "001", "--wave", "1", "--task-slug", "add-foo",
         "--base-branch", "main", "--plan", str(plan), "--tier", "experimental",
         "--output", "json"],
        cwd=repo,
    )
    assert rc == 0
    data = json.loads(stdout)
    c2 = [v for v in data["violations"] if v["check"] == "files_outside_declared"]
    assert len(c2) == 1
    assert c2[0]["severity"] == "SOFT"


def test_check2_lockfile_allowlist(tmp_path):
    """package-lock.json in diff but not declared → ignored."""
    repo = _make_repo_with_branch(
        tmp_path,
        base_files={
            "src/foo.js": "export const x = 1;\n",
            "package-lock.json": "{}\n",
        },
        branch_files={
            "src/foo.js": "export const x = 2;\n",
            "tests/foo.test.js": "test('x', () => { expect(1).toBe(1); expect(2).toBe(2); });\n",
            "package-lock.json": '{"updated": true}\n',
        },
        branch_name="wave-001-1/add-foo",
    )
    plan = _make_plan(repo, "add-foo", ["src/foo.js", "tests/foo.test.js"])

    rc, stdout, _ = _run(
        ["--workspace-num", "001", "--wave", "1", "--task-slug", "add-foo",
         "--base-branch", "main", "--plan", str(plan), "--tier", "production",
         "--output", "json"],
        cwd=repo,
    )
    assert rc == 0
    data = json.loads(stdout)
    c2 = [v for v in data["violations"] if v["check"] == "files_outside_declared"]
    assert len(c2) == 0  # lockfile allowlisted


def test_check2_no_violation_when_clean(tmp_path):
    """All touched files declared → no violation."""
    repo = _make_repo_with_branch(
        tmp_path,
        base_files={"src/foo.py": "x = 1\n"},
        branch_files={
            "src/foo.py": "x = 2\n",
            "tests/test_foo.py": "def test_a():\n    assert 1 == 1\n    assert 2 == 2\n",
        },
        branch_name="wave-001-1/add-foo",
    )
    plan = _make_plan(repo, "add-foo", ["src/foo.py", "tests/test_foo.py"])

    rc, stdout, _ = _run(
        ["--workspace-num", "001", "--wave", "1", "--task-slug", "add-foo",
         "--base-branch", "main", "--plan", str(plan), "--tier", "production",
         "--output", "json"],
        cwd=repo,
    )
    assert rc == 0
    data = json.loads(stdout)
    c2 = [v for v in data["violations"] if v["check"] == "files_outside_declared"]
    assert len(c2) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/test_forensic_plus.py -v -k check2
```
Expected: 4 FAIL.

- [ ] **Step 3: Implement Check 2 + tier matrix helper**

Append to `scripts/forensic-plus.py`:

```python
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
```

Wire into `main()` (insert after Check 1 call):

```python
    try:
        violations.extend(check_files_outside_declared(
            cwd, branch, args.base_branch, task_meta["files_touched"], args.tier,
        ))
    except GitError as e:
        sys.stderr.write(f"forensic-plus: {e}\n")
        return 1
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/unit/test_forensic_plus.py -v -k check2
```
Expected: 4 PASS. Also re-run check1 to confirm no regression: `pytest tests/unit/test_forensic_plus.py -v -k check1` → 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/forensic-plus.py tests/unit/test_forensic_plus.py
git commit -m "feat(forensic-plus): implement Check 2 — files outside declared + tier matrix"
```

---

### Task 4: Check 3 — scope creep > 3× plan estimate

**Files:**
- Modify: `scripts/forensic-plus.py` (add Check 3)
- Modify: `tests/unit/test_forensic_plus.py` (Check 3 cases)

- [ ] **Step 1: Write failing tests for Check 3**

```python
def test_check3_scope_creep_triggered(tmp_path):
    """Estimated 50 lines, actual 200+ → SOFT (development) / HARD (production)."""
    big_diff = "\n".join(f"line_{i} = {i}" for i in range(200))
    repo = _make_repo_with_branch(
        tmp_path,
        base_files={"src/foo.py": "x = 0\n"},
        branch_files={
            "src/foo.py": big_diff + "\n",
            "tests/test_foo.py": "def test_a():\n    assert 1 == 1\n    assert 2 == 2\n",
        },
        branch_name="wave-001-1/add-foo",
    )
    plan = _make_plan(repo, "add-foo", ["src/foo.py", "tests/test_foo.py"], estimated_lines=50)

    rc, stdout, _ = _run(
        ["--workspace-num", "001", "--wave", "1", "--task-slug", "add-foo",
         "--base-branch", "main", "--plan", str(plan), "--tier", "development",
         "--output", "json"],
        cwd=repo,
    )
    data = json.loads(stdout)
    c3 = [v for v in data["violations"] if v["check"] == "scope_creep"]
    assert len(c3) == 1
    assert c3[0]["severity"] == "SOFT"

    # Same scenario, tier=production → HARD
    rc, stdout, _ = _run(
        ["--workspace-num", "001", "--wave", "1", "--task-slug", "add-foo",
         "--base-branch", "main", "--plan", str(plan), "--tier", "production",
         "--output", "json"],
        cwd=repo,
    )
    data = json.loads(stdout)
    c3 = [v for v in data["violations"] if v["check"] == "scope_creep"]
    assert c3[0]["severity"] == "HARD"


def test_check3_under_threshold(tmp_path):
    """Estimated 250, actual <750 (3×) → no violation."""
    repo = _make_repo_with_branch(
        tmp_path,
        base_files={"src/foo.py": "x = 0\n"},
        branch_files={
            "src/foo.py": "x = 1\nx = 2\nx = 3\n",
            "tests/test_foo.py": "def test_a():\n    assert 1 == 1\n    assert 2 == 2\n",
        },
        branch_name="wave-001-1/add-foo",
    )
    plan = _make_plan(repo, "add-foo", ["src/foo.py", "tests/test_foo.py"], estimated_lines=250)

    rc, stdout, _ = _run(
        ["--workspace-num", "001", "--wave", "1", "--task-slug", "add-foo",
         "--base-branch", "main", "--plan", str(plan), "--tier", "development",
         "--output", "json"],
        cwd=repo,
    )
    data = json.loads(stdout)
    c3 = [v for v in data["violations"] if v["check"] == "scope_creep"]
    assert len(c3) == 0


def test_check3_skip_when_estimate_absent(tmp_path):
    """No `### Estimated lines` block → skip Check 3 silently (backward compat)."""
    big_diff = "\n".join(f"line_{i} = {i}" for i in range(2000))
    repo = _make_repo_with_branch(
        tmp_path,
        base_files={"src/foo.py": "x = 0\n"},
        branch_files={
            "src/foo.py": big_diff + "\n",
            "tests/test_foo.py": "def test_a():\n    assert 1 == 1\n    assert 2 == 2\n",
        },
        branch_name="wave-001-1/add-foo",
    )
    plan = _make_plan(repo, "add-foo", ["src/foo.py", "tests/test_foo.py"])  # no estimate

    rc, stdout, _ = _run(
        ["--workspace-num", "001", "--wave", "1", "--task-slug", "add-foo",
         "--base-branch", "main", "--plan", str(plan), "--tier", "production",
         "--output", "json"],
        cwd=repo,
    )
    data = json.loads(stdout)
    c3 = [v for v in data["violations"] if v["check"] == "scope_creep"]
    assert len(c3) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/test_forensic_plus.py -v -k check3
```
Expected: 3 FAIL.

- [ ] **Step 3: Implement Check 3**

Append to `scripts/forensic-plus.py`:

```python
SCOPE_CREEP_MULTIPLIER = 3

_SHORTSTAT_RE = re.compile(r"(\d+)\s+insertion")


def check_scope_creep(
    cwd: Path,
    branch: str,
    base_branch: str,
    estimated_lines: int | None,
    tier: str,
) -> list[dict]:
    """If estimated_lines declared, flag when insertions > N × estimate."""
    if estimated_lines is None:
        return []
    raw = _git_run(cwd, "diff", "--shortstat", f"{base_branch}...{branch}")
    m = _SHORTSTAT_RE.search(raw)
    if not m:
        return []
    insertions = int(m.group(1))
    threshold = SCOPE_CREEP_MULTIPLIER * estimated_lines
    if insertions <= threshold:
        return []
    sev = _severity_for("scope_creep", tier)
    return [{
        "check": "scope_creep",
        "severity": sev,
        "evidence": f"+{insertions} lines vs {estimated_lines} estimate ({SCOPE_CREEP_MULTIPLIER}× threshold = {threshold})",
    }]
```

Wire into `main()`:

```python
    violations.extend(check_scope_creep(
        cwd, branch, args.base_branch, task_meta["estimated_lines"], args.tier,
    ))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/unit/test_forensic_plus.py -v
```
Expected: all check1 + check2 + check3 PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/forensic-plus.py tests/unit/test_forensic_plus.py
git commit -m "feat(forensic-plus): implement Check 3 — scope creep vs estimate"
```

---

### Task 5: Check 4 — TODO/FIXME/HACK added

**Files:**
- Modify: `scripts/forensic-plus.py` (add Check 4)
- Modify: `tests/unit/test_forensic_plus.py` (Check 4 cases)

- [ ] **Step 1: Write failing tests for Check 4**

```python
def test_check4_todo_added(tmp_path):
    """+ line containing TODO → violation (SOFT in dev, HARD in prod)."""
    repo = _make_repo_with_branch(
        tmp_path,
        base_files={"src/foo.py": "x = 1\n"},
        branch_files={
            "src/foo.py": "x = 2\n# TODO: refactor later\n",
            "tests/test_foo.py": "def test_a():\n    assert 1 == 1\n    assert 2 == 2\n",
        },
        branch_name="wave-001-1/add-foo",
    )
    plan = _make_plan(repo, "add-foo", ["src/foo.py", "tests/test_foo.py"])

    rc, stdout, _ = _run(
        ["--workspace-num", "001", "--wave", "1", "--task-slug", "add-foo",
         "--base-branch", "main", "--plan", str(plan), "--tier", "development",
         "--output", "json"],
        cwd=repo,
    )
    data = json.loads(stdout)
    c4 = [v for v in data["violations"] if v["check"] == "todo_added"]
    assert len(c4) == 1
    assert c4[0]["severity"] == "SOFT"
    assert "TODO" in c4[0]["evidence"]


def test_check4_todo_removed_no_violation(tmp_path):
    """- line containing TODO (removed) → no violation."""
    repo = _make_repo_with_branch(
        tmp_path,
        base_files={"src/foo.py": "x = 1\n# TODO: old\n"},
        branch_files={
            "src/foo.py": "x = 2\n",
            "tests/test_foo.py": "def test_a():\n    assert 1 == 1\n    assert 2 == 2\n",
        },
        branch_name="wave-001-1/add-foo",
    )
    plan = _make_plan(repo, "add-foo", ["src/foo.py", "tests/test_foo.py"])

    rc, stdout, _ = _run(
        ["--workspace-num", "001", "--wave", "1", "--task-slug", "add-foo",
         "--base-branch", "main", "--plan", str(plan), "--tier", "production",
         "--output", "json"],
        cwd=repo,
    )
    data = json.loads(stdout)
    c4 = [v for v in data["violations"] if v["check"] == "todo_added"]
    assert len(c4) == 0


def test_check4_production_hard(tmp_path):
    """tier=production with +TODO → HARD."""
    repo = _make_repo_with_branch(
        tmp_path,
        base_files={"src/foo.py": "x = 1\n"},
        branch_files={
            "src/foo.py": "x = 2\n# FIXME: hack\n",
            "tests/test_foo.py": "def test_a():\n    assert 1 == 1\n    assert 2 == 2\n",
        },
        branch_name="wave-001-1/add-foo",
    )
    plan = _make_plan(repo, "add-foo", ["src/foo.py", "tests/test_foo.py"])

    rc, stdout, _ = _run(
        ["--workspace-num", "001", "--wave", "1", "--task-slug", "add-foo",
         "--base-branch", "main", "--plan", str(plan), "--tier", "production",
         "--output", "json"],
        cwd=repo,
    )
    data = json.loads(stdout)
    c4 = [v for v in data["violations"] if v["check"] == "todo_added"]
    assert c4[0]["severity"] == "HARD"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/test_forensic_plus.py -v -k check4
```
Expected: 3 FAIL.

- [ ] **Step 3: Implement Check 4**

Append to `scripts/forensic-plus.py`:

```python
TODO_FILE_GLOBS = (
    "*.py", "*.ts", "*.tsx", "*.js", "*.jsx",
    "*.go", "*.rb", "*.rs", "*.java", "*.kt", "*.cs",
)
TODO_PATTERN = re.compile(r"\b(TODO|FIXME|HACK|XXX)\b")


def check_todo_added(
    cwd: Path,
    branch: str,
    base_branch: str,
    tier: str,
) -> list[dict]:
    """Count + lines containing TODO/FIXME/HACK/XXX in code files."""
    raw = _git_run(
        cwd, "diff", f"{base_branch}...{branch}", "--", *TODO_FILE_GLOBS,
    )
    added: list[str] = []
    for ln in raw.splitlines():
        if not ln.startswith("+") or ln.startswith("+++"):
            continue
        if TODO_PATTERN.search(ln):
            added.append(ln[1:].strip())
    if not added:
        return []
    sev = _severity_for("todo_added", tier)
    sample = "; ".join(added[:3])
    suffix = f" (+{len(added) - 3} more)" if len(added) > 3 else ""
    return [{
        "check": "todo_added",
        "severity": sev,
        "evidence": f"{len(added)} TODO/FIXME/HACK added: {sample}{suffix}",
    }]
```

Wire into `main()`:

```python
    violations.extend(check_todo_added(cwd, branch, args.base_branch, args.tier))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/unit/test_forensic_plus.py -v
```
Expected: all 4 checks + skeleton tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/forensic-plus.py tests/unit/test_forensic_plus.py
git commit -m "feat(forensic-plus): implement Check 4 — TODO/FIXME/HACK added"
```

---

### Task 6: HITL skip + JSON schema property test

**Files:**
- Modify: `tests/unit/test_forensic_plus.py` (HITL + schema tests)

- [ ] **Step 1: Write failing tests for HITL skip and JSON schema**

```python
def test_hitl_task_returns_null(tmp_path):
    """Task with `Type: HITL` → forensic_passed: null, no violations checked."""
    repo = _make_repo_with_branch(
        tmp_path,
        base_files={"src/foo.py": "x = 1\n"},
        branch_files={
            "src/foo.py": "x = 2\n# TODO: would normally violate\n",
        },
        branch_name="wave-001-1/add-foo",
    )
    plan_text = (
        "## Task add-foo:\n"
        "### Files touched\n- src/foo.py\n"
        "### Type\n- HITL\n"
    )
    plan = repo / "plan.md"
    plan.write_text(plan_text, encoding="utf-8")

    rc, stdout, _ = _run(
        ["--workspace-num", "001", "--wave", "1", "--task-slug", "add-foo",
         "--base-branch", "main", "--plan", str(plan), "--tier", "production",
         "--output", "json"],
        cwd=repo,
    )
    assert rc == 0
    data = json.loads(stdout)
    assert data["forensic_passed"] is None
    assert data["max_severity"] is None
    assert data["violations"] == []
    assert data.get("skipped_reason") == "task type=HITL"


def test_json_output_always_has_required_keys(tmp_path):
    """Property-style: every successful run emits the canonical keys."""
    from hypothesis import given, strategies as st, settings

    @given(
        slug=st.from_regex(r"^[a-z][a-z0-9-]{2,20}$", fullmatch=True),
        tier=st.sampled_from(VALID_TIERS_FOR_TEST := ["experimental", "tool", "development", "production"]),
    )
    @settings(max_examples=20, deadline=None)
    def _prop(slug, tier):
        repo = _make_repo_with_branch(
            tmp_path / f"{slug}_{tier}",
            base_files={f"src/{slug}.py": "x = 1\n"},
            branch_files={
                f"src/{slug}.py": "x = 2\n",
                f"tests/test_{slug}.py": "def test_a():\n    assert 1 == 1\n    assert 2 == 2\n",
            },
            branch_name=f"wave-001-1/{slug}",
        )
        plan = _make_plan(repo, slug, [f"src/{slug}.py", f"tests/test_{slug}.py"])
        rc, stdout, _ = _run(
            ["--workspace-num", "001", "--wave", "1", "--task-slug", slug,
             "--base-branch", "main", "--plan", str(plan), "--tier", tier,
             "--output", "json"],
            cwd=repo,
        )
        if rc != 0:
            return  # crash path tested elsewhere
        data = json.loads(stdout)
        assert set(["task_slug", "violations", "forensic_passed", "max_severity"]).issubset(data.keys())
        assert data["task_slug"] == slug
        assert isinstance(data["violations"], list)
        assert data["max_severity"] in ("HARD", "SOFT", "NONE", None)

    _prop()


def test_exit_code_zero_with_violations(tmp_path):
    """Even with HARD violation, exit code is 0 (script ran successfully)."""
    repo = _make_repo_with_branch(
        tmp_path,
        base_files={"src/foo.py": "x = 1\n"},
        branch_files={
            "src/foo.py": "x = 2\n",
            "tests/test_foo.py": "def test_a():\n    assert True\n",  # violates Check 1
        },
        branch_name="wave-001-1/add-foo",
    )
    plan = _make_plan(repo, "add-foo", ["src/foo.py", "tests/test_foo.py"])

    rc, stdout, _ = _run(
        ["--workspace-num", "001", "--wave", "1", "--task-slug", "add-foo",
         "--base-branch", "main", "--plan", str(plan), "--tier", "production",
         "--output", "json"],
        cwd=repo,
    )
    assert rc == 0  # script ran successfully
    data = json.loads(stdout)
    assert data["forensic_passed"] is False
```

- [ ] **Step 2: Run tests to verify they fail (or pass — HITL already wired in Task 2)**

```bash
pytest tests/unit/test_forensic_plus.py -v -k "hitl or schema or exit_code"
```
Expected: HITL test PASS (already implemented in Task 2 main()); schema and exit_code tests PASS (skeleton + Tasks 2-5 already conform).

- [ ] **Step 3: No code changes needed — verify all tests still green**

```bash
pytest tests/unit/test_forensic_plus.py -v
```
Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/unit/test_forensic_plus.py
git commit -m "test(forensic-plus): add HITL skip + JSON schema property tests"
```

---

### Task 7: Crash path (EC1) — git missing branch + plan malformed

**Files:**
- Modify: `tests/unit/test_forensic_plus.py` (crash path tests)
- Modify: `scripts/forensic-plus.py` (verify error messages are clear)

- [ ] **Step 1: Write failing tests for crash path**

```python
def test_crash_git_missing_branch(tmp_path):
    """Branch doesn't exist → exit 1 + stderr clear."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "src").mkdir()
    (repo / "src" / "foo.py").write_text("x = 1\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "init")
    plan = _make_plan(repo, "add-foo", ["src/foo.py", "tests/test_foo.py"])

    rc, stdout, stderr = _run(
        ["--workspace-num", "001", "--wave", "1", "--task-slug", "add-foo",
         "--base-branch", "main", "--plan", str(plan), "--tier", "development",
         "--output", "json"],
        cwd=repo,
    )
    assert rc == 1
    assert "forensic-plus" in stderr
    # Should reference the failed git operation
    assert "wave-001-1/add-foo" in stderr or "fail" in stderr.lower()


def test_crash_plan_malformed(tmp_path):
    """Plan missing the task header → exit 1 with PlanParseError."""
    repo = tmp_path / "repo"
    repo.mkdir()
    plan = repo / "plan.md"
    plan.write_text("# This plan has no task headers\n", encoding="utf-8")

    rc, _, stderr = _run(
        ["--workspace-num", "001", "--wave", "1", "--task-slug", "add-foo",
         "--base-branch", "main", "--plan", str(plan), "--tier", "development",
         "--output", "json"],
        cwd=repo,
    )
    assert rc == 1
    assert "task slug not found" in stderr.lower() or "add-foo" in stderr


def test_crash_plan_missing_file(tmp_path):
    """Plan path doesn't exist → exit 1."""
    rc, _, stderr = _run(
        ["--workspace-num", "001", "--wave", "1", "--task-slug", "add-foo",
         "--base-branch", "main", "--plan", str(tmp_path / "nonexistent.md"),
         "--tier", "development", "--output", "json"],
        cwd=tmp_path,
    )
    assert rc == 1
    assert "not found" in stderr.lower() or "nonexistent" in stderr
```

- [ ] **Step 2: Run tests**

```bash
pytest tests/unit/test_forensic_plus.py -v -k crash
```
Expected: tests should already PASS based on existing error handling, OR show messages that need adjustment. Adjust error messages in `parse_plan_for_task` and `main()` if assertions fail; the implementation is mostly correct from Task 2.

- [ ] **Step 3: Verify all forensic-plus tests pass**

```bash
pytest tests/unit/test_forensic_plus.py -v
```
Expected: full suite green (≥ 18 tests).

- [ ] **Step 4: Run full test suite to confirm no regression**

```bash
bash tests/run.sh --no-bats
```
Expected: 548+/548+ baseline + new forensic-plus tests green.

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_forensic_plus.py scripts/forensic-plus.py
git commit -m "test(forensic-plus): cover crash paths (EC1) — git/plan errors"
```

---

**End of Chunk 1.** At this point `scripts/forensic-plus.py` is fully tested as a standalone unit. Subsequent chunks wire it into the wave-reviewer flow and update canonical docs.

---

## Chunks 2-6 (placeholder — to be drafted after Chunk 1 review)

The remaining work, summarized:

- **Chunk 2:** Snapshot fixtures (6 input/output JSON pairs) + `test_wave_reviewer_forensic_integration.py` (~6 tests with mocked Agent tool, covering re-spawn loop + EC2/EC3/EC5).
- **Chunk 3:** New canonical doc `references/forensic-plus-protocol.md` + edits to `references/wave-execution-protocol.md` (step 8 → 8a/8b/8c/8d), `templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl` (step 8 detailed), `references/4-block-contract-template.md` (Estimated lines section), `references/state-machine-schema.md` (error_type comment).
- **Chunk 4:** Flag rename `skip_wave_reviewer` → `skip_cross_task_audit` in `scripts/wave-planner-script.py` and `references/wave-planner-algorithm.md` with backward-compat alias. New drift detectors in `tests/unit/test_no_drift.py` (4 tests). Update `scripts/bootstrap.py` runtime_refs and `SKILL_VERSION = "3.8.0"`.
- **Chunk 5:** Version sweep across `SKILL.md`, `README.md`, `references/design-system.md`, `references/preview-loop-protocol.md`, `references/changelog.md`. New migration step `migrate_3_7_2_to_3_8_0` in `scripts/migrate-workspace.py` (bump-only) + tests in `tests/unit/test_migrate_workspace.py`.
- **Chunk 6:** Integration `tests/integration/test_forensic_plus_e2e.bats` (CI-only). Final pre-merge gate (full suite green + drift detector green + workflow per CLAUDE.md: branch → tests → ff-only merge to main).

Each subsequent chunk follows the same Task → Steps → Commit pattern with explicit code blocks and test-first ordering.
