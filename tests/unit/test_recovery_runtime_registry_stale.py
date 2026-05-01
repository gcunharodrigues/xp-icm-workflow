"""v3.7.0 — recovery-wizard.py RUNTIME_REGISTRY_STALE detector.

Detecta workspace com `_state/runtime-registry.json` contendo entries
com PIDs mortos (processos finalizados sem unregister). Plan A: sugere
`runtime-registry.py purge-dead`. Não auto-purga (humano confirma).
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
def rw():
    return _load("recovery_wizard", "recovery-wizard.py")


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """Workspace com L1 mínimo válido."""
    ws = tmp_path / "workspaces" / "001-test"
    ws.mkdir(parents=True)
    (ws / "CLAUDE.md").write_text("# L0", encoding="utf-8")
    (ws / "CONTEXT.md").write_text(
        "---\n"
        "workspace: \"001-test\"\n"
        "stage_atual: \"04\"\n"
        "sub_stage: \"04_wave_1_in_progress\"\n"
        "status: \"IN_PROGRESS\"\n"
        "iteration: 0\n"
        "profile_base: \"app_web_frontend\"\n"
        "tier: \"development\"\n"
        "profile_effective_hash: \"abc123\"\n"
        "history: []\n"
        "last_transition:\n"
        "  from: \"03\"\n"
        "  to: \"04\"\n"
        "  at: \"2026-05-01T10:00:00Z\"\n"
        "  commit_sha: \"deadbeef\"\n"
        "---\n",
        encoding="utf-8",
    )
    return ws


def _write_registry(workspace: Path, entries: list[dict]) -> None:
    state = workspace / "_state"
    state.mkdir(exist_ok=True)
    payload = {"version": 1, "workspace": workspace.name, "entries": entries}
    (state / "runtime-registry.json").write_text(json.dumps(payload))


def test_constant_in_canonical_order(rw):
    assert hasattr(rw, "CODE_RUNTIME_REGISTRY_STALE")
    assert rw.CODE_RUNTIME_REGISTRY_STALE in rw.CANONICAL_ORDER


def test_no_registry_no_inconsistency(rw, workspace: Path):
    """Sem registry: detector não dispara."""
    # workspace fixture sem _state/
    incs = rw._detect_runtime_registry_stale(workspace)
    assert incs == []


def test_registry_with_alive_pids_no_inconsistency(rw, workspace: Path, monkeypatch):
    _write_registry(workspace, [
        {"id": "a", "kind": "dev_server", "pid": 1234,
         "registered_at": "2026-05-01T10:00:00Z"},
    ])
    monkeypatch.setattr(rw, "_pid_alive_for_registry", lambda pid: True)
    incs = rw._detect_runtime_registry_stale(workspace)
    assert incs == []


def test_registry_with_dead_pid_flags_inconsistency(rw, workspace: Path, monkeypatch):
    _write_registry(workspace, [
        {"id": "a", "kind": "dev_server", "pid": 1234,
         "registered_at": "2026-05-01T10:00:00Z"},
        {"id": "b", "kind": "background_task", "pid": 5678,
         "registered_at": "2026-05-01T10:00:00Z"},
    ])
    # 1234 morto, 5678 vivo
    monkeypatch.setattr(
        rw, "_pid_alive_for_registry",
        lambda pid: pid != 1234,
    )
    incs = rw._detect_runtime_registry_stale(workspace)
    assert len(incs) == 1
    assert incs[0].code == rw.CODE_RUNTIME_REGISTRY_STALE
    assert "1234" in incs[0].message or "1 entry" in incs[0].message
    assert incs[0].severity == "warning"
    # Plan A: command sugerido
    assert "purge-dead" in incs[0].proposed_action
