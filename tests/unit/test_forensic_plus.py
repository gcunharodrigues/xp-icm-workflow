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

    Plan stub lists only a non-test file — no Check 1 work, no git access required.
    This test pins the JSON contract: keys present, types correct, exit 0.
    """
    plan = tmp_path / "plan.md"
    plan.write_text(
        "## Task add-foo:\n### Files touched\n- src/foo.py\n",
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


# ============================================================================
# Check 1 — test assertions threshold (Task 2)
# ============================================================================

import subprocess as _sp


def _git(cwd, *args):
    """Run git command in cwd; return stdout."""
    return _sp.check_output(["git", *args], cwd=cwd, text=True).strip()


def _make_repo_with_branch(tmp_path, base_files: dict, branch_files: dict, branch_name: str):
    """Initialize a git repo with base commit + a feature branch with extra files."""
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
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
    """Test file with 3 assert statements -> no violation (count threshold met)."""
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
    """Test file with only one assertion -> HARD violation (count below threshold)."""
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
