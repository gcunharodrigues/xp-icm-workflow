"""Tests v3.4.3: Recovery Wizard WAVE_WORKTREE_ORPHAN detection + Plan A
auto-cleanup.

Cobertura:
  * _list_worktrees parsing
  * _is_branch_merged usa merge-base --is-ancestor
  * Detect: worktree wave-<NNN>-* merged → orfa
  * Detect skip: worktree principal, .icm-main, branch nao-wave, branch nao-merged
  * Plan A: invoca git worktree remove + git branch -d
  * Plan A append history recovery_applied (ou warning se falhas)
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import pytest

# Setup: import recovery_wizard
_SCRIPT_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(_SCRIPT_DIR))


def _load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, _SCRIPT_DIR / filename)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


recovery_wizard = _load_module("recovery_wizard_v343", "recovery-wizard.py")


# ============================================================================
# Helpers — build minimal workspace + mocks
# ============================================================================

def _build_workspace_for_wave_test(
    tmp_path: Path,
    *,
    workspace: str = "001-test-wave",
) -> Path:
    """Cria workspace L1 minimalista pra testes de wave cleanup."""
    project_root = tmp_path
    ws = project_root / "workspaces" / workspace
    ws.mkdir(parents=True)
    (ws / "_config").mkdir()
    profile_yaml = "profile_base: app_web_backend\ntier: development\n"
    profile_bytes = profile_yaml.encode("utf-8")
    (ws / "_config" / "profile-effective.yaml").write_bytes(profile_bytes)

    import hashlib  # noqa: PLC0415
    correct_hash = hashlib.sha256(profile_bytes).hexdigest()
    project_root_posix = str(project_root).replace("\\", "/")

    now = datetime(2026, 4, 29, 14, 30, tzinfo=timezone.utc).isoformat()
    context = f"""---
workspace: "{workspace}"
profile_base: "app_web_backend"
profile_effective_hash: "{correct_hash}"
tier: "development"
project_root: "{project_root_posix}"
base_branch: "main"
workspace_branch: "workspace/{workspace}"
stage_atual: "04"
sub_stage: "04_wave_1_in_progress"
status: "IN_PROGRESS"
iteration: 0
llm_review_skipped_count: 0
last_action: "wave 1 active"
last_action_at: "{now}"
next_action: "test"
last_transition:
  from: "03_completed"
  to: "04_wave_1_in_progress"
  at: "{now}"
  commit_sha: "abc123def456"
history:
  - at: "{now}"
    event: "stage_transition"
    from: "03_completed"
    to: "04_wave_1_in_progress"
    commit_sha: "abc123def456"
waves:
  current: 1
  completed: []
  current_sub_wave: null
  blocked_at_sub_wave: null
  blocked_task: null
---

# Workspace
"""
    (ws / "CONTEXT.md").write_text(context, encoding="utf-8")
    return ws


@pytest.fixture
def patched_git(monkeypatch, tmp_path):
    """Mock subprocess.run + helpers em recovery_wizard.

    Default state:
      - 3 worktrees fake: project_root principal, .icm-main, 1 wave orfa
      - branch wave-001-1/auth ja merged em main
      - profile hash bate
      - last_transition.commit_sha existe
      - workspace_branch existe
    """
    project_root = tmp_path
    icm_main = project_root / ".icm-main"
    wave_path = project_root / ".icm-wave-001-1-auth"

    state = {
        "worktrees": [
            (str(project_root), "workspace/001-test-wave"),
            (str(icm_main), "main"),
            (str(wave_path), "wave-001-1/auth"),
        ],
        "merged_branches": {"wave-001-1/auth"},
        "removed_paths": [],
        "deleted_branches": [],
    }

    def fake_run(cmd, *args, **kwargs):
        if not isinstance(cmd, (list, tuple)):
            return subprocess.CompletedProcess(cmd, 0, "", "")

        if "worktree" in cmd and "list" in cmd:
            # Output porcelain format
            lines = []
            for path, branch in state["worktrees"]:
                lines.append(f"worktree {path}")
                if branch:
                    lines.append(f"branch refs/heads/{branch}")
                lines.append("")
            return subprocess.CompletedProcess(
                cmd, 0, "\n".join(lines) + "\n", ""
            )

        if "merge-base" in cmd and "--is-ancestor" in cmd:
            branch = cmd[-2]  # merge-base --is-ancestor <branch> <base>
            rc = 0 if branch in state["merged_branches"] else 1
            return subprocess.CompletedProcess(cmd, rc, "", "")

        if "worktree" in cmd and "remove" in cmd:
            path = cmd[-1]
            state["removed_paths"].append(path)
            return subprocess.CompletedProcess(cmd, 0, "", "")

        if "branch" in cmd and "-d" in cmd:
            branch = cmd[-1]
            state["deleted_branches"].append(branch)
            return subprocess.CompletedProcess(cmd, 0, "", "")

        # Defaults: cat-file -e, branch --list, log
        if "cat-file" in cmd and "-e" in cmd:
            return subprocess.CompletedProcess(cmd, 0, "", "")
        if "branch" in cmd and "--list" in cmd:
            return subprocess.CompletedProcess(
                cmd, 0, f"  {cmd[-1]}\n", ""
            )
        if "log" in cmd:
            return subprocess.CompletedProcess(
                cmd, 0, "2026-04-29T14:30:00+00:00\n", ""
            )
        if "rev-parse" in cmd:
            return subprocess.CompletedProcess(
                cmd, 0, "workspace/001-test-wave\n", ""
            )
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(recovery_wizard.subprocess, "run", fake_run)
    return state


# ============================================================================
# _list_worktrees parsing
# ============================================================================

class TestListWorktrees:
    def test_parses_porcelain_output(self, patched_git, tmp_path):
        result = recovery_wizard._list_worktrees(tmp_path)
        # Esperamos as 3 entries do default
        paths = [p for p, b in result]
        assert str(tmp_path) in paths
        assert any(".icm-wave-001-1-auth" in p for p in paths)


# ============================================================================
# _is_branch_merged
# ============================================================================

class TestIsBranchMerged:
    def test_returns_true_for_merged(self, patched_git, tmp_path):
        assert recovery_wizard._is_branch_merged(
            "wave-001-1/auth", "main", cwd=tmp_path
        )

    def test_returns_false_for_unmerged(self, patched_git, tmp_path):
        assert not recovery_wizard._is_branch_merged(
            "wave-001-1/orphan-not-merged", "main", cwd=tmp_path
        )


# ============================================================================
# Detect WAVE_WORKTREE_ORPHAN
# ============================================================================

class TestDetectWaveWorktreeOrphan:
    def test_detects_orphan_wave_worktree(self, patched_git, tmp_path):
        ws = _build_workspace_for_wave_test(tmp_path)
        now = datetime(2026, 4, 29, 14, 30, tzinfo=timezone.utc)
        result = recovery_wizard.detect_inconsistencies(
            ws, project_root=tmp_path, now=now
        )
        codes = [i.code for i in result]
        assert "WAVE_WORKTREE_ORPHAN" in codes
        # Mensagem inclui path
        msg_combined = " ".join(
            i.message for i in result if i.code == "WAVE_WORKTREE_ORPHAN"
        )
        assert "wave-001-1/auth" in msg_combined

    def test_skip_when_no_wave_worktree(self, patched_git, tmp_path):
        # Remove a wave worktree
        patched_git["worktrees"] = [
            (str(tmp_path), "workspace/001-test-wave"),
            (str(tmp_path / ".icm-main"), "main"),
        ]
        ws = _build_workspace_for_wave_test(tmp_path)
        now = datetime(2026, 4, 29, 14, 30, tzinfo=timezone.utc)
        result = recovery_wizard.detect_inconsistencies(
            ws, project_root=tmp_path, now=now
        )
        codes = [i.code for i in result]
        assert "WAVE_WORKTREE_ORPHAN" not in codes

    def test_skip_branch_not_merged(self, patched_git, tmp_path):
        # Branch existe mas NÃO está em merged_branches
        patched_git["worktrees"] = [
            (str(tmp_path), "workspace/001-test-wave"),
            (str(tmp_path / ".icm-wave-001-1-pending"), "wave-001-1/pending"),
        ]
        # patched_git['merged_branches'] não inclui wave-001-1/pending
        ws = _build_workspace_for_wave_test(tmp_path)
        now = datetime(2026, 4, 29, 14, 30, tzinfo=timezone.utc)
        result = recovery_wizard.detect_inconsistencies(
            ws, project_root=tmp_path, now=now
        )
        codes = [i.code for i in result]
        assert "WAVE_WORKTREE_ORPHAN" not in codes


# ============================================================================
# Plan A: auto-cleanup
# ============================================================================

class TestPlanAAutoCleanup:
    def test_plan_a_runs_worktree_remove_and_branch_delete(
        self, patched_git, tmp_path
    ):
        ws = _build_workspace_for_wave_test(tmp_path)
        now = datetime(2026, 4, 29, 14, 30, tzinfo=timezone.utc)
        recovery_wizard.apply_recovery(
            ws, "A", project_root=tmp_path, now=now
        )

        # Verifica que worktree remove + branch -d foram chamados
        assert any(
            ".icm-wave-001-1-auth" in p
            for p in patched_git["removed_paths"]
        )
        assert "wave-001-1/auth" in patched_git["deleted_branches"]

    def test_plan_a_appends_history_event(self, patched_git, tmp_path):
        ws = _build_workspace_for_wave_test(tmp_path)
        now = datetime(2026, 4, 29, 14, 30, tzinfo=timezone.utc)
        recovery_wizard.apply_recovery(
            ws, "A", project_root=tmp_path, now=now
        )

        state, _, _ = recovery_wizard._parse_l1(ws)
        # Última entrada de history deve ser recovery_applied geral OU
        # recovery_applied específico do wave cleanup
        events = [h.get("event") for h in state.get("history", [])]
        notes = [h.get("note", "") for h in state.get("history", [])]
        assert any(
            "wave worktree cleanup" in n for n in notes
        )
