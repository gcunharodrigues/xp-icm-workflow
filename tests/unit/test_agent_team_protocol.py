"""Testes unitarios para scripts/agent-team-protocol.py.

Cobertura:
- spawn_worktree: happy path, path/branch ja existe, base invalido, return Path.
- cleanup_worktree: happy path, idempotente.
- mailbox_dir: cria se ausente, idempotente.
- write_message / read_messages: timestamp prefix, tipos invalidos, ordem
  cronologica, filtros.
- sync_barrier_check: complete, partial, vazio.
- detect_mid_wave_reduce_signal: blocked_cap, idle_timeout, none.
- record_mid_wave_reduce: snapshot escrito.

Tests usam tmp_path + git real (subprocess) — git for Windows fornece
git compativel em CI.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

# Carrega scripts/agent-team-protocol.py como modulo
SKILL_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = SKILL_ROOT / "scripts" / "agent-team-protocol.py"

_spec = importlib.util.spec_from_file_location("agent_team_protocol", SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
agent_team_protocol = importlib.util.module_from_spec(_spec)
sys.modules["agent_team_protocol"] = agent_team_protocol
_spec.loader.exec_module(agent_team_protocol)

spawn_worktree = agent_team_protocol.spawn_worktree
cleanup_worktree = agent_team_protocol.cleanup_worktree
mailbox_dir = agent_team_protocol.mailbox_dir
write_message = agent_team_protocol.write_message
read_messages = agent_team_protocol.read_messages
sync_barrier_check = agent_team_protocol.sync_barrier_check
detect_mid_wave_reduce_signal = agent_team_protocol.detect_mid_wave_reduce_signal
record_mid_wave_reduce = agent_team_protocol.record_mid_wave_reduce
Message = agent_team_protocol.Message
ReduceSignal = agent_team_protocol.ReduceSignal
WorktreeExists = agent_team_protocol.WorktreeExists
BranchExists = agent_team_protocol.BranchExists
WorktreeError = agent_team_protocol.WorktreeError
InvalidMessageType = agent_team_protocol.InvalidMessageType


# ============================================================================
# Helpers
# ============================================================================

def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Cria git repo limpo com branch main + 1 commit inicial."""
    repo = tmp_path / "project"
    repo.mkdir()
    _git(["init", "-b", "main"], cwd=repo)
    # Config local para permitir commit em CI sem global config
    _git(["config", "user.email", "test@example.com"], cwd=repo)
    _git(["config", "user.name", "Test User"], cwd=repo)
    _git(["config", "commit.gpgsign", "false"], cwd=repo)
    (repo / "README.md").write_text("# test\n", encoding="utf-8")
    _git(["add", "README.md"], cwd=repo)
    _git(["commit", "-m", "initial"], cwd=repo)
    return repo


@pytest.fixture
def workspace_root(tmp_path: Path) -> Path:
    """Cria estrutura minima de workspace (apenas a pasta raiz)."""
    ws = tmp_path / "workspaces" / "042-test"
    ws.mkdir(parents=True)
    return ws


def _write_task_output(
    workspace_root: Path,
    wave_n: int,
    slug: str,
    *,
    status: str = "COMPLETED",
    qa_cycles: int = 0,
    body: str = "task done",
    mtime_offset_min: float | None = None,
) -> Path:
    """Escreve task-<slug>.md com frontmatter minimal.

    Se mtime_offset_min for fornecido, ajusta mtime para now - offset.
    """
    wave_dir = (
        workspace_root
        / "stages"
        / "04_implementation_waves"
        / "output"
        / f"wave-{wave_n}"
    )
    wave_dir.mkdir(parents=True, exist_ok=True)
    path = wave_dir / f"task-{slug}.md"
    content = (
        f"---\n"
        f'task: "{slug}"\n'
        f'status: "{status}"\n'
        f"auto_qa_cycles: {qa_cycles}\n"
        f"---\n"
        f"\n"
        f"{body}\n"
    )
    path.write_text(content, encoding="utf-8")
    if mtime_offset_min is not None:
        new_mtime = time.time() - mtime_offset_min * 60
        os.utime(path, (new_mtime, new_mtime))
    return path


# ============================================================================
# spawn_worktree
# ============================================================================

class TestSpawnWorktree:
    def test_spawn_worktree_happy_path(self, git_repo: Path) -> None:
        wt = spawn_worktree(
            project_root=git_repo,
            workspace="042-x",
            wave_n=1,
            task_slug="task-a",
            base_branch="main",
        )
        assert wt.exists()
        assert wt.is_dir()
        # branch criada
        res = _git(["branch", "--list", "wave-042-x-1/task-a"], cwd=git_repo)
        assert "wave-042-x-1/task-a" in res.stdout

    def test_spawn_worktree_existing_path_raises_WorktreeExists(
        self, git_repo: Path
    ) -> None:
        spawn_worktree(
            project_root=git_repo,
            workspace="042-x",
            wave_n=1,
            task_slug="task-a",
            base_branch="main",
        )
        with pytest.raises(WorktreeExists):
            spawn_worktree(
                project_root=git_repo,
                workspace="042-x",
                wave_n=1,
                task_slug="task-a",
                base_branch="main",
            )

    def test_spawn_worktree_existing_branch_raises_BranchExists(
        self, git_repo: Path
    ) -> None:
        # Cria branch manualmente, depois remove path do worktree (mas branch
        # persiste no git)
        _git(
            ["branch", "wave-042-x-1/task-a", "main"],
            cwd=git_repo,
        )
        with pytest.raises(BranchExists):
            spawn_worktree(
                project_root=git_repo,
                workspace="042-x",
                wave_n=1,
                task_slug="task-a",
                base_branch="main",
            )

    def test_spawn_worktree_invalid_base_branch_raises_WorktreeError(
        self, git_repo: Path
    ) -> None:
        with pytest.raises(WorktreeError, match="base_branch"):
            spawn_worktree(
                project_root=git_repo,
                workspace="042-x",
                wave_n=1,
                task_slug="task-a",
                base_branch="nope-not-real",
            )

    def test_spawn_worktree_returns_path(self, git_repo: Path) -> None:
        wt = spawn_worktree(
            project_root=git_repo,
            workspace="042-x",
            wave_n=2,
            task_slug="task-b",
            base_branch="main",
        )
        assert isinstance(wt, Path)
        expected = (
            git_repo / ".worktrees" / "workspace-042-x" / "wave-2" / "task-b"
        )
        assert wt.resolve() == expected.resolve()

    def test_spawn_worktree_non_git_repo_raises(self, tmp_path: Path) -> None:
        # tmp_path nao tem .git
        with pytest.raises(WorktreeError, match="git repo"):
            spawn_worktree(
                project_root=tmp_path,
                workspace="042-x",
                wave_n=1,
                task_slug="task-a",
                base_branch="main",
            )


# ============================================================================
# cleanup_worktree
# ============================================================================

class TestCleanupWorktree:
    def test_cleanup_worktree_happy_path(self, git_repo: Path) -> None:
        wt = spawn_worktree(
            project_root=git_repo,
            workspace="042-x",
            wave_n=1,
            task_slug="task-a",
            base_branch="main",
        )
        assert wt.exists()
        cleanup_worktree(
            project_root=git_repo,
            workspace="042-x",
            wave_n=1,
            task_slug="task-a",
        )
        assert not wt.exists()

    def test_cleanup_worktree_idempotent(self, git_repo: Path) -> None:
        # Worktree nunca existiu — cleanup deve emitir warning, nao raise.
        with pytest.warns(UserWarning, match="ja inexistente"):
            cleanup_worktree(
                project_root=git_repo,
                workspace="042-x",
                wave_n=1,
                task_slug="task-a",
            )


# ============================================================================
# mailbox_dir
# ============================================================================

class TestMailboxDir:
    def test_mailbox_dir_creates_if_absent(self, workspace_root: Path) -> None:
        mb = mailbox_dir(workspace_root, wave_n=1)
        assert mb.exists()
        assert mb.is_dir()
        expected = (
            workspace_root
            / "stages"
            / "04_implementation_waves"
            / "output"
            / "wave-1"
            / "mailbox"
        )
        assert mb.resolve() == expected.resolve()

    def test_mailbox_dir_idempotent(self, workspace_root: Path) -> None:
        mb1 = mailbox_dir(workspace_root, wave_n=1)
        mb2 = mailbox_dir(workspace_root, wave_n=1)
        assert mb1 == mb2
        assert mb1.exists()


# ============================================================================
# write_message / read_messages
# ============================================================================

class TestWriteMessage:
    def test_write_message_creates_file_with_timestamp_prefix(
        self, workspace_root: Path
    ) -> None:
        mb = mailbox_dir(workspace_root, wave_n=1)
        at = datetime(2026, 4, 26, 10, 30, 0, tzinfo=timezone.utc)
        path = write_message(
            mb,
            from_="lead",
            to_="teammate-a",
            msg_type="status_update",
            body="all good",
            at=at,
        )
        assert path.exists()
        # Filename Windows-safe (sem `:`)
        assert ":" not in path.name
        assert path.name.startswith("2026-04-26T10-30-00")
        assert path.name.endswith("-lead-teammate-a-status_update.md")
        text = path.read_text(encoding="utf-8")
        assert "all good" in text
        assert 'from: "lead"' in text

    def test_write_message_invalid_type_raises_InvalidMessageType(
        self, workspace_root: Path
    ) -> None:
        mb = mailbox_dir(workspace_root, wave_n=1)
        with pytest.raises(InvalidMessageType, match="msg_type invalido"):
            write_message(
                mb,
                from_="lead",
                to_="teammate-a",
                msg_type="bogus_type",
                body="hi",
            )

    def test_write_message_default_at_is_now(self, workspace_root: Path) -> None:
        mb = mailbox_dir(workspace_root, wave_n=1)
        path = write_message(
            mb, from_="lead", to_="t1", msg_type="blocked", body="x"
        )
        # Filename comeca com 4 digitos (ano)
        assert path.name[:4].isdigit()


class TestReadMessages:
    def _make_mailbox_with_msgs(self, workspace_root: Path) -> Path:
        mb = mailbox_dir(workspace_root, wave_n=1)
        write_message(
            mb,
            from_="lead",
            to_="t1",
            msg_type="status_update",
            body="m1",
            at=datetime(2026, 4, 26, 10, 0, tzinfo=timezone.utc),
        )
        write_message(
            mb,
            from_="t1",
            to_="lead",
            msg_type="blocked",
            body="m2",
            at=datetime(2026, 4, 26, 10, 5, tzinfo=timezone.utc),
        )
        write_message(
            mb,
            from_="lead",
            to_="t2",
            msg_type="request_review",
            body="m3",
            at=datetime(2026, 4, 26, 10, 10, tzinfo=timezone.utc),
        )
        return mb

    def test_read_messages_returns_chronological_order(
        self, workspace_root: Path
    ) -> None:
        mb = self._make_mailbox_with_msgs(workspace_root)
        msgs = read_messages(mb)
        assert len(msgs) == 3
        assert [m.body.strip() for m in msgs] == ["m1", "m2", "m3"]
        # crescentes
        for a, b in zip(msgs, msgs[1:]):
            assert a.at <= b.at

    def test_read_messages_filter_by_to(self, workspace_root: Path) -> None:
        mb = self._make_mailbox_with_msgs(workspace_root)
        msgs = read_messages(mb, to_="lead")
        assert len(msgs) == 1
        assert msgs[0].body.strip() == "m2"
        assert msgs[0].from_ == "t1"

    def test_read_messages_filter_by_type(self, workspace_root: Path) -> None:
        mb = self._make_mailbox_with_msgs(workspace_root)
        msgs = read_messages(mb, type_="status_update")
        assert len(msgs) == 1
        assert msgs[0].body.strip() == "m1"

    def test_read_messages_empty_when_mailbox_empty(
        self, workspace_root: Path
    ) -> None:
        mb = mailbox_dir(workspace_root, wave_n=1)
        msgs = read_messages(mb)
        assert msgs == []

    def test_read_messages_returns_messages_with_correct_fields(
        self, workspace_root: Path
    ) -> None:
        mb = mailbox_dir(workspace_root, wave_n=1)
        write_message(
            mb,
            from_="lead",
            to_="t1",
            msg_type="status_update",
            body="hello",
            at=datetime(2026, 4, 26, 10, 0, tzinfo=timezone.utc),
        )
        msgs = read_messages(mb)
        assert len(msgs) == 1
        m = msgs[0]
        assert isinstance(m, Message)
        assert m.from_ == "lead"
        assert m.to_ == "t1"
        assert m.type == "status_update"
        assert m.body.strip() == "hello"
        assert m.path.exists()


# ============================================================================
# sync_barrier_check
# ============================================================================

class TestSyncBarrier:
    def test_sync_barrier_all_complete_returns_true(
        self, workspace_root: Path
    ) -> None:
        _write_task_output(workspace_root, 1, "task-a")
        _write_task_output(workspace_root, 1, "task-b")
        all_complete, completed = sync_barrier_check(
            workspace_root, wave_n=1, expected_tasks={"task-a", "task-b"}
        )
        assert all_complete is True
        assert completed == {"task-a", "task-b"}

    def test_sync_barrier_partial_returns_false_with_completed_set(
        self, workspace_root: Path
    ) -> None:
        _write_task_output(workspace_root, 1, "task-a")
        all_complete, completed = sync_barrier_check(
            workspace_root,
            wave_n=1,
            expected_tasks={"task-a", "task-b"},
        )
        assert all_complete is False
        assert completed == {"task-a"}

    def test_sync_barrier_no_files_returns_false_empty_set(
        self, workspace_root: Path
    ) -> None:
        all_complete, completed = sync_barrier_check(
            workspace_root,
            wave_n=1,
            expected_tasks={"task-a", "task-b"},
        )
        assert all_complete is False
        assert completed == set()


# ============================================================================
# Mid-wave reduce
# ============================================================================

class TestDetectMidWaveReduceSignal:
    def test_detect_reduce_signal_blocked_cap_exceeded(
        self, workspace_root: Path
    ) -> None:
        # task-a com auto_qa_cycles=4 (>=3 cap default)
        _write_task_output(
            workspace_root,
            1,
            "task-a",
            status="IN_PROGRESS",
            qa_cycles=4,
        )
        _write_task_output(workspace_root, 1, "task-b", status="COMPLETED")
        signal = detect_mid_wave_reduce_signal(
            workspace_root,
            wave_n=1,
            expected_tasks={"task-a", "task-b"},
            now=datetime.now(timezone.utc),
        )
        assert signal is not None
        assert signal.reason == "blocked_cap_exceeded"
        assert signal.blocked_tasks == ["task-a"]
        assert signal.idle_tasks == []

    def test_detect_reduce_signal_idle_timeout(
        self, workspace_root: Path
    ) -> None:
        # task-a IN_PROGRESS, mtime 60min atras (> threshold default 30)
        _write_task_output(
            workspace_root,
            1,
            "task-a",
            status="IN_PROGRESS",
            qa_cycles=1,
            mtime_offset_min=60.0,
        )
        signal = detect_mid_wave_reduce_signal(
            workspace_root,
            wave_n=1,
            expected_tasks={"task-a"},
            idle_threshold_min=30,
            blocked_cap=3,
        )
        assert signal is not None
        assert signal.reason == "idle_timeout"
        assert signal.idle_tasks == ["task-a"]
        assert signal.blocked_tasks == []

    def test_detect_reduce_signal_both(self, workspace_root: Path) -> None:
        _write_task_output(
            workspace_root,
            1,
            "task-a",
            status="IN_PROGRESS",
            qa_cycles=5,  # blocked
        )
        _write_task_output(
            workspace_root,
            1,
            "task-b",
            status="IN_PROGRESS",
            qa_cycles=0,
            mtime_offset_min=120.0,  # idle
        )
        signal = detect_mid_wave_reduce_signal(
            workspace_root,
            wave_n=1,
            expected_tasks={"task-a", "task-b"},
        )
        assert signal is not None
        assert signal.reason == "both"
        assert "task-a" in signal.blocked_tasks
        assert "task-b" in signal.idle_tasks

    def test_detect_reduce_signal_none_when_clean(
        self, workspace_root: Path
    ) -> None:
        _write_task_output(
            workspace_root,
            1,
            "task-a",
            status="COMPLETED",
            qa_cycles=1,
        )
        _write_task_output(
            workspace_root,
            1,
            "task-b",
            status="IN_PROGRESS",
            qa_cycles=0,
            mtime_offset_min=5.0,  # nao idle
        )
        signal = detect_mid_wave_reduce_signal(
            workspace_root,
            wave_n=1,
            expected_tasks={"task-a", "task-b"},
            idle_threshold_min=30,
            blocked_cap=3,
        )
        assert signal is None

    def test_detect_reduce_signal_none_when_no_files(
        self, workspace_root: Path
    ) -> None:
        signal = detect_mid_wave_reduce_signal(
            workspace_root,
            wave_n=1,
            expected_tasks={"task-a", "task-b"},
        )
        assert signal is None


class TestRecordMidWaveReduce:
    def test_record_mid_wave_reduce_writes_snapshot(
        self, workspace_root: Path
    ) -> None:
        signal = ReduceSignal(
            reason="blocked_cap_exceeded",
            blocked_tasks=["task-a"],
            idle_tasks=[],
        )
        path = record_mid_wave_reduce(
            workspace_root,
            wave_n=1,
            signal=signal,
            at=datetime(2026, 4, 26, 12, 0, tzinfo=timezone.utc),
        )
        assert path.exists()
        assert path.name == "mid-wave-reduce.md"
        text = path.read_text(encoding="utf-8")
        assert "wave 1" in text
        assert "blocked_cap_exceeded" in text
        assert "task-a" in text
        assert "Blocked tasks" in text
        assert "Idle tasks" in text
        assert "Acao recomendada" in text

    def test_record_mid_wave_reduce_handles_empty_lists(
        self, workspace_root: Path
    ) -> None:
        signal = ReduceSignal(
            reason="idle_timeout",
            blocked_tasks=[],
            idle_tasks=["task-x"],
        )
        path = record_mid_wave_reduce(workspace_root, wave_n=2, signal=signal)
        text = path.read_text(encoding="utf-8")
        assert "_(none)_" in text  # blocked vazio
        assert "task-x" in text


# ============================================================================
# CLI --help
# ============================================================================

class TestCli:
    def test_help_flag_lists_public_api(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "spawn_worktree" in result.stdout
        assert "mailbox_dir" in result.stdout
        assert "write_message" in result.stdout
        assert "sync_barrier_check" in result.stdout

    def test_main_no_args_prints_help_and_exits_0(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "API publica" in result.stdout or "spawn_worktree" in result.stdout
