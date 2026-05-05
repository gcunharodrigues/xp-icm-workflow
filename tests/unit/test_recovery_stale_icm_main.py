"""v3.7.2 — recovery wizard detector STALE_ICM_MAIN_AFTER_CLOSE.

Trigger: workspace COMPLETED + .icm-main/ present + zero other active workspaces
in project_root. Plan A: registers warning suggesting
`scripts/icm-cleanup.py` (does not auto-execute — destructive).
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[2] / "scripts"

spec = importlib.util.spec_from_file_location(
    "recovery_wizard", SCRIPT_DIR / "recovery-wizard.py",
)
assert spec and spec.loader
recovery = importlib.util.module_from_spec(spec)
sys.modules["recovery_wizard"] = recovery
spec.loader.exec_module(recovery)

detect_inconsistencies = recovery.detect_inconsistencies
_count_active_workspaces = recovery._count_active_workspaces
CODE_STALE_ICM_MAIN_AFTER_CLOSE = recovery.CODE_STALE_ICM_MAIN_AFTER_CLOSE


L1_FRONTMATTER_TEMPLATE = """\
---
workspace: {workspace}
profile_base: app_web_backend
profile_effective_hash: deadbeef
tier: development
stage_atual: "08"
sub_stage: "08_decided_A"
status: {status}
iteration: 0
project_root: {project_root}
base_branch: main
workspace_branch: workspace/{workspace}
last_transition:
  from: "08_in_progress"
  to: "08_decided_A"
  at: "2026-05-01T12:00:00Z"
  commit_sha: "abc123"
history: []
---

# {workspace}
"""


def _seed_workspace(
    project_root: Path,
    workspace: str,
    *,
    status: str = "COMPLETED",
) -> Path:
    ws = project_root / "workspaces" / workspace
    ws.mkdir(parents=True)
    ctx = ws / "CONTEXT.md"
    ctx.write_text(
        L1_FRONTMATTER_TEMPLATE.format(
            workspace=workspace, status=status, project_root=project_root,
        ),
        encoding="utf-8",
    )
    return ws


# ============================================================
# _count_active_workspaces
# ============================================================

def test_count_active_zero_when_all_completed(tmp_path: Path):
    _seed_workspace(tmp_path, "001-alpha", status="COMPLETED")
    _seed_workspace(tmp_path, "002-beta", status="COMPLETED")
    assert _count_active_workspaces(tmp_path) == 0


def test_count_active_counts_in_progress(tmp_path: Path):
    _seed_workspace(tmp_path, "001-alpha", status="COMPLETED")
    _seed_workspace(tmp_path, "002-beta", status="IN_PROGRESS")
    _seed_workspace(tmp_path, "003-gamma", status="COMPLETED_AWAITING_HUMAN")
    assert _count_active_workspaces(tmp_path) == 2


def test_count_active_no_workspaces_dir(tmp_path: Path):
    assert _count_active_workspaces(tmp_path) == 0


# ============================================================
# Detector
# ============================================================

def test_detector_fires_when_completed_and_icm_main_present(tmp_path: Path):
    ws = _seed_workspace(tmp_path, "042-feat-auth", status="COMPLETED")
    (tmp_path / ".icm-main").mkdir()

    result = detect_inconsistencies(
        ws, project_root=tmp_path,
        now=datetime(2026, 5, 1, tzinfo=timezone.utc),
    )
    codes = [i.code for i in result]
    assert CODE_STALE_ICM_MAIN_AFTER_CLOSE in codes


def test_detector_does_not_fire_when_workspace_active(tmp_path: Path):
    ws = _seed_workspace(tmp_path, "042-feat-auth", status="IN_PROGRESS")
    (tmp_path / ".icm-main").mkdir()

    result = detect_inconsistencies(
        ws, project_root=tmp_path,
        now=datetime(2026, 5, 1, tzinfo=timezone.utc),
    )
    codes = [i.code for i in result]
    assert CODE_STALE_ICM_MAIN_AFTER_CLOSE not in codes


def test_detector_does_not_fire_when_icm_main_absent(tmp_path: Path):
    ws = _seed_workspace(tmp_path, "042-feat-auth", status="COMPLETED")
    # .icm-main NÃO criado

    result = detect_inconsistencies(
        ws, project_root=tmp_path,
        now=datetime(2026, 5, 1, tzinfo=timezone.utc),
    )
    codes = [i.code for i in result]
    assert CODE_STALE_ICM_MAIN_AFTER_CLOSE not in codes


def test_detector_does_not_fire_when_other_workspace_active(tmp_path: Path):
    ws = _seed_workspace(tmp_path, "042-feat-auth", status="COMPLETED")
    _seed_workspace(tmp_path, "043-payments", status="IN_PROGRESS")
    (tmp_path / ".icm-main").mkdir()

    result = detect_inconsistencies(
        ws, project_root=tmp_path,
        now=datetime(2026, 5, 1, tzinfo=timezone.utc),
    )
    codes = [i.code for i in result]
    assert CODE_STALE_ICM_MAIN_AFTER_CLOSE not in codes


def test_detector_message_cites_icm_cleanup_script(tmp_path: Path):
    ws = _seed_workspace(tmp_path, "042-feat-auth", status="COMPLETED")
    (tmp_path / ".icm-main").mkdir()

    result = detect_inconsistencies(
        ws, project_root=tmp_path,
        now=datetime(2026, 5, 1, tzinfo=timezone.utc),
    )
    matching = [i for i in result if i.code == CODE_STALE_ICM_MAIN_AFTER_CLOSE]
    assert len(matching) == 1
    inc = matching[0]
    assert "icm-cleanup.py" in inc.proposed_action
    assert inc.severity == "warning"
