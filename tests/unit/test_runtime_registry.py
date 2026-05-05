"""v3.7.0 — runtime-registry.py CRUD + cleanup detection.

Schema: workspaces/NNN-slug/_state/runtime-registry.json (gitignored).

Entries shape:
    {
      "version": 1,
      "workspace": "001-001-saas-psicologo-mvp",
      "entries": [
        {
          "id": "<uuid4>",
          "kind": "dev_server" | "background_task" | "docker_container" | ...,
          "pid": 12345,
          "port": 5173,                   # opcional
          "cmd": "npm run dev",           # opcional
          "registered_at": "2026-05-01T...",
          "metadata": {...}               # opcional, kind-specific
        }
      ]
    }

Helpers reusam `_is_pid_alive`/`_is_port_listening` de recovery-wizard.py.
Tests written BEFORE implementation (TDD red phase).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

# Import via _ alias (script tem hífen no nome)
import importlib.util


def _load_runtime_registry():
    spec = importlib.util.spec_from_file_location(
        "runtime_registry",
        SCRIPT_DIR / "runtime-registry.py",
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["runtime_registry"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def rr():
    return _load_runtime_registry()


@pytest.fixture
def workspace_root(tmp_path: Path) -> Path:
    """Cria estrutura mínima workspaces/NNN/."""
    ws = tmp_path / "workspaces" / "001-test-mvp"
    ws.mkdir(parents=True)
    return ws


# ============================================================
# init / load empty
# ============================================================

def test_load_creates_empty_registry_if_absent(rr, workspace_root: Path):
    """Primeira leitura cria registry vazio + dir _state/."""
    reg = rr.load(workspace_root)
    assert reg["version"] == 1
    assert reg["workspace"] == "001-test-mvp"
    assert reg["entries"] == []
    state_dir = workspace_root / "_state"
    assert state_dir.is_dir()


def test_load_returns_persisted_registry(rr, workspace_root: Path):
    state_dir = workspace_root / "_state"
    state_dir.mkdir()
    payload = {
        "version": 1,
        "workspace": "001-test-mvp",
        "entries": [
            {"id": "abc", "kind": "dev_server", "pid": 999, "port": 5173,
             "cmd": "npm run dev", "registered_at": "2026-05-01T10:00:00Z"}
        ],
    }
    (state_dir / "runtime-registry.json").write_text(json.dumps(payload))
    reg = rr.load(workspace_root)
    assert len(reg["entries"]) == 1
    assert reg["entries"][0]["pid"] == 999


# ============================================================
# register
# ============================================================

def test_register_appends_entry(rr, workspace_root: Path):
    entry_id = rr.register(
        workspace_root,
        kind="dev_server",
        pid=12345,
        port=5173,
        cmd="npm run dev",
    )
    assert entry_id  # uuid string returned
    reg = rr.load(workspace_root)
    assert len(reg["entries"]) == 1
    e = reg["entries"][0]
    assert e["id"] == entry_id
    assert e["kind"] == "dev_server"
    assert e["pid"] == 12345
    assert e["port"] == 5173
    assert e["cmd"] == "npm run dev"
    assert "registered_at" in e


def test_register_invalid_kind_raises(rr, workspace_root: Path):
    with pytest.raises(ValueError, match="kind"):
        rr.register(workspace_root, kind="bogus_kind", pid=123)


def test_register_multiple_kinds(rr, workspace_root: Path):
    rr.register(workspace_root, kind="dev_server", pid=1, port=5173)
    rr.register(workspace_root, kind="docker_container", pid=2,
                metadata={"container_id": "deadbeef"})
    rr.register(workspace_root, kind="background_task", pid=3,
                cmd="celery worker")
    reg = rr.load(workspace_root)
    assert len(reg["entries"]) == 3
    kinds = {e["kind"] for e in reg["entries"]}
    assert kinds == {"dev_server", "docker_container", "background_task"}


# ============================================================
# list / filter
# ============================================================

def test_list_filters_by_kind(rr, workspace_root: Path):
    rr.register(workspace_root, kind="dev_server", pid=1)
    rr.register(workspace_root, kind="dev_server", pid=2)
    rr.register(workspace_root, kind="docker_container", pid=3)
    devs = rr.list_entries(workspace_root, kind="dev_server")
    assert len(devs) == 2


def test_list_no_filter_returns_all(rr, workspace_root: Path):
    rr.register(workspace_root, kind="dev_server", pid=1)
    rr.register(workspace_root, kind="docker_container", pid=2)
    all_e = rr.list_entries(workspace_root)
    assert len(all_e) == 2


# ============================================================
# unregister
# ============================================================

def test_unregister_by_id(rr, workspace_root: Path):
    eid = rr.register(workspace_root, kind="dev_server", pid=1)
    rr.register(workspace_root, kind="dev_server", pid=2)
    removed = rr.unregister(workspace_root, entry_id=eid)
    assert removed is True
    reg = rr.load(workspace_root)
    assert len(reg["entries"]) == 1
    assert reg["entries"][0]["pid"] == 2


def test_unregister_unknown_id_returns_false(rr, workspace_root: Path):
    assert rr.unregister(workspace_root, entry_id="nonexistent") is False


def test_purge_removes_dead_entries(rr, workspace_root: Path, monkeypatch):
    """Purge varre entries, remove aquelas com PID morto."""
    rr.register(workspace_root, kind="dev_server", pid=99999)
    rr.register(workspace_root, kind="dev_server", pid=88888)

    # Mock _is_pid_alive: 99999 morto, 88888 vivo
    def fake_is_alive(pid):
        return pid == 88888

    monkeypatch.setattr(rr, "_is_pid_alive", fake_is_alive)

    purged = rr.purge_dead(workspace_root)
    assert len(purged) == 1
    assert purged[0]["pid"] == 99999
    reg = rr.load(workspace_root)
    assert len(reg["entries"]) == 1
    assert reg["entries"][0]["pid"] == 88888


# ============================================================
# legacy .dev-server.pid migration (v3.6.0 → v3.7.0)
# ============================================================

def test_legacy_pid_file_detected_and_listed(rr, tmp_path: Path):
    """Se workspace tem .icm-main/.dev-server.pid (v3.6.0), list inclui
    entry sintética + warning."""
    project_root = tmp_path
    icm_main = project_root / ".icm-main"
    icm_main.mkdir()
    (icm_main / ".dev-server.pid").write_text("54321")
    workspace_root = project_root / "workspaces" / "001-test"
    workspace_root.mkdir(parents=True)

    legacy = rr.detect_legacy_pid_files(project_root)
    assert len(legacy) == 1
    assert legacy[0]["pid"] == 54321
    assert legacy[0]["kind"] == "dev_server"
    assert legacy[0]["source"] == ".icm-main/.dev-server.pid"


def test_legacy_pid_file_absent_returns_empty(rr, tmp_path: Path):
    assert rr.detect_legacy_pid_files(tmp_path) == []


# ============================================================
# CLI smoke
# ============================================================

def test_cli_register_list_unregister(rr, workspace_root: Path, capsys):
    """CLI register → list → unregister round-trip."""
    rc = rr.main([
        "register",
        "--workspace-root", str(workspace_root),
        "--kind", "dev_server",
        "--pid", "12345",
        "--port", "5173",
        "--command", "npm run dev",
    ])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    entry_id = out  # CLI prints created entry id

    rc = rr.main([
        "list",
        "--workspace-root", str(workspace_root),
    ])
    assert rc == 0
    listing = capsys.readouterr().out
    assert "12345" in listing or "dev_server" in listing

    rc = rr.main([
        "unregister",
        "--workspace-root", str(workspace_root),
        "--id", entry_id,
    ])
    assert rc == 0
    reg = rr.load(workspace_root)
    assert reg["entries"] == []
