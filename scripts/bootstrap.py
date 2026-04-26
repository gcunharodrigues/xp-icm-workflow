"""Backend Python do bootstrap one-shot da skill xp-icm-workflow.

Cria workspace ICM dentro de um project_root: branch dedicada, scaffold de
estagios, L0/L1 com placeholders preenchidos, profile efetivo + hash, indice
do projeto, .gitignore atualizado, pre-commit hook instalado, commits atomicos.

Funcoes puras (templating, validacao, manipulacao de indice/.gitignore) sao
testadas em tests/unit/test_bootstrap.py. O fluxo end-to-end e testado em
tests/integration/test_bootstrap.bats (CI-only Ubuntu).

CLI: o caminho principal e via scripts/bootstrap.sh wrapper. Este modulo
expoe `main()` para invocacao direta como debugging.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

# ============================================================================
# Constantes
# ============================================================================

SKILL_VERSION = "3.0.0-beta1"  # template prepends `v`

SLUG_RE = re.compile(r"^[a-z0-9-]+$")
PLACEHOLDER_RE = re.compile(r"\{\{([A-Z_][A-Z0-9_]*)\}\}")
INDEX_ROW_RE = re.compile(
    r"^\|\s*(\d{3})\s*\|\s*([a-z0-9-]+)\s*\|"
)

STAGES: tuple[str, ...] = (
    "00_recon",
    "01_discovery",
    "02_design",
    "03_wave_planner",
    "04_implementation_waves",
    "05_verification",
    "06_review",
    "07_merge",
    "08_feedback_intake",
)

GITIGNORE_LINES: tuple[str, ...] = (
    ".worktrees/",
    ".icm-profile.local.yaml",
    "__pycache__/",
    ".pytest_cache/",
    ".coverage",
)

INDEX_HEADER = (
    "# Workspaces index\n"
    "\n"
    "Indice append-only de workspaces criados pelo bootstrap da skill\n"
    "xp-icm-workflow. NUNCA edite linhas existentes manualmente.\n"
    "\n"
    "| ID | Slug | Profile/Tier | Created at | Status |\n"
    "|---|---|---|---|---|\n"
)


class BootstrapError(Exception):
    """Erro de bootstrap (validacao, IO, git, runtime)."""


# ============================================================================
# Funcoes puras (testadas em test_bootstrap.py)
# ============================================================================

def render_template(tpl_path: Path, vars: dict[str, str]) -> str:
    """Substitui {{KEY}} -> vars[KEY] em conteudo do template.

    Raise BootstrapError se template ausente OU se sobrar `{{X}}` nao resolvido.
    """
    if not tpl_path.exists():
        raise BootstrapError(f"template ausente: {tpl_path}")

    content = tpl_path.read_text(encoding="utf-8")

    def _sub(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in vars:
            raise BootstrapError(
                f"placeholder nao resolvido: {{{{{key}}}}} em {tpl_path.name}"
            )
        return vars[key]

    rendered = PLACEHOLDER_RE.sub(_sub, content)

    # Sanity check (caso o regex de subst tenha furos): nenhuma `{{X}}` sobra
    leftover = PLACEHOLDER_RE.search(rendered)
    if leftover:
        raise BootstrapError(
            f"placeholder nao resolvido: {leftover.group(0)} em {tpl_path.name}"
        )

    return rendered


def resolve_workspace_id(index_path: Path) -> int:
    """Le `.index.md`, retorna proximo NNN (= max(IDs) + 1, ou 1 se vazio)."""
    if not index_path.exists():
        return 1
    text = index_path.read_text(encoding="utf-8")
    if not text.strip():
        return 1
    max_id = 0
    for line in text.splitlines():
        match = INDEX_ROW_RE.match(line.strip())
        if match:
            id_int = int(match.group(1))
            if id_int > max_id:
                max_id = id_int
    return max_id + 1


def update_index(
    index_path: Path,
    *,
    workspace: str,
    profile: str,
    tier: str,
    created_at: str,
) -> None:
    """Append linha ao .index.md. Cria header se ausente.

    `workspace` = "NNN-slug" (ID + slug separados por primeiro hifen).
    """
    nnn, _, slug = workspace.partition("-")
    row = f"| {nnn} | {slug} | {profile}/{tier} | {created_at} | active |\n"

    if not index_path.exists() or not index_path.read_text(encoding="utf-8").strip():
        index_path.write_text(INDEX_HEADER + row, encoding="utf-8")
        return

    current = index_path.read_text(encoding="utf-8")
    if not current.endswith("\n"):
        current += "\n"
    index_path.write_text(current + row, encoding="utf-8")


def update_gitignore(gitignore_path: Path, lines_to_add: list[str]) -> None:
    """Idempotente: adiciona apenas linhas ausentes; preserva existentes."""
    if gitignore_path.exists():
        existing = gitignore_path.read_text(encoding="utf-8")
    else:
        existing = ""

    existing_lines = {ln.strip() for ln in existing.splitlines() if ln.strip()}

    missing = [ln for ln in lines_to_add if ln.strip() not in existing_lines]
    if not missing:
        return

    new_content = existing
    if new_content and not new_content.endswith("\n"):
        new_content += "\n"
    new_content += "\n".join(missing) + "\n"
    gitignore_path.write_text(new_content, encoding="utf-8")


def validate_slug(slug: str) -> None:
    """Aceita kebab-case `^[a-z0-9-]+$`. Raise BootstrapError caso contrario."""
    if not slug:
        raise BootstrapError("slug nao pode ser vazio")
    if not SLUG_RE.match(slug):
        raise BootstrapError(
            f"slug invalido: {slug!r} (esperado kebab-case [a-z0-9-]+, "
            "sem maiuscula/espaco/acento)"
        )


def parse_profile_merge_output(json_str: str) -> tuple[dict[str, Any], str]:
    """Parse JSON de profile-merge.py. Retorna (effective_dict, hash_str)."""
    try:
        parsed = json.loads(json_str)
    except json.JSONDecodeError as exc:
        raise BootstrapError(f"profile-merge output JSON invalido: {exc}") from exc

    if not isinstance(parsed, dict):
        raise BootstrapError("profile-merge output deve ser dict no topo")

    if "effective" not in parsed:
        raise BootstrapError("profile-merge output sem chave 'effective'")
    if "hash" not in parsed:
        raise BootstrapError("profile-merge output sem chave 'hash'")

    effective = parsed["effective"]
    if not isinstance(effective, dict):
        raise BootstrapError("'effective' deve ser dict")

    h = parsed["hash"]
    if not isinstance(h, str):
        raise BootstrapError("'hash' deve ser string")

    return effective, h


# ============================================================================
# Stop points: derivacao de placeholders + render do bloco custom
# ============================================================================

def derive_stop_point_placeholders(effective: dict[str, Any]) -> dict[str, str]:
    """Extrai dict[str, str] com TIER_PAID_MODE/TIER_PAID_THRESHOLD_BRL/
    TIER_OVER_ENG_MODE/TIER_PII_MODE a partir de `stop_points_calibration` no
    profile efetivo.

    Schema esperado (vem de profile-merge.py):
        stop_points_calibration:
          item_5: {mode: warning|hard, limite_mensal_BRL: int}
          item_7: {mode: warning|hard}
          item_8: {mode: warning|hard|hard+DPO}

    Raise BootstrapError se chaves obrigatorias ausentes.
    """
    cal = effective.get("stop_points_calibration")
    if not isinstance(cal, dict):
        raise BootstrapError(
            "profile efetivo sem 'stop_points_calibration' (esperado dict)"
        )

    def _required(key: str, sub: str) -> Any:
        item = cal.get(key)
        if not isinstance(item, dict):
            raise BootstrapError(
                f"stop_points_calibration.{key} ausente ou nao-dict"
            )
        if sub not in item:
            raise BootstrapError(
                f"stop_points_calibration.{key}.{sub} ausente"
            )
        return item[sub]

    return {
        "TIER_PAID_MODE": str(_required("item_5", "mode")),
        "TIER_PAID_THRESHOLD_BRL": str(_required("item_5", "limite_mensal_BRL")),
        "TIER_OVER_ENG_MODE": str(_required("item_7", "mode")),
        "TIER_PII_MODE": str(_required("item_8", "mode")),
    }


def render_custom_stop_points_block(
    custom_stops: list[dict[str, Any]] | None,
    tier: str,
) -> str:
    """Renderiza bloco markdown com custom stop points para o template.

    `custom_stops` segue schema de `_config/profile-matrix.md` -> custom_stop_points:
        - id: str (nao-vazio)
          description: str (nao-vazio)
          threshold: dict[tier_name -> mode_str]

    Se lista vazia/None: retorna "(nenhum custom stop point declarado pelo workspace)".
    Caso contrario: para cada custom stop, secao `### custom: <id>` + descricao
    + threshold para o tier corrente (ou "n/a" se tier nao tem entry no threshold).
    """
    if not custom_stops:
        return "(nenhum custom stop point declarado pelo workspace)"

    lines: list[str] = []
    for sp in custom_stops:
        if not isinstance(sp, dict):
            raise BootstrapError(f"custom_stop_point invalido (nao-dict): {sp!r}")
        sp_id = sp.get("id")
        sp_desc = sp.get("description")
        sp_thresh = sp.get("threshold") or {}
        if not sp_id or not sp_desc:
            raise BootstrapError(
                f"custom_stop_point requer 'id' e 'description' nao-vazios: {sp!r}"
            )
        threshold_for_tier = sp_thresh.get(tier, "n/a") if isinstance(sp_thresh, dict) else "n/a"
        lines.append(f"### custom: {sp_id}")
        lines.append("")
        lines.append(str(sp_desc))
        lines.append("")
        lines.append(f"Threshold tier `{tier}`: `{threshold_for_tier}`")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


# ============================================================================
# Helpers de orquestracao (cobertos por bats integration)
# ============================================================================

def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run_git(args: list[str], cwd: Path, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Wrapper de git com captura de output e check configuravel."""
    cmd = ["git", "-C", str(cwd), *args]
    return subprocess.run(cmd, check=check, capture_output=True, text=True)


def _run_profile_merge(
    skill_root: Path,
    profile: str,
    tier: str,
    override: Path | None,
) -> tuple[dict[str, Any], str]:
    """Invoca scripts/profile-merge.py via subprocess; parse output."""
    cmd = [
        sys.executable,
        str(skill_root / "scripts" / "profile-merge.py"),
        "--profile", profile,
        "--tier", tier,
    ]
    if override is not None:
        cmd.extend(["--override", str(override)])
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise BootstrapError(
            f"profile-merge falhou (rc={result.returncode}): {result.stderr.strip()}"
        )
    return parse_profile_merge_output(result.stdout)


def _greenfield_init(project_root: Path) -> None:
    """git init -b main + .gitignore + commit inicial em projeto novo.

    Hook ainda nao instalado neste ponto, entao --no-verify nao e necessario.
    """
    _run_git(["init", "-b", "main"], cwd=project_root)
    gi = project_root / ".gitignore"
    update_gitignore(gi, list(GITIGNORE_LINES))
    _run_git(["add", ".gitignore"], cwd=project_root)
    _run_git(["commit", "-m", "initial commit"], cwd=project_root)


def _capture_base_branch(project_root: Path) -> str:
    res = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=project_root)
    branch = res.stdout.strip()
    if not branch or branch == "HEAD":
        raise BootstrapError(
            f"nao foi possivel detectar base_branch em {project_root} "
            "(detached HEAD?)"
        )
    return branch


def _create_workspace_branch(project_root: Path, branch: str, base: str) -> None:
    _run_git(["checkout", "-b", branch, base], cwd=project_root)


def _scaffold_workspace_dirs(workspace_dir: Path, skill_root: Path) -> None:
    """Cria stages/00..08, _config/ (com profile-matrix), _references/ vazias."""
    workspace_dir.mkdir(parents=True, exist_ok=False)
    stages = workspace_dir / "stages"
    stages.mkdir()
    for s in STAGES:
        (stages / s).mkdir()

    config_dir = workspace_dir / "_config"
    config_dir.mkdir()
    matrix_src = skill_root / "templates" / "_config" / "profile-matrix.md"
    if matrix_src.exists():
        shutil.copy2(matrix_src, config_dir / "profile-matrix.md")

    refs_dir = workspace_dir / "_references"
    sp_dst = refs_dir / "superpowers-summary"
    sp_dst.mkdir(parents=True)
    sp_src = skill_root / "templates" / "_references" / "superpowers-summary"
    if sp_src.is_dir():
        for f in sp_src.iterdir():
            if f.is_file() and f.suffix == ".md":
                shutil.copy2(f, sp_dst / f.name)

    runtime_dst = refs_dir / "runtime"
    runtime_dst.mkdir(parents=True)
    # Copia subset de references/ que sao consumidos em runtime pelos teammates
    # (R2.5 do plan). Skill formal em references/ continua sendo a fonte; workspace
    # ganha copia self-contained pra continuar trabalhando se skill mudar.
    runtime_refs = (
        "agent-team-protocol.md",
        "wave-planner-algorithm.md",
        "state-machine-schema.md",
        "recovery-wizard.md",
        "stop-points-canonical.md",
        "4-block-contract-template.md",
        "feedback-intake-fase08.md",
    )
    refs_src = skill_root / "references"
    for fname in runtime_refs:
        src = refs_src / fname
        if src.is_file():
            shutil.copy2(src, runtime_dst / fname)


def _save_profile_effective(
    workspace_dir: Path,
    effective: dict[str, Any],
    profile_hash: str,
) -> None:
    """Persiste profile-effective.yaml + hash para validate-state usar depois."""
    import yaml  # noqa: PLC0415  — yaml is a runtime dep of the skill
    payload = dict(effective)
    payload["__hash__"] = profile_hash
    out = workspace_dir / "_config" / "profile-effective.yaml"
    out.write_text(
        yaml.safe_dump(payload, sort_keys=True, allow_unicode=True),
        encoding="utf-8",
    )


_MANAGED_HOOKS: tuple[str, ...] = ("pre-commit", "commit-msg")


def _install_hooks(project_root: Path, skill_root: Path) -> None:
    """Idempotente: instala todos hooks ICM em .git/hooks/.

    Hooks gerenciados (stages canonicos):
      - pre-commit: file/atomicidade checks
      - commit-msg: validacao de prefix da msg (recebe COMMIT_EDITMSG em $1)

    Pre-commit nao pode validar msg porque roda ANTES de
    COMMIT_EDITMSG ser persistido — leria msg do commit anterior.
    Bug original v1, fixado via split.

    Se ja existe e diff != 0, faz backup .bak.<timestamp> e overwrite.
    Em caso de erro de IO (Windows file-in-use, etc), warning e segue.
    """
    dst_dir = project_root / ".git" / "hooks"
    try:
        dst_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        sys.stderr.write(f"warning: nao foi possivel criar {dst_dir}: {exc}\n")
        return

    for hook in _MANAGED_HOOKS:
        src = skill_root / "templates" / ".git-hooks" / hook
        if not src.exists():
            sys.stderr.write(f"warning: hook fonte ausente: {src}\n")
            continue
        dst = dst_dir / hook
        try:
            if dst.exists():
                current = dst.read_bytes()
                new = src.read_bytes()
                if current == new:
                    continue
                ts = _now_iso().replace(":", "").replace("-", "")
                backup = dst.with_suffix(f".bak.{ts}")
                shutil.copy2(dst, backup)
            shutil.copy2(src, dst)
            try:
                os.chmod(dst, 0o755)
            except OSError:
                pass
        except OSError as exc:
            sys.stderr.write(f"warning: falha ao instalar hook {hook}: {exc}\n")


# Backward-compat alias (testes ou call sites antigos)
_install_pre_commit_hook = _install_hooks


def _commit_scaffold(
    project_root: Path,
    workspace: str,
    profile: str,
    tier: str,
) -> str:
    """git add + commit do scaffold inicial. Retorna sha do commit."""
    _run_git(["add", f"workspaces/{workspace}/", "workspaces/.index.md"], cwd=project_root)
    # .gitignore pode ou nao ter mudado; add idempotente
    _run_git(["add", ".gitignore"], cwd=project_root, check=False)
    msg = f"workspace {workspace.split('-', 1)[0]}: bootstrap scaffold (profile={profile} tier={tier})"
    _run_git(["commit", "-m", msg], cwd=project_root)
    res = _run_git(["rev-parse", "HEAD"], cwd=project_root)
    return res.stdout.strip()


def _patch_context_with_sha(context_path: Path, commit_sha: str) -> None:
    text = context_path.read_text(encoding="utf-8")
    patched = text.replace("{{BOOTSTRAP_COMMIT_SHA}}", commit_sha)
    context_path.write_text(patched, encoding="utf-8")


def _commit_context_sha(project_root: Path, workspace: str) -> None:
    nnn = workspace.split("-", 1)[0]
    _run_git(
        ["add", f"workspaces/{workspace}/CONTEXT.md"],
        cwd=project_root,
    )
    msg = f"workspace {nnn}: persist bootstrap commit_sha"
    _run_git(["commit", "-m", msg], cwd=project_root)


# ============================================================================
# Orquestracao de alto nivel (bats cobre)
# ============================================================================

def bootstrap(
    *,
    project_root: Path,
    profile: str,
    tier: str,
    workspace_slug: str,
    skill_root: Path,
    logs_root: str | None = None,
    override_path: Path | None = None,
) -> dict[str, Any]:
    """Executa bootstrap completo. Retorna dict com summary {workspace, branch, hash, sha}."""
    validate_slug(workspace_slug)

    if not project_root.exists() or not project_root.is_dir():
        raise BootstrapError(f"project_root nao e diretorio: {project_root}")

    # Greenfield: git init se necessario
    if not (project_root / ".git").exists():
        _greenfield_init(project_root)

    base_branch = _capture_base_branch(project_root)

    # Resolve workspace ID
    index_path = project_root / "workspaces" / ".index.md"
    nnn = resolve_workspace_id(index_path)
    workspace = f"{nnn:03d}-{workspace_slug}"
    workspace_dir = project_root / "workspaces" / workspace

    if workspace_dir.exists():
        raise BootstrapError(
            f"workspace dir ja existe: {workspace_dir} "
            "(rode recovery-wizard.py)"
        )

    # Profile merge
    effective, profile_hash = _run_profile_merge(skill_root, profile, tier, override_path)

    # Cria branch
    workspace_branch = f"workspace/{workspace}"
    _create_workspace_branch(project_root, workspace_branch, base_branch)

    # Scaffold
    _scaffold_workspace_dirs(workspace_dir, skill_root)

    # Templates
    created_at = _now_iso()
    placeholders: dict[str, str] = {
        "WORKSPACE": workspace,
        "PROFILE": profile,
        "TIER": tier,
        "PROJECT_ROOT": str(project_root).replace("\\", "/"),
        "BASE_BRANCH": base_branch,
        "LOGS_ROOT": f'"{logs_root}"' if logs_root else "null",
        "PROFILE_EFFECTIVE_HASH": profile_hash,
        "CREATED_AT": created_at,
        "SKILL_VERSION": SKILL_VERSION,
        "BOOTSTRAP_COMMIT_SHA": "{{BOOTSTRAP_COMMIT_SHA}}",  # patched depois
    }

    tpl_dir = skill_root / "templates" / "workspace"
    claude_md = render_template(tpl_dir / "CLAUDE.md.tpl", placeholders)
    (workspace_dir / "CLAUDE.md").write_text(claude_md, encoding="utf-8")

    # CONTEXT.md tem placeholder BOOTSTRAP_COMMIT_SHA que so existe pos-commit.
    # render_template raise se sobrar `{{X}}`, entao injetamos sentinel vazio agora
    # e patch depois do primeiro commit.
    placeholders_l1 = dict(placeholders)
    placeholders_l1["BOOTSTRAP_COMMIT_SHA"] = "PENDING"  # sentinel; trocado depois
    context_md = render_template(tpl_dir / "CONTEXT.md.tpl", placeholders_l1)
    # Volta o sentinel para `{{BOOTSTRAP_COMMIT_SHA}}` literal; patch depois
    context_md = context_md.replace("PENDING", "{{BOOTSTRAP_COMMIT_SHA}}")
    (workspace_dir / "CONTEXT.md").write_text(context_md, encoding="utf-8")

    # Stop points: render template _config/stop-points.md com placeholders
    # de tier (TIER_PAID_MODE etc) + bloco de custom stop points.
    sp_placeholders = derive_stop_point_placeholders(effective)
    custom_block = render_custom_stop_points_block(
        effective.get("custom_stop_points"),
        tier=tier,
    )
    sp_template_vars = dict(placeholders)
    sp_template_vars.update(sp_placeholders)
    sp_template_vars["CUSTOM_STOP_POINTS_BLOCK"] = custom_block
    sp_tpl = skill_root / "templates" / "_config" / "stop-points.md"
    sp_rendered = render_template(sp_tpl, sp_template_vars)
    (workspace_dir / "_config" / "stop-points.md").write_text(sp_rendered, encoding="utf-8")

    # Profile efetivo persistido para validate-state
    _save_profile_effective(workspace_dir, effective, profile_hash)

    # Indice + .gitignore do projeto
    update_index(
        index_path,
        workspace=workspace,
        profile=profile,
        tier=tier,
        created_at=created_at,
    )
    update_gitignore(project_root / ".gitignore", list(GITIGNORE_LINES))

    # Commit 1: scaffold (hook NAO instalado ainda — bootstrap e trusted; hook
    # protege atividade futura do usuario).
    commit_sha = _commit_scaffold(project_root, workspace, profile, tier)

    # Patch CONTEXT.md com sha do commit + commit 2
    _patch_context_with_sha(workspace_dir / "CONTEXT.md", commit_sha)
    _commit_context_sha(project_root, workspace)
    final_sha = _run_git(["rev-parse", "HEAD"], cwd=project_root).stdout.strip()

    # Hooks instalados por ULTIMO: protegem commits futuros do usuario sem
    # interferir nos commits atomicos do bootstrap. Pre-commit + commit-msg
    # juntos cobrem file checks e msg validation respectivamente.
    _install_hooks(project_root, skill_root)

    return {
        "workspace": workspace,
        "branch": workspace_branch,
        "base_branch": base_branch,
        "profile": profile,
        "tier": tier,
        "hash": profile_hash,
        "scaffold_commit_sha": commit_sha,
        "final_commit_sha": final_sha,
    }


# ============================================================================
# CLI (debug; .sh wrapper e o caminho principal)
# ============================================================================

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Bootstrap one-shot de workspace ICM (debug CLI; use .sh wrapper em prod).",
    )
    parser.add_argument("--profile", required=True)
    parser.add_argument("--tier", required=True)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--workspace-name", required=True, help="slug kebab-case")
    parser.add_argument("--logs-root", default=None)
    parser.add_argument("--override", default=None)
    parser.add_argument("--skill-root", default=None, help="default: parent of this script")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    skill_root = Path(args.skill_root) if args.skill_root else Path(__file__).resolve().parent.parent
    try:
        summary = bootstrap(
            project_root=Path(args.project_root).resolve(),
            profile=args.profile,
            tier=args.tier,
            workspace_slug=args.workspace_name,
            skill_root=skill_root,
            logs_root=args.logs_root,
            override_path=Path(args.override).resolve() if args.override else None,
        )
    except BootstrapError as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
