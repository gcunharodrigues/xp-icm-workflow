"""v3.7.0 — `handoff.py remove-block --exit-2-if-last-active` CLI exit codes.

Stage 08 exits A/C need to know if the removed workspace was the last active one
to decide whether to invoke `Skill(skill: "init")` in the SAME session. Mechanism:
CLI flag `--exit-2-if-last-active` that makes the command return exit code 2
when deactivate fired (zero blocks remaining), 0 otherwise.

Without the flag, default behavior (backwards-compat) is always exit 0.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[2] / "scripts"
HANDOFF_PY = SCRIPT_DIR / "handoff.py"
sys.path.insert(0, str(SCRIPT_DIR))

from handoff import (  # type: ignore[import-not-found]  # noqa: E402
    WorkspaceBlock,
    update_project_claude_md,
)


def _block(workspace: str, **overrides) -> WorkspaceBlock:
    base = dict(
        workspace=workspace,
        profile="app_web_backend",
        tier="development",
        stage_atual="08",
        stage_dir="08_feedback_intake",
        sub_stage="08_in_progress",
        iteration=0,
        status="COMPLETED_AWAITING_HUMAN",
        last_action="phase 08 init",
        last_action_at="2026-05-01T10:00:00Z",
        next_action="awaiting human feedback",
    )
    base.update(overrides)
    return WorkspaceBlock(**base)


def _run_remove_block(
    project_root: Path,
    workspace: str,
    *,
    outcome: str = "A",
    spawn_to: str | None = None,
    exit_2_if_last_active: bool = False,
) -> subprocess.CompletedProcess[str]:
    args = [
        sys.executable, str(HANDOFF_PY), "remove-block",
        "--project-root", str(project_root),
        "--workspace", workspace,
        "--skill-dir", "/skill",
        "--closed-at", "2026-05-01T12:00:00Z",
        "--outcome", outcome,
    ]
    if spawn_to:
        args += ["--spawn-to", spawn_to]
    if exit_2_if_last_active:
        args.append("--exit-2-if-last-active")
    return subprocess.run(args, capture_output=True, text=True)


def test_exit_code_2_when_removed_last_active_outcome_A(tmp_path: Path):
    """Exit A removing only active workspace → exit 2 with flag."""
    update_project_claude_md(tmp_path, _block("042-feat-auth"), skill_dir="/skill")
    result = _run_remove_block(
        tmp_path, "042-feat-auth",
        outcome="A", exit_2_if_last_active=True,
    )
    assert result.returncode == 2, (
        f"expected exit 2 (last active), got {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_exit_code_0_when_other_workspaces_remain_outcome_A(tmp_path: Path):
    """Exit A with 2+ active workspaces, removing one → exit 0 with flag."""
    update_project_claude_md(tmp_path, _block("042-feat-auth"), skill_dir="/skill")
    update_project_claude_md(tmp_path, _block("043-payments"), skill_dir="/skill")
    result = _run_remove_block(
        tmp_path, "042-feat-auth",
        outcome="A", exit_2_if_last_active=True,
    )
    assert result.returncode == 0, (
        f"expected exit 0 (1 workspace still active), got {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_exit_code_2_when_removed_last_active_outcome_C(tmp_path: Path):
    """Exit C (spawn) removing last active workspace → exit 2 with flag."""
    update_project_claude_md(tmp_path, _block("042-feat-auth"), skill_dir="/skill")
    result = _run_remove_block(
        tmp_path, "042-feat-auth",
        outcome="C", spawn_to="050-billing-pivot",
        exit_2_if_last_active=True,
    )
    assert result.returncode == 2


def test_exit_code_0_default_without_flag(tmp_path: Path):
    """Sem flag, sempre exit 0 (backwards-compat)."""
    update_project_claude_md(tmp_path, _block("042-feat-auth"), skill_dir="/skill")
    result = _run_remove_block(
        tmp_path, "042-feat-auth",
        outcome="A", exit_2_if_last_active=False,
    )
    assert result.returncode == 0


def test_exit_code_0_when_workspace_not_present(tmp_path: Path):
    """Workspace inexistente + flag → exit 0 (target_existed=False)."""
    update_project_claude_md(tmp_path, _block("042-feat-auth"), skill_dir="/skill")
    result = _run_remove_block(
        tmp_path, "999-ghost",
        outcome="A", exit_2_if_last_active=True,
    )
    assert result.returncode == 0
