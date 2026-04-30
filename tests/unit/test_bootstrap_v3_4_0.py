"""Unit tests para funcoes novas v3.4.0 do scripts/bootstrap.py.

Cobre:
  * _ensure_base_branch_docs — cria docs/ scaffolding na base branch
  * _setup_main_worktree — cria `.icm-main/` worktree linkada
  * _install_context_hook — copia ambos hooks (context-check + icm-session-check)
  * _render_project_settings_example — renderiza settings.local.json.example

Tests usam git real em tmp_path (pequeno overhead, mas precisao alta para
operacoes de filesystem e worktree).
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SKILL_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = SKILL_ROOT / "scripts" / "bootstrap.py"

_spec = importlib.util.spec_from_file_location("bootstrap_v34", SCRIPT_PATH)
bootstrap = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules["bootstrap_v34"] = bootstrap
_spec.loader.exec_module(bootstrap)  # type: ignore[union-attr]


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def project_root_with_main(tmp_path: Path) -> Path:
    """Tmp git repo em main com 1 commit."""
    pr = tmp_path / "proj"
    pr.mkdir()
    _git(["init", "-b", "main"], pr)
    _git(["config", "user.email", "test@test"], pr)
    _git(["config", "user.name", "Test"], pr)
    (pr / "README.md").write_text("# proj\n", encoding="utf-8")
    _git(["add", "README.md"], pr)
    _git(["commit", "-m", "initial"], pr)
    return pr


# =========================================================================
# _ensure_base_branch_docs
# =========================================================================

class TestEnsureBaseBranchDocs:
    def test_creates_docs_scaffold(self, project_root_with_main: Path) -> None:
        bootstrap._ensure_base_branch_docs(project_root_with_main)
        assert (project_root_with_main / "docs" / "decisions" / ".keep").exists()
        assert (project_root_with_main / "docs" / "lessons.md").exists()
        assert (project_root_with_main / "docs" / "tech_debt.md").exists()

    def test_commits_changes_on_first_run(self, project_root_with_main: Path) -> None:
        bootstrap._ensure_base_branch_docs(project_root_with_main)
        log = _git(["log", "--oneline"], project_root_with_main).stdout
        assert "scaffold docs/" in log

    def test_idempotent_no_extra_commit(self, project_root_with_main: Path) -> None:
        bootstrap._ensure_base_branch_docs(project_root_with_main)
        first_log = _git(["log", "--oneline"], project_root_with_main).stdout
        bootstrap._ensure_base_branch_docs(project_root_with_main)
        second_log = _git(["log", "--oneline"], project_root_with_main).stdout
        assert first_log == second_log  # no new commit

    def test_preserves_existing_lessons_content(
        self, project_root_with_main: Path
    ) -> None:
        docs = project_root_with_main / "docs"
        docs.mkdir()
        (docs / "lessons.md").write_text("# Custom lessons\n", encoding="utf-8")
        bootstrap._ensure_base_branch_docs(project_root_with_main)
        assert (
            (docs / "lessons.md").read_text(encoding="utf-8")
            == "# Custom lessons\n"
        )


# =========================================================================
# _setup_main_worktree
# =========================================================================

class TestSetupMainWorktree:
    def test_creates_worktree_when_branch_free(
        self, project_root_with_main: Path
    ) -> None:
        # Switch out of main para liberar
        _git(["checkout", "-b", "feat/x"], project_root_with_main)
        bootstrap._setup_main_worktree(project_root_with_main, "main")
        assert (project_root_with_main / ".icm-main").exists()
        # worktree em main
        wt_branch = subprocess.run(
            ["git", "-C", str(project_root_with_main / ".icm-main"),
             "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        assert wt_branch == "main"

    def test_idempotent_when_worktree_exists(
        self, project_root_with_main: Path
    ) -> None:
        _git(["checkout", "-b", "feat/x"], project_root_with_main)
        bootstrap._setup_main_worktree(project_root_with_main, "main")
        # Segunda chamada nao deve raise
        bootstrap._setup_main_worktree(project_root_with_main, "main")
        # Apenas 1 worktree linkada
        listing = _git(["worktree", "list"], project_root_with_main).stdout
        assert listing.count(".icm-main") == 1

    def test_raises_when_path_exists_not_worktree(
        self, project_root_with_main: Path
    ) -> None:
        # Pre-cria diretorio que nao eh worktree
        (project_root_with_main / ".icm-main").mkdir()
        (project_root_with_main / ".icm-main" / "junk.txt").write_text("x", encoding="utf-8")
        with pytest.raises(bootstrap.BootstrapError, match="nao eh worktree"):
            bootstrap._setup_main_worktree(project_root_with_main, "main")


# =========================================================================
# _install_context_hook (deferred 1: copia ambos hooks)
# =========================================================================

class TestInstallContextHook:
    def test_copies_both_hooks(self, project_root_with_main: Path) -> None:
        ws_dir = project_root_with_main / "workspaces" / "001-test"
        ws_dir.mkdir(parents=True)
        bootstrap._install_context_hook(project_root_with_main, SKILL_ROOT, "001-test")
        hooks_dir = ws_dir / ".claude" / "hooks"
        assert (hooks_dir / "context-check.sh").exists()
        assert (hooks_dir / "icm-session-check.sh").exists()

    def test_only_context_check_registered_in_workspace_settings(
        self, project_root_with_main: Path
    ) -> None:
        ws_dir = project_root_with_main / "workspaces" / "001-test"
        ws_dir.mkdir(parents=True)
        bootstrap._install_context_hook(project_root_with_main, SKILL_ROOT, "001-test")
        settings = json.loads(
            (ws_dir / ".claude" / "settings.local.json").read_text(encoding="utf-8")
        )
        post_tool = settings["hooks"]["PostToolUse"]
        commands = [
            h["command"]
            for entry in post_tool
            for h in entry.get("hooks", [])
        ]
        # context-check eh registrado; icm-session-check NAO (vai via project_root settings)
        assert any("context-check.sh" in c for c in commands)
        assert not any("icm-session-check.sh" in c for c in commands)

    def test_workspace_hook_command_uses_claude_project_dir(
        self, project_root_with_main: Path
    ) -> None:
        """Command DEVE usar $CLAUDE_PROJECT_DIR (cwd-independent).

        Path relativo "workspaces/..." quebra quando sessão Claude Code roda
        com cwd != project_root (worktree .icm-main/, subdir). Regression:
        se voltar pra path relativo, este teste pega.
        """
        ws_dir = project_root_with_main / "workspaces" / "001-test"
        ws_dir.mkdir(parents=True)
        bootstrap._install_context_hook(project_root_with_main, SKILL_ROOT, "001-test")
        settings = json.loads(
            (ws_dir / ".claude" / "settings.local.json").read_text(encoding="utf-8")
        )
        post_tool = settings["hooks"]["PostToolUse"]
        command = post_tool[0]["hooks"][0]["command"]
        assert "$CLAUDE_PROJECT_DIR" in command, (
            f"command sem $CLAUDE_PROJECT_DIR — path relativo quebra em "
            f"cwd != project_root. Got: {command!r}"
        )
        assert "workspaces/001-test" in command
        assert command.startswith("bash ")
        # Aspas duplas em torno do path expandido (necessário pra paths com espaços)
        assert '"$CLAUDE_PROJECT_DIR/' in command

    def test_hooks_copied_have_lf_line_endings(
        self, project_root_with_main: Path
    ) -> None:
        """CRLF no shebang faz kernel exec falhar (procura interpretador
        'bash\\r'). Bootstrap DEVE normalizar templates Windows-CRLF para LF.
        Regression: se shutil.copy2 voltar, este teste pega.
        """
        ws_dir = project_root_with_main / "workspaces" / "001-test"
        ws_dir.mkdir(parents=True)
        bootstrap._install_context_hook(
            project_root_with_main, SKILL_ROOT, "001-test", tier="production"
        )
        hooks_dir = ws_dir / ".claude" / "hooks"
        for hook_name in (
            "context-check.sh",
            "icm-session-check.sh",
            "block-init-during-icm.sh",
            "block-dangerous-git.sh",  # production-tier
        ):
            hook_path = hooks_dir / hook_name
            assert hook_path.exists(), f"hook ausente: {hook_path}"
            raw = hook_path.read_bytes()
            assert b"\r\n" not in raw, (
                f"{hook_name} contém CRLF — quebra exec do shebang em Linux/Git Bash"
            )
            assert raw.startswith(b"#!"), f"{hook_name} sem shebang"


# =========================================================================
# _render_project_settings_example (deferred 2)
# =========================================================================

class TestRenderProjectSettingsExample:
    def test_renders_with_workspace_substituted(
        self, project_root_with_main: Path
    ) -> None:
        bootstrap._render_project_settings_example(
            project_root_with_main, SKILL_ROOT, "042-foo"
        )
        out = project_root_with_main / ".claude" / "settings.local.json.example"
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "042-foo" in content
        assert "<NNN-slug>" not in content

    def test_overwrites_on_re_render(
        self, project_root_with_main: Path
    ) -> None:
        bootstrap._render_project_settings_example(
            project_root_with_main, SKILL_ROOT, "001-first"
        )
        bootstrap._render_project_settings_example(
            project_root_with_main, SKILL_ROOT, "002-second"
        )
        content = (
            project_root_with_main / ".claude" / "settings.local.json.example"
        ).read_text(encoding="utf-8")
        assert "002-second" in content
        assert "001-first" not in content
