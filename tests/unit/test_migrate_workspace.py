"""v3.7.0 — migrate-workspace.py orquestrador encadeado.

Escopo:
- Detect versão atual via L0 frontmatter `icm_skill_version`.
- Encadeia migrations: v3.3 → v3.4 → v3.5 → v3.6 → v3.7.
- Floor v3.3.0 (beta1/beta2 explicitamente unsupported).
- Backup automático em .icm-migration-backup/<timestamp>/<workspace>/.
- Idempotente: re-rodar não reaplica steps já-migrados.
- Status-aware: COMPLETED/AWAITING auto-prompt; IN_PROGRESS warning-only.

v3.6 → v3.7 mudanças aplicadas:
  - L0 bump icm_skill_version
  - Add `_state/` dir
  - Migrate `.icm-main/.dev-server.pid` → runtime-registry (se PID alive)
  - Re-render L2 stage 08 (TODO — escopo F3 quando template existe)
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPT_DIR / filename)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def mw():
    return _load("migrate_workspace", "migrate-workspace.py")


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """Workspace v3.6.0 mínimo."""
    ws = tmp_path / "workspaces" / "001-test"
    ws.mkdir(parents=True)
    (ws / "CLAUDE.md").write_text(
        "---\n"
        "layer: L0\n"
        "workspace: \"001-test\"\n"
        "profile: \"app_web_frontend\"\n"
        "tier: \"development\"\n"
        "icm_skill_version: \"3.6.0\"\n"
        "---\n# L0\n",
        encoding="utf-8",
    )
    (ws / "CONTEXT.md").write_text(
        "---\n"
        "workspace: \"001-test\"\n"
        "stage_atual: \"08\"\n"
        "sub_stage: \"08_in_progress\"\n"
        "status: \"COMPLETED_AWAITING_HUMAN\"\n"
        "iteration: 0\n"
        "---\n",
        encoding="utf-8",
    )
    return ws


# ============================================================
# Version detection
# ============================================================

def test_detect_version_from_l0(mw, workspace: Path):
    v = mw.detect_workspace_version(workspace)
    assert v == "3.6.0"


def test_detect_version_returns_none_if_l0_missing(mw, tmp_path: Path):
    ws = tmp_path / "workspaces" / "999-orphan"
    ws.mkdir(parents=True)
    assert mw.detect_workspace_version(ws) is None


def test_detect_version_floor_v3_3_0(mw, tmp_path: Path):
    """Workspaces sem icm_skill_version (beta1/beta2): retorna None."""
    ws = tmp_path / "workspaces" / "999-beta"
    ws.mkdir(parents=True)
    (ws / "CLAUDE.md").write_text("---\nworkspace: \"999\"\n---\n")
    v = mw.detect_workspace_version(ws)
    assert v is None or v == "unknown"


# ============================================================
# Migration plan: which steps apply
# ============================================================

def test_plan_migration_from_3_6_0_to_3_7_0(mw):
    plan = mw.plan_migration("3.6.0", "3.7.0")
    assert plan == ["3.6.0->3.7.0"]


def test_plan_migration_from_3_3_0_to_3_7_0(mw):
    plan = mw.plan_migration("3.3.0", "3.7.0")
    assert plan == [
        "3.3.0->3.4.0",
        "3.4.0->3.5.0",
        "3.5.0->3.6.0",
        "3.6.0->3.7.0",
    ]


def test_plan_migration_from_3_7_0_to_3_7_2(mw):
    """v3.7.1 colapsada em v3.7.2 — step direto."""
    plan = mw.plan_migration("3.7.0", "3.7.2")
    assert plan == ["3.7.0->3.7.2"]


def test_plan_migration_from_3_3_0_to_canonical(mw):
    """Cadeia full do floor até CURRENT_SKILL_VERSION."""
    plan = mw.plan_migration("3.3.0", mw.CURRENT_SKILL_VERSION)
    assert plan == [
        "3.3.0->3.4.0",
        "3.4.0->3.5.0",
        "3.5.0->3.6.0",
        "3.6.0->3.7.0",
        "3.7.0->3.7.2",
        "3.7.2->3.8.0",
        "3.8.0->3.9.0",
    ]


def test_current_skill_version_matches_bootstrap(mw):
    """CURRENT_SKILL_VERSION deve refletir scripts/bootstrap.py SKILL_VERSION."""
    bs = _load("bootstrap_for_drift", "bootstrap.py")
    assert mw.CURRENT_SKILL_VERSION == bs.SKILL_VERSION


def test_plan_migration_below_floor_raises(mw):
    """v3.0/v3.2 abaixo do floor v3.3.0 → unsupported."""
    with pytest.raises(mw.MigrationError, match="floor"):
        mw.plan_migration("3.0.0-beta1", "3.7.0")


def test_plan_migration_already_at_target(mw):
    plan = mw.plan_migration("3.7.0", "3.7.0")
    assert plan == []


def test_plan_migration_at_canonical_target_noop(mw):
    """Workspace já em CURRENT_SKILL_VERSION: plan vazio."""
    canonical = mw.CURRENT_SKILL_VERSION
    plan = mw.plan_migration(canonical, canonical)
    assert plan == []


# ============================================================
# Backup
# ============================================================

def test_backup_creates_timestamped_copy(mw, workspace: Path):
    backup_dir = mw.backup_workspace(workspace)
    assert backup_dir.is_dir()
    assert ".icm-migration-backup" in str(backup_dir)
    # Original L0 ainda existe + backup tem cópia
    assert (workspace / "CLAUDE.md").is_file()
    assert (backup_dir / "CLAUDE.md").is_file()


# ============================================================
# v3.6.0 → v3.7.0 step
# ============================================================

def test_migrate_3_6_to_3_7_bumps_l0_version(mw, workspace: Path):
    mw.migrate_3_6_to_3_7(workspace, project_root=workspace.parent.parent)
    text = (workspace / "CLAUDE.md").read_text(encoding="utf-8")
    assert "icm_skill_version: \"3.7.0\"" in text


def test_migrate_3_6_to_3_7_creates_state_dir(mw, workspace: Path):
    mw.migrate_3_6_to_3_7(workspace, project_root=workspace.parent.parent)
    assert (workspace / "_state").is_dir()


def test_migrate_3_6_to_3_7_migrates_legacy_pid(mw, workspace: Path, monkeypatch):
    """Se .icm-main/.dev-server.pid existe + PID vivo: registra no registry."""
    project_root = workspace.parent.parent
    icm_main = project_root / ".icm-main"
    icm_main.mkdir()
    (icm_main / ".dev-server.pid").write_text("99999")

    # Mock _is_pid_alive: 99999 vivo
    rr = _load("runtime_registry_for_test", "runtime-registry.py")
    monkeypatch.setattr(rr, "_is_pid_alive", lambda pid: pid == 99999)
    sys.modules["runtime_registry"] = rr

    mw.migrate_3_6_to_3_7(workspace, project_root=project_root)

    # Registry tem entry, PID file removido
    registry_path = workspace / "_state" / "runtime-registry.json"
    assert registry_path.is_file()
    data = json.loads(registry_path.read_text())
    assert any(e.get("pid") == 99999 and e.get("kind") == "dev_server"
               for e in data["entries"])
    assert not (icm_main / ".dev-server.pid").exists()


def test_migrate_3_6_to_3_7_skips_dead_legacy_pid(mw, workspace: Path, monkeypatch):
    """PID file legacy mas processo morto: NÃO migra (cleanup direto)."""
    project_root = workspace.parent.parent
    icm_main = project_root / ".icm-main"
    icm_main.mkdir()
    (icm_main / ".dev-server.pid").write_text("88888")

    rr = _load("runtime_registry_for_test_dead", "runtime-registry.py")
    monkeypatch.setattr(rr, "_is_pid_alive", lambda pid: False)
    sys.modules["runtime_registry"] = rr

    mw.migrate_3_6_to_3_7(workspace, project_root=project_root)

    registry_path = workspace / "_state" / "runtime-registry.json"
    if registry_path.is_file():
        data = json.loads(registry_path.read_text())
        assert not any(e.get("pid") == 88888 for e in data["entries"])
    # PID file removido
    assert not (icm_main / ".dev-server.pid").exists()


def test_migrate_idempotent(mw, workspace: Path):
    """Rodar migration 2x = mesma versão final, sem duplicar entries."""
    project_root = workspace.parent.parent
    mw.migrate_3_6_to_3_7(workspace, project_root=project_root)
    v1 = mw.detect_workspace_version(workspace)
    mw.migrate_3_6_to_3_7(workspace, project_root=project_root)
    v2 = mw.detect_workspace_version(workspace)
    assert v1 == v2 == "3.7.0"


# ============================================================
# v3.7.0 → v3.7.2 step
# ============================================================

def test_migrate_3_7_0_to_3_7_2_bumps_l0_version(mw, tmp_path: Path):
    ws = tmp_path / "workspaces" / "010-test"
    ws.mkdir(parents=True)
    (ws / "CLAUDE.md").write_text(
        "---\nicm_skill_version: \"3.7.0\"\n---\n", encoding="utf-8",
    )
    mw.migrate_3_7_0_to_3_7_2(ws, project_root=ws.parent.parent)
    text = (ws / "CLAUDE.md").read_text(encoding="utf-8")
    assert "icm_skill_version: \"3.7.2\"" in text


def test_migrate_3_7_0_to_3_7_2_idempotent(mw, tmp_path: Path):
    ws = tmp_path / "workspaces" / "011-test"
    ws.mkdir(parents=True)
    (ws / "CLAUDE.md").write_text(
        "---\nicm_skill_version: \"3.7.0\"\n---\n", encoding="utf-8",
    )
    project_root = ws.parent.parent
    mw.migrate_3_7_0_to_3_7_2(ws, project_root=project_root)
    mw.migrate_3_7_0_to_3_7_2(ws, project_root=project_root)
    assert mw.detect_workspace_version(ws) == "3.7.2"


def test_step_functions_dispatcher_has_3_7_0_to_3_7_2(mw):
    assert "3.7.0->3.7.2" in mw.STEP_FUNCTIONS
    assert mw.STEP_FUNCTIONS["3.7.0->3.7.2"] is mw.migrate_3_7_0_to_3_7_2


# ============================================================
# v3.7.2 → v3.8.0 step
# ============================================================

def test_migrate_3_7_2_to_3_8_0_bumps_l0_version(mw, tmp_path: Path):
    ws = tmp_path / "workspaces" / "012-test"
    ws.mkdir(parents=True)
    (ws / "CLAUDE.md").write_text(
        "---\nicm_skill_version: \"3.7.2\"\n---\n", encoding="utf-8",
    )
    mw.migrate_3_7_2_to_3_8_0(ws, project_root=ws.parent.parent)
    text = (ws / "CLAUDE.md").read_text(encoding="utf-8")
    assert "icm_skill_version: \"3.8.0\"" in text


def test_migrate_3_7_2_to_3_8_0_idempotent(mw, tmp_path: Path):
    ws = tmp_path / "workspaces" / "013-test"
    ws.mkdir(parents=True)
    (ws / "CLAUDE.md").write_text(
        "---\nicm_skill_version: \"3.7.2\"\n---\n", encoding="utf-8",
    )
    project_root = ws.parent.parent
    mw.migrate_3_7_2_to_3_8_0(ws, project_root=project_root)
    mw.migrate_3_7_2_to_3_8_0(ws, project_root=project_root)
    assert mw.detect_workspace_version(ws) == "3.8.0"


def test_step_functions_dispatcher_has_3_7_2_to_3_8_0(mw):
    assert "3.7.2->3.8.0" in mw.STEP_FUNCTIONS
    assert mw.STEP_FUNCTIONS["3.7.2->3.8.0"] is mw.migrate_3_7_2_to_3_8_0


# ============================================================
# Trigger heuristic (auto-prompt vs warning)
# ============================================================

def test_trigger_mode_completed_auto_prompt(mw, workspace: Path):
    """Status COMPLETED_AWAITING_HUMAN → trigger 'auto-prompt'."""
    mode = mw.detect_trigger_mode(workspace)
    assert mode == "auto-prompt"


def test_trigger_mode_in_progress_warning_only(mw, tmp_path: Path):
    ws = tmp_path / "workspaces" / "002-busy"
    ws.mkdir(parents=True)
    (ws / "CLAUDE.md").write_text(
        "---\nicm_skill_version: \"3.6.0\"\n---\n", encoding="utf-8",
    )
    (ws / "CONTEXT.md").write_text(
        "---\nstatus: \"IN_PROGRESS\"\n---\n", encoding="utf-8",
    )
    mode = mw.detect_trigger_mode(ws)
    assert mode == "warning-only"


def test_step_functions_includes_v3_8_0(mw):
    """Dispatcher must register the v3.8.0 step with the canonical 'from->to' string key."""
    assert "3.7.2->3.8.0" in mw.STEP_FUNCTIONS
    assert mw.STEP_FUNCTIONS["3.7.2->3.8.0"] is mw.migrate_3_7_2_to_3_8_0


def test_step_functions_includes_v3_9_0(mw):
    """Dispatcher must register the v3.9.0 step with the canonical 'from->to' string key."""
    assert "3.8.0->3.9.0" in mw.STEP_FUNCTIONS
    assert mw.STEP_FUNCTIONS["3.8.0->3.9.0"] is mw.migrate_3_8_0_to_3_9_0


def test_supported_versions_ends_with_3_9_0(mw):
    """Tuple must include 3.9.0 as the last entry."""
    assert mw.SUPPORTED_VERSIONS[-1] == "3.9.0"


def test_supported_versions_includes_3_8_0(mw):
    """v3.8.0 should still be present (intermediate step)."""
    assert "3.8.0" in mw.SUPPORTED_VERSIONS


def test_migrate_3_8_0_to_3_9_0_smoke(mw, tmp_path: Path):
    """Smoke: bump-only migration produz L0 com nova versão."""
    ws = tmp_path / "001-test"
    ws.mkdir()
    (ws / "CLAUDE.md").write_text(
        '---\nicm_skill_version: "3.8.0"\n---\n# Workspace 001\n',
        encoding="utf-8",
    )
    mw.migrate_3_8_0_to_3_9_0(ws, project_root=tmp_path)
    text = (ws / "CLAUDE.md").read_text(encoding="utf-8")
    assert 'icm_skill_version: "3.9.0"' in text


def test_migrate_3_8_0_to_3_9_0_idempotent(mw, tmp_path: Path):
    """Aplicar migrate sobre workspace já em 3.9.0 não deve quebrar nem alterar version."""
    ws = tmp_path / "002-idempotent"
    ws.mkdir()
    (ws / "CLAUDE.md").write_text(
        '---\nicm_skill_version: "3.9.0"\n---\n# Workspace 002\n',
        encoding="utf-8",
    )
    mw.migrate_3_8_0_to_3_9_0(ws, project_root=tmp_path)
    text = (ws / "CLAUDE.md").read_text(encoding="utf-8")
    assert 'icm_skill_version: "3.9.0"' in text
