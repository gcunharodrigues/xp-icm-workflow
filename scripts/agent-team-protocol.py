"""Helpers do protocolo Agent Team na fase 04 (implementation waves).

Biblioteca de funcoes utilitarias que o lead session usa para gerenciar:

- worktrees git por teammate (spawn/cleanup);
- mailbox de mensagens entre lead e teammates (status_update, blocked,
  request_review, review_complete, reduce_signal);
- sync barrier check (todos teammates COMPLETE antes de fechar wave);
- mid-wave reduce signal detection (tasks travadas / idle timeout — D'').

Nao e um agente runtime. Nao tem CLI funcional alem de --help (lista API
publica para discovery). E modulo Python importado pelo lead session via
`from agent_team_protocol import spawn_worktree, ...` ou similar.

Convencoes:
- Dataclasses + type hints explicitos (Pyright-friendly).
- Docstrings em portugues.
- Filenames de mensagem usam timestamp ISO sem `:` (Windows-safe).
- Worktree path: `<project_root>/.worktrees/workspace-<workspace>/wave-<N>/<slug>/`.
- Branch name: `wave-<workspace>-<N>/<slug>`.

Decisoes de design:
- spawn_worktree e estrito (raise se path/branch ja existe). Idempotencia
  e do orquestrador — script nao adivinha.
- cleanup_worktree e tolerante (warning se ja foi removido). Garante
  idempotencia em pre-flight checks.
- detect_mid_wave_reduce_signal le state de task-<slug>.md no FS (campos
  status, auto_qa_cycles, mtime). Nao polla mailbox — single source of
  truth e o output file declarado pelo teammate.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import warnings
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# ============================================================================
# Constantes
# ============================================================================

VALID_MESSAGE_TYPES: tuple[str, ...] = (
    "status_update",
    "blocked",
    "request_review",
    "review_complete",
    "reduce_signal",
)

# Filename pattern: <iso-noColon>-<from>-<to>-<type>.md
MESSAGE_FILENAME_RE = re.compile(
    r"^(?P<at>\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}(?:\.\d+)?)"
    r"-(?P<from>[a-z0-9_-]+)"
    r"-(?P<to>[a-z0-9_-]+)"
    r"-(?P<type>[a-z_]+)\.md$"
)

# Frontmatter minimal pra parse
FRONTMATTER_RE = re.compile(
    r"^---\n(?P<fm>.*?)\n---\n(?P<body>.*)$",
    re.DOTALL,
)

# Frontmatter de task-<slug>.md (snapshot por teammate)
TASK_STATUS_RE = re.compile(r"^status:\s*\"?([A-Z_]+)\"?\s*$", re.MULTILINE)
TASK_QA_CYCLES_RE = re.compile(r"^auto_qa_cycles:\s*(\d+)\s*$", re.MULTILINE)


# ============================================================================
# Errors
# ============================================================================

class WorktreeError(Exception):
    """Erro generico de operacao sobre worktree (git falhou, base invalido, etc)."""


class WorktreeExists(WorktreeError):
    """Worktree path ja existe — spawn deve recusar (idempotencia explicita)."""


class BranchExists(WorktreeError):
    """Branch git ja existe — spawn deve recusar (idempotencia explicita)."""


class InvalidMessageType(Exception):
    """Tipo de mensagem fora do conjunto canonico VALID_MESSAGE_TYPES."""


# ============================================================================
# Dataclasses
# ============================================================================

@dataclass
class Message:
    """Mensagem persistida no mailbox entre lead e teammates.

    Campos:
        from_: identificador do remetente (lead, teammate-<slug>, etc).
        to_: identificador do destinatario.
        at: datetime UTC do envio (parsed do filename).
        type: um de VALID_MESSAGE_TYPES.
        body: corpo markdown apos frontmatter (pode ser vazio).
        path: caminho absoluto do arquivo no mailbox.
    """
    from_: str
    to_: str
    at: datetime
    type: str
    body: str
    path: Path


@dataclass
class ReduceSignal:
    """Sinal de mid-wave reduce (D'') — lead deve encerrar wave parcial.

    Campos:
        reason: "blocked_cap_exceeded" | "idle_timeout" | "both".
        blocked_tasks: slugs com auto_qa_cycles >= cap.
        idle_tasks: slugs IN_PROGRESS sem mtime update ha > threshold.
    """
    reason: str
    blocked_tasks: list[str] = field(default_factory=list)
    idle_tasks: list[str] = field(default_factory=list)


# ============================================================================
# Worktree helpers
# ============================================================================

def _git(args: list[str], cwd: Path, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Wrapper de git com captura de stdout/stderr."""
    cmd = ["git", "-C", str(cwd), *args]
    return subprocess.run(cmd, check=check, capture_output=True, text=True)


def _worktree_path(project_root: Path, workspace: str, wave_n: int, task_slug: str) -> Path:
    """Caminho canonico do worktree."""
    return (
        project_root
        / ".worktrees"
        / f"workspace-{workspace}"
        / f"wave-{wave_n}"
        / task_slug
    )


def _branch_name(workspace: str, wave_n: int, task_slug: str) -> str:
    """Nome canonico da branch."""
    return f"wave-{workspace}-{wave_n}/{task_slug}"


def _branch_exists(project_root: Path, branch: str) -> bool:
    """Retorna True se branch existe localmente (refs/heads/<branch>)."""
    res = _git(
        ["rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"],
        cwd=project_root,
        check=False,
    )
    return res.returncode == 0


def _ref_exists(project_root: Path, ref: str) -> bool:
    """Retorna True se ref (branch/tag/sha) e resolvivel."""
    res = _git(
        ["rev-parse", "--verify", "--quiet", ref],
        cwd=project_root,
        check=False,
    )
    return res.returncode == 0


def spawn_worktree(
    project_root: Path,
    workspace: str,
    wave_n: int,
    task_slug: str,
    base_branch: str,
) -> Path:
    """Cria git worktree para um teammate da wave.

    Path: `<project_root>/.worktrees/workspace-<workspace>/wave-<N>/<task_slug>/`.
    Branch: `wave-<workspace>-<N>/<task_slug>` criada de `<base_branch>`.

    Args:
        project_root: raiz do projeto (deve ser git repo).
        workspace: identificador do workspace (ex: "042-feature-x").
        wave_n: numero da wave (1, 2, ...).
        task_slug: slug kebab-case da task.
        base_branch: branch existente da qual derivar.

    Raises:
        WorktreeError: project_root nao e git repo OU base_branch invalido.
        WorktreeExists: path do worktree ja existe.
        BranchExists: branch ja existe localmente.

    Returns:
        Path absoluto do worktree criado.
    """
    if not (project_root / ".git").exists():
        raise WorktreeError(
            f"project_root nao e git repo: {project_root} (faltando .git)"
        )

    if not _ref_exists(project_root, base_branch):
        raise WorktreeError(
            f"base_branch nao existe: {base_branch!r} em {project_root}"
        )

    wt_path = _worktree_path(project_root, workspace, wave_n, task_slug)
    branch = _branch_name(workspace, wave_n, task_slug)

    if wt_path.exists():
        raise WorktreeExists(f"worktree path ja existe: {wt_path}")

    if _branch_exists(project_root, branch):
        raise BranchExists(f"branch ja existe: {branch}")

    # Garante diretorio pai
    wt_path.parent.mkdir(parents=True, exist_ok=True)

    res = _git(
        ["worktree", "add", str(wt_path), "-b", branch, base_branch],
        cwd=project_root,
        check=False,
    )
    if res.returncode != 0:
        raise WorktreeError(
            f"git worktree add falhou (rc={res.returncode}): "
            f"{res.stderr.strip()}"
        )

    return wt_path


def cleanup_worktree(
    project_root: Path,
    workspace: str,
    wave_n: int,
    task_slug: str,
) -> None:
    """Remove worktree de teammate (idempotente).

    Tolera worktree ja removido (warning, nao raise). Util em pre-flight
    checks de wave subsequente.

    Args:
        project_root: raiz do projeto.
        workspace: identificador do workspace.
        wave_n: numero da wave.
        task_slug: slug kebab-case.
    """
    wt_path = _worktree_path(project_root, workspace, wave_n, task_slug)

    if not wt_path.exists():
        warnings.warn(
            f"cleanup_worktree: path ja inexistente: {wt_path}",
            stacklevel=2,
        )
        # Mesmo com path inexistente, tenta git worktree prune pra limpar
        # registros stale (best effort; ignora falha).
        _git(["worktree", "prune"], cwd=project_root, check=False)
        return

    res = _git(
        ["worktree", "remove", str(wt_path), "--force"],
        cwd=project_root,
        check=False,
    )
    if res.returncode != 0:
        # Best effort: prune e ignora
        _git(["worktree", "prune"], cwd=project_root, check=False)
        warnings.warn(
            f"cleanup_worktree: git worktree remove falhou ({res.stderr.strip()}); "
            "prune chamado",
            stacklevel=2,
        )


# ============================================================================
# Mailbox helpers
# ============================================================================

def mailbox_dir(workspace_root: Path, wave_n: int) -> Path:
    """Retorna (e cria se ausente) diretorio do mailbox para a wave.

    Path: `<workspace_root>/stages/04_implementation_waves/output/wave-<N>/mailbox/`.

    Args:
        workspace_root: raiz do workspace (ex: project/workspaces/042-x/).
        wave_n: numero da wave.

    Returns:
        Path do diretorio mailbox (criado, idempotente).
    """
    mb = (
        workspace_root
        / "stages"
        / "04_implementation_waves"
        / "output"
        / f"wave-{wave_n}"
        / "mailbox"
    )
    mb.mkdir(parents=True, exist_ok=True)
    return mb


def _windows_safe_iso(at: datetime) -> str:
    """ISO 8601 sem `:` (Windows-safe). Ex: 2026-04-26T10-30-00."""
    # Sem timezone offset no filename (ja usamos UTC implicito); apenas
    # date+time. Replace ':' por '-'.
    iso = at.strftime("%Y-%m-%dT%H-%M-%S")
    # Microsegundos opcionais para evitar colisao em testes com calls rapidas.
    if at.microsecond:
        iso = f"{iso}.{at.microsecond:06d}"
    return iso


def write_message(
    mailbox: Path,
    from_: str,
    to_: str,
    msg_type: str,
    body: str,
    *,
    at: datetime | None = None,
) -> Path:
    """Escreve mensagem no mailbox com filename timestamp-prefixed.

    Filename: `<at-noColon>-<from>-<to>-<type>.md` (Windows-safe).
    Conteudo: frontmatter yaml + body markdown.

    Args:
        mailbox: diretorio criado por mailbox_dir().
        from_: identificador do remetente.
        to_: identificador do destinatario.
        msg_type: um de VALID_MESSAGE_TYPES.
        body: corpo markdown (pode ser vazio).
        at: timestamp opcional (default: now UTC).

    Raises:
        InvalidMessageType: msg_type fora do conjunto canonico.

    Returns:
        Path do arquivo criado.
    """
    if msg_type not in VALID_MESSAGE_TYPES:
        raise InvalidMessageType(
            f"msg_type invalido: {msg_type!r} "
            f"(esperado um de {VALID_MESSAGE_TYPES})"
        )

    at_dt = at if at is not None else datetime.now(timezone.utc)
    iso = _windows_safe_iso(at_dt)
    iso_full = at_dt.isoformat()

    filename = f"{iso}-{from_}-{to_}-{msg_type}.md"
    path = mailbox / filename

    fm_lines = [
        "---",
        f'from: "{from_}"',
        f'to: "{to_}"',
        f'at: "{iso_full}"',
        f'type: "{msg_type}"',
        "---",
        "",
        body,
    ]
    path.write_text("\n".join(fm_lines), encoding="utf-8")
    return path


def _parse_message_file(path: Path) -> Message | None:
    """Parse arquivo de mensagem. Retorna None se nome nao bate com schema."""
    match = MESSAGE_FILENAME_RE.match(path.name)
    if match is None:
        return None

    raw_at = match.group("at")
    # Reverter `T<H>-<M>-<S>` para `T<H>:<M>:<S>` para parse ISO
    iso_norm = re.sub(
        r"T(\d{2})-(\d{2})-(\d{2})",
        r"T\1:\2:\3",
        raw_at,
    )
    try:
        at = datetime.fromisoformat(iso_norm)
    except ValueError:
        return None

    if at.tzinfo is None:
        at = at.replace(tzinfo=timezone.utc)

    text = path.read_text(encoding="utf-8")
    body = ""
    fm_match = FRONTMATTER_RE.match(text)
    if fm_match:
        body = fm_match.group("body").lstrip("\n")

    return Message(
        from_=match.group("from"),
        to_=match.group("to"),
        at=at,
        type=match.group("type"),
        body=body,
        path=path,
    )


def read_messages(
    mailbox: Path,
    to_: str | None = None,
    type_: str | None = None,
) -> list[Message]:
    """Le mensagens do mailbox em ordem cronologica.

    Args:
        mailbox: diretorio do mailbox (mailbox_dir()).
        to_: filtro opcional por destinatario.
        type_: filtro opcional por tipo de mensagem.

    Returns:
        Lista de Message ordenada por `at` ascendente. Lista vazia se
        mailbox inexistente ou sem matches.
    """
    if not mailbox.exists():
        return []

    msgs: list[Message] = []
    for f in mailbox.iterdir():
        if not f.is_file() or not f.name.endswith(".md"):
            continue
        msg = _parse_message_file(f)
        if msg is None:
            continue
        if to_ is not None and msg.to_ != to_:
            continue
        if type_ is not None and msg.type != type_:
            continue
        msgs.append(msg)

    msgs.sort(key=lambda m: (m.at, m.path.name))
    return msgs


# ============================================================================
# Sync barrier
# ============================================================================

def _wave_output_dir(workspace_root: Path, wave_n: int) -> Path:
    return (
        workspace_root
        / "stages"
        / "04_implementation_waves"
        / "output"
        / f"wave-{wave_n}"
    )


def sync_barrier_check(
    workspace_root: Path,
    wave_n: int,
    expected_tasks: set[str],
) -> tuple[bool, set[str]]:
    """Verifica se todos teammates sinalizaram COMPLETE.

    Criterio: arquivo `task-<slug>.md` existe em `<wave>/output/wave-<N>/`.
    A presenca do arquivo e o sinal canonico de COMPLETE (escrita atomica
    pelo teammate apos auto-QA passar).

    Args:
        workspace_root: raiz do workspace.
        wave_n: numero da wave.
        expected_tasks: set de slugs esperados.

    Returns:
        (all_complete, completed_set). all_complete=True se
        completed_set >= expected_tasks.
    """
    wave_dir = _wave_output_dir(workspace_root, wave_n)
    completed: set[str] = set()

    if wave_dir.exists():
        for f in wave_dir.iterdir():
            if not f.is_file():
                continue
            if f.name.startswith("task-") and f.name.endswith(".md"):
                slug = f.name[len("task-"):-len(".md")]
                completed.add(slug)

    all_complete = expected_tasks.issubset(completed)
    return (all_complete, completed)


# ============================================================================
# Mid-wave reduce signal (D'')
# ============================================================================

def _read_task_state(
    workspace_root: Path,
    wave_n: int,
    task_slug: str,
) -> tuple[str | None, int, datetime | None]:
    """Le task-<slug>.md (parcial ou final). Retorna (status, qa_cycles, mtime).

    Se arquivo nao existe: (None, 0, None).
    """
    path = _wave_output_dir(workspace_root, wave_n) / f"task-{task_slug}.md"
    if not path.exists():
        return (None, 0, None)

    text = path.read_text(encoding="utf-8")
    status_m = TASK_STATUS_RE.search(text)
    qa_m = TASK_QA_CYCLES_RE.search(text)
    status = status_m.group(1) if status_m else None
    qa_cycles = int(qa_m.group(1)) if qa_m else 0
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return (status, qa_cycles, mtime)


def detect_mid_wave_reduce_signal(
    workspace_root: Path,
    wave_n: int,
    expected_tasks: set[str],
    idle_threshold_min: int = 30,
    blocked_cap: int = 3,
    *,
    now: datetime | None = None,
) -> ReduceSignal | None:
    """Detecta condicoes de mid-wave reduce (D'').

    Condicoes:
    - blocked_cap_exceeded: task com auto_qa_cycles >= blocked_cap.
    - idle_timeout: task IN_PROGRESS sem mtime update ha > idle_threshold_min.

    Args:
        workspace_root: raiz do workspace.
        wave_n: numero da wave.
        expected_tasks: slugs da wave.
        idle_threshold_min: minutos sem update para idle (default 30).
        blocked_cap: ciclos auto-QA para considerar blocked (default 3).
        now: datetime atual (default: now UTC). Util para testes.

    Returns:
        ReduceSignal com reason ∈ {blocked_cap_exceeded, idle_timeout, both}.
        None se nenhuma condicao satisfeita.
    """
    now_dt = now if now is not None else datetime.now(timezone.utc)
    blocked: list[str] = []
    idle: list[str] = []

    for slug in sorted(expected_tasks):
        status, qa_cycles, mtime = _read_task_state(workspace_root, wave_n, slug)

        if qa_cycles >= blocked_cap:
            blocked.append(slug)

        if status == "IN_PROGRESS" and mtime is not None:
            idle_min = (now_dt - mtime).total_seconds() / 60.0
            if idle_min > idle_threshold_min:
                idle.append(slug)

    if not blocked and not idle:
        return None

    if blocked and idle:
        reason = "both"
    elif blocked:
        reason = "blocked_cap_exceeded"
    else:
        reason = "idle_timeout"

    return ReduceSignal(reason=reason, blocked_tasks=blocked, idle_tasks=idle)


def record_mid_wave_reduce(
    workspace_root: Path,
    wave_n: int,
    signal: ReduceSignal,
    *,
    at: datetime | None = None,
) -> Path:
    """Persiste snapshot do reduce signal em mid-wave-reduce.md.

    Path: `<workspace_root>/stages/04_implementation_waves/output/wave-<N>/mid-wave-reduce.md`.

    Args:
        workspace_root: raiz do workspace.
        wave_n: numero da wave.
        signal: ReduceSignal a persistir.
        at: timestamp do registro (default: now UTC).

    Returns:
        Path do arquivo criado.
    """
    at_dt = at if at is not None else datetime.now(timezone.utc)
    wave_dir = _wave_output_dir(workspace_root, wave_n)
    wave_dir.mkdir(parents=True, exist_ok=True)
    path = wave_dir / "mid-wave-reduce.md"

    blocked_section = (
        "\n".join(f"- {s}" for s in signal.blocked_tasks)
        if signal.blocked_tasks
        else "_(none)_"
    )
    idle_section = (
        "\n".join(f"- {s}" for s in signal.idle_tasks)
        if signal.idle_tasks
        else "_(none)_"
    )

    content = (
        f"# Mid-wave reduce signal — wave {wave_n}\n"
        f"\n"
        f"- Detected at: `{at_dt.isoformat()}`\n"
        f"- Reason: `{signal.reason}`\n"
        f"\n"
        f"## Blocked tasks (auto_qa_cycles >= cap)\n"
        f"\n"
        f"{blocked_section}\n"
        f"\n"
        f"## Idle tasks (IN_PROGRESS, no mtime update > threshold)\n"
        f"\n"
        f"{idle_section}\n"
        f"\n"
        f"## Acao recomendada\n"
        f"\n"
        f"Lead encerra wave parcial com BLOCKED + snapshot pra humano.\n"
        f"Tasks completas sao mergeadas; tasks blocked/idle viram backlog\n"
        f"da proxima wave (re-planejar com wave-planner-script.py).\n"
    )
    path.write_text(content, encoding="utf-8")
    return path


# ============================================================================
# CLI (--help only; modulo nao tem CLI funcional)
# ============================================================================

PUBLIC_API: tuple[str, ...] = (
    "spawn_worktree(project_root, workspace, wave_n, task_slug, base_branch) -> Path",
    "cleanup_worktree(project_root, workspace, wave_n, task_slug) -> None",
    "mailbox_dir(workspace_root, wave_n) -> Path",
    "write_message(mailbox, from_, to_, msg_type, body) -> Path",
    "read_messages(mailbox, to_=None, type_=None) -> list[Message]",
    "sync_barrier_check(workspace_root, wave_n, expected_tasks) -> tuple[bool, set[str]]",
    "detect_mid_wave_reduce_signal(workspace_root, wave_n, expected_tasks, ...) -> ReduceSignal | None",
    "record_mid_wave_reduce(workspace_root, wave_n, signal) -> Path",
)


def _build_parser() -> argparse.ArgumentParser:
    api_block = "\n".join(f"  {fn}" for fn in PUBLIC_API)
    parser = argparse.ArgumentParser(
        prog="agent-team-protocol.py",
        description=(
            "Helpers Python do protocolo Agent Team (fase 04). "
            "Modulo importado pelo lead session — sem CLI funcional. "
            "Use --help para discovery da API publica.\n\n"
            f"API publica:\n{api_block}"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    parser.parse_args(argv)
    # Sem args funcionais; --help imprime acima e sai 0.
    print(parser.format_help())
    return 0


if __name__ == "__main__":
    sys.exit(main())
