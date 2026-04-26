"""Fixtures pytest compartilhadas pra suite da skill."""
from __future__ import annotations

from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
TEMPLATES_DIR = REPO_ROOT / "templates"
FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def scripts_dir() -> Path:
    return SCRIPTS_DIR


@pytest.fixture(scope="session")
def templates_dir() -> Path:
    return TEMPLATES_DIR


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def tmp_workspace(tmp_path: Path) -> Path:
    """Workspace temporário pra testes que precisam FS."""
    ws = tmp_path / "workspaces" / "999-test"
    ws.mkdir(parents=True)
    (ws / "stages").mkdir()
    (ws / "_config").mkdir()
    return ws
