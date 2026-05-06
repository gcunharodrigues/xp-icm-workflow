"""v3.7.1 — saída A/C cleanup completo: index + settings.local.json.

Bug pré-v3.7.1:
- `.index.md` mantinha workspace fechado como "active" (bootstrap.update_index
  só append). SessionStart hook lia index stale e reportava workspace
  fechado como ativo.
- Hooks duplicados em `.claude/settings.local.json` — bootstrap registra
  por workspace, saída A/C nunca removia.

Fix v3.7.1:
- `handoff._update_index_status` reescreve linha do workspace.
- `handoff._unregister_workspace_hooks` remove entries do settings.
- Ambos chamados dentro de `remove_workspace_block` (saídas A + C).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from handoff import (  # type: ignore[import-not-found]  # noqa: E402
    WorkspaceBlock,
    _unregister_workspace_hooks,
    _update_index_status,
    remove_workspace_block,
    update_project_claude_md,
)


INDEX_HEADER = """# Workspaces Index

| ID | Slug | Profile/Tier | Created | Status |
|----|------|--------------|---------|--------|
"""


def _block(workspace: str, **overrides) -> WorkspaceBlock:
    base = dict(
        workspace=workspace,
        profile="app_web_backend",
        tier="development",
        stage_atual="08",
        stage_dir="08_feedback_intake",
        sub_stage="08_in_progress",
        iteration=0,
        status="BLOCKED",
        last_action="phase 08 init",
        last_action_at="2026-05-01T10:00:00Z",
        next_action="awaiting human feedback",
    )
    base.update(overrides)
    return WorkspaceBlock(**base)


def _seed_index(project_root: Path, *workspaces: str) -> Path:
    idx = project_root / "workspaces" / ".index.md"
    idx.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for ws in workspaces:
        nnn, _, slug = ws.partition("-")
        rows.append(f"| {nnn} | {slug} | app_web_backend/development | 2026-05-01T10:00:00Z | active |")
    idx.write_text(INDEX_HEADER + "\n".join(rows) + "\n", encoding="utf-8")
    return idx


def _seed_settings_with_hooks(project_root: Path, *workspaces: str) -> Path:
    settings_dir = project_root / ".claude"
    settings_dir.mkdir(parents=True, exist_ok=True)
    hooks: dict[str, list[dict]] = {}
    for ws in workspaces:
        for event, matcher, fname in [
            ("SessionStart", ".*", "icm-session-check.sh"),
            ("PreToolUse", "SlashCommand|Bash", "block-init-during-icm.sh"),
            ("PostToolUse", ".*", "context-check.sh"),
        ]:
            cmd = f'bash "$CLAUDE_PROJECT_DIR/workspaces/{ws}/.claude/hooks/{fname}"'
            hooks.setdefault(event, []).append({
                "matcher": matcher,
                "hooks": [{"type": "command", "command": cmd}],
            })
    settings_path = settings_dir / "settings.local.json"
    settings_path.write_text(json.dumps({"hooks": hooks}, indent=2), encoding="utf-8")
    return settings_path


# ============================================================
# _update_index_status
# ============================================================

def test_update_index_status_marks_completed(tmp_path: Path):
    _seed_index(tmp_path, "042-feat-auth", "043-payments")
    changed = _update_index_status(tmp_path, "042-feat-auth", "COMPLETED")
    assert changed is True
    text = (tmp_path / "workspaces" / ".index.md").read_text(encoding="utf-8")
    assert "| 042 | feat-auth | app_web_backend/development | 2026-05-01T10:00:00Z | COMPLETED |" in text
    assert "| 043 | payments | app_web_backend/development | 2026-05-01T10:00:00Z | active |" in text


def test_update_index_status_no_index_noop(tmp_path: Path):
    """Index ausente → no-op, retorna False."""
    changed = _update_index_status(tmp_path, "042-feat-auth", "COMPLETED")
    assert changed is False


def test_update_index_status_workspace_not_in_index(tmp_path: Path):
    _seed_index(tmp_path, "042-feat-auth")
    changed = _update_index_status(tmp_path, "999-ghost", "COMPLETED")
    assert changed is False
    text = (tmp_path / "workspaces" / ".index.md").read_text(encoding="utf-8")
    assert "active" in text


def test_update_index_status_idempotent(tmp_path: Path):
    """Status já igual ao novo → no-op."""
    _seed_index(tmp_path, "042-feat-auth")
    _update_index_status(tmp_path, "042-feat-auth", "COMPLETED")
    changed = _update_index_status(tmp_path, "042-feat-auth", "COMPLETED")
    assert changed is False


# ============================================================
# _unregister_workspace_hooks
# ============================================================

def test_unregister_hooks_removes_all_entries_of_workspace(tmp_path: Path):
    settings_path = _seed_settings_with_hooks(tmp_path, "042-feat-auth", "043-payments")
    changed = _unregister_workspace_hooks(tmp_path, "042-feat-auth")
    assert changed is True
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    # Deve restar apenas hooks do 043
    for event, entries in settings["hooks"].items():
        for entry in entries:
            for h in entry.get("hooks", []):
                assert "042-feat-auth" not in h.get("command", ""), (
                    f"hook do 042 ainda presente em {event}"
                )
                assert "043-payments" in h.get("command", "")


def test_unregister_hooks_removes_event_when_empty(tmp_path: Path):
    """Se workspace fechado era único do evento, evento vira chave ausente."""
    settings_path = _seed_settings_with_hooks(tmp_path, "042-feat-auth")
    changed = _unregister_workspace_hooks(tmp_path, "042-feat-auth")
    assert changed is True
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    assert settings["hooks"] == {}, f"esperado hooks vazio, got {settings['hooks']}"


def test_unregister_hooks_settings_absent_noop(tmp_path: Path):
    changed = _unregister_workspace_hooks(tmp_path, "042-feat-auth")
    assert changed is False


def test_unregister_hooks_preserves_non_icm_entries(tmp_path: Path):
    settings_dir = tmp_path / ".claude"
    settings_dir.mkdir(parents=True, exist_ok=True)
    settings_path = settings_dir / "settings.local.json"
    settings = {
        "hooks": {
            "SessionStart": [
                {"matcher": ".*", "hooks": [{"type": "command", "command": "echo user-custom"}]},
                {"matcher": ".*", "hooks": [{"type": "command", "command": 'bash "$CLAUDE_PROJECT_DIR/workspaces/042-feat-auth/.claude/hooks/icm-session-check.sh"'}]},
            ],
        },
    }
    settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    changed = _unregister_workspace_hooks(tmp_path, "042-feat-auth")
    assert changed is True
    result = json.loads(settings_path.read_text(encoding="utf-8"))
    entries = result["hooks"]["SessionStart"]
    assert len(entries) == 1
    assert entries[0]["hooks"][0]["command"] == "echo user-custom"


# ============================================================
# Integration: remove_workspace_block triggers cleanup
# ============================================================

def test_remove_block_outcome_A_updates_index_and_unregisters_hooks(tmp_path: Path):
    block = _block("042-feat-auth")
    update_project_claude_md(tmp_path, block, skill_dir="/skill")
    _seed_index(tmp_path, "042-feat-auth", "043-payments")
    settings_path = _seed_settings_with_hooks(tmp_path, "042-feat-auth", "043-payments")

    remove_workspace_block(
        tmp_path, "042-feat-auth",
        skill_dir="/skill",
        closed_at="2026-05-01T12:00:00Z",
        outcome="A",
    )

    idx = (tmp_path / "workspaces" / ".index.md").read_text(encoding="utf-8")
    assert "| 042 | feat-auth | app_web_backend/development | 2026-05-01T10:00:00Z | COMPLETED |" in idx
    assert "| 043 | payments | app_web_backend/development | 2026-05-01T10:00:00Z | active |" in idx

    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    for entries in settings.get("hooks", {}).values():
        for entry in entries:
            for h in entry.get("hooks", []):
                assert "042-feat-auth" not in h.get("command", "")


def test_remove_block_outcome_C_updates_index_and_unregisters_hooks(tmp_path: Path):
    block = _block("042-feat-auth")
    update_project_claude_md(tmp_path, block, skill_dir="/skill")
    _seed_index(tmp_path, "042-feat-auth")
    settings_path = _seed_settings_with_hooks(tmp_path, "042-feat-auth")

    remove_workspace_block(
        tmp_path, "042-feat-auth",
        skill_dir="/skill",
        closed_at="2026-05-01T12:00:00Z",
        outcome="C",
        spawn_to="050-billing-pivot",
    )

    idx = (tmp_path / "workspaces" / ".index.md").read_text(encoding="utf-8")
    assert "COMPLETED" in idx and "active" not in idx

    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    assert settings.get("hooks", {}) == {}, "esperado hooks vazio pós-cleanup"
