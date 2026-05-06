"""Unit tests for os 3 codes novos do recovery-wizard.py em v3.4.0:

  * WORKTREE_MISSING — `.icm-main/` worktree ausente em project_root
  * WORKTREE_WRONG_BRANCH — `.icm-main/` em branch != base_branch
  * WRONG_BRANCH_CHECKOUT — project_root checkado em branch != workspace_branch
    enquanto workspace ainda ativo (status != COMPLETED).

Usa git real em tmp_path para evitar mocks fragilizados — operacoes git
sao locais e rapidas. Comparar com test_recovery_wizard.py (mock-based)
que cobre os 5 codes pre-v3.4.0.
"""
from __future__ import annotations

import hashlib
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

SKILL_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

_SPEC = importlib.util.spec_from_file_location(
    "recovery_wizard_v34",
    SCRIPT_DIR / "recovery-wizard.py",
)
assert _SPEC is not None and _SPEC.loader is not None
recovery_wizard = importlib.util.module_from_spec(_SPEC)
sys.modules["recovery_wizard_v34"] = recovery_wizard
_SPEC.loader.exec_module(recovery_wizard)

detect_inconsistencies = recovery_wizard.detect_inconsistencies


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _build_workspace_l1(
    project_root: Path,
    *,
    workspace_id: str = "001-test",
    base_branch: str = "main",
    workspace_branch: str = "workspace/001-test",
    status: str = "IN_PROGRESS",
) -> Path:
    """Cria L1 minimo apontando para project_root real."""
    ws = project_root / "workspaces" / workspace_id
    ws.mkdir(parents=True)
    (ws / "_config").mkdir()
    profile_yaml = "profile_base: cli_tool\ntier: experimental\n"
    profile_bytes = profile_yaml.encode("utf-8")
    (ws / "_config" / "profile-effective.yaml").write_bytes(profile_bytes)
    correct_hash = hashlib.sha256(profile_bytes).hexdigest()

    now = "2026-04-29T10:00:00+00:00"
    pr_str = str(project_root).replace("\\", "/")
    context = f"""---
workspace: "{workspace_id}"
profile_base: "cli_tool"
profile_effective_hash: "{correct_hash}"
tier: "experimental"
project_root: "{pr_str}"
base_branch: "{base_branch}"
workspace_branch: "{workspace_branch}"
stage_atual: "00"
sub_stage: "00_in_progress"
status: "{status}"
iteration: 0
llm_review_skipped_count: 0
last_action: "bootstrap"
last_action_at: "{now}"
next_action: "stage 00"
last_transition:
  from: "init"
  to: "00_in_progress"
  at: "{now}"
  commit_sha: "abc123def456"
history:
  - at: "{now}"
    event: "stage_transition"
    from: "init"
    to: "00_in_progress"
    commit_sha: "abc123def456"
---

# {workspace_id}
"""
    (ws / "CONTEXT.md").write_text(context, encoding="utf-8")
    return ws


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    """Tmp git repo com main + workspace/001-test, sem .icm-main."""
    pr = tmp_path / "proj"
    pr.mkdir()
    _git(["init", "-b", "main"], pr)
    _git(["config", "user.email", "t@t"], pr)
    _git(["config", "user.name", "T"], pr)
    (pr / "README.md").write_text("x\n", encoding="utf-8")
    _git(["add", "README.md"], pr)
    _git(["commit", "-m", "initial"], pr)
    _git(["checkout", "-b", "workspace/001-test"], pr)
    return pr


# Mock subprocess para que MISSING_COMMIT nao trigger durante estes tests
# (o L1 referencia abc123def456 que nao existe no tmp git repo).
@pytest.fixture(autouse=True)
def _allow_fake_sha(monkeypatch):
    real_run = subprocess.run

    def fake_run(cmd, *args, **kwargs):
        if isinstance(cmd, (list, tuple)) and "cat-file" in cmd and "-e" in cmd:
            return subprocess.CompletedProcess(cmd, 0, "", "")
        if (
            isinstance(cmd, (list, tuple))
            and "branch" in cmd and "--list" in cmd
        ):
            return subprocess.CompletedProcess(cmd, 0, f"  {cmd[-1]}\n", "")
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(recovery_wizard.subprocess, "run", fake_run)


# =========================================================================
# WORKTREE_MISSING
# =========================================================================

class TestWorktreeMissing:
    def test_triggers_when_icm_main_absent(self, project_root: Path) -> None:
        ws = _build_workspace_l1(project_root)
        result = detect_inconsistencies(ws, project_root=project_root)
        codes = [i.code for i in result]
        assert "WORKTREE_MISSING" in codes
        wm = next(i for i in result if i.code == "WORKTREE_MISSING")
        assert wm.severity == "critical"
        assert "worktree add .icm-main main" in wm.proposed_action

    def test_no_trigger_when_worktree_exists(self, project_root: Path) -> None:
        ws = _build_workspace_l1(project_root)
        # Cria worktree real em main
        _git(["worktree", "add", ".icm-main", "main"], project_root)
        result = detect_inconsistencies(ws, project_root=project_root)
        codes = [i.code for i in result]
        assert "WORKTREE_MISSING" not in codes


# =========================================================================
# WORKTREE_WRONG_BRANCH
# =========================================================================

class TestWorktreeWrongBranch:
    def test_triggers_when_worktree_in_other_branch(
        self, project_root: Path
    ) -> None:
        ws = _build_workspace_l1(project_root)
        # Cria branch alternativa e worktree apontando pra ela
        _git(["branch", "feature/x", "main"], project_root)
        _git(["worktree", "add", ".icm-main", "feature/x"], project_root)
        result = detect_inconsistencies(ws, project_root=project_root)
        codes = [i.code for i in result]
        assert "WORKTREE_WRONG_BRANCH" in codes
        wb = next(i for i in result if i.code == "WORKTREE_WRONG_BRANCH")
        assert wb.severity == "warning"
        assert "feature/x" in wb.message

    def test_no_trigger_when_in_correct_base_branch(
        self, project_root: Path
    ) -> None:
        ws = _build_workspace_l1(project_root)
        _git(["worktree", "add", ".icm-main", "main"], project_root)
        result = detect_inconsistencies(ws, project_root=project_root)
        codes = [i.code for i in result]
        assert "WORKTREE_WRONG_BRANCH" not in codes


# =========================================================================
# WRONG_BRANCH_CHECKOUT
# =========================================================================

class TestWrongBranchCheckout:
    def test_triggers_when_project_in_unrelated_branch(
        self, project_root: Path
    ) -> None:
        ws = _build_workspace_l1(project_root)
        # Switch project_root pra branch que nao eh workspace/001-test
        _git(["checkout", "main"], project_root)
        result = detect_inconsistencies(ws, project_root=project_root)
        codes = [i.code for i in result]
        assert "WRONG_BRANCH_CHECKOUT" in codes
        wbc = next(i for i in result if i.code == "WRONG_BRANCH_CHECKOUT")
        assert wbc.severity == "warning"
        assert "main" in wbc.message
        assert "workspace/001-test" in wbc.proposed_action

    def test_no_trigger_when_in_workspace_branch(
        self, project_root: Path
    ) -> None:
        ws = _build_workspace_l1(project_root)
        # project_root ja esta em workspace/001-test (fixture)
        result = detect_inconsistencies(ws, project_root=project_root)
        codes = [i.code for i in result]
        assert "WRONG_BRANCH_CHECKOUT" not in codes

    def test_no_trigger_when_status_completed(
        self, project_root: Path
    ) -> None:
        ws = _build_workspace_l1(project_root, status="COMPLETED")
        _git(["checkout", "main"], project_root)
        result = detect_inconsistencies(ws, project_root=project_root)
        codes = [i.code for i in result]
        assert "WRONG_BRANCH_CHECKOUT" not in codes
