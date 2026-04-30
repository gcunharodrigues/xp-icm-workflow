"""Tests para v3.4.2: gate inline + Recovery Wizard KICKOFF_WITHOUT_GATE
+ bootstrap auto-merge project_root settings.local.json.

Cobertura:

Recovery Wizard:
  * Detect KICKOFF_WITHOUT_GATE: kickoff existe + L1 status pendente
  * Detect skip: kickoff ausente OR status nao pendente OR sub_stage nao _completed
  * Detect skip: stage_atual=04 (logica de waves complexa, omitida)
  * Plan A: aprovar gate retroativo (transita L1 pra NN+1)
  * Plan A stage 07: auto-transita pra 08 com COMPLETED_AWAITING_HUMAN
  * Plan B: deleta kickoff + volta sub_stage pra _in_progress

Bootstrap:
  * _merge_project_settings_local cria arquivo se ausente
  * Idempotente: re-execucao com hooks ja presentes nao muda arquivo
  * Preserva customizacoes do user (outros keys + outros hooks)
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

# ============================================================================
# Setup: import scripts via importlib (hifen no nome do arquivo)
# ============================================================================

_SCRIPT_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(_SCRIPT_DIR))


def _load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, _SCRIPT_DIR / filename)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


recovery_wizard = _load_module("recovery_wizard_v342", "recovery-wizard.py")
bootstrap_mod = _load_module("bootstrap_v342", "bootstrap.py")


# ============================================================================
# Helpers
# ============================================================================

def _build_workspace_with_state(
    tmp_path: Path,
    *,
    workspace: str = "999-test-gate",
    stage_atual: str,
    sub_stage: str,
    status: str,
    create_kickoff_for_next: str | None = None,
) -> Path:
    """Cria workspace L1 com state customizado.

    Se create_kickoff_for_next dado, cria stages/<dir>/_kickoff.md vazio.
    """
    ws = tmp_path / workspace
    ws.mkdir(parents=True)
    (ws / "_config").mkdir()
    profile_yaml = "profile_base: app_web_backend\ntier: development\n"
    profile_bytes = profile_yaml.encode("utf-8")
    (ws / "_config" / "profile-effective.yaml").write_bytes(profile_bytes)

    import hashlib  # noqa: PLC0415
    correct_hash = hashlib.sha256(profile_bytes).hexdigest()

    now = datetime(2026, 4, 29, 14, 30, tzinfo=timezone.utc).isoformat()
    project_root_posix = str(tmp_path).replace("\\", "/")
    context = f"""---
workspace: "{workspace}"
profile_base: "app_web_backend"
profile_effective_hash: "{correct_hash}"
tier: "development"
project_root: "{project_root_posix}"
base_branch: "main"
workspace_branch: "workspace/{workspace}"
stage_atual: "{stage_atual}"
sub_stage: "{sub_stage}"
status: "{status}"
iteration: 0
llm_review_skipped_count: 0
last_action: "test"
last_action_at: "{now}"
next_action: "test"
last_transition:
  from: "{stage_atual}_in_progress"
  to: "{sub_stage}"
  at: "{now}"
  commit_sha: "abc123def456"
history:
  - at: "{now}"
    event: "stage_transition"
    from: "{stage_atual}_in_progress"
    to: "{sub_stage}"
    commit_sha: "abc123def456"
---

# Workspace
"""
    (ws / "CONTEXT.md").write_text(context, encoding="utf-8")

    if create_kickoff_for_next:
        kickoff_dir = ws / "stages" / create_kickoff_for_next
        kickoff_dir.mkdir(parents=True)
        (kickoff_dir / "_kickoff.md").write_text(
            "---\nlayer: L4-kickoff\n---\n\n# kickoff\n",
            encoding="utf-8",
        )

    return ws


@pytest.fixture
def mock_git(monkeypatch):
    """Mock subprocess.run pra git: branch, sha, log sempre OK."""
    import subprocess as _sp  # noqa: PLC0415

    def fake_run(cmd, *args, **kwargs):
        if not isinstance(cmd, (list, tuple)):
            return _sp.CompletedProcess(cmd, 0, "", "")
        # cat-file -e <sha>: sucesso
        if "cat-file" in cmd and "-e" in cmd:
            return _sp.CompletedProcess(cmd, 0, "", "")
        # branch --list: sempre acha
        if "branch" in cmd and "--list" in cmd:
            target = cmd[-1]
            return _sp.CompletedProcess(cmd, 0, f"  {target}\n", "")
        # log: commit recente
        if "log" in cmd:
            iso = "2026-04-29T14:30:00+00:00"
            return _sp.CompletedProcess(cmd, 0, iso + "\n", "")
        # rev-parse --abbrev-ref HEAD: workspace branch
        if "rev-parse" in cmd:
            return _sp.CompletedProcess(cmd, 0, "workspace/999-test-gate\n", "")
        return _sp.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(recovery_wizard.subprocess, "run", fake_run)


# ============================================================================
# Recovery Wizard: KICKOFF_WITHOUT_GATE detection
# ============================================================================

class TestKickoffWithoutGateDetect:
    def test_detects_when_kickoff_exists_and_status_pending(
        self, tmp_path, mock_git
    ):
        ws = _build_workspace_with_state(
            tmp_path,
            stage_atual="02",
            sub_stage="02_completed",
            status="COMPLETED_AWAITING_HUMAN",
            create_kickoff_for_next="03_wave_planner",
        )
        now = datetime(2026, 4, 29, 14, 30, tzinfo=timezone.utc)
        result = recovery_wizard.detect_inconsistencies(ws, now=now)
        codes = [i.code for i in result]
        assert "KICKOFF_WITHOUT_GATE" in codes

    def test_no_detection_when_kickoff_absent(self, tmp_path, mock_git):
        ws = _build_workspace_with_state(
            tmp_path,
            stage_atual="02",
            sub_stage="02_completed",
            status="COMPLETED_AWAITING_HUMAN",
            create_kickoff_for_next=None,  # SEM kickoff
        )
        now = datetime(2026, 4, 29, 14, 30, tzinfo=timezone.utc)
        result = recovery_wizard.detect_inconsistencies(ws, now=now)
        codes = [i.code for i in result]
        assert "KICKOFF_WITHOUT_GATE" not in codes

    def test_no_detection_when_status_in_progress(self, tmp_path, mock_git):
        ws = _build_workspace_with_state(
            tmp_path,
            stage_atual="02",
            sub_stage="02_in_progress",
            status="IN_PROGRESS",
            create_kickoff_for_next="03_wave_planner",
        )
        now = datetime(2026, 4, 29, 14, 30, tzinfo=timezone.utc)
        result = recovery_wizard.detect_inconsistencies(ws, now=now)
        codes = [i.code for i in result]
        assert "KICKOFF_WITHOUT_GATE" not in codes

    def test_no_detection_when_stage_04(self, tmp_path, mock_git):
        # Stage 04 omitido por logica de waves complexa
        ws = _build_workspace_with_state(
            tmp_path,
            stage_atual="04",
            sub_stage="04_wave_1_completed",
            status="COMPLETED_AWAITING_HUMAN",
            create_kickoff_for_next="05_verification",
        )
        now = datetime(2026, 4, 29, 14, 30, tzinfo=timezone.utc)
        result = recovery_wizard.detect_inconsistencies(ws, now=now)
        codes = [i.code for i in result]
        assert "KICKOFF_WITHOUT_GATE" not in codes


# ============================================================================
# Recovery Wizard: Plan A (aprovar gate retroativamente)
# ============================================================================

class TestKickoffWithoutGatePlanA:
    def test_plan_a_transits_to_next_stage(self, tmp_path, mock_git):
        ws = _build_workspace_with_state(
            tmp_path,
            stage_atual="02",
            sub_stage="02_completed",
            status="COMPLETED_AWAITING_HUMAN",
            create_kickoff_for_next="03_wave_planner",
        )
        now = datetime(2026, 4, 29, 14, 30, tzinfo=timezone.utc)
        recovery_wizard.apply_recovery(ws, "A", now=now)

        # Re-parse L1 pra ver state
        state, _, _ = recovery_wizard._parse_l1(ws)
        assert state["stage_atual"] == "03"
        assert state["sub_stage"] == "03_in_progress"
        assert state["status"] == "IN_PROGRESS"
        # Kickoff ainda existe
        assert (ws / "stages" / "03_wave_planner" / "_kickoff.md").is_file()

    def test_plan_a_stage_07_auto_transits_to_08(self, tmp_path, mock_git):
        ws = _build_workspace_with_state(
            tmp_path,
            stage_atual="07",
            sub_stage="07_completed",
            status="COMPLETED_AWAITING_HUMAN",
            create_kickoff_for_next="08_feedback_intake",
        )
        now = datetime(2026, 4, 29, 14, 30, tzinfo=timezone.utc)
        recovery_wizard.apply_recovery(ws, "A", now=now)

        state, _, _ = recovery_wizard._parse_l1(ws)
        assert state["stage_atual"] == "08"
        assert state["sub_stage"] == "08_in_progress"
        # Stage 07→08 special: status remains COMPLETED_AWAITING_HUMAN
        assert state["status"] == "COMPLETED_AWAITING_HUMAN"


# ============================================================================
# Recovery Wizard: Plan B (deletar kickoff + voltar)
# ============================================================================

class TestKickoffWithoutGatePlanB:
    def test_plan_b_deletes_kickoff_and_resets(self, tmp_path, mock_git):
        ws = _build_workspace_with_state(
            tmp_path,
            stage_atual="02",
            sub_stage="02_completed",
            status="COMPLETED_AWAITING_HUMAN",
            create_kickoff_for_next="03_wave_planner",
        )
        kickoff_path = ws / "stages" / "03_wave_planner" / "_kickoff.md"
        assert kickoff_path.is_file()  # pre-condition

        now = datetime(2026, 4, 29, 14, 30, tzinfo=timezone.utc)
        recovery_wizard.apply_recovery(ws, "B", now=now)

        state, _, _ = recovery_wizard._parse_l1(ws)
        assert state["stage_atual"] == "02"  # nao mudou
        assert state["sub_stage"] == "02_in_progress"  # voltou a in_progress
        assert state["status"] == "IN_PROGRESS"
        assert not kickoff_path.is_file()  # deletado


# ============================================================================
# Bootstrap: _merge_project_settings_local idempotency + customization preserve
# ============================================================================

class TestMergeProjectSettings:
    def test_creates_file_if_absent(self, tmp_path):
        project_root = tmp_path / "project"
        project_root.mkdir()
        bootstrap_mod._merge_project_settings_local(project_root, "001-test")

        settings_path = project_root / ".claude" / "settings.local.json"
        assert settings_path.is_file()
        data = json.loads(settings_path.read_text(encoding="utf-8"))
        assert "hooks" in data
        # 3 hooks ICM presentes (SessionStart, PreToolUse, PostToolUse)
        cmds = []
        for event in ("SessionStart", "PreToolUse", "PostToolUse"):
            for entry in data["hooks"].get(event, []):
                for h in entry.get("hooks", []):
                    cmds.append(h.get("command", ""))
        assert any("icm-session-check.sh" in c for c in cmds)
        assert any("block-init-during-icm.sh" in c for c in cmds)
        assert any("context-check.sh" in c for c in cmds)
        assert any("workspaces/001-test/" in c for c in cmds)
        # Commands cwd-independent via $CLAUDE_PROJECT_DIR (worktree-safe)
        assert all("$CLAUDE_PROJECT_DIR" in c for c in cmds), (
            f"command sem $CLAUDE_PROJECT_DIR: {cmds}"
        )

    def test_pretoolse_matcher_is_slashcommand_or_bash(self, tmp_path):
        """block-init-during-icm hook só interessa em SlashCommand ou Bash —
        matcher deve ser específico, não `.*` (evita overhead em outros tools).
        """
        project_root = tmp_path / "project"
        project_root.mkdir()
        bootstrap_mod._merge_project_settings_local(project_root, "001-test")
        data = json.loads(
            (project_root / ".claude" / "settings.local.json").read_text(encoding="utf-8")
        )
        pre_tool = data["hooks"]["PreToolUse"]
        block_init_entry = next(
            entry for entry in pre_tool
            if any(
                "block-init-during-icm.sh" in h.get("command", "")
                for h in entry.get("hooks", [])
            )
        )
        matcher = block_init_entry["matcher"]
        assert "SlashCommand" in matcher and "Bash" in matcher, (
            f"matcher esperado conter SlashCommand+Bash, got: {matcher!r}"
        )

    def test_block_dangerous_git_registered_for_production(self, tmp_path):
        """tier=production registra block-dangerous-git como PreToolUse(Bash).

        Hook .sh é COPIADO em tier=production (vide _PRODUCTION_HOOK_FILES).
        Pre-fix: registro em settings.local.json estava ausente — hook
        inerte. Este test bloqueia regressão.
        """
        project_root = tmp_path / "project"
        project_root.mkdir()
        bootstrap_mod._merge_project_settings_local(
            project_root, "001-test", tier="production"
        )
        data = json.loads(
            (project_root / ".claude" / "settings.local.json").read_text(encoding="utf-8")
        )
        pre_tool = data["hooks"]["PreToolUse"]
        # 2 entries em PreToolUse: block-init (SlashCommand|Bash) + block-dangerous (Bash)
        commands = [
            (entry["matcher"], h["command"])
            for entry in pre_tool
            for h in entry.get("hooks", [])
        ]
        assert any(
            "block-dangerous-git.sh" in cmd and matcher == "Bash"
            for matcher, cmd in commands
        ), f"block-dangerous-git ausente ou matcher errado em production: {commands}"
        # E command com $CLAUDE_PROJECT_DIR (cwd-independent)
        dangerous_cmd = next(
            cmd for matcher, cmd in commands if "block-dangerous-git.sh" in cmd
        )
        assert "$CLAUDE_PROJECT_DIR" in dangerous_cmd

    def test_block_dangerous_git_NOT_registered_for_non_production(self, tmp_path):
        """tier != production: hook .sh nem é copiado, registro NÃO existe."""
        for tier in ("experimental", "tool", "development", ""):
            project_root = tmp_path / f"project-{tier or 'empty'}"
            project_root.mkdir()
            bootstrap_mod._merge_project_settings_local(
                project_root, "001-test", tier=tier
            )
            data = json.loads(
                (project_root / ".claude" / "settings.local.json").read_text(encoding="utf-8")
            )
            commands = [
                h.get("command", "")
                for entries in data["hooks"].values()
                for entry in entries
                for h in entry.get("hooks", [])
            ]
            assert not any(
                "block-dangerous-git.sh" in c for c in commands
            ), f"tier={tier!r}: block-dangerous-git registrado indevidamente"

    def test_idempotent_rerun_no_change(self, tmp_path):
        project_root = tmp_path / "project"
        project_root.mkdir()
        bootstrap_mod._merge_project_settings_local(project_root, "001-test")
        settings_path = project_root / ".claude" / "settings.local.json"
        first_content = settings_path.read_text(encoding="utf-8")

        # Re-roda — deve ser no-op idempotente
        bootstrap_mod._merge_project_settings_local(project_root, "001-test")
        second_content = settings_path.read_text(encoding="utf-8")
        assert first_content == second_content

    def test_preserves_user_customizations(self, tmp_path):
        project_root = tmp_path / "project"
        project_root.mkdir()
        claude_dir = project_root / ".claude"
        claude_dir.mkdir()
        # User criou settings.local.json com customizacoes
        existing = {
            "permissions": {"allow": ["Read(*)"]},  # custom user key
            "hooks": {
                "PostToolUse": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {"type": "command", "command": "bash my-custom-hook.sh"}
                        ],
                    }
                ]
            },
        }
        settings_path = claude_dir / "settings.local.json"
        settings_path.write_text(
            json.dumps(existing, indent=2), encoding="utf-8"
        )

        bootstrap_mod._merge_project_settings_local(project_root, "001-test")

        merged = json.loads(settings_path.read_text(encoding="utf-8"))
        # Custom permissions preservadas
        assert merged.get("permissions") == {"allow": ["Read(*)"]}
        # User's PostToolUse hook preservado
        post_hooks = merged["hooks"]["PostToolUse"]
        assert any(
            any("my-custom-hook.sh" in h.get("command", "") for h in entry.get("hooks", []))
            for entry in post_hooks
        )
        # ICM hook adicionado
        assert any(
            any("context-check.sh" in h.get("command", "") for h in entry.get("hooks", []))
            for entry in post_hooks
        )
