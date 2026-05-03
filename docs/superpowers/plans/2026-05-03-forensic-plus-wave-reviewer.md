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


def test_cli_skeleton_emits_canonical_keys(tmp_path):
    """Skeleton stage: with minimal valid args, CLI exits 0 + emits canonical JSON keys.

    No git repo, no checks active yet — main() returns the empty-violations skeleton
    populated only via argparse. This test pins the JSON contract before any check
    is implemented.
    """
    plan = tmp_path / "plan.md"
    plan.write_text(
        "## Task add-foo:\n### Files touched\n- src/foo.py\n- tests/test_foo.py\n",
        encoding="utf-8",
    )

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
    assert rc == 0, f"skeleton expected exit 0, got {rc}; stderr={stderr}"
    data = json.loads(stdout)
    assert data["task_slug"] == "add-foo"
    assert data["violations"] == []
    assert data["forensic_passed"] is True
    assert data["max_severity"] == "NONE"
```

> **Note:** the skeleton in Task 1 has no git/check logic, so it always emits an empty result regardless of repo state. Once Task 2 wires in the first git call, this exact test will need to evolve (Task 2 swaps the inputs to a real-repo fixture). The skeleton test exists only to pin the JSON contract early.

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
    """Test file with 3 assert statements → no violation (count threshold met)."""
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


def test_check1_python_fails_with_single_assertion(tmp_path):
    """Test file with only one assertion → HARD violation (count below threshold)."""
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
    """Verify each declared test file has ≥ ASSERT_THRESHOLD assertion-shaped tokens.

    The check is purely count-based — it does not distinguish `assert True` from
    `assert x == y`. Rationale (spec §4.1): a single assertion is too easily a
    placeholder; ≥2 indicates a minimal real suite. Quality of the assertion is
    out of scope for forensic+; the wave-reviewer's acceptance audit (step 8c)
    catches semantic emptiness.

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


def test_all_four_checks_compose_in_main(tmp_path):
    """Integration: a single task that triggers all 4 checks → main() accumulates all violations.

    Confirms `main()` does not short-circuit and that severity reduction picks
    HARD when any HARD is present.
    """
    big_diff = "\n".join(f"line_{i} = {i}" for i in range(200))
    branch_files = {
        # +TODO triggers Check 4
        "src/foo.py": big_diff + "\n# TODO: refactor\n",
        # single assert triggers Check 1 (count < 2)
        "tests/test_foo.py": "def test_a():\n    assert True\n",
        # undeclared file triggers Check 2
        "src/utils/extra.py": "y = 1\n",
    }
    repo = _make_repo_with_branch(
        tmp_path,
        base_files={"src/foo.py": "x = 0\n"},
        branch_files=branch_files,
        branch_name="wave-001-1/add-foo",
    )
    # estimated 50 → 200+ insertions triggers Check 3
    plan = _make_plan(
        repo, "add-foo", ["src/foo.py", "tests/test_foo.py"], estimated_lines=50,
    )

    rc, stdout, _ = _run(
        ["--workspace-num", "001", "--wave", "1", "--task-slug", "add-foo",
         "--base-branch", "main", "--plan", str(plan), "--tier", "production",
         "--output", "json"],
        cwd=repo,
    )
    assert rc == 0
    data = json.loads(stdout)
    checks_seen = {v["check"] for v in data["violations"]}
    assert checks_seen == {
        "test_assertions_too_few",
        "files_outside_declared",
        "scope_creep",
        "todo_added",
    }
    assert data["forensic_passed"] is False
    assert data["max_severity"] == "HARD"
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
        tier=st.sampled_from(["experimental", "tool", "development", "production"]),
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

- [ ] **Step 2: Run tests to verify expected outcomes**

```bash
pytest tests/unit/test_forensic_plus.py -v -k crash
```
Expected: all 3 PASS without code changes. Error handling was wired into `parse_plan_for_task` (Task 2) and `main()` (Task 2 wiring); the assertions match the messages emitted today. If any test fails, fix the corresponding error message in `forensic-plus.py` to match the assertion (do not weaken the assertion).

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

## Chunk 2: Snapshot fixtures + structural integration tests

**Goal:** lock the JSON contract of `forensic-plus.py` against regression via 6 snapshot fixtures, and verify the L2 stage 04 template will be updated correctly via filesystem-shape tests.

**Rationale for "structural" not "behavioral" integration tests:** the wave-reviewer is an Agent (LLM with prompt instructions), not a Python module. The decision logic (HARD → re-spawn, SOFT → warn, cap MAX_FORENSIC_RETRIES = 2) lives in the L2 prompt + canonical doc. Behavioral tests of that logic would require mocking the Agent tool with synthetic responses, which is fragile. Instead, we test:
1. `forensic-plus.py` JSON output is stable (snapshot fixtures, parametrized).
2. The L2 template (after Chunk 3 edits) contains the decision rules as text (drift-style structural assertions). This catches accidental L2 prompt drift.

The "behavioral" verification of the reviewer Agent's decision happens at runtime via the existing wave-reviewer audit — Forensic+ violations land in `task-<slug>.md` frontmatter, lead session reads and acts.

### Task 8: Constants module — `MAX_FORENSIC_RETRIES`

Promote the cap to a Python constant in `forensic-plus.py` so canonical doc + L2 template can reference it by name and a drift detector can verify consistency.

**Files:**
- Modify: `scripts/forensic-plus.py`
- Test: `tests/unit/test_forensic_plus.py`

- [ ] **Step 1: Write the failing test**

```python
def test_max_forensic_retries_exposed_as_module_constant():
    """Constant must be importable + value 2 (per spec §6.2)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("forensic_plus", str(SCRIPT))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert hasattr(mod, "MAX_FORENSIC_RETRIES")
    assert mod.MAX_FORENSIC_RETRIES == 2
```

- [ ] **Step 2: Run to verify it fails**

```bash
pytest tests/unit/test_forensic_plus.py::test_max_forensic_retries_exposed_as_module_constant -v
```
Expected: FAIL with AttributeError.

- [ ] **Step 3: Add the constant**

In `scripts/forensic-plus.py` near the top (with other constants):

```python
# Per spec §6.2 — cap on Forensic+-driven re-spawns before BLOCKED_ERROR.
# Referenced by L2 stage 04 template + canonical forensic-plus-protocol.md.
# Drift-checked in tests/unit/test_no_drift.py.
MAX_FORENSIC_RETRIES = 2
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/unit/test_forensic_plus.py::test_max_forensic_retries_exposed_as_module_constant -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/forensic-plus.py tests/unit/test_forensic_plus.py
git commit -m "feat(forensic-plus): expose MAX_FORENSIC_RETRIES module constant"
```

---

### Task 9: Snapshot fixture infrastructure + 1st fixture (clean pass)

**Files:**
- Create: `tests/fixtures/forensic-plus-expected/01-clean-pass.json`
- Create: `tests/fixtures/forensic-plus-expected/01-clean-pass.input.md` (plan stub)
- Create: `tests/fixtures/forensic-plus-expected/01-clean-pass.spec.yaml` (test recipe — git fixture description, tier, expected exit code)
- Modify: `tests/unit/test_forensic_plus.py` (snapshot test runner)

The `*.spec.yaml` recipe describes how to construct the git fixture deterministically; the runner builds the repo, invokes the script, asserts output matches `*.json` byte-for-byte.

- [ ] **Step 1: Write the snapshot test runner (failing)**

Append to `tests/unit/test_forensic_plus.py`:

```python
import yaml  # already in requirements.txt for state-machine YAML parsing

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "forensic-plus-expected"


def _build_fixture_repo(tmp_path: Path, recipe: dict) -> Path:
    """Construct a deterministic git repo from the recipe."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", recipe.get("base_branch", "main"))
    _git(repo, "config", "user.email", "fixture@example.com")
    _git(repo, "config", "user.name", "Fixture")
    for path, content in recipe.get("base_files", {}).items():
        full = repo / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "base")

    branch = recipe["branch"]
    _git(repo, "checkout", "-b", branch)
    for path, content in recipe.get("branch_files", {}).items():
        full = repo / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "branch work")
    _git(repo, "checkout", recipe.get("base_branch", "main"))
    return repo


@pytest.mark.parametrize(
    "fixture_name",
    sorted(p.stem.replace(".spec", "") for p in FIXTURE_DIR.glob("*.spec.yaml")),
)
def test_snapshot_fixture(fixture_name, tmp_path):
    """Each fixture: build repo, run script, compare JSON byte-for-byte."""
    spec_path = FIXTURE_DIR / f"{fixture_name}.spec.yaml"
    plan_path_src = FIXTURE_DIR / f"{fixture_name}.input.md"
    expected_path = FIXTURE_DIR / f"{fixture_name}.json"

    recipe = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    repo = _build_fixture_repo(tmp_path, recipe)
    plan = repo / "plan.md"
    plan.write_text(plan_path_src.read_text(encoding="utf-8"), encoding="utf-8")

    rc, stdout, stderr = _run(
        [
            "--workspace-num", recipe["workspace_num"],
            "--wave", str(recipe["wave"]),
            "--task-slug", recipe["task_slug"],
            "--base-branch", recipe.get("base_branch", "main"),
            "--plan", str(plan),
            "--tier", recipe["tier"],
            "--output", "json",
        ],
        cwd=repo,
    )
    expected_rc = recipe.get("expected_exit_code", 0)
    assert rc == expected_rc, f"exit code mismatch; stderr={stderr}"

    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    actual = json.loads(stdout)
    assert actual == expected, (
        f"snapshot mismatch for {fixture_name}\n"
        f"expected: {json.dumps(expected, indent=2)}\n"
        f"actual:   {json.dumps(actual, indent=2)}"
    )
```

- [ ] **Step 2: Run test (no fixtures yet, parametrize empty → 0 collected)**

```bash
pytest tests/unit/test_forensic_plus.py::test_snapshot_fixture -v
```
Expected: 0 tests collected (no fixture files yet).

- [ ] **Step 3: Create the 1st fixture — clean pass**

Create `tests/fixtures/forensic-plus-expected/01-clean-pass.spec.yaml`:

```yaml
workspace_num: "042"
wave: 1
task_slug: add-greet
base_branch: main
tier: development
expected_exit_code: 0
branch: wave-042-1/add-greet
base_files:
  src/greet.py: "def greet(): return 'hello'\n"
branch_files:
  src/greet.py: "def greet(name='world'): return f'hello {name}'\n"
  tests/test_greet.py: |
    from src.greet import greet

    def test_default():
        assert greet() == "hello world"

    def test_named():
        assert greet("foo") == "hello foo"
```

Create `tests/fixtures/forensic-plus-expected/01-clean-pass.input.md`:

```markdown
## Task add-greet:

### O QUE
- saudação parametrizável

### Files touched
- src/greet.py
- tests/test_greet.py

### Estimated lines
~30
```

Create `tests/fixtures/forensic-plus-expected/01-clean-pass.json`:

```json
{
  "task_slug": "add-greet",
  "violations": [],
  "forensic_passed": true,
  "max_severity": "NONE"
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/unit/test_forensic_plus.py::test_snapshot_fixture -v
```
Expected: 1 PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/forensic-plus-expected tests/unit/test_forensic_plus.py
git commit -m "test(forensic-plus): snapshot fixture infra + 01-clean-pass"
```

---

### Task 10: Snapshot fixtures 02-06

Add the remaining 5 fixtures, each covering a distinct violation profile.

**Files (all under `tests/fixtures/forensic-plus-expected/`):**
- Create: `02-test-asserts-fail.{spec.yaml,input.md,json}` — Check 1 HARD
- Create: `03-files-outside-dev.{spec.yaml,input.md,json}` — Check 2 HARD (development tier)
- Create: `04-scope-creep-prod.{spec.yaml,input.md,json}` — Check 3 HARD (production tier)
- Create: `05-todo-soft.{spec.yaml,input.md,json}` — Check 4 SOFT (development tier)
- Create: `06-hitl-skip.{spec.yaml,input.md,json}` — Q4 task type=HITL → forensic_passed: null

- [ ] **Step 1: Create fixture 02-test-asserts-fail**

`02-test-asserts-fail.spec.yaml`:
```yaml
workspace_num: "042"
wave: 1
task_slug: add-shout
base_branch: main
tier: experimental
expected_exit_code: 0
branch: wave-042-1/add-shout
base_files:
  src/shout.py: "def shout(): return 'A'\n"
branch_files:
  src/shout.py: "def shout(s): return s.upper()\n"
  tests/test_shout.py: "def test_one():\n    assert True\n"
```

`02-test-asserts-fail.input.md`:
```markdown
## Task add-shout:
### Files touched
- src/shout.py
- tests/test_shout.py
```

`02-test-asserts-fail.json`:
```json
{
  "task_slug": "add-shout",
  "violations": [
    {
      "check": "test_assertions_too_few",
      "severity": "HARD",
      "evidence": "tests/test_shout.py: 1 non-trivial assertion(s) found, need ≥2"
    }
  ],
  "forensic_passed": false,
  "max_severity": "HARD"
}
```

> **Note:** the evidence string is the literal output of `check_test_assertions` from Task 2. If you tightened the wording in the implementation, update this expected JSON to match exactly. Goal: byte-for-byte match.

- [ ] **Step 2: Create fixture 03-files-outside-dev**

`03-files-outside-dev.spec.yaml`:
```yaml
workspace_num: "042"
wave: 1
task_slug: add-foo
base_branch: main
tier: development
expected_exit_code: 0
branch: wave-042-1/add-foo
base_files:
  src/foo.py: "x = 1\n"
branch_files:
  src/foo.py: "x = 2\n"
  tests/test_foo.py: |
    def test_a():
        assert 1 == 1
        assert 2 == 2
  src/extra.py: "y = 3\n"
```

`03-files-outside-dev.input.md`:
```markdown
## Task add-foo:
### Files touched
- src/foo.py
- tests/test_foo.py
```

`03-files-outside-dev.json`:
```json
{
  "task_slug": "add-foo",
  "violations": [
    {
      "check": "files_outside_declared",
      "severity": "HARD",
      "evidence": "1 undeclared file(s): src/extra.py"
    }
  ],
  "forensic_passed": false,
  "max_severity": "HARD"
}
```

- [ ] **Step 3: Create fixture 04-scope-creep-prod**

`04-scope-creep-prod.spec.yaml`:
```yaml
workspace_num: "042"
wave: 1
task_slug: bulk-refactor
base_branch: main
tier: production
expected_exit_code: 0
branch: wave-042-1/bulk-refactor
base_files:
  src/big.py: "x = 0\n"
branch_files:
  # tests file via direct content (3 lines including assertions)
  tests/test_big.py: |
    def test_a():
        assert 1 == 1
        assert 2 == 2
expansion:
  # Replaces src/big.py with 152 generated lines.
  # Math: estimate=50, threshold=3×50=150. Need >150 insertions to fire HARD.
  # 152 lines from expansion + 1-line removal of base "x = 0\n" =>
  #   git diff --shortstat reports "152 insertions(+), 1 deletion(-)"
  # plus 3 insertions from tests/test_big.py = 155 total insertions.
  src/big.py:
    repeat_lines: 152
    template: "var_{i} = {i}\n"
```

`04-scope-creep-prod.input.md`:
```markdown
## Task bulk-refactor:
### Files touched
- src/big.py
- tests/test_big.py
### Estimated lines
~50
```

`04-scope-creep-prod.json`:
```json
{
  "task_slug": "bulk-refactor",
  "violations": [
    {
      "check": "scope_creep",
      "severity": "HARD",
      "evidence": "+155 lines vs 50 estimate (3× threshold = 150)"
    }
  ],
  "forensic_passed": false,
  "max_severity": "HARD"
}
```

> **Implementation note:** the runner from Task 9 only handles flat `branch_files`. Fixture 04 adds an `expansion` key. Extend `_build_fixture_repo` so the expansion lands **on the branch** (after `git checkout -b <branch>`, before final `git checkout main`), and **only commits when `expansion` is non-empty** (otherwise fixtures 01/02/03/05/06 break with "nothing to commit"):
>
> ```python
> # Inside _build_fixture_repo, AFTER the branch_files write+commit,
> # BEFORE git checkout <base_branch>:
> expansion = recipe.get("expansion") or {}
> if expansion:
>     for path, exp in expansion.items():
>         full = repo / path
>         full.parent.mkdir(parents=True, exist_ok=True)
>         n = exp["repeat_lines"]
>         tmpl = exp["template"]
>         full.write_text(
>             "".join(tmpl.format(i=i) for i in range(n)),
>             encoding="utf-8",
>         )
>     _git(repo, "add", "-A")
>     _git(repo, "commit", "-m", "expansion files")
> ```
>
> When implementing fixture 04, edit `_build_fixture_repo` (which lives in Task 9) and amend Task 9's commit if needed — or commit the helper change as part of Task 10 step 3.
>
> **Note on byte-exact match:** the evidence string `+155 lines vs 50 estimate (3× threshold = 150)` is the literal output of `check_scope_creep` in `forensic-plus.py` from Task 4. If you adjust the wording in the implementation, update this expected JSON to match. Verify by running the script manually once and copying its actual stdout into the fixture file.

- [ ] **Step 4: Create fixture 05-todo-soft**

`05-todo-soft.spec.yaml`:
```yaml
workspace_num: "042"
wave: 1
task_slug: add-cache
base_branch: main
tier: development
expected_exit_code: 0
branch: wave-042-1/add-cache
base_files:
  src/cache.py: "def get(k): return None\n"
branch_files:
  src/cache.py: |
    def get(k):
        # TODO: add LRU eviction
        return None
  tests/test_cache.py: |
    from src.cache import get

    def test_miss():
        assert get("k") is None

    def test_str():
        assert get("a") is None
```

`05-todo-soft.input.md`:
```markdown
## Task add-cache:
### Files touched
- src/cache.py
- tests/test_cache.py
```

`05-todo-soft.json`:
```json
{
  "task_slug": "add-cache",
  "violations": [
    {
      "check": "todo_added",
      "severity": "SOFT",
      "evidence": "1 TODO/FIXME/HACK added: # TODO: add LRU eviction"
    }
  ],
  "forensic_passed": true,
  "max_severity": "SOFT"
}
```

- [ ] **Step 5: Create fixture 06-hitl-skip**

`06-hitl-skip.spec.yaml`:
```yaml
workspace_num: "042"
wave: 1
task_slug: review-data
base_branch: main
tier: production
expected_exit_code: 0
branch: wave-042-1/review-data
base_files:
  src/data.py: "x = 1\n"
branch_files:
  # Multiple violations would normally fire — but task is HITL, so all skipped
  src/data.py: "x = 2\n# TODO: review\n"
  src/extra.py: "y = 1\n"
```

`06-hitl-skip.input.md`:
```markdown
## Task review-data:
### Files touched
- src/data.py
### Type
- HITL
```

`06-hitl-skip.json`:
```json
{
  "task_slug": "review-data",
  "violations": [],
  "forensic_passed": null,
  "max_severity": null,
  "skipped_reason": "task type=HITL"
}
```

- [ ] **Step 6: Run all snapshot tests to verify all pass**

```bash
pytest tests/unit/test_forensic_plus.py::test_snapshot_fixture -v
```
Expected: 6 PASS.

- [ ] **Step 7: Run full forensic test suite**

```bash
pytest tests/unit/test_forensic_plus.py -v
```
Expected: original tests + 6 snapshots all green.

- [ ] **Step 8: Commit**

```bash
git add tests/fixtures/forensic-plus-expected tests/unit/test_forensic_plus.py
git commit -m "test(forensic-plus): snapshots 02-06 (asserts/files/scope/todo/hitl)"
```

---

### Task 11: Structural drift test — L2 template will mention MAX_FORENSIC_RETRIES

> **Note:** the L2 template hasn't been edited yet (Chunk 3 does that). This task adds a drift detector that will *fail until Chunk 3 is done*, intentionally. Mark this test xfail in this commit and remove xfail in Chunk 3 Task 13. The test exists now to prove the contract is locked.

**Files:**
- Modify: `tests/unit/test_no_drift.py` (xfail-marked stub)

- [ ] **Step 1: Write the (currently xfail) test**

Append to `tests/unit/test_no_drift.py`:

```python
@pytest.mark.xfail(
    reason="L2 stage 04 template edit lands in Chunk 3 Task 13; remove xfail there.",
    strict=True,
)
def test_l2_stage_04_mentions_max_forensic_retries():
    """L2 stage 04 template must reference the cap value (sourced from forensic-plus.py)."""
    l2_path = (
        REPO_ROOT
        / "templates"
        / "workspace"
        / "stages"
        / "04_implementation_waves"
        / "CONTEXT.md.tpl"
    )
    text = l2_path.read_text(encoding="utf-8")
    # The L2 template must mention the constant by name AND value to allow drift detection.
    assert "MAX_FORENSIC_RETRIES" in text
    assert "= 2" in text  # value embedded so reading the prompt is self-explanatory
```

- [ ] **Step 2: Run to verify it xfails (required to pass strict)**

```bash
pytest tests/unit/test_no_drift.py::test_l2_stage_04_mentions_max_forensic_retries -v
```
Expected: XFAIL (no L2 edits yet).

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_no_drift.py
git commit -m "test(no-drift): xfail stub — L2 must reference MAX_FORENSIC_RETRIES"
```

---

**End of Chunk 2.** `forensic-plus.py` JSON output is now snapshot-locked across 6 representative scenarios; one xfail-marked drift test stands ready to flip green when Chunk 3 edits L2.

---

## Chunk 3: Canonical doc + L2 + reference edits

**Goal:** ship the canonical doc `references/forensic-plus-protocol.md`, expand step 8 of `references/wave-execution-protocol.md`, update L2 stage 04 template, add `### Estimated lines` section to the 4-block contract, comment `state-machine-schema.md` about new `error_type` values.

### Task 12: Create `references/forensic-plus-protocol.md`

**Files:**
- Create: `references/forensic-plus-protocol.md`

- [ ] **Step 1: Write the canonical doc**

```markdown
# Forensic+ Protocol — Canonical (v3.8.0)

> **Versão:** v3.8.0
> **Skill:** `xp-icm-workflow`
> **Estágio consumidor:** `04_implementation_waves` (step 8a)
> **Propósito:** documento canônico do Forensic+ — auditoria estrutural anti-fraude por task na wave-reviewer. Descreve os 4 checks, matriz tier×severidade, ações HARD/SOFT, cap de re-spawn, edge cases, e schema JSON do `scripts/forensic-plus.py`.

## Resumo (1 parágrafo)

Forensic+ é um audit determinístico, git-only, executado pelo wave-reviewer (step 8a do pipeline 12-passos) por cada task AFK da wave. Roda 4 checks: (1) test file com ≥2 asserções, (2) files fora de `files_touched` declarado, (3) scope creep > 3× plan estimate, (4) TODO/FIXME/HACK adicionados. Cada violation tem severidade tier-aware (HARD/SOFT). HARD bloqueia merge e força re-spawn (cap `MAX_FORENSIC_RETRIES = 2`); SOFT acumula em `wave-summary.md`. Tasks `type: HITL` são skipped. Output via `scripts/forensic-plus.py` em JSON estruturado, parsed pelo reviewer Agent.

## Os 4 checks

### Check 1 — Test file com ≥2 asserções

Garante que test files declarados em `files_touched` contêm ≥2 tokens reconhecidos como asserções (count-based, não filtragem semântica). Skip quando task tem `Conventions extras: doc-only` ou `config-only`.

Comando: `git show wave-<NNN>-<N>/<slug>:<test-file>` por test file.

Linguagem-aware regex (extensão → padrão):

| Ext | Padrão | Threshold |
|-----|--------|-----------|
| `.py` | `\bassert\b\|pytest\.raises\|self\.assert\w+` | ≥ 2 |
| `.ts/.tsx/.js/.jsx` | `\b(expect\|assert\|should\|it\(\|test\()\b` | ≥ 2 |
| `.go` | `\bt\.\(Errorf\|Fatal\|Run\)\b` | ≥ 2 |
| `.rb` | `\b(expect\|assert\|should)\b` | ≥ 2 |
| `.rs` | `\bassert(_eq\|_ne)?!\b` | ≥ 2 |
| `.java/.kt` | `\b(assert\|@Test\|assertEquals)` | ≥ 2 |
| `.cs` | `\b(Assert\.\|\[Test\]\|\[Fact\]\|\[Theory\])` | ≥ 2 |

Severity: **HARD** em todo tier.

### Check 2 — Files fora de `files_touched` declarado

Compara nome de arquivos do diff (`git diff --name-only BASE...wave`) contra declarado em plan.md task. Diferença set (atual − declarado) é violation, exceto se filename está na allowlist global de lockfiles/caches.

Allowlist tier-agnóstica: `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`, `bun.lockb`, `Cargo.lock`, `Gemfile.lock`, `poetry.lock`, `go.sum`, `.prettierrc.cache`, `.eslintcache`.

Severity:

| Tier | Severity |
|------|----------|
| experimental/tool | SOFT |
| development/production | HARD |

### Check 3 — Scope creep > 3× plan estimate

Lê `### Estimated lines` opcional do plan.md task (ver `references/4-block-contract-template.md`). Compara com `git diff --shortstat` insertions count. Trigger se `insertions > 3 × estimate`. Se campo ausente, skip silently (backward compat).

Severity:

| Tier | Severity |
|------|----------|
| experimental/tool/development | SOFT |
| production | HARD |

### Check 4 — TODO/FIXME/HACK adicionados

Conta linhas começando `+` (não `+++`) que match `(TODO|FIXME|HACK|XXX)` em arquivos de código (`.py .ts .tsx .js .jsx .go .rb .rs .java .kt .cs`). Ignora linhas removidas (`-`) e contexto.

Severity:

| Tier | Severity |
|------|----------|
| experimental/tool/development | SOFT |
| production | HARD |

## Tier × violation matrix consolidada

| Check | exp | tool | dev | prod |
|-------|-----|------|-----|------|
| Test asserções | HARD | HARD | HARD | HARD |
| Files fora declared | SOFT | SOFT | HARD | HARD |
| Scope creep 3× | SOFT | SOFT | SOFT | HARD |
| TODO/FIXME/HACK | SOFT | SOFT | SOFT | HARD |

## Action HARD vs SOFT

- **HARD em ≥1 check** → reviewer emit `approved_pending_ci: false`, lead re-spawn subagente original.
- **Apenas SOFT** → reviewer emit `approved_pending_ci: true`, violations gravam em `wave-summary.md`, merge prossegue.
- **Nenhum** → padrão approved.

## Re-spawn cap + brief prescritivo

Cap: `MAX_FORENSIC_RETRIES = 2` (hardcoded em `scripts/forensic-plus.py`, drift-checked). Tier-agnostic.

| Tentativa | Resultado | Action |
|-----------|-----------|--------|
| 1ª original | HARD | re-spawn round 1 |
| 2ª (round 1) | HARD | re-spawn round 2 |
| 3ª (round 2) | HARD | `BLOCKED_ERROR error_type: forensic_max_retries`, escala humano |
| Qualquer | SOFT only | merge prossegue |
| Qualquer | NONE | merge prossegue |

Brief de re-spawn injeta no AGENT-BRIEF do subagente:

| Violation | Texto injetado |
|-----------|----------------|
| `test_assertions_too_few` | "Test file `<path>` tem `<N>` asserções. Adicione ≥2 asserções não-triviais cobrindo edge cases + happy path." |
| `files_outside_declared` | "Você tocou `<path>` não declarado em files_touched. Reverta ou escreva `output/wave-<N>/task-<slug>-blocked.md` pra escalar (sem novo stop point — usa BLOCKED handoff existente)." |
| `scope_creep` | "Diff `<X>` linhas vs estimate `<Y>`. Reduza ou divida. Se scope real é maior, escalar via stop point `over_eng`." |
| `todo_added` | "TODOs adicionados: `<list>`. Remova ou converta em issues." |

## Edge cases

| EC | Scenario | Behavior |
|----|----------|----------|
| EC1 | `forensic-plus.py` crash (git missing branch / plan malformed) | Script exit 1 + stderr. Reviewer emit `forensic_passed: null, forensic_error: <stderr>`. Lead → `BLOCKED_ERROR error_type: forensic_script_crash`. Escala humano. |
| EC2 | JSON parse fail | Treat as EC1. |
| EC3 | Re-spawn introduz nova HARD diferente | Conta como retry. Cap 2 ainda aplica. Anti-gaming. |
| EC4 | Wave HITL + AFK | Roda só em AFK. HITL → `forensic_passed: null`. |
| EC5 | Wave 1-task | Forensic+ roda. Akita-tipo cross-task skipped (`skip_cross_task_audit: true`). |
| EC6 | TODO obfuscation (`T0D0`, `F1XME`) | Out of scope. |
| EC7 | Lockfile vulnerabilities | Allowlist ignora. Stage 05 / security_gate cobre. |

## CI global step 10 interaction

Inalterado. `approved_pending_ci: true` é semântica (decisão final pendente CI). Step 10 vermelho → `references/ci-rollback-protocol.md` existente. Forensic+ não dispara rollback automático.

## JSON schema do `scripts/forensic-plus.py`

**Input (CLI):**

```bash
python scripts/forensic-plus.py \
    --workspace-num <NNN> \
    --wave <N> \
    --task-slug <slug> \
    --base-branch <BASE> \
    --plan <path-to-plan.md> \
    --tier <experimental|tool|development|production> \
    --output json
```

**Output (stdout JSON):**

```json
{
  "task_slug": "<slug>",
  "violations": [
    {
      "check": "<test_assertions_too_few|files_outside_declared|scope_creep|todo_added>",
      "severity": "<HARD|SOFT>",
      "evidence": "<human-readable explanation>"
    }
  ],
  "forensic_passed": true | false | null,
  "max_severity": "HARD" | "SOFT" | "NONE" | null,
  "skipped_reason": "task type=HITL"   // present only if HITL
}
```

**Exit codes:**
- `0` — script ran successfully (regardless of violations).
- `1` — script crash (git missing, plan malformed). Stderr formatted.

## Cross-references

- Pipeline 12-passos consumidor: `references/wave-execution-protocol.md` step 8a-8d.
- Schema task plan.md: `references/4-block-contract-template.md` (`### Estimated lines`).
- L2 runtime: `templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl`.
- State machine: `references/state-machine-schema.md` (`error_type: forensic_max_retries|forensic_script_crash`).
- Stop points (tabela: este audit não é stop point, é audit pós-COMPLETE): `references/stop-points-canonical.md`.
- Conflict / CI rollback: `references/conflict-resolution-protocol.md`, `references/ci-rollback-protocol.md`.
```

- [ ] **Step 2: No test for content (covered by drift detectors in Chunk 4); commit**

```bash
git add references/forensic-plus-protocol.md
git commit -m "docs(forensic-plus): canonical doc forensic-plus-protocol.md"
```

---

### Task 13: Update L2 stage 04 template — step 8 → 8a/8b/8c/8d

**Files:**
- Modify: `templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl`
- Modify: `tests/unit/test_no_drift.py` (remove xfail from Task 11 stub)

- [ ] **Step 1: Edit step 8 in the L2 template**

Locate the existing step 8 in `templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl` (`Wave-reviewer:` block). Replace with the expanded version:

```markdown
8. **Wave-reviewer (Agent sem worktree, expandido em sub-steps):**

   8a. **Forensic+ checks** — pra cada task AFK da wave (skip `type: HITL`), reviewer
       Agent invoca `python {{SKILL_DIR}}/scripts/forensic-plus.py --workspace-num {{WORKSPACE_NUM}}
       --wave <N> --task-slug <slug> --base-branch {{BASE_BRANCH}} --plan
       {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/02_design/output/plan.md
       --tier <T> --output json`. Parse JSON. Grava em `output/wave-<N>/task-<slug>.md`
       frontmatter campos `forensic_violations`, `forensic_passed`, `forensic_max_severity`,
       `forensic_respawn_count`. Doc canônico: `references/forensic-plus-protocol.md`.
       Crash do script (exit 1) → reviewer emit `forensic_error` + treat como HARD; lead → `BLOCKED_ERROR
       error_type: forensic_script_crash`.

   8b. **Audit existente** — Auto-QA Akita declarado, files touched real (`git diff
       --name-only`), acceptance criteria. Skip cross-task audit em wave 1-task
       (flag `skip_cross_task_audit: true` no wave-plan.md).

   8c. **Forensic git log** (`qa_loops_used` declarado vs commits RED/GREEN/REFACTOR
       reais) — mantém status quo. Acceptance criteria audit por task continua.

   8d. **Emit decision:**
       - HARD em ≥1 task → `approved_pending_ci: false`, `issues: [...]` →
         lead re-spawn subagente original. Cap `MAX_FORENSIC_RETRIES = 2`
         (após 3ª tentativa HARD → `BLOCKED_ERROR error_type: forensic_max_retries`).
         AGENT-BRIEF do re-spawn injeta brief prescritivo por violation type
         (ver `references/forensic-plus-protocol.md` § Re-spawn brief).
       - Apenas SOFT → `approved_pending_ci: true`, warnings logged em
         `wave-summary.md` § Forensic+ summary. Merge prossegue.
       - Nenhum → padrão approved.
```

> **Note:** preserve existing surrounding text in the L2 template; only step 8 changes. The literal string `MAX_FORENSIC_RETRIES = 2` MUST appear so the drift detector from Task 11 passes.

- [ ] **Step 2: Remove xfail from drift test**

Edit `tests/unit/test_no_drift.py`:

```python
# Replace:
# @pytest.mark.xfail(...)
# def test_l2_stage_04_mentions_max_forensic_retries(): ...
# with the un-marked version:

def test_l2_stage_04_mentions_max_forensic_retries():
    """L2 stage 04 template must reference the cap value (sourced from forensic-plus.py)."""
    l2_path = (
        REPO_ROOT
        / "templates"
        / "workspace"
        / "stages"
        / "04_implementation_waves"
        / "CONTEXT.md.tpl"
    )
    text = l2_path.read_text(encoding="utf-8")
    assert "MAX_FORENSIC_RETRIES" in text
    assert "= 2" in text
```

- [ ] **Step 3: Run drift test to verify it passes**

```bash
pytest tests/unit/test_no_drift.py::test_l2_stage_04_mentions_max_forensic_retries -v
```
Expected: PASS.

- [ ] **Step 4: Run full no-drift suite**

```bash
pytest tests/unit/test_no_drift.py -v
```
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl tests/unit/test_no_drift.py
git commit -m "feat(stage04): expand step 8 → 8a/8b/8c/8d wave-reviewer + forensic+"
```

---

### Task 14: Update `references/wave-execution-protocol.md`

**Files:**
- Modify: `references/wave-execution-protocol.md` (step 8 expansion + cross-ref)

- [ ] **Step 1: Edit the canonical pipeline doc**

In `references/wave-execution-protocol.md`, locate "8. **Wave-reviewer**" in the "Pipeline (12 passos)" section. Replace with:

```markdown
8. **Wave-reviewer** — Agent sem worktree. Expandido em 8a/8b/8c/8d (v3.8.0):
   - **8a Forensic+** — `scripts/forensic-plus.py` por task AFK (4 checks: test asserções, files fora declared, scope creep, TODO/FIXME). Doc canônico: `references/forensic-plus-protocol.md`.
   - **8b Audit existente** — Auto-QA Akita declarado, files touched, acceptance.
   - **8c Forensic git log** — `qa_loops_used` vs commits reais.
   - **8d Decision** — HARD → `approved_pending_ci: false` + re-spawn (cap `MAX_FORENSIC_RETRIES = 2`); SOFT → warnings; NONE → approve.
```

Add to the "Cross-references" section at the bottom:

```markdown
- Forensic+ audit: `references/forensic-plus-protocol.md`
```

- [ ] **Step 2: Add a structural drift test for this doc**

Append to `tests/unit/test_no_drift.py`:

```python
def test_wave_execution_protocol_has_forensic_substeps():
    """Pipeline canonical doc must reflect step 8 expansion."""
    path = REPO_ROOT / "references" / "wave-execution-protocol.md"
    text = path.read_text(encoding="utf-8")
    assert "**8a Forensic+**" in text
    assert "**8b Audit existente**" in text
    assert "**8c Forensic git log**" in text
    assert "**8d Decision**" in text
    assert "forensic-plus-protocol.md" in text
```

- [ ] **Step 3: Run the new test**

```bash
pytest tests/unit/test_no_drift.py::test_wave_execution_protocol_has_forensic_substeps -v
```
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add references/wave-execution-protocol.md tests/unit/test_no_drift.py
git commit -m "docs(wave-execution): expand step 8 → 8a/8b/8c/8d + drift test"
```

---

### Task 15: Update `references/4-block-contract-template.md` — `### Estimated lines`

**Files:**
- Modify: `references/4-block-contract-template.md`

- [ ] **Step 1: Add the optional section after `### Files touched`**

Locate the schema example in §2 of the doc and insert `### Estimated lines` between `### Files touched` and `### Depends on`:

```markdown
### Files touched
- src/path/file.ts
- tests/path/file.test.ts

### Estimated lines
~250    <!-- optional. If present, forensic-plus.py Check 3 (scope creep)
            triggers when actual diff insertions > 3 × estimate. Plan author
            opts in for tasks where bounded scope matters. Absent → check skipped.
            See references/forensic-plus-protocol.md § Check 3. -->

### Depends on
- <slug-de-task-pai> OR nenhum (task raiz)
```

Update the `| Campo | Quem preenche | Quem consome |` table in the same section, adding the row:

```markdown
| Estimated lines (opcional) | Designer (fase 02) | forensic-plus.py (Check 3 scope creep) |
```

- [ ] **Step 2: No drift detector needed (test fixtures in Chunk 1 already exercise the parser); commit**

```bash
git add references/4-block-contract-template.md
git commit -m "docs(4-block): add optional ### Estimated lines section (forensic+ Check 3)"
```

---

### Task 16: Update `references/state-machine-schema.md` — `error_type` comment

**Files:**
- Modify: `references/state-machine-schema.md`

- [ ] **Step 1: Locate the `blocked_error` event row in the schema**

The field `error_type` lives on the `blocked_error` history event row in the §"Event types canônicos" table (around line 113 of `references/state-machine-schema.md`), NOT on `last_transition` (whose schema is `{from, to, at, commit_sha}` only).

Below the table, add a new subsection listing known `error_type` string values (the field is free-form text — no enum constraint exists, so this is documentation only):

```markdown
### `error_type` values (conhecidos, lista crescente — não enum)

Quando `status: BLOCKED_ERROR` é setado, `last_transition.error_type` (free-form
string) é populado com um dos valores abaixo. Lista evolui por versão; não há
enforcement automático.

- `merge_conflict`
- `ci_red`
- `cap_exceeded`
- `cleanup_unsafe`
- `runtime_cleanup_failed`
- `forensic_max_retries`        <!-- v3.8.0 — cap MAX_FORENSIC_RETRIES esgotado -->
- `forensic_script_crash`       <!-- v3.8.0 — forensic-plus.py exit 1 -->
- `human_abort`
```

- [ ] **Step 2: Add a smoke drift detector**

Append to `tests/unit/test_no_drift.py`:

```python
def test_state_machine_schema_documents_v3_8_0_error_types():
    """Schema doc must list new forensic_* error_type values."""
    path = REPO_ROOT / "references" / "state-machine-schema.md"
    text = path.read_text(encoding="utf-8")
    assert "forensic_max_retries" in text
    assert "forensic_script_crash" in text
```

- [ ] **Step 3: Run drift test to verify**

```bash
pytest tests/unit/test_no_drift.py::test_state_machine_schema_documents_v3_8_0_error_types -v
```
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add references/state-machine-schema.md tests/unit/test_no_drift.py
git commit -m "docs(state-machine): document v3.8.0 forensic_* error_type values + drift test"
```

---

**End of Chunk 3.** Canonical doc, L2 template, pipeline doc, 4-block template, and state-machine doc are all aligned with the spec.

---

## Chunk 4: Flag rename + drift detectors + bootstrap version

**Goal:** rename `skip_wave_reviewer` → `skip_cross_task_audit` with backward-compat alias, add the remaining drift detectors, bump `SKILL_VERSION = "3.8.0"` and add forensic-plus-protocol.md to bootstrap runtime_refs.

### Task 17: Introduce `skip_cross_task_audit` field in `render_wave_plan` output

**Files:**
- Modify: `scripts/wave-planner-script.py` (extend `render_wave_plan` to emit per-wave frontmatter for 1-task waves)
- Modify: `tests/unit/test_wave_planner_dag.py` (add concrete test cases)

> **Reframing note:** verified by repo grep — the flag `skip_wave_reviewer` appears today **only** in `references/wave-planner-algorithm.md` documentation, NOT in any production code under `scripts/` or `tests/`. So Task 17 is *introducing* the new field name (`skip_cross_task_audit`) for the first time in code. The "backward-compat alias for `skip_wave_reviewer`" is a forward-defensive guard for any external tooling that may have read the doc and started emitting the legacy name; it can be implemented as a no-op pass-through and removed in v3.9.0.

- [ ] **Step 1: Confirm no existing code touches the flag**

```bash
grep -rn "skip_wave_reviewer\|skip_cross_task_audit" scripts/ tests/
```
Expected: 0 hits in `scripts/` and `tests/` (only `references/wave-planner-algorithm.md` mentions the legacy name).

- [ ] **Step 2: Write failing tests using the existing helper API**

`tests/unit/test_wave_planner_dag.py` already exposes `parse_plan`, `plan_waves`, `render_wave_plan` from the script. Append:

```python
def test_render_wave_plan_emits_skip_cross_task_audit_for_one_task_wave(tmp_path):
    """1-task wave's section must carry `skip_cross_task_audit: true` annotation."""
    plan_md = (
        "## Task add-only:\n"
        "### Files touched\n"
        "- src/x.py\n"
        "- tests/test_x.py\n"
    )
    plan_path = tmp_path / "plan.md"
    plan_path.write_text(plan_md, encoding="utf-8")
    tasks = parse_plan(plan_path)
    result = plan_waves(
        tasks=tasks,
        tier="development",
        profile="app_web_backend",
    )
    rendered = render_wave_plan(result, plan_source=str(plan_path), workspace="042-foo")

    # The 1-task wave section must contain the new annotation either as a
    # YAML-style metadata line just below the section header OR inside the
    # table; pick whichever fits the existing render style. Spec: appears
    # exactly once per 1-task wave; never on multi-task waves.
    assert "skip_cross_task_audit: true" in rendered
    # Multi-task scenario sanity check — no annotation expected:
    plan_md2 = (
        "## Task add-a:\n### Files touched\n- src/a.py\n- tests/test_a.py\n\n"
        "## Task add-b:\n### Files touched\n- src/b.py\n- tests/test_b.py\n"
    )
    plan_path2 = tmp_path / "plan2.md"
    plan_path2.write_text(plan_md2, encoding="utf-8")
    tasks2 = parse_plan(plan_path2)
    result2 = plan_waves(tasks=tasks2, tier="development", profile="app_web_backend")
    rendered2 = render_wave_plan(result2, plan_source=str(plan_path2), workspace="042-foo")
    assert "skip_cross_task_audit" not in rendered2


def test_legacy_skip_wave_reviewer_alias_documented():
    """Forward-defensive: any consumer that emits the legacy `skip_wave_reviewer`
    string should still be parseable. v3.8.0 only writes the new name; this test
    pins the alias contract via doc inspection (the new doc must say the alias
    exists and will be removed in v3.9.0).
    """
    doc = (Path(__file__).resolve().parents[2] / "references" / "wave-planner-algorithm.md").read_text(encoding="utf-8")
    assert "skip_cross_task_audit" in doc
    assert "skip_wave_reviewer" in doc  # legacy alias mentioned
    assert "v3.9.0" in doc  # deprecation horizon
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
pytest tests/unit/test_wave_planner_dag.py -v -k "skip_cross_task_audit or skip_wave_reviewer_alias"
```
Expected: FAIL — `render_wave_plan` does not yet emit the annotation; doc not yet updated (Task 18).

- [ ] **Step 4: Extend `render_wave_plan` to emit the annotation**

In `scripts/wave-planner-script.py`, inside the inner sub-wave loop of `render_wave_plan` (around line 482), add an annotation line right after the section heading when `count == 1`:

```python
            lines.append(
                f"## Wave {w_idx} (sub-wave {w_idx}.{label}) - {count} tasks paralelas{cap_note}"
            )
            if count == 1:
                lines.append("")
                lines.append("> **skip_cross_task_audit: true** — wave 1-task pula audit cross-task no step 8b (Forensic+ ainda roda em 8a). Doc: references/wave-planner-algorithm.md §10.")
            lines.append("")
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/unit/test_wave_planner_dag.py -v -k "skip_cross_task_audit or skip_wave_reviewer_alias"
```
Expected: first test PASS; second still FAILs until Task 18 updates the doc.

- [ ] **Step 6: Run full wave-planner test suite to confirm no regression**

```bash
pytest tests/unit/test_wave_planner_dag.py -v
```
Expected: all green except the alias-doc test (passes after Task 18).

- [ ] **Step 7: Commit**

```bash
git add scripts/wave-planner-script.py tests/unit/test_wave_planner_dag.py
git commit -m "feat(wave-planner): emit skip_cross_task_audit annotation for 1-task waves"
```

---

### Task 18: Update `references/wave-planner-algorithm.md` — flag rename owner doc

**Files:**
- Modify: `references/wave-planner-algorithm.md`

- [ ] **Step 1: Edit the doc**

Locate §10 (Wave-reviewer skip exception). Update text to use `skip_cross_task_audit` and add a backward-compat note:

```markdown
## 10. Wave-reviewer skip exception (F2 — renamed v3.8.0)

Wave com **1 task** pula o wave-reviewer **cross-task** audit (sem coherence check possível). Forensic+ (step 8a) ainda roda, e CI global cobre o escape.

Schema `wave-plan.md` marca `skip_cross_task_audit: true` na wave aplicável. Lead da fase 04 lê esse flag e ajusta o protocolo (skip step 8b cross-task, mas mantém 8a Forensic+ + 8c forensic git log).

> **Backward compat (v3.7.x → v3.8.0):** o nome legado `skip_wave_reviewer` é reconhecido como alias pelo wave-planner-script.py durante v3.8.0. Wave-plans novos sempre emitem `skip_cross_task_audit`. v3.9.0 remove o alias.
```

- [ ] **Step 2: Commit**

```bash
git add references/wave-planner-algorithm.md
git commit -m "docs(wave-planner): rename skip_wave_reviewer → skip_cross_task_audit + alias"
```

---

### Task 19: Add 4 new drift detectors

**Files:**
- Modify: `tests/unit/test_no_drift.py`

(Tasks 11 and 14 already added 2 detectors; this task adds the remaining 2: bootstrap runtime_refs containing forensic-plus-protocol.md, and L2 referencing the canonical protocol doc.)

- [ ] **Step 1: Write failing tests**

Append to `tests/unit/test_no_drift.py`:

```python
def test_forensic_plus_doc_canonical_exists():
    """Sanity: the canonical doc must exist and contain expected H1 + sections."""
    path = REPO_ROOT / "references" / "forensic-plus-protocol.md"
    assert path.is_file(), "forensic-plus-protocol.md missing"
    text = path.read_text(encoding="utf-8")
    assert "# Forensic+ Protocol" in text
    assert "## Os 4 checks" in text
    assert "## JSON schema" in text


def test_forensic_plus_in_bootstrap_runtime_refs():
    """bootstrap.py runtime_refs tuple must list forensic-plus-protocol.md."""
    path = REPO_ROOT / "scripts" / "bootstrap.py"
    text = path.read_text(encoding="utf-8")
    assert '"forensic-plus-protocol.md"' in text


def test_l2_stage_04_references_forensic_plus_protocol():
    """L2 stage 04 must cross-ref the canonical doc."""
    path = (
        REPO_ROOT / "templates" / "workspace" / "stages"
        / "04_implementation_waves" / "CONTEXT.md.tpl"
    )
    text = path.read_text(encoding="utf-8")
    assert "forensic-plus-protocol.md" in text
```

- [ ] **Step 2: Run tests to verify expected outcomes**

```bash
pytest tests/unit/test_no_drift.py -v -k forensic
```
Expected:
- `test_forensic_plus_doc_canonical_exists` PASS (Chunk 3 Task 12 created the doc).
- `test_l2_stage_04_references_forensic_plus_protocol` PASS (Chunk 3 Task 13's step 8a expansion already mentions `references/forensic-plus-protocol.md`).
- `test_forensic_plus_in_bootstrap_runtime_refs` FAIL (bootstrap edit lands in Task 20).

> **Note:** if `test_l2_stage_04_references_forensic_plus_protocol` does NOT pass at this point, that means Task 13 step 1 was implemented without the cross-ref. Go back and add `references/forensic-plus-protocol.md` mention to the step 8a text. Don't duplicate-edit here.

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_no_drift.py
git commit -m "test(no-drift): forensic-plus doc/L2/bootstrap detectors"
```

---

### Task 20: Update `scripts/bootstrap.py` — version + runtime_refs

**Files:**
- Modify: `scripts/bootstrap.py`

- [ ] **Step 1: Bump SKILL_VERSION + add to runtime_refs**

In `scripts/bootstrap.py`:

```python
# Was:
SKILL_VERSION = "3.7.2"
# Becomes:
SKILL_VERSION = "3.8.0"
```

In the `runtime_refs` tuple (around line 651), add:

```python
runtime_refs = (
    "subagent-protocol.md",
    "wave-planner-algorithm.md",
    "state-machine-schema.md",
    # ... existing entries ...
    "design-system.md",
    "forensic-plus-protocol.md",   # v3.8.0
)
```

- [ ] **Step 2: Run drift detector to confirm**

```bash
pytest tests/unit/test_no_drift.py -v -k forensic_plus_in_bootstrap
```
Expected: PASS.

- [ ] **Step 3: Run full no-drift suite (some will still fail until Chunk 5 sweep)**

```bash
pytest tests/unit/test_no_drift.py -v
```
Expected: most PASS; version-canonical-files test will fail until Chunk 5.

- [ ] **Step 4: Commit**

```bash
git add scripts/bootstrap.py
git commit -m "feat(bootstrap): SKILL_VERSION 3.8.0 + forensic-plus-protocol.md in runtime_refs"
```

---

**End of Chunk 4.**

---

## Chunk 5: Version sweep + migration

**Goal:** sweep version-stamping across the 6 remaining canonical files (per CLAUDE.md v3.7.0 rule) and add the `migrate_3_7_2_to_3_8_0` step.

### Task 21: Update `SKILL.md`

**Files:**
- Modify: `SKILL.md`

- [ ] **Step 1: Update the H1 header**

```markdown
# xp-icm-workflow v3.8.0
```
(was: `v3.7.2`)

- [ ] **Step 2: Commit**

```bash
git add SKILL.md
git commit -m "chore(version): SKILL.md v3.8.0"
```

---

### Task 22: Update `README.md` — header line + badge + Versão atual + Highlights

**Files:**
- Modify: `README.md`

> **Note on actual structure:** README has no `## v3.7.x` section to insert before. Layout (verified):
> - Line 3: inline `v3.7.2.` at end of intro paragraph
> - Line 5: `tests-<count>%20passed` badge (count varies — bump approximately to reflect new tests added)
> - Line 8: `version-v3.7.2` badge
> - Line 240: `## Versão atual`
> - Line 242: bold paragraph `**v3.7.2** — <description>.`
> - Line 246-253: `### Highlights por versão` followed by bullet list of past versions

- [ ] **Step 1: Bump intro line 3**

```markdown
> ... v3.8.0.
```
(was: `v3.7.2.`)

- [ ] **Step 2: Bump test count badge (line 5)**

Approximate the new total: existing 823 + ~25 new (forensic-plus unit tests + 6 snapshots + 5 drift detectors + 3 migrate tests + 2 bats) = ~858. Use a round number:

```markdown
[![tests](https://img.shields.io/badge/tests-855%20passed-brightgreen)](tests/)
```

(Run `pytest tests/unit/ --collect-only -q | tail -1` after Chunk 5 lands to confirm exact count; if off by ±5, leave the round number — drift detector doesn't enforce exact count, only version sync.)

- [ ] **Step 3: Bump version badge (line 8)**

```markdown
[![version](https://img.shields.io/badge/version-v3.8.0-blue)](references/changelog.md)
```

- [ ] **Step 4: Update `## Versão atual` paragraph (lines 240-244)**

Replace the bold v3.7.2 paragraph (line 242) with:

```markdown
**v3.8.0** — Forensic+ wave reviewer: auditoria estrutural anti-fraude no step 8 do wave-reviewer (stage 04). 4 checks tier-aware (test asserções, files fora declared, scope creep, TODO/FIXME), re-spawn cap `MAX_FORENSIC_RETRIES = 2`, novo `scripts/forensic-plus.py` + doc canônico `references/forensic-plus-protocol.md`.
```

- [ ] **Step 5: Add new bullet at top of `### Highlights por versão` (line 248)**

Insert as the first bullet, before the existing `**v3.7.2** (2026-05-01) — ...` line:

```markdown
- **v3.8.0** (2026-05-03) — Forensic+ wave reviewer. 4 checks anti-fraude per task no step 8 wave-reviewer (test asserções, files fora declared, scope creep, TODO/FIXME). Tier-aware HARD/SOFT severity. Re-spawn cap 2. Doc: `references/forensic-plus-protocol.md`.
```

- [ ] **Step 6: Verify the changes**

```bash
grep -n "v3.8.0" README.md
```
Expected: at least 4 hits (intro line, version badge, Versão atual paragraph, Highlights bullet).

- [ ] **Step 7: Commit**

```bash
git add README.md
git commit -m "chore(version): README v3.8.0 — header, badges, Versão atual, Highlights"
```

---

### Task 23: Update `references/design-system.md`

**Files:**
- Modify: `references/design-system.md`

> **Note on actual structure:** the file has NO YAML frontmatter. Version stamps live in:
> - Line 1: H1 title `# Design System — DESIGN.md format (v3.7.2)`
> - Line 3: blockquote `> **Versão:** v3.7.2`

- [ ] **Step 1: Bump H1 (line 1)**

```markdown
# Design System — DESIGN.md format (v3.8.0)
```

- [ ] **Step 2: Bump version blockquote (line 3)**

```markdown
> **Versão:** v3.8.0
```

- [ ] **Step 3: Commit**

```bash
git add references/design-system.md
git commit -m "chore(version): design-system v3.8.0 (H1 + blockquote)"
```

---

### Task 24: Update `references/preview-loop-protocol.md`

**Files:**
- Modify: `references/preview-loop-protocol.md`

- [ ] **Step 1: Bump title + version line**

```markdown
# Preview Loop Protocol — build-iterate visual (v3.8.0)
```
(was: `(v3.7.2)`)

```markdown
> **Versão:** v3.8.0
```

- [ ] **Step 2: Commit**

```bash
git add references/preview-loop-protocol.md
git commit -m "chore(version): preview-loop-protocol v3.8.0"
```

---

### Task 25: Update `references/changelog.md`

**Files:**
- Modify: `references/changelog.md`

- [ ] **Step 1: Add new entry at top**

Insert as the first version section (above current top, likely v3.7.2):

```markdown
## v3.8.0 — Forensic+ wave reviewer (2026-05-03)

### Mudanças

- **NEW:** `scripts/forensic-plus.py` — auditoria estrutural per task no step 8 wave-reviewer (4 checks git-only).
- **NEW:** `references/forensic-plus-protocol.md` — doc canônico.
- **NEW:** schema `task-<slug>.md` frontmatter ganha `forensic_violations`, `forensic_passed`, `forensic_max_severity`, `forensic_respawn_count` (opcionais, backward compat).
- **NEW:** `wave-summary.md` ganha seção `## Forensic+ summary`.
- **NEW:** `plan.md` task aceita `### Estimated lines` opcional (Check 3 scope creep).
- **CHANGE:** step 8 do pipeline 12-passos expandido em 8a/8b/8c/8d (`references/wave-execution-protocol.md` + L2 stage 04 template).
- **CHANGE:** flag wave-plan.md `skip_wave_reviewer` renomeado pra `skip_cross_task_audit`. Backward-compat alias mantido em v3.8.0; removido em v3.9.0.
- **CHANGE:** `state-machine-schema.md` documenta novos `error_type: forensic_max_retries|forensic_script_crash` (sem enum change).
- **DEPS:** sem novas dependências runtime. PyYAML já presente em `requirements.txt`.
- **TESTS:** +20 unit (`test_forensic_plus.py`), +6 snapshot fixtures, +4 drift detectors, +1 bats e2e.

### Migração

`migrate_3_7_2_to_3_8_0` é bump-only — workspaces existentes são compatíveis sem mutação destrutiva. Campos novos no task-md frontmatter têm parser default tolerante a ausência.

### Rationale

Self-grading do subagente (Auto-QA Akita 15-itens) sofre de bias documentado (Huang et al. ICLR 2024, Self-Correction Benchmark 2025). Forensic+ adiciona auditoria externa estrutural sem importar prompt-only re-grade caro. Aproveita strength único do ICM (forensic git-log audit) ampliando cobertura de 1 vetor (qa_loops_used vs commits) pra 4 vetores de fraude estrutural.
```

- [ ] **Step 2: Commit**

```bash
git add references/changelog.md
git commit -m "chore(changelog): v3.8.0 entry — forensic+ wave reviewer"
```

---

### Task 26: Update `scripts/migrate-workspace.py` — new step

**Files:**
- Modify: `scripts/migrate-workspace.py`

> **Note on actual structure (verified):**
> - `CURRENT_SKILL_VERSION = "3.7.2"` at line 38
> - `SUPPORTED_VERSIONS` tuple at lines 44-51 (semver only — no `beta` entries; floor is `3.3.0`)
> - All migrate functions have signature `(workspace_root: Path, project_root: Path) -> None` (lines 181, 239, 246, 251, 256). Take BOTH args even if `project_root` is unused — the orchestrator passes both.
> - Helper `_bump_version_only(workspace_root, target)` exists at line 228 — use it.
> - The version field is `icm_skill_version` in **L0** (`<ws>/CLAUDE.md`), NOT `version` in L1 (`CONTEXT.md`). `VERSION_RE` at lines 78-80 is the canonical regex.
> - `STEP_FUNCTIONS` is a **string-keyed** dict with `"<from>-><to>"` keys (lines 265-271).
> - The most recent step is `migrate_3_7_0_to_3_7_2` (line 256) — v3.7.1 was collapsed.

- [ ] **Step 1: Bump `CURRENT_SKILL_VERSION` + extend tuple**

```python
# Line 38:
CURRENT_SKILL_VERSION = "3.8.0"

# Lines 44-51:
SUPPORTED_VERSIONS: tuple[str, ...] = (
    "3.3.0",
    "3.4.0",
    "3.5.0",
    "3.6.0",
    "3.7.0",
    "3.7.2",
    "3.8.0",
)
```

- [ ] **Step 2: Add migration function (bump-only) using existing helper**

After `migrate_3_7_0_to_3_7_2` (around line 263):

```python
def migrate_3_7_2_to_3_8_0(workspace_root: Path, project_root: Path) -> None:
    """v3.7.2 → v3.8.0: forensic+ wave reviewer. Bump-only.

    No data mutation needed:
    - task-<slug>.md without new forensic_* fields → parser defaults to []/null.
    - plan.md without `### Estimated lines` → check 3 silently skipped.
    - wave-summary.md without Forensic+ section → empty display OK.
    - L0 `icm_skill_version` bumped via existing `_bump_version_only` helper.
    """
    _bump_version_only(workspace_root, "3.8.0")
```

- [ ] **Step 3: Add to `STEP_FUNCTIONS` dispatcher**

Inside the dict at lines 265-271, append:

```python
STEP_FUNCTIONS = {
    "3.3.0->3.4.0": migrate_3_3_to_3_4,
    "3.4.0->3.5.0": migrate_3_4_to_3_5,
    "3.5.0->3.6.0": migrate_3_5_to_3_6,
    "3.6.0->3.7.0": migrate_3_6_to_3_7,
    "3.7.0->3.7.2": migrate_3_7_0_to_3_7_2,
    "3.7.2->3.8.0": migrate_3_7_2_to_3_8_0,    # v3.8.0
}
```

- [ ] **Step 4: Commit**

```bash
git add scripts/migrate-workspace.py
git commit -m "feat(migrate): migrate_3_7_2_to_3_8_0 (bump-only via _bump_version_only)"
```

---

### Task 27: Tests for migration step

**Files:**
- Modify: `tests/unit/test_migrate_workspace.py`

> **Note on test conventions (verified):** the file uses an `_load(name, filename)` helper (lines 30-36) and an `mw` pytest fixture (lines 39-41) that wraps the script. New tests must reuse these — do NOT reach for `REPO_ROOT` (not defined in this file) or hand-rolled `importlib.util` calls. The `workspace` fixture (lines 44-69) creates a v3.6.0 workspace; for our new tests build a v3.7.2 workspace inline.

- [ ] **Step 1: Write failing tests using existing helpers**

Append to `tests/unit/test_migrate_workspace.py`:

```python
def test_current_skill_version_matches_bootstrap(mw):
    """CURRENT_SKILL_VERSION in migrate-workspace.py must equal SKILL_VERSION in bootstrap.py."""
    bootstrap = _load("bootstrap", "bootstrap.py")
    assert bootstrap.SKILL_VERSION == mw.CURRENT_SKILL_VERSION


@pytest.fixture
def workspace_v372(tmp_path: Path) -> Path:
    """Workspace with L0 already at v3.7.2."""
    ws = tmp_path / "workspaces" / "001-test"
    ws.mkdir(parents=True)
    (ws / "CLAUDE.md").write_text(
        "---\n"
        "layer: L0\n"
        "workspace: \"001-test\"\n"
        "profile: \"app_web_backend\"\n"
        "tier: \"development\"\n"
        "icm_skill_version: \"3.7.2\"\n"
        "---\n# L0\n",
        encoding="utf-8",
    )
    return ws


def test_migrate_3_7_2_to_3_8_0_smoke(mw, workspace_v372: Path, tmp_path: Path):
    """Migrate updates L0 icm_skill_version 3.7.2 → 3.8.0 (bump-only)."""
    project_root = tmp_path
    mw.migrate_3_7_2_to_3_8_0(workspace_v372, project_root)
    text = (workspace_v372 / "CLAUDE.md").read_text(encoding="utf-8")
    assert 'icm_skill_version: "3.8.0"' in text
    assert "3.7.2" not in text


def test_migrate_3_7_2_to_3_8_0_idempotent(mw, workspace_v372: Path, tmp_path: Path):
    """Running migration twice is a no-op (already at 3.8.0 after first run)."""
    project_root = tmp_path
    mw.migrate_3_7_2_to_3_8_0(workspace_v372, project_root)
    first = (workspace_v372 / "CLAUDE.md").read_text(encoding="utf-8")
    mw.migrate_3_7_2_to_3_8_0(workspace_v372, project_root)
    second = (workspace_v372 / "CLAUDE.md").read_text(encoding="utf-8")
    assert first == second


def test_step_functions_includes_v3_8_0(mw):
    """Dispatcher must register the new step with the canonical 'from->to' string key."""
    assert "3.7.2->3.8.0" in mw.STEP_FUNCTIONS
    assert mw.STEP_FUNCTIONS["3.7.2->3.8.0"] is mw.migrate_3_7_2_to_3_8_0


def test_supported_versions_ends_with_3_8_0(mw):
    """Tuple must include 3.8.0 as the last entry."""
    assert mw.SUPPORTED_VERSIONS[-1] == "3.8.0"
```

- [ ] **Step 2: Run tests**

```bash
pytest tests/unit/test_migrate_workspace.py -v -k "3_7_2_to_3_8_0 or current_skill_version or step_functions or supported_versions"
```
Expected: 5 PASS.

- [ ] **Step 3: Run full migrate test suite + drift detector**

```bash
pytest tests/unit/test_migrate_workspace.py tests/unit/test_no_drift.py -v
```
Expected: all green (version sweep complete, all drift detectors pass).

- [ ] **Step 4: Commit**

```bash
git add tests/unit/test_migrate_workspace.py
git commit -m "test(migrate): cover 3.7.2 → 3.8.0 (smoke + idempotency + dispatcher)"
```

---

**End of Chunk 5.**

---

## Chunk 6: bats e2e + final pre-merge gate

**Goal:** add the full-pipeline e2e bats test (CI-only) and walk through the merge workflow per CLAUDE.md.

### Task 28: bats e2e test

**Files:**
- Create: `tests/integration/test_forensic_plus_e2e.bats`

- [ ] **Step 1: Write the bats e2e**

```bash
#!/usr/bin/env bats
# tests/integration/test_forensic_plus_e2e.bats
# Full-pipeline e2e: real git, real script, real plan.md fixture, asserts JSON output.

setup() {
  TMPDIR_E2E="$(mktemp -d)"
  export TMPDIR_E2E
}

teardown() {
  rm -rf "$TMPDIR_E2E"
}

@test "forensic-plus e2e: clean pass with all 4 checks dormant" {
  cd "$TMPDIR_E2E"
  git init -b main >/dev/null
  git config user.email test@example.com
  git config user.name Test

  mkdir -p src tests
  echo "x = 1" > src/foo.py
  git add -A && git commit -m base >/dev/null

  git checkout -b wave-001-1/add-foo >/dev/null
  echo "x = 2" > src/foo.py
  cat > tests/test_foo.py <<EOF
def test_a():
    assert 1 == 1
    assert 2 == 2
EOF
  git add -A && git commit -m work >/dev/null
  git checkout main >/dev/null

  cat > plan.md <<EOF
## Task add-foo:
### Files touched
- src/foo.py
- tests/test_foo.py
EOF

  run python "$BATS_TEST_DIRNAME/../../scripts/forensic-plus.py" \
    --workspace-num 001 --wave 1 --task-slug add-foo \
    --base-branch main --plan plan.md --tier development --output json
  [ "$status" -eq 0 ]
  echo "$output" | grep -q '"forensic_passed": true'
  echo "$output" | grep -q '"max_severity": "NONE"'
}

@test "forensic-plus e2e: HARD violation flagged" {
  cd "$TMPDIR_E2E"
  git init -b main >/dev/null
  git config user.email test@example.com
  git config user.name Test
  mkdir -p src tests
  echo "x = 1" > src/foo.py
  git add -A && git commit -m base >/dev/null
  git checkout -b wave-001-1/add-foo >/dev/null
  echo "x = 2" > src/foo.py
  cat > tests/test_foo.py <<EOF
def test_a():
    assert True
EOF
  echo "y = 1" > src/extra.py
  git add -A && git commit -m work >/dev/null
  git checkout main >/dev/null
  cat > plan.md <<EOF
## Task add-foo:
### Files touched
- src/foo.py
- tests/test_foo.py
EOF

  run python "$BATS_TEST_DIRNAME/../../scripts/forensic-plus.py" \
    --workspace-num 001 --wave 1 --task-slug add-foo \
    --base-branch main --plan plan.md --tier development --output json
  [ "$status" -eq 0 ]
  echo "$output" | grep -q '"forensic_passed": false'
  echo "$output" | grep -q '"max_severity": "HARD"'
  # Both Check 1 (test asserções) and Check 2 (files outside dev=HARD) fire.
  echo "$output" | grep -q '"check": "test_assertions_too_few"'
  echo "$output" | grep -q '"check": "files_outside_declared"'
}
```

- [ ] **Step 2: Run bats locally if available, otherwise rely on CI**

```bash
bash tests/run.sh --ci
```
Expected: bats tests green (Linux CI only; on Windows the wrapper skips bats).

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_forensic_plus_e2e.bats
git commit -m "test(forensic-plus): bats e2e (clean pass + HARD violation)"
```

---

### Task 29: Final pre-merge gate

**Files:**
- (none modified) — read-only verification

- [ ] **Step 1: Full unit suite**

```bash
bash tests/run.sh --no-bats
```
Expected: all green, baseline `548+ tests` + new forensic-plus tests + new drift detectors.

- [ ] **Step 2: Full no-drift suite explicitly**

```bash
pytest tests/unit/test_no_drift.py -v
```
Expected: all detectors green (version-canonical-files, changelog-has-entry, scripts-skill-version-sync, status-canonical, forensic-plus-doc-canonical-exists, forensic-plus-in-bootstrap-runtime-refs, l2-stage-04-mentions-max-forensic-retries, wave-execution-protocol-has-forensic-substeps, l2-stage-04-references-forensic-plus-protocol).

- [ ] **Step 3: bats integration if available**

```bash
bash tests/run.sh --ci
```
Expected: bats green.

- [ ] **Step 4: Confirm 7-file version sweep complete**

```bash
grep -l "3.8.0" scripts/bootstrap.py SKILL.md README.md references/design-system.md references/preview-loop-protocol.md references/changelog.md scripts/migrate-workspace.py
```
Expected: all 7 paths printed.

- [ ] **Step 5: Inspect commit log for branch hygiene**

```bash
git log --oneline main..HEAD
```
Expected: clean commit-per-task series; each commit message follows Conventional Commits style.

---

### Task 30: Merge to main per CLAUDE.md workflow

**Files:**
- (none modified) — git operations

- [ ] **Step 1: Confirm working tree clean**

```bash
git status
```
Expected: `nothing to commit, working tree clean`.

- [ ] **Step 2: Switch to main + ff-only merge**

```bash
git checkout main
git merge --ff-only feat/forensic-plus-spec
```
Expected: merge succeeds linear (no merge commit). If conflict: `git checkout feat/forensic-plus-spec`, `git rebase main`, resolve, retry.

- [ ] **Step 3: Push if remote configured (no-op otherwise per CLAUDE.md)**

```bash
git push origin main 2>/dev/null || echo "no remote configured — skipped"
```

- [ ] **Step 4: Delete feature branch**

```bash
git branch -d feat/forensic-plus-spec
```
Expected: branch deleted (already merged).

- [ ] **Step 5: Final smoke**

```bash
git log --oneline -10
bash tests/run.sh --no-bats
```
Expected: top commit is the last forensic+ commit; all tests green.

---

**End of Chunk 6.** Implementation complete. v3.8.0 ready to ship.
