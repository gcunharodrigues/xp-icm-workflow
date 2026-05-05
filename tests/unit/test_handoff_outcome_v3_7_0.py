"""v3.7.0 — handoff.py outcome-aware idle render.

Bug v3.6.0 and earlier: `_render_icm_idle()` in handoff.py:401
hardcoded "Exit A" — exit C (spawn) reused the same function and lied about
the closure type.

Fix v3.7.0:
- `remove_workspace_block` accepts param `outcome ∈ {"A", "C"}` and `spawn_to`.
- `deactivate_project_claude_md` same signature.
- `_render_icm_idle` branches message by outcome.
- CLI `remove-block` accepts `--outcome {A,C}` and `--spawn-to`.

Tests written BEFORE implementation (TDD).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from handoff import (  # type: ignore[import-not-found]  # noqa: E402
    WorkspaceBlock,
    deactivate_project_claude_md,
    remove_workspace_block,
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


# ============================================================
# remove_workspace_block + outcome param
# ============================================================

def test_remove_block_outcome_A_renders_close_message(tmp_path: Path):
    """Exit A: idle message says 'Exit A — close'."""
    project_root = tmp_path
    block = _block("042-feat-auth")
    update_project_claude_md(project_root, block, skill_dir="/skill")
    remove_workspace_block(
        project_root,
        "042-feat-auth",
        skill_dir="/skill",
        closed_at="2026-05-01T12:00:00Z",
        outcome="A",
    )
    text = (project_root / "CLAUDE.md").read_text(encoding="utf-8")
    assert "Exit A" in text
    assert "close" in text.lower()
    assert "Exit C" not in text
    assert "spawn" not in text.lower() or "spawn_to" not in text


def test_remove_block_outcome_C_renders_spawn_message(tmp_path: Path):
    """Exit C: idle message says 'Exit C — spawn <slug>' and cites bootstrap."""
    project_root = tmp_path
    block = _block("042-feat-auth")
    update_project_claude_md(project_root, block, skill_dir="/skill")
    remove_workspace_block(
        project_root,
        "042-feat-auth",
        skill_dir="/skill",
        closed_at="2026-05-01T12:00:00Z",
        outcome="C",
        spawn_to="043-feat-billing",
    )
    text = (project_root / "CLAUDE.md").read_text(encoding="utf-8")
    assert "Exit C" in text
    assert "043-feat-billing" in text
    assert "Bootstrap in a new session" in text or "bootstrap" in text.lower()
    assert "Exit A" not in text


def test_remove_block_outcome_A_default(tmp_path: Path):
    """Backward compat: outcome default = A if not passed."""
    project_root = tmp_path
    block = _block("042-feat-auth")
    update_project_claude_md(project_root, block, skill_dir="/skill")
    remove_workspace_block(
        project_root,
        "042-feat-auth",
        skill_dir="/skill",
        closed_at="2026-05-01T12:00:00Z",
        # outcome omitted — should default to A
    )
    text = (project_root / "CLAUDE.md").read_text(encoding="utf-8")
    assert "Exit A" in text


def test_remove_block_outcome_C_requires_spawn_to(tmp_path: Path):
    """Exit C without spawn_to → raise."""
    project_root = tmp_path
    block = _block("042-feat-auth")
    update_project_claude_md(project_root, block, skill_dir="/skill")
    with pytest.raises(ValueError, match="spawn_to"):
        remove_workspace_block(
            project_root,
            "042-feat-auth",
            skill_dir="/skill",
            outcome="C",
            # spawn_to omitido
        )


def test_remove_block_invalid_outcome_raises(tmp_path: Path):
    """outcome ∉ {A, C} → raise."""
    project_root = tmp_path
    block = _block("042-feat-auth")
    update_project_claude_md(project_root, block, skill_dir="/skill")
    with pytest.raises(ValueError, match="outcome"):
        remove_workspace_block(
            project_root,
            "042-feat-auth",
            skill_dir="/skill",
            outcome="B",  # B uses update_project_claude_md, not remove
        )


# ============================================================
# Multi-workspace: removing a non-last workspace does not invoke idle
# ============================================================

def test_remove_block_with_other_workspaces_no_idle_message(tmp_path: Path):
    """Remove 1 workspace mas outros existem → bloco removido, idle NÃO disparado."""
    project_root = tmp_path
    update_project_claude_md(project_root, _block("042-a"), skill_dir="/skill")
    update_project_claude_md(project_root, _block("043-b"), skill_dir="/skill")
    remove_workspace_block(
        project_root, "042-a", skill_dir="/skill", outcome="C", spawn_to="044-c",
    )
    text = (project_root / "CLAUDE.md").read_text(encoding="utf-8")
    assert "042-a" not in text
    assert "043-b" in text
    # Idle not triggered because 043 still exists
    assert "No active workspace" not in text


# ============================================================
# deactivate_project_claude_md ganha outcome+spawn_to também
# ============================================================

def test_deactivate_outcome_C_renders_spawn(tmp_path: Path):
    project_root = tmp_path
    block = _block("042-feat-auth")
    update_project_claude_md(project_root, block, skill_dir="/skill")
    deactivate_project_claude_md(
        project_root,
        closed_at="2026-05-01T12:00:00Z",
        outcome="C",
        spawn_to="043-billing",
    )
    text = (project_root / "CLAUDE.md").read_text(encoding="utf-8")
    assert "Exit C" in text
    assert "043-billing" in text
