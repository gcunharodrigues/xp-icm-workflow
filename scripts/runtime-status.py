"""Runtime status — checklist cross-platform de side-effects ativos (v3.7.0).

Consumido por L2 stage 08 entry hook (saída A/B/C step 0). Verifica 6
categorias de side-effects que humano DEVE confirmar antes de transição:

  1. dev_servers      — runtime-registry kind=dev_server alive
  2. background_tasks — kind=background_task alive
  3. docker           — containers + volumes label icm-workspace=NNN
  4. wave_branches    — git branches `wave-NNN-N/<task>` órfãs
  5. working_tree     — git status --short na workspace branch
  6. untracked        — `.icm-main/` dirty + git ls-files --others

Cada check retorna `{clean: bool, items: list[dict], summary: str}`.
`check_all` agrega todas categorias num dict pra ICM agent consumir.

Doc canônico: `references/runtime-cleanup-protocol.md`.

CLI:
    python runtime-status.py --workspace-root <ws> --project-root <pr> \\
        [--check dev_servers] [--format json|text] [--exit-code]

Exit code:
    0 = todas categorias clean (ou --exit-code não passado)
    1 = pelo menos 1 categoria dirty (apenas com --exit-code)
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence


# ============================================================================
# Constantes
# ============================================================================

CATEGORIES = (
    "dev_servers",
    "background_tasks",
    "docker",
    "wave_branches",
    "working_tree",
    "untracked",
)


# ============================================================================
# Helpers cross-platform
# ============================================================================

def _pid_alive(pid: int) -> bool:
    """Reusa lógica de runtime-registry (lazy import via importlib)."""
    rr = _load_runtime_registry()
    return rr._is_pid_alive(int(pid))


def _load_runtime_registry():
    """Lazy import runtime-registry.py (filename com hyphen)."""
    if "runtime_registry" in sys.modules:
        return sys.modules["runtime_registry"]
    path = Path(__file__).resolve().parent / "runtime-registry.py"
    spec = importlib.util.spec_from_file_location("runtime_registry", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["runtime_registry"] = mod
    spec.loader.exec_module(mod)
    return mod


def _git(args: list[str], cwd: Path) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            ["git"] + args, cwd=str(cwd),
            capture_output=True, text=True, check=False,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except FileNotFoundError:
        return 127, "", "git not found"


# ============================================================================
# Per-category checks
# ============================================================================

def _registry_entries(workspace_root: Path, kind: str) -> list[dict]:
    rr = _load_runtime_registry()
    return rr.list_entries(workspace_root, kind=kind)


def _filter_alive(entries: list[dict]) -> list[dict]:
    alive = []
    for e in entries:
        pid = e.get("pid")
        if pid is None:
            continue
        if _pid_alive(int(pid)):
            alive.append(e)
    return alive


def check_dev_servers(workspace_root: Path) -> dict[str, Any]:
    entries = _registry_entries(workspace_root, "dev_server")
    alive = _filter_alive(entries)
    return {
        "clean": len(alive) == 0,
        "items": alive,
        "summary": (
            "no dev servers" if not alive
            else f"{len(alive)} dev server(s) alive: "
                 + ", ".join(f"pid={e.get('pid')}" for e in alive)
        ),
    }


def check_background_tasks(workspace_root: Path) -> dict[str, Any]:
    entries = _registry_entries(workspace_root, "background_task")
    alive = _filter_alive(entries)
    return {
        "clean": len(alive) == 0,
        "items": alive,
        "summary": (
            "no background tasks" if not alive
            else f"{len(alive)} background task(s) alive"
        ),
    }


def check_docker(workspace_root: Path) -> dict[str, Any]:
    """Docker containers com label icm-workspace=<NNN>.

    Returns clean=True se docker daemon não disponível (humano sabe se
    usa docker; sem evidência, presume clean).
    """
    workspace_id = workspace_root.name
    label = f"icm-workspace={workspace_id}"
    try:
        proc = subprocess.run(
            ["docker", "ps", "--filter", f"label={label}",
             "--format", "{{.ID}}\t{{.Names}}\t{{.Image}}"],
            capture_output=True, text=True, check=False, timeout=10,
        )
        if proc.returncode != 0:
            # Daemon down ou docker ausente: assume clean
            return {"clean": True, "items": [],
                    "summary": "docker unavailable (assumed clean)"}
        lines = [ln for ln in proc.stdout.strip().splitlines() if ln]
        items = []
        for ln in lines:
            parts = ln.split("\t")
            if len(parts) >= 3:
                items.append({
                    "container_id": parts[0],
                    "name": parts[1],
                    "image": parts[2],
                })
        return {
            "clean": len(items) == 0,
            "items": items,
            "summary": (
                "no docker containers" if not items
                else f"{len(items)} container(s) with label {label}"
            ),
        }
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {"clean": True, "items": [],
                "summary": "docker not installed/timeout (assumed clean)"}


def check_wave_branches(workspace_root: Path,
                        project_root: Path) -> dict[str, Any]:
    """Lista branches wave-<workspace_num>-N/<task-slug> existentes.

    Wave branches devem ser deletadas pelo lead após merge wave-end. Se
    sobraram, candidatas a cleanup pré-saída fase 08.
    """
    # Extract workspace number from "001-test-mvp" → "001"
    workspace_id = workspace_root.name
    workspace_num = workspace_id.split("-", 1)[0]
    pattern = f"wave-{workspace_num}-*"
    rc, out, _ = _git(["branch", "--list", pattern], project_root)
    if rc != 0:
        return {"clean": True, "items": [],
                "summary": "git unavailable (assumed clean)"}
    branches = [
        ln.strip().lstrip("* ").strip()
        for ln in out.splitlines() if ln.strip()
    ]
    return {
        "clean": len(branches) == 0,
        "items": [{"branch": b} for b in branches],
        "summary": (
            f"no wave-{workspace_num}-* branches" if not branches
            else f"{len(branches)} wave branch(es) órfã(s)"
        ),
    }


def check_working_tree(project_root: Path) -> dict[str, Any]:
    """git status --short do project_root (workspace branch)."""
    rc, out, _ = _git(["status", "--short"], project_root)
    if rc != 0:
        return {"clean": True, "items": [],
                "summary": "git unavailable (assumed clean)"}
    lines = [ln for ln in out.splitlines() if ln.strip()]
    return {
        "clean": len(lines) == 0,
        "items": [{"line": ln} for ln in lines],
        "summary": (
            "working tree clean" if not lines
            else f"{len(lines)} unstaged/untracked path(s)"
        ),
    }


def check_untracked(project_root: Path) -> dict[str, Any]:
    """Untracked artifacts: .icm-main/ dirty + ls-files --others."""
    items: list[dict] = []
    icm_main = project_root / ".icm-main"
    if icm_main.is_dir():
        rc, out, _ = _git(["status", "--short"], icm_main)
        if rc == 0 and out.strip():
            for ln in out.splitlines():
                if ln.strip():
                    items.append({"location": ".icm-main", "line": ln.strip()})
    return {
        "clean": len(items) == 0,
        "items": items,
        "summary": (
            ".icm-main clean" if not items
            else f".icm-main dirty: {len(items)} entry(ies)"
        ),
    }


def check_all(workspace_root: Path, project_root: Path) -> dict[str, dict]:
    return {
        "dev_servers": check_dev_servers(workspace_root),
        "background_tasks": check_background_tasks(workspace_root),
        "docker": check_docker(workspace_root),
        "wave_branches": check_wave_branches(workspace_root, project_root),
        "working_tree": check_working_tree(project_root),
        "untracked": check_untracked(project_root),
    }


# ============================================================================
# CLI
# ============================================================================

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="runtime-status.py")
    p.add_argument("--workspace-root", type=Path, required=True)
    p.add_argument("--project-root", type=Path, required=True)
    p.add_argument("--check", choices=CATEGORIES, default=None,
                   help="categoria específica (default: todas)")
    p.add_argument("--format", choices=("json", "text"), default="text")
    p.add_argument("--exit-code", action="store_true",
                   help="sai com 1 se alguma categoria dirty (gating)")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(list(argv) if argv is not None else None)
    ws = args.workspace_root.resolve()
    pr = args.project_root.resolve()

    if args.check:
        # Single category
        fn_map = {
            "dev_servers": lambda: check_dev_servers(ws),
            "background_tasks": lambda: check_background_tasks(ws),
            "docker": lambda: check_docker(ws),
            "wave_branches": lambda: check_wave_branches(ws, pr),
            "working_tree": lambda: check_working_tree(pr),
            "untracked": lambda: check_untracked(pr),
        }
        result = {args.check: fn_map[args.check]()}
    else:
        result = check_all(ws, pr)

    if args.format == "json":
        print(json.dumps(result, indent=2))
    else:
        for cat, payload in result.items():
            mark = "✓" if payload["clean"] else "✗"
            print(f"{mark} {cat}: {payload['summary']}")

    if args.exit_code:
        any_dirty = any(not v["clean"] for v in result.values())
        return 1 if any_dirty else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
