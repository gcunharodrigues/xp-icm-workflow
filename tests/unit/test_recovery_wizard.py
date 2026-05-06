"""Unit tests deterministicos pro Recovery Wizard (R2.7).

Cobertura:

Detect (4 + 1 inconsistencias):
  * Workspace consistente -> lista vazia
  * HASH_MISMATCH -> hash recomputado != declarado em L1
  * MISSING_OUTPUT -> history referencia output ausente no FS
  * STALE_IN_PROGRESS -> IN_PROGRESS sem commit nas ultimas 24h
  * MISSING_COMMIT -> last_transition.commit_sha nao existe em git
  * BRANCH_MISSING -> branch workspace/NNN-slug nao existe (R4.5)
  * Multiplas -> ordem deterministic

Plan rendering:
  * propose_recovery_plan retorna markdown com 3 opcoes A/B/C
  * Renderiza tabela com codes/severity/proposed_action

Apply:
  * apply_recovery(A) em HASH_MISMATCH atualiza hash em L1
  * apply_recovery(C) marca BLOCKED_ERROR + history append
  * apply_recovery em workspace consistente -> no-op

CLI:
  * --dry-run nao modifica L1 (assert byte-identical)
  * --apply A modifica L1
  * Workspace OK -> exit 0 + "consistent"
  * Workspace path invalido -> exit 1
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import pytest

# Adicionar scripts/ ao path para import
SCRIPT_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

# Import of module under test — script usa hifen no nome de arquivo,
# entao usamos importlib pra carregar.
import importlib.util  # noqa: E402

_SPEC = importlib.util.spec_from_file_location(
    "recovery_wizard",
    SCRIPT_DIR / "recovery-wizard.py",
)
assert _SPEC is not None and _SPEC.loader is not None
recovery_wizard = importlib.util.module_from_spec(_SPEC)
# Registrar em sys.modules ANTES de exec_module — dataclass usa
# sys.modules[cls.__module__] internamente.
sys.modules["recovery_wizard"] = recovery_wizard
_SPEC.loader.exec_module(recovery_wizard)

Inconsistency = recovery_wizard.Inconsistency
RecoveryWizardError = recovery_wizard.RecoveryWizardError
detect_inconsistencies = recovery_wizard.detect_inconsistencies
propose_recovery_plan = recovery_wizard.propose_recovery_plan
apply_recovery = recovery_wizard.apply_recovery


FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"
ORPHAN_FIXTURE = FIXTURES_DIR / "workspace_orphan"


# Helpers ----------------------------------------------------------------------

def _copy_orphan(tmp_path: Path) -> Path:
    """Copies orphan fixture to tmp_path/orphan e retorna caminho."""
    dst = tmp_path / "orphan"
    shutil.copytree(ORPHAN_FIXTURE, dst)
    return dst


def _build_consistent_workspace(tmp_path: Path) -> Path:
    """Cria workspace L1 consistente (sem inconsistencias).

    profile_effective_hash bate com sha256 do _config/profile-effective.yaml.
    Sem outputs declarados em history. status=COMPLETED_AWAITING_HUMAN.
    """
    ws = tmp_path / "consistent"
    ws.mkdir()
    (ws / "_config").mkdir()
    profile_yaml = "profile_base: app_web_backend\ntier: development\n"
    profile_bytes = profile_yaml.encode("utf-8")
    (ws / "_config" / "profile-effective.yaml").write_bytes(profile_bytes)
    correct_hash = hashlib.sha256(profile_bytes).hexdigest()

    now = datetime(2026, 4, 25, 14, 30, tzinfo=timezone.utc).isoformat()
    context = f"""---
workspace: "888-consistent"
profile_base: "app_web_backend"
profile_effective_hash: "{correct_hash}"
tier: "development"
project_root: "/tmp/fake-project"
base_branch: "main"
workspace_branch: "workspace/888-consistent"
stage_atual: "02"
sub_stage: "02_completed"
status: "COMPLETED_AWAITING_HUMAN"
iteration: 0
llm_review_skipped_count: 0
last_action: "design done"
last_action_at: "{now}"
next_action: "human gate"
last_transition:
  from: "02_in_progress"
  to: "02_completed"
  at: "{now}"
  commit_sha: "abc123def456"
history:
  - at: "{now}"
    event: "stage_transition"
    from: "02_in_progress"
    to: "02_completed"
    commit_sha: "abc123def456"
---

# Workspace 888 — consistent
"""
    (ws / "CONTEXT.md").write_text(context, encoding="utf-8")
    return ws


# Patch git operations to be deterministic in tests.
@pytest.fixture
def mock_git(monkeypatch):
    """Mock subprocess.run para git commands.

    By default: cat-file -e sha -> sucesso (sha existe);
                log -> commit recente em workspaces/;
                branch --list -> branch existe.
    Tests sobreescrevem.
    """

    class GitState:
        existing_shas: set[str] = {"abc123def456", "1111111111111111111111111111111111111111"}
        existing_branches: set[str] = {"workspace/888-consistent", "workspace/999-orphan-fixture"}
        last_commit_at: datetime = datetime(2026, 4, 25, 14, 0, tzinfo=timezone.utc)

    state = GitState()

    def fake_run(cmd, *args, **kwargs):
        # Esperamos lista de tokens.
        if not isinstance(cmd, (list, tuple)):
            return subprocess.CompletedProcess(cmd, 0, "", "")

        if "cat-file" in cmd and "-e" in cmd:
            sha = cmd[-1]
            rc = 0 if sha in state.existing_shas else 1
            return subprocess.CompletedProcess(cmd, rc, "", "")

        if "branch" in cmd and "--list" in cmd:
            target = cmd[-1]
            stdout = f"  {target}\n" if target in state.existing_branches else ""
            return subprocess.CompletedProcess(cmd, 0, stdout, "")

        if "log" in cmd:
            # Espera --pretty=format:%cI -- workspaces/<NNN>
            iso = state.last_commit_at.isoformat()
            return subprocess.CompletedProcess(cmd, 0, iso + "\n", "")

        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(recovery_wizard.subprocess, "run", fake_run)
    return state


# Detect tests -----------------------------------------------------------------

class TestDetectConsistent:
    def test_consistent_workspace_returns_empty(self, tmp_path, mock_git):
        ws = _build_consistent_workspace(tmp_path)
        now = datetime(2026, 4, 25, 14, 30, tzinfo=timezone.utc)
        result = detect_inconsistencies(ws, now=now)
        assert result == []


class TestDetectHashMismatch:
    def test_hash_mismatch_in_orphan_fixture(self, tmp_path, mock_git):
        ws = _copy_orphan(tmp_path)
        # Now anchored long after orphan's last_action_at to also trigger STALE,
        # but we filter for HASH_MISMATCH here.
        now = datetime(2026, 4, 25, 14, 30, tzinfo=timezone.utc)
        result = detect_inconsistencies(ws, now=now)
        codes = [i.code for i in result]
        assert "HASH_MISMATCH" in codes

    def test_hash_match_no_inconsistency(self, tmp_path, mock_git):
        ws = _build_consistent_workspace(tmp_path)
        now = datetime(2026, 4, 25, 14, 30, tzinfo=timezone.utc)
        result = detect_inconsistencies(ws, now=now)
        assert all(i.code != "HASH_MISMATCH" for i in result)


class TestDetectMissingOutput:
    def test_history_references_missing_output(self, tmp_path, mock_git):
        ws = _copy_orphan(tmp_path)
        now = datetime(2026, 4, 25, 14, 30, tzinfo=timezone.utc)
        result = detect_inconsistencies(ws, now=now)
        codes = [i.code for i in result]
        assert "MISSING_OUTPUT" in codes
        # Mensagem deve referenciar o ghost
        msg_combined = " ".join(i.message for i in result if i.code == "MISSING_OUTPUT")
        assert "ghost.md" in msg_combined


class TestDetectStaleInProgress:
    def test_stale_in_progress(self, tmp_path, mock_git):
        ws = _copy_orphan(tmp_path)
        # last_action_at na fixture = 2026-04-20T10:00:00Z. Now muito depois.
        now = datetime(2026, 4, 25, 14, 30, tzinfo=timezone.utc)
        # Force git log para retornar commit antigo (>24h)
        mock_git.last_commit_at = datetime(2026, 4, 22, 0, 0, tzinfo=timezone.utc)
        result = detect_inconsistencies(ws, now=now)
        codes = [i.code for i in result]
        assert "STALE_IN_PROGRESS" in codes

    def test_recent_commit_no_stale(self, tmp_path, mock_git):
        ws = _copy_orphan(tmp_path)
        now = datetime(2026, 4, 25, 14, 30, tzinfo=timezone.utc)
        # Commit recente (<24h)
        mock_git.last_commit_at = now - timedelta(hours=1)
        result = detect_inconsistencies(ws, now=now)
        assert all(i.code != "STALE_IN_PROGRESS" for i in result)

    def test_completed_status_no_stale(self, tmp_path, mock_git):
        ws = _build_consistent_workspace(tmp_path)
        # status=COMPLETED_AWAITING_HUMAN -> stale check pula
        now = datetime(2026, 4, 25, 14, 30, tzinfo=timezone.utc)
        result = detect_inconsistencies(ws, now=now)
        assert all(i.code != "STALE_IN_PROGRESS" for i in result)


class TestDetectMissingCommit:
    def test_commit_sha_not_in_git(self, tmp_path, mock_git):
        ws = _copy_orphan(tmp_path)
        # Remove the orphan sha das existing
        # (deadbeef... ja nao esta em mock_git.existing_shas por padrao)
        now = datetime(2026, 4, 25, 14, 30, tzinfo=timezone.utc)
        result = detect_inconsistencies(ws, now=now)
        codes = [i.code for i in result]
        assert "MISSING_COMMIT" in codes
        # Mensagem deve mencionar deadbeef
        msg = next(i.message for i in result if i.code == "MISSING_COMMIT")
        assert "deadbeef" in msg

    def test_commit_sha_exists_no_inconsistency(self, tmp_path, mock_git):
        ws = _build_consistent_workspace(tmp_path)
        # consistent fixture usa "abc123def456" que ja esta em existing_shas
        now = datetime(2026, 4, 25, 14, 30, tzinfo=timezone.utc)
        result = detect_inconsistencies(ws, now=now)
        assert all(i.code != "MISSING_COMMIT" for i in result)


class TestDetectBranchMissing:
    def test_branch_missing(self, tmp_path, mock_git):
        ws = _build_consistent_workspace(tmp_path)
        # Remove branch das existing
        mock_git.existing_branches.discard("workspace/888-consistent")
        now = datetime(2026, 4, 25, 14, 30, tzinfo=timezone.utc)
        result = detect_inconsistencies(ws, now=now)
        codes = [i.code for i in result]
        assert "BRANCH_MISSING" in codes

    def test_branch_present_no_inconsistency(self, tmp_path, mock_git):
        ws = _build_consistent_workspace(tmp_path)
        now = datetime(2026, 4, 25, 14, 30, tzinfo=timezone.utc)
        result = detect_inconsistencies(ws, now=now)
        assert all(i.code != "BRANCH_MISSING" for i in result)


class TestDetectMultipleOrdering:
    def test_orphan_fixture_multiple_codes_deterministic_order(
        self, tmp_path, mock_git
    ):
        ws = _copy_orphan(tmp_path)
        # Force STALE: commit antigo
        mock_git.last_commit_at = datetime(
            2026, 4, 18, 0, 0, tzinfo=timezone.utc
        )
        now = datetime(2026, 4, 25, 14, 30, tzinfo=timezone.utc)
        result = detect_inconsistencies(ws, now=now)
        codes = [i.code for i in result]
        # Esperamos pelo menos: HASH_MISMATCH, MISSING_OUTPUT,
        # STALE_IN_PROGRESS, MISSING_COMMIT
        for expected in (
            "HASH_MISMATCH",
            "MISSING_COMMIT",
            "MISSING_OUTPUT",
            "STALE_IN_PROGRESS",
        ):
            assert expected in codes
        # Ordem deterministic: HASH > MISSING_COMMIT > MISSING_OUTPUT > STALE
        # > BRANCH_MISSING
        canonical_order = [
            "HASH_MISMATCH",
            "MISSING_COMMIT",
            "MISSING_OUTPUT",
            "STALE_IN_PROGRESS",
            "BRANCH_MISSING",
        ]
        # Filtra so codes presentes em result, na ordem canonica esperada
        expected_filtered = [c for c in canonical_order if c in codes]
        assert codes == expected_filtered


# Plan rendering tests --------------------------------------------------------

class TestProposeRecoveryPlan:
    def test_empty_inconsistencies_returns_consistent_message(self):
        out = propose_recovery_plan([])
        assert "consistent" in out.lower()

    def test_renders_three_options(self):
        inc = Inconsistency(
            code="HASH_MISMATCH",
            message="hash declarado divergiu",
            proposed_action="recompute hash + update L1",
            severity="warning",
            context={"declared": "0" * 64, "actual": "1" * 64},
        )
        out = propose_recovery_plan([inc])
        # 3 opcoes A/B/C visiveis
        assert "Plan A" in out
        assert "Plan B" in out
        assert "Plan C" in out
        # Code aparece
        assert "HASH_MISMATCH" in out
        # Acao proposta aparece
        assert "recompute hash" in out

    def test_renders_table_for_multiple(self):
        incs = [
            Inconsistency(
                code="HASH_MISMATCH",
                message="m1",
                proposed_action="a1",
                severity="warning",
                context={},
            ),
            Inconsistency(
                code="MISSING_COMMIT",
                message="m2",
                proposed_action="a2",
                severity="critical",
                context={},
            ),
        ]
        out = propose_recovery_plan(incs)
        assert "HASH_MISMATCH" in out
        assert "MISSING_COMMIT" in out
        assert "critical" in out
        assert "warning" in out


# Apply tests -----------------------------------------------------------------

class TestApplyRecovery:
    def test_apply_in_consistent_workspace_is_noop(self, tmp_path, mock_git):
        ws = _build_consistent_workspace(tmp_path)
        before = (ws / "CONTEXT.md").read_bytes()
        apply_recovery(ws, "A")
        after = (ws / "CONTEXT.md").read_bytes()
        assert before == after

    def test_apply_a_hash_mismatch_updates_hash(self, tmp_path, mock_git):
        ws = _copy_orphan(tmp_path)
        now = datetime(2026, 4, 25, 14, 30, tzinfo=timezone.utc)
        # ApplyRecovery deve usar 'now' tambem; expor via parametro
        apply_recovery(ws, "A", now=now)
        # Reler L1 e checar hash != 64 zeros
        import yaml
        content = (ws / "CONTEXT.md").read_text(encoding="utf-8")
        # Parse frontmatter
        body = content.split("---")[1]
        data = yaml.safe_load(body)
        assert data["profile_effective_hash"] != "0" * 64
        assert len(data["profile_effective_hash"]) == 64

    def test_apply_c_marks_blocked_error(self, tmp_path, mock_git):
        ws = _copy_orphan(tmp_path)
        now = datetime(2026, 4, 25, 14, 30, tzinfo=timezone.utc)
        apply_recovery(ws, "C", now=now)
        import yaml
        content = (ws / "CONTEXT.md").read_text(encoding="utf-8")
        body = content.split("---")[1]
        data = yaml.safe_load(body)
        assert data["status"] == "BLOCKED"  # v4.0
        assert data.get("block_reason") == "error"
        # History append
        assert any(
            ev.get("event") == "recovery_applied"
            for ev in data["history"]
        )

    def test_apply_invalid_choice_raises(self, tmp_path, mock_git):
        ws = _copy_orphan(tmp_path)
        with pytest.raises(RecoveryWizardError):
            apply_recovery(ws, "Z")

    def test_apply_a_appends_history(self, tmp_path, mock_git):
        ws = _copy_orphan(tmp_path)
        now = datetime(2026, 4, 25, 14, 30, tzinfo=timezone.utc)
        import yaml
        before_content = (ws / "CONTEXT.md").read_text(encoding="utf-8")
        before_data = yaml.safe_load(before_content.split("---")[1])
        before_history_len = len(before_data["history"])

        apply_recovery(ws, "A", now=now)

        after_content = (ws / "CONTEXT.md").read_text(encoding="utf-8")
        after_data = yaml.safe_load(after_content.split("---")[1])
        # Append-only: nunca encolhe
        assert len(after_data["history"]) > before_history_len
        # Last event eh recovery_applied
        assert after_data["history"][-1]["event"] == "recovery_applied"


# CLI tests --------------------------------------------------------------------

class TestCLI:
    def test_dry_run_does_not_modify_file(self, tmp_path, mock_git):
        ws = _copy_orphan(tmp_path)
        before = (ws / "CONTEXT.md").read_bytes()
        # Patch git no escopo do main()
        with mock.patch.object(recovery_wizard.subprocess, "run",
                               recovery_wizard.subprocess.run):
            rc = recovery_wizard.main([
                "--workspace", str(ws), "--dry-run"
            ])
        after = (ws / "CONTEXT.md").read_bytes()
        assert before == after
        # dry-run sempre exit 0 (audit mode)
        assert rc == 0

    def test_apply_modifies_file(self, tmp_path, mock_git):
        ws = _copy_orphan(tmp_path)
        before = (ws / "CONTEXT.md").read_bytes()
        rc = recovery_wizard.main([
            "--workspace", str(ws), "--apply", "A"
        ])
        after = (ws / "CONTEXT.md").read_bytes()
        assert before != after
        assert rc == 0

    def test_consistent_workspace_exits_0(self, tmp_path, mock_git, capsys):
        ws = _build_consistent_workspace(tmp_path)
        rc = recovery_wizard.main([
            "--workspace", str(ws), "--dry-run"
        ])
        assert rc == 0
        out = capsys.readouterr().out
        assert "consistent" in out.lower()

    def test_invalid_workspace_exits_1(self, tmp_path):
        rc = recovery_wizard.main([
            "--workspace", str(tmp_path / "does-not-exist"),
            "--dry-run",
        ])
        assert rc == 1

    def test_apply_invalid_choice_exits_nonzero(self, tmp_path, mock_git):
        ws = _copy_orphan(tmp_path)
        # argparse rejeita 'Q' (invalid choice) com SystemExit(2).
        # Aceitamos qualquer exit nao-zero como sucesso do guard.
        with pytest.raises(SystemExit) as exc_info:
            recovery_wizard.main([
                "--workspace", str(ws), "--apply", "Q"
            ])
        assert exc_info.value.code != 0


# ============================================================================
# G5 — CLAUDE_MD_ROOT_STALE / CLAUDE_MD_ROOT_MISSING (T1.1)
# ============================================================================


CODE_CLAUDE_MD_ROOT_STALE = recovery_wizard.CODE_CLAUDE_MD_ROOT_STALE
CODE_CLAUDE_MD_ROOT_MISSING = recovery_wizard.CODE_CLAUDE_MD_ROOT_MISSING


def _make_minimal_workspace(tmp_path: Path, *, stage_atual: str = "03",
                             status: str = "IN_PROGRESS") -> Path:
    """Cria workspace mínimo com L1 válido em tmp_path/project/workspaces/001-test."""
    project = tmp_path / "project"
    workspace = project / "workspaces" / "001-test"
    workspace.mkdir(parents=True)
    (workspace / "_config").mkdir()
    # profile-effective.yaml com hash conhecido
    eff = workspace / "_config" / "profile-effective.yaml"
    eff.write_text("dummy: data\n", encoding="utf-8")
    h = hashlib.sha256(eff.read_bytes()).hexdigest()
    # L1 com stage_atual e workspace
    l1 = workspace / "CONTEXT.md"
    l1.write_text(
        f"---\n"
        f"workspace: '001-test'\n"
        f"workspace_branch: 'workspace/001-test'\n"
        f"profile_base: 'app_web_backend'\n"
        f"tier: 'development'\n"
        f"profile_effective_hash: '{h}'\n"
        f"project_root: '{project}'\n"
        f"stage_atual: '{stage_atual}'\n"
        f"sub_stage: '{stage_atual}_in_progress'\n"
        f"status: '{status}'\n"
        f"iteration: 0\n"
        f"history: []\n"
        f"---\n\n# L1\n",
        encoding="utf-8",
    )
    return workspace


def test_claude_md_root_missing_when_no_file(tmp_path, mock_git):
    """workspace IN_PROGRESS + project_root sem CLAUDE.md → MISSING detectado."""
    workspace = _make_minimal_workspace(tmp_path)
    project = workspace.parent.parent
    incs = detect_inconsistencies(workspace, project_root=project)
    codes = [i.code for i in incs]
    assert CODE_CLAUDE_MD_ROOT_MISSING in codes


def test_claude_md_root_missing_when_no_block(tmp_path, mock_git):
    """CLAUDE.md existe mas sem bloco do workspace → MISSING."""
    workspace = _make_minimal_workspace(tmp_path)
    project = workspace.parent.parent
    (project / "CLAUDE.md").write_text(
        "# Project\n\n<!-- ICM-START -->\n## ICM\n(empty)\n<!-- ICM-END -->\n",
        encoding="utf-8",
    )
    incs = detect_inconsistencies(workspace, project_root=project)
    codes = [i.code for i in incs]
    assert CODE_CLAUDE_MD_ROOT_MISSING in codes


def test_claude_md_root_stale_when_stage_diverges(tmp_path, mock_git):
    """v4.0: L1.stage_atual=04 mas bloco no CLAUDE.md mostra 02 → STALE."""
    workspace = _make_minimal_workspace(tmp_path, stage_atual="04")
    project = workspace.parent.parent

    # Lazy import handoff to write block
    sys.path.insert(0, str(SCRIPT_DIR))
    import handoff
    block = handoff.WorkspaceBlock(
        workspace="001-test", profile="app_web_backend", tier="development",
        stage_atual="02", stage_dir="02_design", sub_stage="02_in_progress",
        iteration=0, status="IN_PROGRESS", last_action="stale", last_action_at="x",
        next_action="x",
    )
    handoff.update_project_claude_md(project, block, "/skill")

    incs = detect_inconsistencies(workspace, project_root=project)
    codes = [i.code for i in incs]
    assert CODE_CLAUDE_MD_ROOT_STALE in codes


def test_claude_md_root_consistent_no_inconsistency(tmp_path, mock_git):
    """v4.0: L1 and block in sync → detects nothing."""
    workspace = _make_minimal_workspace(tmp_path, stage_atual="02")
    project = workspace.parent.parent

    sys.path.insert(0, str(SCRIPT_DIR))
    import handoff
    block = handoff.WorkspaceBlock(
        workspace="001-test", profile="app_web_backend", tier="development",
        stage_atual="02", stage_dir="02_design", sub_stage="02_in_progress",
        iteration=0, status="IN_PROGRESS", last_action="ok", last_action_at="x",
        next_action="x",
    )
    handoff.update_project_claude_md(project, block, "/skill")

    incs = detect_inconsistencies(workspace, project_root=project)
    codes = [i.code for i in incs]
    assert CODE_CLAUDE_MD_ROOT_STALE not in codes
    assert CODE_CLAUDE_MD_ROOT_MISSING not in codes


def test_claude_md_root_skipped_when_status_not_in_progress(tmp_path, mock_git):
    """status=COMPLETED → does not fire MISSING/STALE."""
    workspace = _make_minimal_workspace(tmp_path, status="COMPLETED")
    project = workspace.parent.parent
    # sem CLAUDE.md
    incs = detect_inconsistencies(workspace, project_root=project)
    codes = [i.code for i in incs]
    assert CODE_CLAUDE_MD_ROOT_MISSING not in codes
    assert CODE_CLAUDE_MD_ROOT_STALE not in codes
