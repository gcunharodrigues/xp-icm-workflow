"""Tests para recovery wizard tipos novos v3.6.0:
- DEV_SERVER_ORPHAN: PID file existe + processo morto
- CDP_DISCONNECTED: profile dir existe + porta 9222 nao listening

Setup minimo: cria fake workspace + project_root estrutura.
"""
from __future__ import annotations

import importlib.util
import os
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_recovery():
    name = "recovery_wizard"
    spec = importlib.util.spec_from_file_location(
        name, REPO_ROOT / "scripts" / "recovery-wizard.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    # Registra em sys.modules pra dataclass resolver __module__ lookups.
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def rw():
    return _load_recovery()


def _make_fake_workspace(tmp_path: Path) -> tuple[Path, Path]:
    """Cria estrutura minima pra detect_inconsistencies rodar.

    Returns: (workspace_path, project_root)
    """
    project_root = tmp_path / "proj"
    project_root.mkdir()
    # Estado L1 minimo: workspace, project_root.
    workspace = project_root / "workspaces" / "001-test"
    workspace.mkdir(parents=True)
    workspace_yaml = (
        f"---\n"
        f"workspace: 001-test\n"
        f"project_root: {project_root.as_posix()}\n"
        f"stage_atual: '04'\n"
        f"sub_stage: 04_wave_1_in_progress\n"
        f"status: IN_PROGRESS\n"
        f"profile_base: app_web_frontend\n"
        f"tier: development\n"
        f"iteration: 0\n"
        f"history: []\n"
        f"---\n"
        f"# fake workspace\n"
    )
    (workspace / "CONTEXT.md").write_text(workspace_yaml, encoding="utf-8")
    return workspace, project_root


def _find_free_port() -> int:
    """Retorna porta livre — usada pra confirmar que 9222 NÃO está ocupada."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# ============================================================
# DEV_SERVER_ORPHAN
# ============================================================

class TestDevServerOrphan:
    def test_no_pid_file_no_inconsistency(self, tmp_path, rw):
        ws, proj = _make_fake_workspace(tmp_path)
        incs = rw.detect_inconsistencies(ws, project_root=proj)
        codes = [i.code for i in incs]
        assert rw.CODE_DEV_SERVER_ORPHAN not in codes

    def test_pid_file_with_dead_process_detected(self, tmp_path, rw):
        ws, proj = _make_fake_workspace(tmp_path)
        icm_main = proj / ".icm-main"
        icm_main.mkdir()
        # PID 999999 — quase certamente morto/inexistente
        (icm_main / ".dev-server.pid").write_text("999999", encoding="utf-8")
        incs = rw.detect_inconsistencies(ws, project_root=proj)
        codes = [i.code for i in incs]
        assert rw.CODE_DEV_SERVER_ORPHAN in codes
        # Verifica context
        match = next(i for i in incs if i.code == rw.CODE_DEV_SERVER_ORPHAN)
        assert match.context["pid"] == 999999
        assert match.severity == "warning"

    def test_pid_file_with_alive_process_not_detected(self, tmp_path, rw):
        ws, proj = _make_fake_workspace(tmp_path)
        icm_main = proj / ".icm-main"
        icm_main.mkdir()
        # PID do processo Python atual = vivo
        (icm_main / ".dev-server.pid").write_text(str(os.getpid()), encoding="utf-8")
        incs = rw.detect_inconsistencies(ws, project_root=proj)
        codes = [i.code for i in incs]
        assert rw.CODE_DEV_SERVER_ORPHAN not in codes

    def test_pid_file_corrupt_treated_as_no_op(self, tmp_path, rw):
        ws, proj = _make_fake_workspace(tmp_path)
        icm_main = proj / ".icm-main"
        icm_main.mkdir()
        (icm_main / ".dev-server.pid").write_text("garbage", encoding="utf-8")
        # PID parsing falha → pid = -1 → not alive, mas detecção exige pid > 0
        incs = rw.detect_inconsistencies(ws, project_root=proj)
        codes = [i.code for i in incs]
        # corrupt PID nao dispara DEV_SERVER_ORPHAN (pid <= 0 path)
        assert rw.CODE_DEV_SERVER_ORPHAN not in codes

    def test_apply_plan_a_removes_pid_file(self, tmp_path, rw):
        ws, proj = _make_fake_workspace(tmp_path)
        icm_main = proj / ".icm-main"
        icm_main.mkdir()
        pid_file = icm_main / ".dev-server.pid"
        pid_file.write_text("999999", encoding="utf-8")
        log_file = icm_main / ".dev-server.log"
        log_file.write_text("dummy log", encoding="utf-8")

        now = datetime.now(timezone.utc)
        rw.apply_recovery(ws, "A", project_root=proj, now=now)

        # PID file removido
        assert not pid_file.is_file(), "PID file deveria ser apagado"
        # Log file removido
        assert not log_file.is_file(), "log file deveria ser apagado"


# ============================================================
# CDP_DISCONNECTED
# ============================================================

class TestCdpDisconnected:
    def test_no_profile_dir_no_inconsistency(self, tmp_path, rw):
        ws, proj = _make_fake_workspace(tmp_path)
        incs = rw.detect_inconsistencies(ws, project_root=proj)
        codes = [i.code for i in incs]
        assert rw.CODE_CDP_DISCONNECTED not in codes

    def test_profile_dir_no_listener_detected(self, tmp_path, rw):
        ws, proj = _make_fake_workspace(tmp_path)
        chrome_profile = proj / ".icm-chrome-profile"
        chrome_profile.mkdir()
        # Garante que 9222 nao esta listening (assume host livre)
        # Se algo ja estiver em 9222, skip teste pra evitar falso negativo.
        if rw._is_port_listening("127.0.0.1", 9222):
            pytest.skip("port 9222 ocupada — não testável aqui")
        incs = rw.detect_inconsistencies(ws, project_root=proj)
        codes = [i.code for i in incs]
        assert rw.CODE_CDP_DISCONNECTED in codes
        match = next(i for i in incs if i.code == rw.CODE_CDP_DISCONNECTED)
        assert match.severity == "warning"
        assert ".icm-chrome-profile" in match.context["profile_dir"]

    def test_apply_plan_a_preserves_profile_dir(self, tmp_path, rw):
        ws, proj = _make_fake_workspace(tmp_path)
        chrome_profile = proj / ".icm-chrome-profile"
        chrome_profile.mkdir()
        (chrome_profile / "marker.txt").write_text("preserved", encoding="utf-8")

        if rw._is_port_listening("127.0.0.1", 9222):
            pytest.skip("port 9222 ocupada")

        now = datetime.now(timezone.utc)
        rw.apply_recovery(ws, "A", project_root=proj, now=now)

        # Profile dir preservado (warning-only, nao mata)
        assert chrome_profile.is_dir()
        assert (chrome_profile / "marker.txt").is_file()


# ============================================================
# Helpers (sanity)
# ============================================================

class TestHelpers:
    def test_is_pid_alive_self(self, rw):
        assert rw._is_pid_alive(os.getpid()) is True

    def test_is_pid_alive_dead(self, rw):
        # PID 999999999 quase certamente nao existe
        assert rw._is_pid_alive(999999999) is False

    def test_is_pid_alive_zero(self, rw):
        assert rw._is_pid_alive(0) is False

    def test_is_pid_alive_negative(self, rw):
        assert rw._is_pid_alive(-1) is False

    def test_is_port_listening_open_port(self, rw):
        # Abre porta dummy, confirma detecta
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
            srv.bind(("127.0.0.1", 0))
            srv.listen(1)
            port = srv.getsockname()[1]
            assert rw._is_port_listening("127.0.0.1", port) is True

    def test_is_port_listening_closed_port(self, rw):
        # Acha porta livre + nao binda nada
        port = _find_free_port()
        assert rw._is_port_listening("127.0.0.1", port) is False


# ============================================================
# Canonical order inclui novos codes
# ============================================================

def test_canonical_order_includes_new_codes(rw):
    assert rw.CODE_DEV_SERVER_ORPHAN in rw.CANONICAL_ORDER
    assert rw.CODE_CDP_DISCONNECTED in rw.CANONICAL_ORDER
