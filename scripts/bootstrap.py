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
import uuid
from pathlib import Path
from typing import Any

# ============================================================================
# Constantes
# ============================================================================

SKILL_VERSION = "3.0.0-beta5"  # template prepends `v`

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

STAGE_NAMES: dict[int, str] = {
    0: "recon",
    1: "discovery",
    2: "design",
    3: "wave_planner",
    4: "implementation_waves",
    5: "verification",
    6: "review",
    7: "merge",
    8: "feedback_intake",
}

GITIGNORE_LINES: tuple[str, ...] = (
    ".icm-profile.local.yaml",
    "__pycache__/",
    ".pytest_cache/",
    ".coverage",
)


def yaml_safe_list(items: list[str]) -> str:
    """Render list[str] as YAML flow sequence for frontmatter: ``[item1, item2]``."""
    if not items:
        return "[]"
    return "[" + ", ".join(f'"{i}"' for i in items) + "]"

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


def _scaffold_workspace_dirs(workspace_dir: Path, skill_root: Path, project_root: Path) -> None:
    """Cria stages/00..08 (com output/), _config/, _references/, docs/decisions/, docs/lessons.md stub."""
    workspace_dir.mkdir(parents=True, exist_ok=False)
    stages = workspace_dir / "stages"
    stages.mkdir()
    for s in STAGES:
        (stages / s).mkdir()
        (stages / s / "output").mkdir()

    # docs/decisions/, lessons.md stub e tech_debt.md stub no project_root
    decisions_dir = project_root / "docs" / "decisions"
    decisions_dir.mkdir(parents=True, exist_ok=True)
    lessons_file = project_root / "docs" / "lessons.md"
    if not lessons_file.exists():
        lessons_file.write_text(
            "# Lessons Learned\n\nRegisto append-only de lições por workspace e iteração.\n\n",
            encoding="utf-8",
        )
    tech_debt_file = project_root / "docs" / "tech_debt.md"
    if not tech_debt_file.exists():
        tech_debt_file.write_text(
            "# Tech Debt\n\nRegisto append-only de débitos técnicos. Cada item: workspace+task de origem, severidade P2/P3, descrição.\n\n",
            encoding="utf-8",
        )

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
    # Copia subset de references/ que sao consumidos em runtime pelos subagentes
    # (R2.5 do plan). Skill formal em references/ continua sendo a fonte; workspace
    # ganha copia self-contained pra continuar trabalhando se skill mudar.
    runtime_refs = (
        "subagent-protocol.md",
        "wave-planner-algorithm.md",
        "state-machine-schema.md",
        "recovery-wizard.md",
        "stop-points-canonical.md",
        "4-block-contract-template.md",
        "feedback-intake-fase08.md",
        "session-handoff-protocol.md",
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
            except OSError as _chmod_exc:
                # Windows não suporta permissão executável — Git Bash resolve
                # via ACL, mas os.chmod é silently ignored. Log warning apenas
                # se NÃO for Windows (erro inesperado em POSIX).
                if os.name != "nt":
                    sys.stderr.write(
                        f"warning: falha ao tornar hook executável: {dst}: {_chmod_exc}\n"
                    )
        except OSError as exc:
            sys.stderr.write(f"warning: falha ao instalar hook {hook}: {exc}\n")


def _install_context_hook(project_root: Path, skill_root: Path, workspace: str) -> None:
    """Idempotente: instala context-check.sh hook + registro em settings.local.json.

    Cria workspaces/<workspace>/.claude/hooks/context-check.sh copiando do template
    da skill e registra como PostToolUse hook em
    workspaces/<workspace>/.claude/settings.local.json.

    O hook e seu registro vivem dentro do workspace (ICM: workspace e self-contained).
    O command registrado usa path relativo ao workspace: bash .claude/hooks/context-check.sh

    Se settings.local.json do workspace nao existe, cria com estrutura minima.
    Se ja existe, adiciona o hook sem duplicar.
    """
    workspace_dir = project_root / "workspaces" / workspace
    hooks_dir = workspace_dir / ".claude" / "hooks"
    try:
        hooks_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        sys.stderr.write(f"warning: nao foi possivel criar {hooks_dir}: {exc}\n")
        return

    src_hook = skill_root / "templates" / ".claude" / "hooks" / "context-check.sh"
    dst_hook = hooks_dir / "context-check.sh"

    if not src_hook.exists():
        sys.stderr.write(f"warning: context-check.sh template ausente: {src_hook}\n")
        return

    try:
        shutil.copy2(src_hook, dst_hook)
        try:
            os.chmod(dst_hook, 0o755)
        except OSError as _chmod_exc2:
            if os.name != "nt":
                sys.stderr.write(
                    f"warning: falha ao tornar hook executável: {dst_hook}: {_chmod_exc2}\n"
                )
    except OSError as exc:
        sys.stderr.write(f"warning: falha ao instalar context-check.sh: {exc}\n")
        return

    # Registrar hook em workspaces/<workspace>/.claude/settings.local.json
    # Path relativo ao workspace (onde Claude Code resolve o command)
    hook_command = "bash .claude/hooks/context-check.sh"
    settings_path = workspace_dir / ".claude" / "settings.local.json"
    hook_entry = {
        "matcher": "",
        "hooks": [{"type": "command", "command": hook_command}],
    }

    settings: dict[str, Any] = {}
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
            if not isinstance(settings, dict):
                settings = {}
        except (json.JSONDecodeError, OSError):
            settings = {}

    # Adicionar PostToolUse hook sem duplicar
    post_tool_hooks = settings.get("hooks", {}).get("PostToolUse", [])
    already_exists = any(
        isinstance(entry, dict)
        and entry.get("hooks") == hook_entry["hooks"]
        and entry.get("matcher") == ""
        for entry in post_tool_hooks
    )
    if not already_exists:
        post_tool_hooks.append(hook_entry)
        if "hooks" not in settings:
            settings["hooks"] = {}
        settings["hooks"]["PostToolUse"] = post_tool_hooks

        try:
            settings_path.parent.mkdir(parents=True, exist_ok=True)
            settings_path.write_text(
                json.dumps(settings, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            sys.stderr.write(f"warning: falha ao escrever settings.local.json: {exc}\n")

    # Cleanup: remove hook legado de project_root/.claude/ se existir.
    # Bootstrap antigo (pre-v3.1) instalava em project_root/.claude/hooks/.
    # Novo design instala em workspaces/<workspace>/.claude/hooks/ + settings do workspace.
    _cleanup_legacy_context_hook(project_root)


def _cleanup_legacy_context_hook(project_root: Path) -> None:
    """Remove context-check.sh legado de project_root/.claude/hooks/ e
    sua entrada em project_root/.claude/settings.local.json.

    Bootstrap pre-v3.1 instalava o hook na raiz do projeto. O novo design
    instala tudo dentro do workspace. Esta funcao migra/remove o legado.
    """
    # Remove script legado
    legacy_hook = project_root / ".claude" / "hooks" / "context-check.sh"
    if legacy_hook.exists():
        try:
            legacy_hook.unlink()
        except OSError as exc:
            sys.stderr.write(f"warning: nao foi possivel remover {legacy_hook}: {exc}\n")

    # Remove diretorio hooks vazio
    legacy_hooks_dir = project_root / ".claude" / "hooks"
    if legacy_hooks_dir.exists() and legacy_hooks_dir.is_dir():
        try:
            # rmdir so funciona se vazio
            legacy_hooks_dir.rmdir()
        except OSError:
            pass  # dir nao vazio, nao remove

    # Remove entrada do hook legado em project_root/.claude/settings.local.json
    legacy_settings = project_root / ".claude" / "settings.local.json"
    if not legacy_settings.exists():
        return

    settings: dict[str, Any] = {}
    try:
        settings = json.loads(legacy_settings.read_text(encoding="utf-8"))
        if not isinstance(settings, dict):
            return
    except (json.JSONDecodeError, OSError):
        return

    post_tool_hooks: list[dict[str, Any]] = settings.get("hooks", {}).get("PostToolUse", [])
    original_len = len(post_tool_hooks)

    # Remove entradas com context-check.sh (legado = path relativo .claude/hooks/ ou
    # workspaces/NNN-slug/.claude/hooks/)
    post_tool_hooks[:] = [
        entry for entry in post_tool_hooks
        if not (
            isinstance(entry, dict)
            and isinstance(entry.get("hooks"), list)
            and any(
                isinstance(h, dict)
                and h.get("type") == "command"
                and "context-check.sh" in h.get("command", "")
                for h in entry["hooks"]
            )
        )
    ]

    if len(post_tool_hooks) != original_len:
        if post_tool_hooks:
            settings["hooks"]["PostToolUse"] = post_tool_hooks
        else:
            settings["hooks"].pop("PostToolUse", None)
            if not settings["hooks"]:
                settings.pop("hooks", None)

        try:
            legacy_settings.write_text(
                json.dumps(settings, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            sys.stderr.write(f"warning: falha ao limpar settings.local.json legado: {exc}\n")


# Backward-compat alias (testes ou call sites antigos)
_install_pre_commit_hook = _install_hooks


def _commit_scaffold(
    project_root: Path,
    workspace: str,
    profile: str,
    tier: str,
) -> str:
    """git add + commit do scaffold inicial. Retorna sha do commit.

    Usa --no-verify porque hooks de workspace anterior podem estar
    instalados e rejeitar paths como .gitignore e workspaces/.index.md
    que sao legitimos no bootstrap mas fora do workspace NNN-slug/.
    Bootstrap e trusted; hooks protegem atividade futura do usuario.
    """
    _run_git(["add", f"workspaces/{workspace}/", "workspaces/.index.md"], cwd=project_root)
    # .gitignore pode ou nao ter mudado; add idempotente
    _run_git(["add", ".gitignore"], cwd=project_root, check=False)
    # CLAUDE.md root: criado/atualizado por _render_project_claude_md;
    # add idempotente (check=False) — pode estar limpo se brownfield e nada mudou.
    _run_git(["add", "CLAUDE.md"], cwd=project_root, check=False)
    msg = f"workspace {workspace.split('-', 1)[0]}: bootstrap scaffold (profile={profile} tier={tier})"
    _run_git(["commit", "--no-verify", "-m", msg], cwd=project_root)
    res = _run_git(["rev-parse", "HEAD"], cwd=project_root)
    return res.stdout.strip()


def _render_project_claude_md(
    project_root: Path,
    *,
    workspace: str,
    profile: str,
    tier: str,
    stage_atual: str,
    stage_dir: str,
    sub_stage: str,
    iteration: int,
    status: str,
    last_action: str,
    last_action_at: str,
    next_action: str,
    skill_dir: str,
) -> Path:
    """Cria/atualiza <project_root>/CLAUDE.md com bloco ICM do workspace.

    Idempotente. Brownfield-safe (preserva conteúdo fora dos marcadores ICM).
    Multi-workspace: adiciona bloco preservando blocos de outros workspaces.
    Doc canônico: references/project-root-claude-md.md.
    """
    # Lazy import: handoff.py está no mesmo diretório scripts/ mas não há __init__.py
    # então import direto via sys.path adjustment.
    _scripts_dir = str(Path(__file__).parent)
    if _scripts_dir not in sys.path:
        sys.path.insert(0, _scripts_dir)
    from handoff import WorkspaceBlock, update_project_claude_md  # noqa: PLC0415

    block = WorkspaceBlock(
        workspace=workspace,
        profile=profile,
        tier=tier,
        stage_atual=stage_atual,
        stage_dir=stage_dir,
        sub_stage=sub_stage,
        iteration=iteration,
        status=status,
        last_action=last_action,
        last_action_at=last_action_at,
        next_action=next_action,
    )
    return update_project_claude_md(project_root, block, skill_dir)


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
    _run_git(["commit", "--no-verify", "-m", msg], cwd=project_root)


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
    _scaffold_workspace_dirs(workspace_dir, skill_root, project_root)

    # Copia test-recipe especifica do profile efetivo para _references/test-recipes/.
    # So o arquivo do profile ativo e copiado; profiles sem receita (experiment,
    # technical_article) tem arquivo minimo no template.
    test_recipes_src = skill_root / "templates" / "_references" / "test-recipes"
    if test_recipes_src.is_dir():
        recipe_file = test_recipes_src / f"{profile}.md"
        if recipe_file.is_file():
            test_recipes_dst = workspace_dir / "_references" / "test-recipes"
            test_recipes_dst.mkdir(parents=True, exist_ok=True)
            shutil.copy2(recipe_file, test_recipes_dst / f"{profile}.md")

    # Stages skipped: derive from profile-effective and write SKIP.md markers
    stages_skipped: list[str] = effective.get("stages_skipped", [])
    for skip_id in stages_skipped:
        skip_dir = workspace_dir / "stages" / f"{skip_id}_{STAGE_NAMES[int(skip_id)]}"
        if skip_dir.exists():
            skip_file = skip_dir / "SKIP.md"
            skip_file.write_text(
                f"---\nlayer: L2-skip\nstage: \"{skip_id}\"\nreason: \"skipped by profile/tier\"\n---\n\n"
                f"# Stage {skip_id} ({STAGE_NAMES[int(skip_id)]}) — SKIPPED\n\n"
                f"Este estágio foi pulado pelo profile/tier deste workspace.\n"
                f"O fluxo transita automaticamente deste stage para o próximo não-pulado.\n",
                encoding="utf-8",
            )

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
        "SKILL_DIR": str(skill_root).replace("\\", "/"),
        "BOOTSTRAP_COMMIT_SHA": "{{BOOTSTRAP_COMMIT_SHA}}",  # patched depois
        "STAGES_SKIPPED": yaml_safe_list(stages_skipped),
        "WORKSPACE_NUM": workspace.split("-", 1)[0],
    }

    tpl_dir = skill_root / "templates" / "workspace"

    # Render L2 CONTEXT.md for each stage
    stages_tpl_dir = tpl_dir / "stages"
    for stage_dir_name in STAGES:
        l2_tpl = stages_tpl_dir / stage_dir_name / "CONTEXT.md.tpl"
        if l2_tpl.exists():
            l2_rendered = render_template(l2_tpl, placeholders)
            l2_out = workspace_dir / "stages" / stage_dir_name / "CONTEXT.md"
            l2_out.write_text(l2_rendered, encoding="utf-8")

    claude_md = render_template(tpl_dir / "CLAUDE.md.tpl", placeholders)
    (workspace_dir / "CLAUDE.md").write_text(claude_md, encoding="utf-8")

    # xp-conventions.md (L3 — convenções de código/processo)
    xp_conv_tpl = tpl_dir / "_config" / "xp-conventions.md.tpl"
    if xp_conv_tpl.exists():
        xp_conv_rendered = render_template(xp_conv_tpl, placeholders)
        (workspace_dir / "_config" / "xp-conventions.md").write_text(
            xp_conv_rendered, encoding="utf-8"
        )

    # CONTEXT.md tem placeholder BOOTSTRAP_COMMIT_SHA que so existe pos-commit.
    # Usamos UUID sentinel colision-safe em vez de "PENDING" (que podia colidir
    # com outros campos). Patch depois do primeiro commit.
    _sha_sentinel = f"__BOOTSTRAP_SHA_{uuid.uuid4().hex[:12]}__"
    placeholders_l1 = dict(placeholders)
    placeholders_l1["BOOTSTRAP_COMMIT_SHA"] = _sha_sentinel
    context_md = render_template(tpl_dir / "CONTEXT.md.tpl", placeholders_l1)
    # Volta o sentinel para `{{BOOTSTRAP_COMMIT_SHA}}` literal; patch depois
    context_md = context_md.replace(_sha_sentinel, "{{BOOTSTRAP_COMMIT_SHA}}")
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

    # CLAUDE.md no project_root: cria/atualiza com bloco do novo workspace.
    # Brownfield-safe: marcadores ICM delimitam região; conteúdo fora preservado.
    # Multi-workspace: blocos de workspaces existentes preservados.
    # Doc canônico: references/project-root-claude-md.md.
    _render_project_claude_md(
        project_root=project_root,
        workspace=workspace,
        profile=profile,
        tier=tier,
        stage_atual="00",
        stage_dir="00_recon",
        sub_stage="00_in_progress",
        iteration=0,
        status="IN_PROGRESS",
        last_action=f"bootstrap (profile={profile} tier={tier})",
        last_action_at=created_at,
        next_action="iniciar stage 00 recon",
        skill_dir=str(skill_root).replace("\\", "/"),
    )

    # Indice + .gitignore do projeto
    update_index(
        index_path,
        workspace=workspace,
        profile=profile,
        tier=tier,
        created_at=created_at,
    )
    update_gitignore(project_root / ".gitignore", list(GITIGNORE_LINES))

    # Commit 1: scaffold com --no-verify. Hooks de workspace anterior podem
    # estar instalados e rejeitar paths legitimos do bootstrap (.gitignore,
    # workspaces/.index.md). Bootstrap e trusted; hooks protegem atividade
    # futura do usuario.
    commit_sha = _commit_scaffold(project_root, workspace, profile, tier)

    # Patch CONTEXT.md com sha do commit + commit 2
    _patch_context_with_sha(workspace_dir / "CONTEXT.md", commit_sha)
    _commit_context_sha(project_root, workspace)
    final_sha = _run_git(["rev-parse", "HEAD"], cwd=project_root).stdout.strip()

    # Hooks instalados por ULTIMO: protegem commits futuros do usuario sem
    # interferir nos commits atomicos do bootstrap. Pre-commit + commit-msg
    # juntos cobrem file checks e msg validation respectivamente.
    _install_hooks(project_root, skill_root)

    # Context checkpoint hook (anti-compact): detecta contexto >= 70% e
    # dispara handoff antecipado obrigatorio. Instalado apos git hooks.
    _install_context_hook(project_root, skill_root, workspace)

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
    except subprocess.CalledProcessError as exc:
        print(f"erro: comando git falhou (rc={exc.returncode}): {exc.stderr.strip() if exc.stderr else exc}", file=sys.stderr)
        return 1
    except BootstrapError as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
