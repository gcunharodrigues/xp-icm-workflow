"""Unit tests para scripts/migrate-v3.3-to-v3.4.py.

Cobre detect/idempotencia/update-paths em workspaces tmp.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

SKILL_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = SKILL_ROOT / "scripts" / "migrate-v3.3-to-v3.4.py"

_spec = importlib.util.spec_from_file_location("migrate_v34", SCRIPT)
assert _spec is not None and _spec.loader is not None
migrate = importlib.util.module_from_spec(_spec)
sys.modules["migrate_v34"] = migrate
_spec.loader.exec_module(migrate)


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _build_v33_workspace(project_root: Path, ws_id: str = "001-legacy") -> Path:
    """Cria workspace v3.3.x: L0 com icm_skill_version v3.3.0 + L2 com paths antigos."""
    ws = project_root / "workspaces" / ws_id
    ws.mkdir(parents=True)
    pr_str = str(project_root).replace("\\", "/")
    (ws / "CLAUDE.md").write_text(
        f"""---
layer: L0
workspace: "{ws_id}"
profile: "cli_tool"
tier: "experimental"
project_root: "{pr_str}"
base_branch: "main"
workspace_branch: "workspace/{ws_id}"
icm_skill_version: "3.3.0"
---

# Workspace {ws_id}

ADRs em `{pr_str}/docs/decisions/`.
""",
        encoding="utf-8",
    )
    (ws / "stages").mkdir()
    s02 = ws / "stages" / "02_design"
    s02.mkdir()
    (s02 / "CONTEXT.md").write_text(
        f"# Stage 02\n\nLer ADRs em `{pr_str}/docs/decisions/0001-foo.md`.\n",
        encoding="utf-8",
    )
    return ws


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    pr = tmp_path / "proj"
    pr.mkdir()
    _git(["init", "-b", "main"], pr)
    _git(["config", "user.email", "t@t"], pr)
    _git(["config", "user.name", "T"], pr)
    (pr / "README.md").write_text("x\n", encoding="utf-8")
    _git(["add", "README.md"], pr)
    _git(["commit", "-m", "initial"], pr)
    return pr


# =========================================================================
# detect_workspace_version + is_v3_3_x
# =========================================================================

class TestDetectVersion:
    def test_detects_v3_3_0(self, tmp_path: Path) -> None:
        cm = tmp_path / "CLAUDE.md"
        cm.write_text('---\nicm_skill_version: "3.3.0"\n---\n', encoding="utf-8")
        assert migrate.detect_workspace_version(cm) == "3.3.0"

    def test_returns_none_when_field_absent(self, tmp_path: Path) -> None:
        cm = tmp_path / "CLAUDE.md"
        cm.write_text("---\nfoo: bar\n---\n", encoding="utf-8")
        assert migrate.detect_workspace_version(cm) is None

    def test_returns_none_when_file_absent(self, tmp_path: Path) -> None:
        assert migrate.detect_workspace_version(tmp_path / "missing.md") is None

    @pytest.mark.parametrize("ver,expected", [
        ("3.3.0", True),
        ("3.3.5", True),
        ("v3.3.0", True),
        ("3.4.0", False),
        ("3.4.1", False),
        ("v3.4.0", False),
        (None, True),  # workspaces antigos sem campo
    ])
    def test_is_v3_3_x(self, ver: str | None, expected: bool) -> None:
        assert migrate.is_v3_3_x(ver) is expected


# =========================================================================
# discover_workspaces
# =========================================================================

class TestDiscoverWorkspaces:
    def test_discovers_only_with_claude_md(self, project_root: Path) -> None:
        _build_v33_workspace(project_root, "001-foo")
        # Dir vazia (sem CLAUDE.md) deve ser ignorada
        (project_root / "workspaces" / "999-empty").mkdir()
        found = migrate.discover_workspaces(project_root)
        names = [w.name for w in found]
        assert "001-foo" in names
        assert "999-empty" not in names

    def test_returns_empty_when_no_workspaces_dir(self, project_root: Path) -> None:
        assert migrate.discover_workspaces(project_root) == []


# =========================================================================
# update_l0_version + update_gitignore + setup_worktree
# =========================================================================

class TestUpdateL0Version:
    def test_bumps_version(self, project_root: Path) -> None:
        ws = _build_v33_workspace(project_root)
        changed = migrate.update_l0_version(ws / "CLAUDE.md", dry_run=False)
        assert changed
        assert 'icm_skill_version: "3.4.1"' in (ws / "CLAUDE.md").read_text(encoding="utf-8")

    def test_dry_run_no_write(self, project_root: Path) -> None:
        ws = _build_v33_workspace(project_root)
        before = (ws / "CLAUDE.md").read_text(encoding="utf-8")
        changed = migrate.update_l0_version(ws / "CLAUDE.md", dry_run=True)
        assert changed
        assert (ws / "CLAUDE.md").read_text(encoding="utf-8") == before

    def test_idempotent_when_already_target(self, project_root: Path) -> None:
        ws = _build_v33_workspace(project_root)
        migrate.update_l0_version(ws / "CLAUDE.md", dry_run=False)
        # 2a chamada
        changed = migrate.update_l0_version(ws / "CLAUDE.md", dry_run=False)
        assert not changed


class TestUpdateGitignore:
    def test_adds_when_absent(self, project_root: Path) -> None:
        (project_root / ".gitignore").write_text("foo\n", encoding="utf-8")
        changed = migrate.update_gitignore(project_root, dry_run=False)
        assert changed
        content = (project_root / ".gitignore").read_text(encoding="utf-8")
        assert ".icm-main/" in content

    def test_idempotent(self, project_root: Path) -> None:
        (project_root / ".gitignore").write_text(".icm-main/\n", encoding="utf-8")
        assert not migrate.update_gitignore(project_root, dry_run=False)


class TestSetupWorktree:
    def test_creates_worktree_when_absent(self, project_root: Path) -> None:
        _git(["checkout", "-b", "workspace/001-legacy"], project_root)
        created = migrate.setup_worktree(project_root, "main", dry_run=False)
        assert created
        assert (project_root / ".icm-main").exists()

    def test_idempotent_when_worktree_exists(self, project_root: Path) -> None:
        _git(["checkout", "-b", "workspace/001-legacy"], project_root)
        migrate.setup_worktree(project_root, "main", dry_run=False)
        # 2a chamada
        assert not migrate.setup_worktree(project_root, "main", dry_run=False)


# =========================================================================
# update_paths_in_file
# =========================================================================

class TestUpdatePathsInFile:
    def test_replaces_docs_path(self, project_root: Path) -> None:
        ws = _build_v33_workspace(project_root)
        ctx = ws / "stages" / "02_design" / "CONTEXT.md"
        changed = migrate.update_paths_in_file(ctx, project_root, dry_run=False)
        assert changed
        text = ctx.read_text(encoding="utf-8")
        pr_str = str(project_root).replace("\\", "/")
        assert f"{pr_str}/.icm-main/docs/" in text
        assert f"{pr_str}/docs/" not in text

    def test_idempotent_after_replace(self, project_root: Path) -> None:
        ws = _build_v33_workspace(project_root)
        ctx = ws / "stages" / "02_design" / "CONTEXT.md"
        migrate.update_paths_in_file(ctx, project_root, dry_run=False)
        # 2a chamada
        assert not migrate.update_paths_in_file(ctx, project_root, dry_run=False)


# =========================================================================
# migrate_project (end-to-end)
# =========================================================================

class TestMigrateProject:
    def test_full_migration_creates_worktree_and_bumps_version(
        self, project_root: Path
    ) -> None:
        _build_v33_workspace(project_root)
        _git(["checkout", "-b", "workspace/001-legacy"], project_root)
        # Bootstrap-como teria deixado: workspace branch ativo, sem .icm-main, L0 v3.3.0
        summary = migrate.migrate_project(project_root, update_paths=True)
        assert summary["_global"]["worktree_setup"]
        assert (project_root / ".icm-main").exists()
        assert summary["001-legacy"]["l0_version_bumped"]
        assert 'icm_skill_version: "3.4.1"' in (
            project_root / "workspaces" / "001-legacy" / "CLAUDE.md"
        ).read_text(encoding="utf-8")

    def test_skips_v3_4_workspace(self, project_root: Path) -> None:
        ws = _build_v33_workspace(project_root)
        # Forca v3.4.0 no L0
        cm = ws / "CLAUDE.md"
        cm.write_text(
            cm.read_text(encoding="utf-8").replace('"3.3.0"', '"3.4.0"'),
            encoding="utf-8",
        )
        _git(["checkout", "-b", "workspace/001-legacy"], project_root)
        summary = migrate.migrate_project(project_root)
        assert summary["001-legacy"]["skipped"]

    def test_dry_run_no_changes(self, project_root: Path) -> None:
        _build_v33_workspace(project_root)
        _git(["checkout", "-b", "workspace/001-legacy"], project_root)
        before_l0 = (
            project_root / "workspaces" / "001-legacy" / "CLAUDE.md"
        ).read_text(encoding="utf-8")
        migrate.migrate_project(project_root, dry_run=True)
        after_l0 = (
            project_root / "workspaces" / "001-legacy" / "CLAUDE.md"
        ).read_text(encoding="utf-8")
        assert before_l0 == after_l0
        assert not (project_root / ".icm-main").exists()
