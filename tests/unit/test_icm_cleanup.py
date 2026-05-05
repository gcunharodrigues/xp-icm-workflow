"""v3.7.2 — `scripts/icm-cleanup.py` cleanup after exit A/C last active.

Covers:
- Pre-checks (uncommitted abort).
- Dry-run does not modify filesystem or git state.
- Full cleanup: subagent worktrees, checkout base, branch delete, .icm-main remove.
- --keep-worktree preserves .icm-main.
- Idempotent: 2 consecutive runs = same final state.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[2] / "scripts"

# Importa via spec porque filename tem hifen
spec = importlib.util.spec_from_file_location(
    "icm_cleanup", SCRIPT_DIR / "icm-cleanup.py",
)
assert spec and spec.loader
icm_cleanup = importlib.util.module_from_spec(spec)
sys.modules["icm_cleanup"] = icm_cleanup
spec.loader.exec_module(icm_cleanup)

cleanup_after_close = icm_cleanup.cleanup_after_close
CleanupReport = icm_cleanup.CleanupReport


# ============================================================
# Fixtures: criar repo git real com workspace branch + .icm-main
# ============================================================

def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git"] + args, cwd=str(cwd), capture_output=True, text=True, check=True,
    )


def _setup_repo_with_workspace(
    tmp_path: Path,
    workspace: str = "042-feat-auth",
    *,
    create_icm_main: bool = True,
    create_subagent_wt: bool = False,
) -> Path:
    """Cria repo git com main + workspace branch + opcional .icm-main worktree."""
    repo = tmp_path / "project"
    repo.mkdir()
    _git(["init", "-b", "main"], cwd=repo)
    _git(["config", "user.email", "test@test.com"], cwd=repo)
    _git(["config", "user.name", "Test"], cwd=repo)
    (repo / "README.md").write_text("# project\n", encoding="utf-8")
    # .gitignore: .icm-main worktree dir (canonico bootstrap real adiciona)
    (repo / ".gitignore").write_text(".icm-main/\n", encoding="utf-8")
    _git(["add", "."], cwd=repo)
    _git(["commit", "-m", "initial"], cwd=repo)

    # Workspace branch + commit
    workspace_branch = f"workspace/{workspace}"
    _git(["checkout", "-b", workspace_branch], cwd=repo)
    ws_dir = repo / "workspaces" / workspace
    ws_dir.mkdir(parents=True)
    (ws_dir / "CONTEXT.md").write_text("---\nstatus: COMPLETED\n---\n", encoding="utf-8")
    _git(["add", "."], cwd=repo)
    _git(["commit", "-m", f"workspace {workspace}: state"], cwd=repo)

    # .icm-main worktree linked to main
    if create_icm_main:
        _git(["worktree", "add", ".icm-main", "main"], cwd=repo)

    # Orphan subagent worktree (simulates stage 04 without cleanup)
    if create_subagent_wt:
        _git(["branch", "wave-1-1-task-foo"], cwd=repo)
        wt_path = tmp_path / "subagent-foo"
        _git(["worktree", "add", str(wt_path), "wave-1-1-task-foo"], cwd=repo)

    return repo


# ============================================================
# Pre-checks
# ============================================================

def test_aborts_if_not_git_repo(tmp_path: Path):
    fake = tmp_path / "fake"
    fake.mkdir()
    report = cleanup_after_close(fake, "042-feat-auth")
    assert report.aborted is True
    assert "is not a git repo" in report.abort_reason


def test_aborts_if_workspace_branch_uncommitted(tmp_path: Path):
    repo = _setup_repo_with_workspace(tmp_path)
    # Atualmente em workspace branch — adiciona dirty file
    (repo / "dirty.txt").write_text("uncommitted\n", encoding="utf-8")
    _git(["add", "dirty.txt"], cwd=repo)  # staged but not committed

    report = cleanup_after_close(repo, "042-feat-auth")
    assert report.aborted is True
    assert "uncommitted" in report.abort_reason.lower()


def test_aborts_if_icm_main_uncommitted(tmp_path: Path):
    repo = _setup_repo_with_workspace(tmp_path, create_icm_main=True)
    # Workspace branch limpa — mas .icm-main dirty
    (repo / ".icm-main" / "dirty.txt").write_text("dirty\n", encoding="utf-8")

    report = cleanup_after_close(repo, "042-feat-auth")
    assert report.aborted is True
    assert ".icm-main" in report.abort_reason


def test_force_bypasses_uncommitted_check(tmp_path: Path):
    repo = _setup_repo_with_workspace(tmp_path)
    (repo / "dirty.txt").write_text("uncommitted\n", encoding="utf-8")

    report = cleanup_after_close(repo, "042-feat-auth", force=True)
    assert report.aborted is False


# ============================================================
# Dry-run
# ============================================================

def test_dry_run_no_filesystem_change(tmp_path: Path):
    repo = _setup_repo_with_workspace(tmp_path, create_icm_main=True)
    icm_main_before = (repo / ".icm-main").exists()
    branch_before = subprocess.run(
        ["git", "branch", "--list", "workspace/042-feat-auth"],
        cwd=str(repo), capture_output=True, text=True,
    ).stdout

    report = cleanup_after_close(repo, "042-feat-auth", dry_run=True)
    assert report.dry_run is True
    assert report.aborted is False

    # State inalterado
    assert (repo / ".icm-main").exists() == icm_main_before
    branch_after = subprocess.run(
        ["git", "branch", "--list", "workspace/042-feat-auth"],
        cwd=str(repo), capture_output=True, text=True,
    ).stdout
    assert branch_before == branch_after

    # Mas report tem ações listadas como [dry-run]
    assert any("[dry-run]" in a for a in report.actions_taken)


# ============================================================
# Cleanup full
# ============================================================

def test_cleanup_removes_workspace_branch_and_icm_main(tmp_path: Path):
    repo = _setup_repo_with_workspace(tmp_path, create_icm_main=True)

    report = cleanup_after_close(repo, "042-feat-auth")
    assert report.aborted is False, f"abort: {report.abort_reason}"

    # Workspace branch deletada
    branches = subprocess.run(
        ["git", "branch", "--list"],
        cwd=str(repo), capture_output=True, text=True,
    ).stdout
    assert "workspace/042-feat-auth" not in branches

    # .icm-main worktree removida
    assert not (repo / ".icm-main").exists()

    # project_root agora em main
    current = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=str(repo), capture_output=True, text=True,
    ).stdout.strip()
    assert current == "main"


def test_cleanup_removes_subagent_worktrees(tmp_path: Path):
    repo = _setup_repo_with_workspace(
        tmp_path, create_icm_main=True, create_subagent_wt=True,
    )

    report = cleanup_after_close(repo, "042-feat-auth")
    assert report.aborted is False

    wt_list = subprocess.run(
        ["git", "worktree", "list"],
        cwd=str(repo), capture_output=True, text=True,
    ).stdout
    assert "subagent-foo" not in wt_list
    assert ".icm-main" not in wt_list


def test_cleanup_no_icm_main_still_works(tmp_path: Path):
    """Sem .icm-main worktree (cenário legacy): cleanup só remove branch."""
    repo = _setup_repo_with_workspace(tmp_path, create_icm_main=False)

    report = cleanup_after_close(repo, "042-feat-auth")
    assert report.aborted is False, f"abort: {report.abort_reason}"

    branches = subprocess.run(
        ["git", "branch", "--list"],
        cwd=str(repo), capture_output=True, text=True,
    ).stdout
    assert "workspace/042-feat-auth" not in branches
    assert any(".icm-main/ absent" in s for s in report.actions_skipped)


# ============================================================
# Idempotência
# ============================================================

def test_idempotent_second_run_noop(tmp_path: Path):
    repo = _setup_repo_with_workspace(tmp_path, create_icm_main=True)

    report1 = cleanup_after_close(repo, "042-feat-auth")
    assert report1.aborted is False

    report2 = cleanup_after_close(repo, "042-feat-auth")
    assert report2.aborted is False
    # Segunda run deve ter mais skips ou warnings (estado já limpo)
    assert len(report2.actions_skipped) >= 2  # base_branch + .icm-main + branch


# ============================================================
# Workspace branch ausente
# ============================================================

def test_cleanup_no_workspace_branch_warns_but_continues(tmp_path: Path):
    repo = _setup_repo_with_workspace(tmp_path, create_icm_main=True)
    # Remove .icm-main primeiro pra liberar main, depois volta pra main e deleta workspace branch
    _git(["worktree", "remove", ".icm-main"], cwd=repo)
    _git(["checkout", "main"], cwd=repo)
    _git(["branch", "-D", "workspace/042-feat-auth"], cwd=repo)

    report = cleanup_after_close(repo, "042-feat-auth")
    assert report.aborted is False
    assert any("does not exist" in w for w in report.warnings)
