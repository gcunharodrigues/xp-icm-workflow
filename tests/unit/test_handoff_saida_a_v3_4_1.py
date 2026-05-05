"""Tests v3.4.1: handoff saída A migra CLAUDE.md root para base branch.

Cobre `_persist_claude_md_to_base_via_worktree`:
  * Skip silently se `.icm-main/` ausente (projeto pre-v3.4.0).
  * Copia CLAUDE.md para `.icm-main/CLAUDE.md` + commit base branch.
  * Idempotente: re-rodar com mesmo conteudo nao gera commit extra.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

SKILL_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = SKILL_ROOT / "scripts" / "handoff.py"

_spec = importlib.util.spec_from_file_location("handoff_v341", SCRIPT)
assert _spec is not None and _spec.loader is not None
handoff = importlib.util.module_from_spec(_spec)
sys.modules["handoff_v341"] = handoff
_spec.loader.exec_module(handoff)


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True, capture_output=True, text=True,
    )


@pytest.fixture
def project_with_worktree(tmp_path: Path) -> Path:
    """Tmp project_root com workspace branch ativo + .icm-main worktree em main."""
    pr = tmp_path / "proj"
    pr.mkdir()
    _git(["init", "-b", "main"], pr)
    _git(["config", "user.email", "t@t"], pr)
    _git(["config", "user.name", "T"], pr)
    (pr / "README.md").write_text("x\n", encoding="utf-8")
    _git(["add", "README.md"], pr)
    _git(["commit", "-m", "initial"], pr)
    _git(["checkout", "-b", "workspace/001-test"], pr)
    _git(["worktree", "add", ".icm-main", "main"], pr)
    return pr


# =========================================================================
# _persist_claude_md_to_base_via_worktree
# =========================================================================

class TestPersistClaudeMdToBase:
    def test_silent_noop_when_no_worktree(self, tmp_path: Path) -> None:
        pr = tmp_path / "proj"
        pr.mkdir()
        cm = pr / "CLAUDE.md"
        cm.write_text("# idle\n", encoding="utf-8")
        # Sem .icm-main/ — deve silently no-op
        handoff._persist_claude_md_to_base_via_worktree(pr, cm)
        # Nada deveria ter sido criado
        assert not (pr / ".icm-main").exists()

    def test_copies_and_commits_when_worktree_exists(
        self, project_with_worktree: Path
    ) -> None:
        pr = project_with_worktree
        cm = pr / "CLAUDE.md"
        cm.write_text("# Idle workspace\n", encoding="utf-8")

        handoff._persist_claude_md_to_base_via_worktree(pr, cm)

        wt_cm = pr / ".icm-main" / "CLAUDE.md"
        assert wt_cm.exists()
        assert wt_cm.read_text(encoding="utf-8") == "# Idle workspace\n"

        # Commit em main via worktree
        log = _git(["log", "--oneline", "main"], pr).stdout
        assert "exit A handoff" in log

    def test_idempotent_same_content_no_extra_commit(
        self, project_with_worktree: Path
    ) -> None:
        pr = project_with_worktree
        cm = pr / "CLAUDE.md"
        cm.write_text("# Idle\n", encoding="utf-8")
        handoff._persist_claude_md_to_base_via_worktree(pr, cm)
        first_log = _git(["log", "--oneline", "main"], pr).stdout

        # 2a chamada com mesmo conteudo
        handoff._persist_claude_md_to_base_via_worktree(pr, cm)
        second_log = _git(["log", "--oneline", "main"], pr).stdout
        assert first_log == second_log


# =========================================================================
# deactivate_project_claude_md (saída A end-to-end)
# =========================================================================

class TestDeactivateProjectClaudeMd:
    def test_writes_idle_region_to_root_and_base(
        self, project_with_worktree: Path
    ) -> None:
        pr = project_with_worktree
        # Pre-cria CLAUDE.md root com região ICM
        (pr / "CLAUDE.md").write_text(
            "# Project\n\n<!-- ICM-START -->\n"
            "(blocos antigos)\n"
            "<!-- ICM-END -->\n",
            encoding="utf-8",
        )

        result = handoff.deactivate_project_claude_md(pr, closed_at="2026-04-29T10:00:00Z")
        assert result == pr / "CLAUDE.md"

        # Root tem idle
        root_text = (pr / "CLAUDE.md").read_text(encoding="utf-8")
        assert "ICM-START" in root_text
        assert "(blocos antigos)" not in root_text

        # Worktree base tambem persistiu
        wt_text = (pr / ".icm-main" / "CLAUDE.md").read_text(encoding="utf-8")
        assert wt_text == root_text
