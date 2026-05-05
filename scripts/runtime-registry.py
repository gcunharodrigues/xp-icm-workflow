"""Runtime registry — tracking of active side-effects per workspace (v3.7.0).

Registers processes, containers and tasks that must be cleaned up before
the stage 08 exit transition (A close, B restart, C spawn). Replaces the
ad-hoc PID file `.icm-main/.dev-server.pid` from v3.6.0 with a structured
JSON at `<workspace>/_state/runtime-registry.json` (gitignored).

Canonical doc: `references/runtime-cleanup-protocol.md`.

Schema:
    {
      "version": 1,
      "workspace": "001-001-saas-psicologo-mvp",
      "entries": [
        {
          "id": "<uuid4>",
          "kind": "dev_server" | "background_task" | "docker_container"
                  | "subagent_worktree",
          "pid": 12345,                   # opcional (containers usam metadata)
          "port": 5173,                   # opcional
          "cmd": "npm run dev",           # opcional
          "registered_at": "ISO8601 UTC",
          "metadata": {...}               # opcional, kind-specific
        }
      ]
    }

CLI:
    python runtime-registry.py register --workspace-root <path> \\
        --kind dev_server --pid 12345 [--port 5173] [--cmd "npm run dev"]
    python runtime-registry.py list --workspace-root <path> [--kind dev_server]
    python runtime-registry.py unregister --workspace-root <path> --id <uuid>
    python runtime-registry.py purge-dead --workspace-root <path>
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Sequence


# ============================================================================
# Constants
# ============================================================================

REGISTRY_VERSION = 1

VALID_KINDS = frozenset({
    "dev_server",
    "background_task",
    "docker_container",
    "subagent_worktree",
})

REGISTRY_FILENAME = "runtime-registry.json"
STATE_DIRNAME = "_state"

# Legacy PID file from v3.6.0 (preview loop)
LEGACY_DEV_SERVER_PID = ".icm-main/.dev-server.pid"


# ============================================================================
# Cross-platform helpers (mirror recovery-wizard.py)
# ============================================================================

def _is_pid_alive(pid: int) -> bool:
    """Cross-platform liveness check.

    POSIX: `os.kill(pid, 0)` — sends no signal but validates permission.
    Windows: ctypes.OpenProcess. No external deps.
    """
    if pid <= 0:
        return False
    if os.name == "nt":
        return _is_pid_alive_win(pid)
    return _is_pid_alive_posix(pid)


def _is_pid_alive_posix(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # process exists but belongs to another user; still "alive"
        return True
    except OSError:
        return False


def _is_pid_alive_win(pid: int) -> bool:
    import ctypes  # noqa: PLC0415
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    STILL_ACTIVE = 259
    try:
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, pid,
        )
        if not handle:
            return False
        try:
            exit_code = ctypes.c_ulong()
            ok = kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
            if not ok:
                return False
            return exit_code.value == STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    except OSError:
        return False


def _utc_now_iso() -> str:
    return _dt.datetime.now(_dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# ============================================================================
# IO
# ============================================================================

def _registry_path(workspace_root: Path) -> Path:
    return workspace_root / STATE_DIRNAME / REGISTRY_FILENAME


def _ensure_state_dir(workspace_root: Path) -> Path:
    state = workspace_root / STATE_DIRNAME
    state.mkdir(parents=True, exist_ok=True)
    return state


def _atomic_write_json(path: Path, payload: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(path)


def load(workspace_root: Path) -> dict[str, Any]:
    """Read registry. If absent, returns empty structure (does not write to disk).

    If called for the first time, creates `_state/` dir but does NOT write JSON
    until first register/purge.
    """
    workspace = workspace_root.name
    _ensure_state_dir(workspace_root)
    path = _registry_path(workspace_root)
    if not path.is_file():
        return {
            "version": REGISTRY_VERSION,
            "workspace": workspace,
            "entries": [],
        }
    text = path.read_text(encoding="utf-8")
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"corrupted registry: {path} (expected dict)")
    return data


def _save(workspace_root: Path, registry: dict) -> None:
    _ensure_state_dir(workspace_root)
    _atomic_write_json(_registry_path(workspace_root), registry)


# ============================================================================
# CRUD
# ============================================================================

def register(
    workspace_root: Path,
    *,
    kind: str,
    pid: int | None = None,
    port: int | None = None,
    cmd: str | None = None,
    metadata: dict | None = None,
) -> str:
    """Add entry. Returns generated ID (uuid4 hex)."""
    if kind not in VALID_KINDS:
        raise ValueError(
            f"invalid kind: {kind!r} (expected: {sorted(VALID_KINDS)})"
        )
    reg = load(workspace_root)
    entry_id = uuid.uuid4().hex
    entry: dict[str, Any] = {
        "id": entry_id,
        "kind": kind,
        "registered_at": _utc_now_iso(),
    }
    if pid is not None:
        entry["pid"] = int(pid)
    if port is not None:
        entry["port"] = int(port)
    if cmd is not None:
        entry["cmd"] = cmd
    if metadata is not None:
        entry["metadata"] = metadata
    reg["entries"].append(entry)
    _save(workspace_root, reg)
    return entry_id


def list_entries(
    workspace_root: Path,
    *,
    kind: str | None = None,
) -> list[dict]:
    reg = load(workspace_root)
    entries = reg["entries"]
    if kind is not None:
        entries = [e for e in entries if e.get("kind") == kind]
    return entries


def unregister(workspace_root: Path, *, entry_id: str) -> bool:
    """Remove entry by id. Returns True if removed, False if not found."""
    reg = load(workspace_root)
    before = len(reg["entries"])
    reg["entries"] = [e for e in reg["entries"] if e.get("id") != entry_id]
    if len(reg["entries"]) == before:
        return False
    _save(workspace_root, reg)
    return True


def purge_dead(workspace_root: Path) -> list[dict]:
    """Remove entries with dead PID. Returns removed entries."""
    reg = load(workspace_root)
    alive: list[dict] = []
    dead: list[dict] = []
    for entry in reg["entries"]:
        pid = entry.get("pid")
        if pid is None or _is_pid_alive(int(pid)):
            alive.append(entry)
        else:
            dead.append(entry)
    if dead:
        reg["entries"] = alive
        _save(workspace_root, reg)
    return dead


# ============================================================================
# Legacy migration (.icm-main/.dev-server.pid -> registry)
# ============================================================================

def detect_legacy_pid_files(project_root: Path) -> list[dict]:
    """Detect `.icm-main/.dev-server.pid` (v3.6.0). Returns synthetic entries
    for UI/cleanup proposal.

    Does not remove the legacy file automatically — human confirms migration.
    """
    legacy = project_root / LEGACY_DEV_SERVER_PID
    if not legacy.is_file():
        return []
    try:
        pid = int(legacy.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        return []
    return [{
        "kind": "dev_server",
        "pid": pid,
        "source": LEGACY_DEV_SERVER_PID,
        "alive": _is_pid_alive(pid),
    }]


# ============================================================================
# CLI
# ============================================================================

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="runtime-registry.py")
    sub = parser.add_subparsers(dest="cmd", required=True)

    reg = sub.add_parser("register", help="Add entry to registry")
    reg.add_argument("--workspace-root", type=Path, required=True)
    reg.add_argument("--kind", required=True, choices=sorted(VALID_KINDS))
    reg.add_argument("--pid", type=int, default=None)
    reg.add_argument("--port", type=int, default=None)
    reg.add_argument("--command", dest="command", default=None,
                     help="command that started the process (e.g. 'npm run dev')")
    reg.add_argument("--metadata", default=None,
                     help="JSON string (optional)")

    lst = sub.add_parser("list", help="List entries (optionally by kind)")
    lst.add_argument("--workspace-root", type=Path, required=True)
    lst.add_argument("--kind", default=None, choices=sorted(VALID_KINDS))
    lst.add_argument("--format", choices=("json", "text"), default="text")

    unr = sub.add_parser("unregister", help="Remove entry by id")
    unr.add_argument("--workspace-root", type=Path, required=True)
    unr.add_argument("--id", required=True, dest="entry_id")

    purge = sub.add_parser("purge-dead",
                           help="Remove entries with dead PID")
    purge.add_argument("--workspace-root", type=Path, required=True)

    legacy = sub.add_parser("detect-legacy",
                            help="Detect .icm-main/.dev-server.pid v3.6.0")
    legacy.add_argument("--project-root", type=Path, required=True)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.cmd == "register":
        meta = json.loads(args.metadata) if args.metadata else None
        eid = register(
            args.workspace_root.resolve(),
            kind=args.kind,
            pid=args.pid,
            port=args.port,
            cmd=args.command,
            metadata=meta,
        )
        print(eid)
        return 0

    if args.cmd == "list":
        entries = list_entries(args.workspace_root.resolve(), kind=args.kind)
        if args.format == "json":
            print(json.dumps(entries, indent=2))
        else:
            if not entries:
                print("(empty)")
            for e in entries:
                pid = e.get("pid", "-")
                port = e.get("port", "-")
                cmd = e.get("cmd", "-")
                print(f"{e['id']}  {e['kind']}  pid={pid} port={port}  {cmd}")
        return 0

    if args.cmd == "unregister":
        ok = unregister(args.workspace_root.resolve(), entry_id=args.entry_id)
        return 0 if ok else 1

    if args.cmd == "purge-dead":
        dead = purge_dead(args.workspace_root.resolve())
        print(json.dumps(dead, indent=2))
        return 0

    if args.cmd == "detect-legacy":
        legacy = detect_legacy_pid_files(args.project_root.resolve())
        print(json.dumps(legacy, indent=2))
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
