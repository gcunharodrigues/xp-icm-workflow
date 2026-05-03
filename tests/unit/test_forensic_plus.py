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
