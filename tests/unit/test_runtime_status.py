"""v3.7.0 — runtime-status.py: cross-platform checklist runtime cleanup.

Consumido por L2 stage 08 entry hook (saída A/B/C step 0). Verifica 6
categorias de side-effects:
  1. dev_servers      — runtime-registry entries kind=dev_server alive
  2. background_tasks — kind=background_task alive
  3. docker           — containers + volumes label icm-workspace=NNN
  4. wave_branches    — git branches `wave-NNN-N/<task>` órfãs
  5. working_tree     — git status --short (workspace branch)
  6. untracked        — `.icm-main/` dirty + git ls-files --others

Output JSON estruturado pra ICM agent consumir; text humano pra terminal.
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
def rs():
    return _load("runtime_status", "runtime-status.py")


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "workspaces" / "001-test"
    ws.mkdir(parents=True)
    return ws


# ============================================================
# CATEGORIES enum + aggregator
# ============================================================

def test_categories_constant(rs):
    assert "dev_servers" in rs.CATEGORIES
    assert "background_tasks" in rs.CATEGORIES
    assert "docker" in rs.CATEGORIES
    assert "wave_branches" in rs.CATEGORIES
    assert "working_tree" in rs.CATEGORIES
    assert "untracked" in rs.CATEGORIES


def test_check_all_returns_dict_per_category(rs, workspace: Path, monkeypatch):
    """check_all retorna dict {category: {clean: bool, items: list, summary}}."""
    # Stub each check fn to avoid touching real git/docker
    monkeypatch.setattr(rs, "check_dev_servers",
                        lambda ws: {"clean": True, "items": [], "summary": "no dev servers"})
    monkeypatch.setattr(rs, "check_background_tasks",
                        lambda ws: {"clean": True, "items": [], "summary": "none"})
    monkeypatch.setattr(rs, "check_docker",
                        lambda ws: {"clean": True, "items": [], "summary": "none"})
    monkeypatch.setattr(rs, "check_wave_branches",
                        lambda ws, project_root: {"clean": True, "items": [],
                                                  "summary": "no wave branches"})
    monkeypatch.setattr(rs, "check_working_tree",
                        lambda project_root: {"clean": True, "items": [],
                                              "summary": "clean"})
    monkeypatch.setattr(rs, "check_untracked",
                        lambda project_root: {"clean": True, "items": [],
                                              "summary": "none"})

    result = rs.check_all(workspace, project_root=workspace.parent.parent)
    assert set(result.keys()) == set(rs.CATEGORIES)
    for cat, payload in result.items():
        assert "clean" in payload
        assert "items" in payload
        assert "summary" in payload


# ============================================================
# Per-category integration with runtime-registry
# ============================================================

def test_check_dev_servers_uses_registry(rs, workspace: Path, monkeypatch):
    """check_dev_servers consulta runtime-registry kind=dev_server."""
    state_dir = workspace / "_state"
    state_dir.mkdir()
    payload = {
        "version": 1,
        "workspace": "001-test",
        "entries": [
            {"id": "a", "kind": "dev_server", "pid": 12345, "port": 5173,
             "registered_at": "2026-05-01T..."},
            {"id": "b", "kind": "background_task", "pid": 999,
             "registered_at": "2026-05-01T..."},
        ],
    }
    (state_dir / "runtime-registry.json").write_text(json.dumps(payload))
    monkeypatch.setattr(rs, "_pid_alive", lambda pid: True)

    result = rs.check_dev_servers(workspace)
    assert result["clean"] is False
    assert len(result["items"]) == 1
    assert result["items"][0]["pid"] == 12345


def test_check_background_tasks_uses_registry(rs, workspace: Path, monkeypatch):
    state_dir = workspace / "_state"
    state_dir.mkdir()
    payload = {
        "version": 1,
        "workspace": "001-test",
        "entries": [
            {"id": "x", "kind": "background_task", "pid": 7777,
             "registered_at": "2026-05-01T..."},
        ],
    }
    (state_dir / "runtime-registry.json").write_text(json.dumps(payload))
    monkeypatch.setattr(rs, "_pid_alive", lambda pid: True)
    result = rs.check_background_tasks(workspace)
    assert result["clean"] is False
    assert len(result["items"]) == 1


def test_check_dev_servers_clean_when_pid_dead(rs, workspace: Path, monkeypatch):
    """Dead PID = clean (registry stale, but no active side-effect)."""
    state_dir = workspace / "_state"
    state_dir.mkdir()
    payload = {
        "version": 1, "workspace": "001-test",
        "entries": [{"id": "a", "kind": "dev_server", "pid": 1,
                     "registered_at": "x"}],
    }
    (state_dir / "runtime-registry.json").write_text(json.dumps(payload))
    monkeypatch.setattr(rs, "_pid_alive", lambda pid: False)
    result = rs.check_dev_servers(workspace)
    assert result["clean"] is True


# ============================================================
# CLI
# ============================================================

def test_cli_check_all_json_output(rs, workspace: Path, monkeypatch, capsys):
    for name in ("check_dev_servers", "check_background_tasks",
                 "check_docker"):
        monkeypatch.setattr(rs, name,
                            lambda ws: {"clean": True, "items": [], "summary": "ok"})
    monkeypatch.setattr(rs, "check_wave_branches",
                        lambda ws, project_root: {"clean": True, "items": [],
                                                  "summary": "ok"})
    monkeypatch.setattr(rs, "check_working_tree",
                        lambda project_root: {"clean": True, "items": [],
                                              "summary": "ok"})
    monkeypatch.setattr(rs, "check_untracked",
                        lambda project_root: {"clean": True, "items": [],
                                              "summary": "ok"})

    rc = rs.main([
        "--workspace-root", str(workspace),
        "--project-root", str(workspace.parent.parent),
        "--format", "json",
    ])
    assert rc == 0
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert "dev_servers" in parsed


def test_cli_check_specific_category(rs, workspace: Path, monkeypatch, capsys):
    monkeypatch.setattr(rs, "check_dev_servers",
                        lambda ws: {"clean": True, "items": [], "summary": "ok"})
    rc = rs.main([
        "--workspace-root", str(workspace),
        "--project-root", str(workspace.parent.parent),
        "--check", "dev_servers",
        "--format", "json",
    ])
    assert rc == 0
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert list(parsed.keys()) == ["dev_servers"]


def test_cli_exit_code_non_zero_if_dirty(rs, workspace: Path, monkeypatch):
    """Exit code 1 if any category is not clean. Useful for bash hook gating."""
    monkeypatch.setattr(rs, "check_dev_servers",
                        lambda ws: {"clean": False, "items": [{"pid": 1}],
                                    "summary": "1 dev server alive"})
    monkeypatch.setattr(rs, "check_background_tasks",
                        lambda ws: {"clean": True, "items": [], "summary": "ok"})
    monkeypatch.setattr(rs, "check_docker",
                        lambda ws: {"clean": True, "items": [], "summary": "ok"})
    monkeypatch.setattr(rs, "check_wave_branches",
                        lambda ws, project_root: {"clean": True, "items": [],
                                                  "summary": "ok"})
    monkeypatch.setattr(rs, "check_working_tree",
                        lambda project_root: {"clean": True, "items": [],
                                              "summary": "ok"})
    monkeypatch.setattr(rs, "check_untracked",
                        lambda project_root: {"clean": True, "items": [],
                                              "summary": "ok"})
    rc = rs.main([
        "--workspace-root", str(workspace),
        "--project-root", str(workspace.parent.parent),
        "--format", "json",
        "--exit-code",
    ])
    assert rc == 1
