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


def test_max_forensic_retries_exposed_as_module_constant():
    """Constant must be importable + value 2 (per spec §6.2)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("forensic_plus", str(SCRIPT))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert hasattr(mod, "MAX_FORENSIC_RETRIES")
    assert mod.MAX_FORENSIC_RETRIES == 2


def test_cli_requires_all_args():
    """Missing required args → exit 2 (argparse default for missing args)."""
    rc, _, stderr = _run([])
    assert rc == 2
    assert "required" in stderr.lower() or "the following arguments" in stderr.lower()


# ============================================================================
# Check 1 — test assertions threshold (Task 2)
# ============================================================================
# Note: the Task 1 skeleton test (`test_cli_skeleton_emits_canonical_keys`) was
# removed in Task 3. Its purpose — pinning the JSON contract (keys + types +
# exit 0) — is now fully exercised by the Check 1 / Check 2 tests below, which
# also build real git repos. Once Check 2 calls `_git_run` directly, the
# skeleton's no-git fixture forced a `GitError → exit 1`, and resurrecting it
# would require initializing a full git repo just to repeat coverage already
# present.

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
    body = f"## Task {task_slug}:\n\n### WHAT\n- placeholder\n\n### Files touched\n"
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


# ============================================================================
# Check 2 — files outside declared (Task 3)
# ============================================================================


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


def test_hitl_task_returns_skipped_payload(tmp_path):
    """Task with `Type: HITL` short-circuits all checks and emits skipped payload."""
    # Build a real repo so Check 2 wouldn't crash on git, but HITL skip happens before
    repo = _make_repo_with_branch(
        tmp_path,
        base_files={"src/foo.py": "x = 1\n"},
        branch_files={
            # All would normally violate (single assert, undeclared file, +TODO)
            "src/foo.py": "x = 2\n# TODO: review later\n",
            "src/extra.py": "y = 1\n",
        },
        branch_name="wave-001-1/review-data",
    )
    plan_text = (
        "## Task review-data:\n"
        "### Files touched\n- src/foo.py\n"
        "### Type\n- HITL\n"
    )
    plan = repo / "plan.md"
    plan.write_text(plan_text, encoding="utf-8")

    rc, stdout, _ = _run(
        ["--workspace-num", "001", "--wave", "1", "--task-slug", "review-data",
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


# ============================================================================
# Check 3 — scope creep vs estimate (Task 4)
# ============================================================================


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


# ============================================================================
# Check 4 — TODO/FIXME/HACK added (Task 5)
# ============================================================================


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
    """Integration: a single task triggers all 4 checks → main() accumulates all violations.

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


# ============================================================================
# HITL skip + JSON schema property + exit code (Task 6)
# ============================================================================


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
        assert {"task_slug", "violations", "forensic_passed", "max_severity"}.issubset(data.keys())
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


# ============================================================================
# Crash path (EC1) — git missing branch + plan malformed (Task 7)
# ============================================================================


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


# ============================================================================
# Snapshot fixtures (Task 9 + Task 10) — locks JSON contract
# ============================================================================

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

    # Optional expansion stage: write generated lines into specific files,
    # commit only when expansion is non-empty so other fixtures don't break
    # with "nothing to commit".
    expansion = recipe.get("expansion") or {}
    if expansion:
        for path, exp in expansion.items():
            full = repo / path
            full.parent.mkdir(parents=True, exist_ok=True)
            n = exp["repeat_lines"]
            tmpl = exp["template"]
            full.write_text(
                "".join(tmpl.format(i=i) for i in range(n)),
                encoding="utf-8",
            )
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", "expansion files")

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


# ============================================================================
# v3.9.0 — Checks 5/6/7 (acceptance↔test mapping, OUT OF SCOPE violations, ADR import drift)
# ============================================================================

def _make_plan_v3_9_0(
    repo,
    task_slug,
    files_touched,
    *,
    validacao=None,
    nao_quero=None,
    adrs_aplicaveis=None,
    conventions_extras=None,
    estimated_lines=None,
):
    """Write a plan.md with v3.9.0 blocks (OUT OF SCOPE, VALIDATION, Applicable ADRs sections)."""
    plan = repo / "plan.md"
    body = f"## Task {task_slug}:\n\n### WHAT\n- placeholder\n\n"
    if nao_quero:
        body += "### OUT OF SCOPE\n"
        for b in nao_quero:
            body += f"- {b}\n"
        body += "\n"
    if validacao:
        body += "### VALIDATION\n"
        for b in validacao:
            body += f"- {b}\n"
        body += "\n"
    body += "### Files touched\n"
    for f in files_touched:
        body += f"- {f}\n"
    if adrs_aplicaveis:
        body += "\n### Applicable ADRs\n"
        for a in adrs_aplicaveis:
            body += f"- {a}\n"
    if estimated_lines is not None:
        body += f"\n### Estimated lines\n~{estimated_lines}\n"
    if conventions_extras:
        body += f"\n### Conventions extras\n- {conventions_extras}\n"
    plan.write_text(body, encoding="utf-8")
    return plan


# Check 5: acceptance ↔ test mapping
def test_check5_acceptance_unmapped_hard_in_dev(tmp_path):
    """VALIDATION bullet cites test_foo_bar but test file does not contain the name → HARD in dev."""
    test_content = (
        "def test_other_thing():\n"
        "    assert True\n\n"
        "def test_yet_another():\n"
        "    assert 1 == 1\n"
    )
    repo = _make_repo_with_branch(
        tmp_path,
        base_files={"src/auth/mw.py": "# stub\n"},
        branch_files={
            "src/auth/mw.py": "# stub impl\ndef require_jwt():\n    pass\n",
            "tests/test_mw.py": test_content,
        },
        branch_name="wave-001-1/auth-mw",
    )
    _make_plan_v3_9_0(
        repo, "auth-mw",
        files_touched=["src/auth/mw.py", "tests/test_mw.py"],
        validacao=[
            "Test `test_missing_header_returns_401`: header ausente → 401",
        ],
    )
    rc, stdout, stderr = _run([
        "--workspace-num", "001", "--wave", "1",
        "--task-slug", "auth-mw", "--base-branch", "main",
        "--plan", str(repo / "plan.md"), "--tier", "development",
    ], cwd=repo)
    assert rc == 0, f"stderr: {stderr}"
    result = json.loads(stdout)
    violations = [v for v in result["violations"] if v["check"] == "acceptance_test_unmapped"]
    assert len(violations) >= 1
    assert violations[0]["severity"] == "HARD"


def test_check5_acceptance_unmapped_soft_in_tool(tmp_path):
    """Mesmo cenário em tier tool → SOFT."""
    repo = _make_repo_with_branch(
        tmp_path,
        base_files={"src/foo.py": "# stub\n"},
        branch_files={
            "src/foo.py": "# stub\n",
            "tests/test_foo.py": "def test_other():\n    assert True\n    assert 1\n",
        },
        branch_name="wave-001-1/foo",
    )
    _make_plan_v3_9_0(
        repo, "foo",
        files_touched=["src/foo.py", "tests/test_foo.py"],
        validacao=["Test `test_specific_unmapped`: missing test."],
    )
    rc, stdout, _ = _run([
        "--workspace-num", "001", "--wave", "1",
        "--task-slug", "foo", "--base-branch", "main",
        "--plan", str(repo / "plan.md"), "--tier", "tool",
    ], cwd=repo)
    assert rc == 0
    result = json.loads(stdout)
    violations = [v for v in result["violations"] if v["check"] == "acceptance_test_unmapped"]
    assert len(violations) >= 1
    assert violations[0]["severity"] == "SOFT"


# Check 6: OUT OF SCOPE violations
def test_check6_nao_quero_mock_violation_hard_in_dev(tmp_path):
    """OUT OF SCOPE declares 'Mock interno de jose'; diff uses jest.mock("jose") → HARD."""
    test_content = (
        'jest.mock("jose");\n'
        'test("foo", () => { expect(1).toBe(1); });\n'
        'test("bar", () => { expect(2).toBe(2); });\n'
    )
    repo = _make_repo_with_branch(
        tmp_path,
        base_files={"src/auth.ts": "// stub\n"},
        branch_files={
            "src/auth.ts": "// impl\nexport const requireJwt = () => {};\n",
            "tests/auth.test.ts": test_content,
        },
        branch_name="wave-001-1/auth",
    )
    _make_plan_v3_9_0(
        repo, "auth",
        files_touched=["src/auth.ts", "tests/auth.test.ts"],
        nao_quero=["Mock interno de jose"],
    )
    rc, stdout, _ = _run([
        "--workspace-num", "001", "--wave", "1",
        "--task-slug", "auth", "--base-branch", "main",
        "--plan", str(repo / "plan.md"), "--tier", "development",
    ], cwd=repo)
    assert rc == 0
    result = json.loads(stdout)
    violations = [v for v in result["violations"] if v["check"] == "nao_quero_violation"]
    assert len(violations) >= 1
    assert violations[0]["severity"] == "HARD"


def test_check6_nao_quero_no_violation_when_pattern_absent(tmp_path):
    """OUT OF SCOPE descriptive (no detectable pattern) → no check."""
    repo = _make_repo_with_branch(
        tmp_path,
        base_files={"src/foo.ts": "// stub\n"},
        branch_files={
            "src/foo.ts": "export const foo = () => 'ok';\n",
            "tests/foo.test.ts": "test('foo', () => { expect(1).toBe(1); expect(2).toBe(2); });\n",
        },
        branch_name="wave-001-1/foo",
    )
    _make_plan_v3_9_0(
        repo, "foo",
        files_touched=["src/foo.ts", "tests/foo.test.ts"],
        nao_quero=["Cachear resultados em memória", "Implementar refresh-token"],
    )
    rc, stdout, _ = _run([
        "--workspace-num", "001", "--wave", "1",
        "--task-slug", "foo", "--base-branch", "main",
        "--plan", str(repo / "plan.md"), "--tier", "development",
    ], cwd=repo)
    assert rc == 0
    result = json.loads(stdout)
    nq_violations = [v for v in result["violations"] if v["check"] == "nao_quero_violation"]
    assert nq_violations == []  # descriptive bullets, no detection


# Check 7: ADR import drift
def test_check7_adr_import_drift_hard_in_prod(tmp_path):
    """Applicable ADR prohibits `jsonwebtoken`; diff imports it → HARD in production."""
    repo = _make_repo_with_branch(
        tmp_path,
        base_files={
            "src/auth.ts": "// stub\n",
            "docs/decisions/0001-stack.md": (
                "# ADR 0001 — Stack\n\n"
                "## Forbidden imports\n"
                "- `jsonwebtoken` (use `jose`)\n"
            ),
        },
        branch_files={
            "src/auth.ts": "import jwt from 'jsonwebtoken';\nexport const x = () => {};\n",
            "tests/auth.test.ts": "test('a', () => { expect(1).toBe(1); expect(2).toBe(2); });\n",
        },
        branch_name="wave-001-1/auth",
    )
    _make_plan_v3_9_0(
        repo, "auth",
        files_touched=["src/auth.ts", "tests/auth.test.ts"],
        adrs_aplicaveis=["docs/decisions/0001-stack.md"],
    )
    rc, stdout, _ = _run([
        "--workspace-num", "001", "--wave", "1",
        "--task-slug", "auth", "--base-branch", "main",
        "--plan", str(repo / "plan.md"), "--tier", "production",
    ], cwd=repo)
    assert rc == 0
    result = json.loads(stdout)
    violations = [v for v in result["violations"] if v["check"] == "adr_import_drift"]
    assert len(violations) >= 1
    assert violations[0]["severity"] == "HARD"


def test_check7_adr_no_forbidden_section_skip_silently(tmp_path):
    """ADR sem `## Forbidden imports` section → check skipped (backward compat)."""
    repo = _make_repo_with_branch(
        tmp_path,
        base_files={
            "src/auth.ts": "// stub\n",
            "docs/decisions/0001-stack.md": "# ADR 0001\n\n## Decision\n- Use TS.\n",
        },
        branch_files={
            "src/auth.ts": "import jwt from 'jsonwebtoken';\n",
            "tests/auth.test.ts": "test('a', () => { expect(1).toBe(1); expect(2).toBe(2); });\n",
        },
        branch_name="wave-001-1/auth",
    )
    _make_plan_v3_9_0(
        repo, "auth",
        files_touched=["src/auth.ts", "tests/auth.test.ts"],
        adrs_aplicaveis=["docs/decisions/0001-stack.md"],
    )
    rc, stdout, _ = _run([
        "--workspace-num", "001", "--wave", "1",
        "--task-slug", "auth", "--base-branch", "main",
        "--plan", str(repo / "plan.md"), "--tier", "production",
    ], cwd=repo)
    assert rc == 0
    result = json.loads(stdout)
    adr_violations = [v for v in result["violations"] if v["check"] == "adr_import_drift"]
    assert adr_violations == []


# ============================================================================
# v3.10.0 — Check 8 user-journey coverage (e2e)
# ============================================================================

def _make_plan_v3_10_0(
    repo,
    task_slug,
    files_touched,
    *,
    requires_e2e_update=False,
    e2e_skip=None,
    conventions_extras=None,
):
    """Plan with v3.10.0 Requires E2E update field + optional **E2E:** skip."""
    plan = repo / "plan.md"
    body = f"## Task {task_slug}:\n\n### WHAT\n- placeholder\n\n"
    if e2e_skip:
        body += f"**E2E:** skip - {e2e_skip}\n\n"
    body += "### Files touched\n"
    for f in files_touched:
        body += f"- {f}\n"
    if requires_e2e_update:
        body += "\n### Requires E2E update\n- true\n"
    if conventions_extras:
        body += f"\n### Conventions extras\n- {conventions_extras}\n"
    plan.write_text(body, encoding="utf-8")
    return plan


def test_check8_e2e_missing_hard_in_dev(tmp_path):
    """requires_e2e_update=True, no e2e files in diff, dev tier → HARD."""
    repo = _make_repo_with_branch(
        tmp_path,
        base_files={"src/routes/checkout.ts": "// stub\n"},
        branch_files={
            "src/routes/checkout.ts": "// impl\nexport const checkout = () => {};\n",
            "tests/checkout.test.ts": "test('a', () => { expect(1).toBe(1); expect(2).toBe(2); });\n",
        },
        branch_name="wave-001-1/checkout",
    )
    _make_plan_v3_10_0(
        repo, "checkout",
        files_touched=["src/routes/checkout.ts", "tests/checkout.test.ts"],
        requires_e2e_update=True,
    )
    rc, stdout, _ = _run([
        "--workspace-num", "001", "--wave", "1",
        "--task-slug", "checkout", "--base-branch", "main",
        "--plan", str(repo / "plan.md"), "--tier", "development",
    ], cwd=repo)
    assert rc == 0
    result = json.loads(stdout)
    e2e_violations = [v for v in result["violations"] if v["check"] == "e2e_coverage_missing"]
    assert len(e2e_violations) == 1
    assert e2e_violations[0]["severity"] == "HARD"


def test_check8_e2e_present_passes(tmp_path):
    """requires_e2e_update=True + e2e file in diff → no violation."""
    repo = _make_repo_with_branch(
        tmp_path,
        base_files={"src/routes/checkout.ts": "// stub\n"},
        branch_files={
            "src/routes/checkout.ts": "// impl\n",
            "tests/checkout.test.ts": "test('a', () => { expect(1).toBe(1); expect(2).toBe(2); });\n",
            "e2e/checkout-flow.spec.ts": "test('e2e', () => { expect(1).toBe(1); });\n",
        },
        branch_name="wave-001-1/checkout",
    )
    _make_plan_v3_10_0(
        repo, "checkout",
        files_touched=["src/routes/checkout.ts", "tests/checkout.test.ts", "e2e/checkout-flow.spec.ts"],
        requires_e2e_update=True,
    )
    rc, stdout, _ = _run([
        "--workspace-num", "001", "--wave", "1",
        "--task-slug", "checkout", "--base-branch", "main",
        "--plan", str(repo / "plan.md"), "--tier", "development",
    ], cwd=repo)
    assert rc == 0
    result = json.loads(stdout)
    e2e_violations = [v for v in result["violations"] if v["check"] == "e2e_coverage_missing"]
    assert e2e_violations == []


def test_check8_e2e_skip_override_silent(tmp_path):
    """**E2E:** skip - rationale → Check 8 silent skip even if requires_e2e_update."""
    repo = _make_repo_with_branch(
        tmp_path,
        base_files={"src/routes/foo.ts": "// stub\n"},
        branch_files={
            "src/routes/foo.ts": "// refactor\n",
            "tests/foo.test.ts": "test('a', () => { expect(1).toBe(1); expect(2).toBe(2); });\n",
        },
        branch_name="wave-001-1/foo",
    )
    _make_plan_v3_10_0(
        repo, "foo",
        files_touched=["src/routes/foo.ts", "tests/foo.test.ts"],
        requires_e2e_update=True,
        e2e_skip="refactor interno, behavior preservado",
    )
    rc, stdout, _ = _run([
        "--workspace-num", "001", "--wave", "1",
        "--task-slug", "foo", "--base-branch", "main",
        "--plan", str(repo / "plan.md"), "--tier", "development",
    ], cwd=repo)
    assert rc == 0
    result = json.loads(stdout)
    e2e_violations = [v for v in result["violations"] if v["check"] == "e2e_coverage_missing"]
    assert e2e_violations == []


def test_check8_e2e_no_flag_skip(tmp_path):
    """No requires_e2e_update field → Check 8 skip silently."""
    repo = _make_repo_with_branch(
        tmp_path,
        base_files={"src/utils/helper.ts": "// stub\n"},
        branch_files={
            "src/utils/helper.ts": "export const x = () => 1;\n",
            "tests/helper.test.ts": "test('a', () => { expect(1).toBe(1); expect(2).toBe(2); });\n",
        },
        branch_name="wave-001-1/helper",
    )
    _make_plan_v3_10_0(
        repo, "helper",
        files_touched=["src/utils/helper.ts", "tests/helper.test.ts"],
        # requires_e2e_update=False (default)
    )
    rc, stdout, _ = _run([
        "--workspace-num", "001", "--wave", "1",
        "--task-slug", "helper", "--base-branch", "main",
        "--plan", str(repo / "plan.md"), "--tier", "development",
    ], cwd=repo)
    assert rc == 0
    result = json.loads(stdout)
    e2e_violations = [v for v in result["violations"] if v["check"] == "e2e_coverage_missing"]
    assert e2e_violations == []


def test_check8_e2e_soft_in_tool_tier(tmp_path):
    """requires_e2e_update=True, no e2e files, tool tier → SOFT."""
    repo = _make_repo_with_branch(
        tmp_path,
        base_files={"src/api/foo.ts": "// stub\n"},
        branch_files={
            "src/api/foo.ts": "// impl\n",
            "tests/foo.test.ts": "test('a', () => { expect(1).toBe(1); expect(2).toBe(2); });\n",
        },
        branch_name="wave-001-1/foo",
    )
    _make_plan_v3_10_0(
        repo, "foo",
        files_touched=["src/api/foo.ts", "tests/foo.test.ts"],
        requires_e2e_update=True,
    )
    rc, stdout, _ = _run([
        "--workspace-num", "001", "--wave", "1",
        "--task-slug", "foo", "--base-branch", "main",
        "--plan", str(repo / "plan.md"), "--tier", "tool",
    ], cwd=repo)
    assert rc == 0
    result = json.loads(stdout)
    e2e_violations = [v for v in result["violations"] if v["check"] == "e2e_coverage_missing"]
    assert len(e2e_violations) == 1
    assert e2e_violations[0]["severity"] == "SOFT"
