"""v3.7.0 — bootstrap.py spawn-pending detection + --spawn-from arg.

Cenários:
- `.icm/spawn-pending.json` em project_root é detectado pelo bootstrap.
- Schema validado (campos obrigatórios + tipos).
- Arg CLI `--spawn-from` aceito; conflito com arquivo resolvido.
- GITIGNORE_LINES inclui paths v3.7.0 (`.icm/spawn-pending.json`,
  `_state/`, `coverage/`, `__pycache__/`, etc.).
- Pós-bootstrap consome (unlink) o arquivo.

Tests escritos ANTES da implementação.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import bootstrap  # type: ignore[import-not-found]  # noqa: E402


# ============================================================
# GITIGNORE_LINES extended (v3.7.0)
# ============================================================

REQUIRED_GITIGNORE_PATHS_V3_7_0 = {
    ".icm-profile.local.yaml",
    ".icm-main/",
    ".icm-chrome-profile/",
    ".icm/spawn-pending.json",          # NOVO v3.7.0
    "workspaces/*/_state/",             # NOVO v3.7.0 (registry local-only)
    "**/coverage/",                     # NOVO v3.7.0 (untracked artifact)
    "**/coverage.json",                 # NOVO v3.7.0
    "**/tsconfig.tsbuildinfo",          # NOVO v3.7.0
    "**/.vite/",                        # NOVO v3.7.0
    "__pycache__/",
}


def test_gitignore_lines_v3_7_0_supersets():
    """GITIGNORE_LINES inclui novos paths v3.7.0."""
    actual = set(bootstrap.GITIGNORE_LINES)
    missing = REQUIRED_GITIGNORE_PATHS_V3_7_0 - actual
    assert not missing, f"GITIGNORE_LINES falta: {missing}"


# ============================================================
# spawn-pending.json schema + parse
# ============================================================

VALID_PAYLOAD = {
    "spawn_from": "001-001-saas-psicologo-mvp",
    "intake_report_path": (
        "workspaces/001-001-saas-psicologo-mvp/stages/"
        "08_feedback_intake/output/intake-report.md"
    ),
    "intake_report_branch": "workspace/001-001-saas-psicologo-mvp",
    "proposed_workspace_name": "002-e2e-playwright-suite",
    "proposed_profile": "app_web_frontend",
    "proposed_tier": "tool",
    "intake_commit_sha": "abc1234",
    "agent_brief": {
        "por_que_spawn": "Suite E2E precisa cobertura Playwright.",
        "escopo_motivador": "Cobrir fluxos críticos de booking.",
        "heranca_aplicavel": "ADRs 0001-0003 do parent.",
        "nao_quero": "Tests unitários (já cobertos no parent).",
        "notes_livre": "",
    },
    "created_at": "2026-05-01T12:00:00Z",
}


def test_detect_spawn_pending_returns_payload(tmp_path: Path):
    """Se .icm/spawn-pending.json existe, parse retorna dict completo."""
    icm_dir = tmp_path / ".icm"
    icm_dir.mkdir()
    (icm_dir / "spawn-pending.json").write_text(
        json.dumps(VALID_PAYLOAD), encoding="utf-8",
    )
    detected = bootstrap.detect_spawn_pending(tmp_path)
    assert detected is not None
    assert detected["spawn_from"] == "001-001-saas-psicologo-mvp"
    assert detected["proposed_profile"] == "app_web_frontend"


def test_detect_spawn_pending_returns_none_if_absent(tmp_path: Path):
    assert bootstrap.detect_spawn_pending(tmp_path) is None


def test_detect_spawn_pending_invalid_json_raises(tmp_path: Path):
    icm_dir = tmp_path / ".icm"
    icm_dir.mkdir()
    (icm_dir / "spawn-pending.json").write_text("{ invalid json", encoding="utf-8")
    with pytest.raises(bootstrap.BootstrapError, match="spawn-pending"):
        bootstrap.detect_spawn_pending(tmp_path)


def test_detect_spawn_pending_missing_required_field_raises(tmp_path: Path):
    icm_dir = tmp_path / ".icm"
    icm_dir.mkdir()
    bad = dict(VALID_PAYLOAD)
    del bad["spawn_from"]
    (icm_dir / "spawn-pending.json").write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(bootstrap.BootstrapError, match="spawn_from"):
        bootstrap.detect_spawn_pending(tmp_path)


# ============================================================
# Conflict resolution: arquivo vs --spawn-from arg
# ============================================================

def test_resolve_spawn_arg_no_conflict_arg_only(tmp_path: Path):
    """Sem arquivo: arg ganha."""
    decision = bootstrap.resolve_spawn_source(
        project_root=tmp_path,
        spawn_from_arg="042-old-ws",
    )
    assert decision["source"] == "arg"
    assert decision["spawn_from"] == "042-old-ws"


def test_resolve_spawn_arg_no_conflict_file_only(tmp_path: Path):
    """Sem arg: arquivo ganha."""
    icm_dir = tmp_path / ".icm"
    icm_dir.mkdir()
    (icm_dir / "spawn-pending.json").write_text(
        json.dumps(VALID_PAYLOAD), encoding="utf-8",
    )
    decision = bootstrap.resolve_spawn_source(
        project_root=tmp_path,
        spawn_from_arg=None,
    )
    assert decision["source"] == "file"
    assert decision["spawn_from"] == "001-001-saas-psicologo-mvp"


def test_resolve_spawn_arg_match_file_wins(tmp_path: Path):
    """Match arquivo + arg: arquivo wins (carrega payload completo)."""
    icm_dir = tmp_path / ".icm"
    icm_dir.mkdir()
    (icm_dir / "spawn-pending.json").write_text(
        json.dumps(VALID_PAYLOAD), encoding="utf-8",
    )
    decision = bootstrap.resolve_spawn_source(
        project_root=tmp_path,
        spawn_from_arg="001-001-saas-psicologo-mvp",  # mesmo workspace
    )
    assert decision["source"] == "file"


def test_resolve_spawn_arg_mismatch_marks_conflict(tmp_path: Path):
    """Arquivo aponta NNN-X, arg passa NNN-Y → conflict (humano decide)."""
    icm_dir = tmp_path / ".icm"
    icm_dir.mkdir()
    (icm_dir / "spawn-pending.json").write_text(
        json.dumps(VALID_PAYLOAD), encoding="utf-8",
    )
    decision = bootstrap.resolve_spawn_source(
        project_root=tmp_path,
        spawn_from_arg="042-old-ws",  # diferente do arquivo
    )
    assert decision["source"] == "conflict"
    assert decision["file_value"] == "001-001-saas-psicologo-mvp"
    assert decision["arg_value"] == "042-old-ws"


def test_resolve_spawn_arg_neither(tmp_path: Path):
    """Sem arquivo e sem arg → source='none'."""
    decision = bootstrap.resolve_spawn_source(
        project_root=tmp_path,
        spawn_from_arg=None,
    )
    assert decision["source"] == "none"


# ============================================================
# Consume (unlink após bootstrap successful)
# ============================================================

def test_consume_spawn_pending_removes_file(tmp_path: Path):
    icm_dir = tmp_path / ".icm"
    icm_dir.mkdir()
    pending = icm_dir / "spawn-pending.json"
    pending.write_text(json.dumps(VALID_PAYLOAD), encoding="utf-8")
    bootstrap.consume_spawn_pending(tmp_path)
    assert not pending.exists()


def test_consume_spawn_pending_idempotent_if_missing(tmp_path: Path):
    """Consume sem arquivo: no-op (não raise)."""
    bootstrap.consume_spawn_pending(tmp_path)  # ok


# ============================================================
# CLI --spawn-from arg
# ============================================================

def test_cli_parser_accepts_spawn_from():
    parser = bootstrap._build_parser()
    args = parser.parse_args([
        "--profile", "app_web_backend",
        "--tier", "development",
        "--project-root", "/tmp/proj",
        "--workspace-name", "001-test",
        "--spawn-from", "042-parent",
    ])
    assert args.spawn_from == "042-parent"


def test_cli_parser_spawn_from_optional():
    """--spawn-from é opcional (default None)."""
    parser = bootstrap._build_parser()
    args = parser.parse_args([
        "--profile", "app_web_backend",
        "--tier", "development",
        "--project-root", "/tmp/proj",
        "--workspace-name", "001-test",
    ])
    assert args.spawn_from is None
