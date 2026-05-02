"""Backend Python do protocolo de session handoff (1 stage = 1 sessao).

Renderiza `_kickoff.md` no diretorio do proximo stage usando template em
`templates/workspace/stages/_kickoff.md.tpl`. Helpers determinsticos sao
testados em `tests/unit/test_handoff.py`. Doc canonico em
`references/session-handoff-protocol.md`.

CLI mode (debug): `python scripts/handoff.py render --workspace-root <path>
  --prev-stage 02 --prev-stage-name design
  --stage-target 03 --stage-target-name wave_planner --commit-sha abc123`.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Sequence

import yaml


# ============================================================================
# Constantes
# ============================================================================

PLACEHOLDER_RE = re.compile(r"\{\{([A-Z_][A-Z0-9_]*)\}\}")

# Mapping fixo stage_id -> nome do diretorio (id + name canonico)
STAGE_DIR_BY_ID: dict[str, str] = {
    "00": "00_recon",
    "01": "01_discovery",
    "02": "02_design",
    "03": "03_wave_planner",
    "04": "04_implementation_waves",
    "05": "05_verification",
    "06": "06_review",
    "07": "07_merge",
    "08": "08_feedback_intake",
}

# Indent canonico do bloco YAML literal `prev_decisions_summary: |`
DECISIONS_INDENT = "  "


# ============================================================================
# Tipos
# ============================================================================

class HandoffError(Exception):
    """Erro de protocolo de handoff (template, render, parse, IO)."""


@dataclass(frozen=True)
class PrevOutput:
    """Output declarado pela sessao anterior, listado em prev_outputs."""
    path: str       # path relativo ao workspace, ex "stages/02_design/output/plan.md"
    summary: str    # 1-2 linhas


@dataclass(frozen=True)
class HandoffData:
    """Dados completos para renderizar `_kickoff.md`."""
    workspace: str           # "042-feat-auth"
    project_root: str        # absolute path
    prev_stage: str          # "02"
    prev_stage_name: str     # "design"
    stage_target: str        # "03"
    stage_target_name: str   # "wave_planner"
    stage_target_dir: str    # "03_wave_planner"
    generated_at: str        # ISO 8601 UTC
    generator_commit_sha: str
    prev_outputs: Sequence[PrevOutput] = field(default_factory=tuple)
    prev_decisions_summary: str = ""
    pending_for_this_stage: Sequence[str] = field(default_factory=tuple)
    prev_state_prose: str = ""
    next_tasks_prose: str = ""


# ============================================================================
# Helpers determinsticos
# ============================================================================

def stage_target_dir(stage_id: str, stage_name: str) -> str:
    """Resolve nome canonico do diretorio (`<id>_<name>`).

    Valida que `stage_id` esta no mapping e que `stage_name` bate o canonico.
    """
    if stage_id not in STAGE_DIR_BY_ID:
        raise HandoffError(
            f"stage_id desconhecido: {stage_id!r} (validos: "
            f"{sorted(STAGE_DIR_BY_ID)})"
        )
    canonical = STAGE_DIR_BY_ID[stage_id]
    expected_name = canonical[3:]  # strip "NN_"
    if stage_name != expected_name:
        raise HandoffError(
            f"stage_name {stage_name!r} nao bate canonico {expected_name!r} "
            f"para stage_id {stage_id}"
        )
    return canonical


def utc_now_iso() -> str:
    """Timestamp UTC ISO 8601 com sufixo Z."""
    return _dt.datetime.now(_dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _yaml_inline_list(items: Sequence[str]) -> str:
    """Lista YAML inline. Vazio -> `[]`. Strings entre aspas duplas."""
    if not items:
        return "[]"
    quoted = ", ".join(f'"{_yaml_escape(s)}"' for s in items)
    return f"[{quoted}]"


def _yaml_escape(s: str) -> str:
    """Escape minimo para string YAML entre aspas duplas."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _prev_outputs_yaml(outputs: Sequence[PrevOutput]) -> str:
    """Serializa prev_outputs como bloco YAML.

    Vazio -> `[]` inline. Caso contrario, lista de objetos em linhas
    seguintes, com indent zero porque a chave ja foi escrita no template.
    """
    if not outputs:
        return "[]"
    lines: list[str] = [""]  # quebra logo apos `prev_outputs:`
    for item in outputs:
        lines.append(f'  - path: "{_yaml_escape(item.path)}"')
        lines.append(f'    summary: "{_yaml_escape(item.summary)}"')
    return "\n".join(lines)


def _indent_multiline(text: str, indent: str) -> str:
    """Aplica indent em cada linha (para YAML literal block)."""
    if not text:
        return ""
    lines = text.split("\n")
    return ("\n" + indent).join(lines)


def _build_placeholders(data: HandoffData) -> dict[str, str]:
    """Mapeia HandoffData -> dict de placeholders para o template."""
    return {
        "WORKSPACE": data.workspace,
        "PROJECT_ROOT": data.project_root,
        "PREV_STAGE": data.prev_stage,
        "PREV_STAGE_NAME": data.prev_stage_name,
        "STAGE_TARGET": data.stage_target,
        "STAGE_TARGET_NAME": data.stage_target_name,
        "STAGE_TARGET_DIR": data.stage_target_dir,
        "GENERATED_AT": data.generated_at,
        "GENERATOR_COMMIT_SHA": data.generator_commit_sha,
        "PREV_OUTPUTS_YAML": _prev_outputs_yaml(data.prev_outputs),
        "PREV_DECISIONS_SUMMARY_INDENTED": _indent_multiline(
            data.prev_decisions_summary, DECISIONS_INDENT
        ),
        "PENDING_YAML": _yaml_inline_list(data.pending_for_this_stage),
        "PREV_STATE_PROSE": data.prev_state_prose,
        "NEXT_TASKS_PROSE": data.next_tasks_prose,
    }


# ============================================================================
# API publica
# ============================================================================

def render_kickoff(template_path: Path, data: HandoffData) -> str:
    """Substitui placeholders `{{KEY}}` pelos valores derivados de `data`.

    Raise `HandoffError` se template ausente ou se sobra placeholder
    nao resolvido.
    """
    if not template_path.exists():
        raise HandoffError(f"template ausente: {template_path}")

    placeholders = _build_placeholders(data)
    content = template_path.read_text(encoding="utf-8")

    def _sub(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in placeholders:
            raise HandoffError(
                f"placeholder nao resolvido: {{{{{key}}}}} em {template_path.name}"
            )
        return placeholders[key]

    rendered = PLACEHOLDER_RE.sub(_sub, content)
    leftover = PLACEHOLDER_RE.search(rendered)
    if leftover:
        raise HandoffError(
            f"placeholder nao resolvido: {leftover.group(0)} em {template_path.name}"
        )
    return rendered


def write_kickoff(
    workspace_root: Path,
    data: HandoffData,
    *,
    template_path: Path | None = None,
) -> Path:
    """Escreve `<workspace_root>/stages/<stage_target_dir>/_kickoff.md`.

    Cria dir se ausente. Idempotente (sobrescreve com mesmo conteudo).
    Retorna path absoluto escrito.
    """
    tpl = template_path or _default_template_path()
    rendered = render_kickoff(tpl, data)
    target_dir = workspace_root / "stages" / data.stage_target_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    out_path = (target_dir / "_kickoff.md").resolve()
    out_path.write_text(rendered, encoding="utf-8")
    return out_path


def extract_kickoff_metadata(kickoff_path: Path) -> dict:
    """Parse YAML frontmatter de `_kickoff.md`. Retorna dict.

    Raise `HandoffError` se arquivo ausente, frontmatter ausente ou YAML invalido.
    """
    if not kickoff_path.exists():
        raise HandoffError(f"kickoff ausente: {kickoff_path}")
    text = kickoff_path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise HandoffError(f"frontmatter ausente em {kickoff_path}")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise HandoffError(f"frontmatter mal formado (sem fim) em {kickoff_path}")
    fm_text = text[4:end]
    try:
        meta = yaml.safe_load(fm_text)
    except yaml.YAMLError as exc:
        raise HandoffError(f"YAML invalido em {kickoff_path}: {exc}") from exc
    if not isinstance(meta, dict):
        raise HandoffError(f"frontmatter nao e dict em {kickoff_path}")
    return meta


def validate_kickoff_present(workspace_root: Path, stage_atual: str) -> bool:
    """Pre-flight de sessao nova: verifica se `_kickoff.md` existe.

    Retorna True se OK, False se ausente. Stage_id desconhecido -> raise.
    """
    if stage_atual not in STAGE_DIR_BY_ID:
        raise HandoffError(
            f"stage_atual desconhecido: {stage_atual!r}"
        )
    kickoff = (
        workspace_root
        / "stages"
        / STAGE_DIR_BY_ID[stage_atual]
        / "_kickoff.md"
    )
    return kickoff.is_file()


# ============================================================================
# Internals
# ============================================================================

def _default_template_path() -> Path:
    return (
        Path(__file__).resolve().parent.parent
        / "templates"
        / "workspace"
        / "stages"
        / "_kickoff.md.tpl"
    )


# ============================================================================
# CLAUDE.md no project_root: bloco dinâmico do workspace ativo
# ============================================================================

ICM_START_MARKER = "<!-- ICM-START -->"
ICM_END_MARKER = "<!-- ICM-END -->"


@dataclass(frozen=True)
class WorkspaceBlock:
    """Estado renderizado de um workspace na região ICM do CLAUDE.md root.

    Serializado como JSON em comentário `<!-- ICM-DATA:... -->` para round-trip
    determinístico (parse + re-render preservam todos os campos).
    """
    workspace: str
    profile: str
    tier: str
    stage_atual: str
    stage_dir: str
    sub_stage: str
    iteration: int
    status: str
    last_action: str
    last_action_at: str
    next_action: str


def _block_marker_start(workspace: str) -> str:
    return f"<!-- ICM-WORKSPACE:{workspace} -->"


def _block_marker_end(workspace: str) -> str:
    return f"<!-- /ICM-WORKSPACE:{workspace} -->"


def _atomic_write(path: Path, content: str) -> None:
    """Write tmp + fsync + rename — crash mid-write não corrompe arquivo (G15).

    Sufixo `.tmp` no mesmo diretório garante atomic rename mesmo entre filesystems.
    """
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    try:
        fd = os.open(str(tmp), os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError:
        # fsync pode falhar em filesystems não-POSIX (Windows network drives,
        # tmpfs alguns kernels). Nesses casos rename ainda é atomic.
        pass
    tmp.replace(path)


def _render_workspace_block_md(b: WorkspaceBlock) -> str:
    """Markdown do bloco do workspace (sem marcadores HTML)."""
    return (
        f"### Workspace `{b.workspace}` · profile=`{b.profile}` · tier=`{b.tier}`\n"
        "\n"
        f"- **Stage atual:** `{b.stage_atual}` (`{b.stage_dir}`) · "
        f"**Sub-stage:** `{b.sub_stage}` · **Iteration:** `{b.iteration}`\n"
        f"- **Status:** `{b.status}`\n"
        f"- **Last action:** `{b.last_action}` em `{b.last_action_at}`\n"
        f"- **Next action:** `{b.next_action}`\n"
        "\n"
        "**Read order para retomar:**\n"
        f"1. `workspaces/{b.workspace}/CLAUDE.md` (L0)\n"
        f"2. `workspaces/{b.workspace}/CONTEXT.md` (L1)\n"
        f"3. `workspaces/{b.workspace}/stages/{b.stage_dir}/CONTEXT.md` (L2)\n"
        f"4. `workspaces/{b.workspace}/stages/{b.stage_dir}/_kickoff.md` (se existir)\n"
    )


def _wrap_block_with_markers(b: WorkspaceBlock) -> str:
    """Bloco markdown encapsulado por marcadores HTML + JSON serializado.

    Estrutura:
        <!-- ICM-WORKSPACE:NNN-slug -->
        <!-- ICM-DATA:{...json...} -->
        ### Workspace `NNN-slug` · ...
        ...
        <!-- /ICM-WORKSPACE:NNN-slug -->
    """
    data_json = json.dumps(asdict(b), ensure_ascii=False, sort_keys=True)
    return (
        f"{_block_marker_start(b.workspace)}\n"
        f"<!-- ICM-DATA:{data_json} -->\n"
        f"{_render_workspace_block_md(b)}"
        f"{_block_marker_end(b.workspace)}\n"
    )


def _render_icm_header() -> str:
    return (
        "## Active ICM Workspaces\n"
        "\n"
        "> Esta seção é mantida automaticamente pela skill `xp-icm-workflow`.\n"
        "> Não editar manualmente — atualizada a cada handoff de stage.\n"
        "> **Não rode `/init` enquanto houver workspace ativo.**\n"
        "\n"
    )


def _render_icm_footer(skill_dir: str) -> str:
    return (
        "\n"
        "---\n"
        "\n"
        f"**Skill:** `{skill_dir}/SKILL.md` · "
        f"**Recovery:** `python {skill_dir}/scripts/recovery-wizard.py` · "
        "**Estado canônico:** `workspaces/.index.md`\n"
    )


def _render_icm_idle(
    closed_at: str,
    *,
    outcome: str = "A",
    spawn_to: str | None = None,
) -> str:
    """Mensagem 'nenhum workspace ativo' (Saída A close ou Saída C spawn).

    v3.7.0: branches por outcome.
    - A (default): workspace fechado limpo. Próximo passo `/init`.
    - C: workspace transicionou pra spawn_to. Próximo passo bootstrap em
      sessão nova (humano cola `/xp-icm-workflow spawn_from=<old>`).
    """
    if outcome not in ("A", "C"):
        raise ValueError(
            f"outcome inválido: {outcome!r} (esperado 'A' ou 'C')"
        )
    if outcome == "C" and not spawn_to:
        raise ValueError("outcome='C' requer spawn_to não-vazio")
    closed = closed_at if closed_at else "desconhecido"
    if outcome == "A":
        return (
            "## ICM — Nenhum workspace ativo\n"
            "\n"
            f"> Último workspace foi finalizado em `{closed}` (Saída A — close).\n"
            "> Histórico em `workspaces/`.\n"
            ">\n"
            "> **Próximo passo:** rode `/init` para regenerar a região abaixo com\n"
            "> informações do código construído. Esta região ICM permanecerá vazia\n"
            "> até bootstrap de novo workspace.\n"
        )
    # outcome == "C"
    return (
        "## ICM — Nenhum workspace ativo\n"
        "\n"
        f"> Último workspace transicionou em `{closed}` "
        f"(Saída C — spawn `{spawn_to}`).\n"
        "> Bootstrap em sessão nova: `/xp-icm-workflow` detecta "
        "`.icm/spawn-pending.json` automaticamente,\n"
        f"> ou cole arg explícito `--spawn-from=<NNN>` para `{spawn_to}`.\n"
        "> Histórico em `workspaces/`.\n"
    )


def _render_full_icm_region(blocks: Sequence[WorkspaceBlock], skill_dir: str) -> str:
    """Conteúdo completo da região ICM (sem marcadores externos START/END).

    Vazio -> mensagem idle (default Saída A). Para idle outcome-aware (Saída C),
    use `_write_icm_region` com kwargs `outcome` + `spawn_to`.
    1+ workspaces -> header + blocos + footer.
    """
    if not blocks:
        return _render_icm_idle("")
    sorted_blocks = sorted(blocks, key=lambda b: b.workspace)
    body = "\n".join(_wrap_block_with_markers(b) for b in sorted_blocks)
    return _render_icm_header() + body + _render_icm_footer(skill_dir)


def _wrap_outer(region_inner: str) -> str:
    """Envolve região em <!-- ICM-START --> ... <!-- ICM-END -->."""
    return f"{ICM_START_MARKER}\n{region_inner}{ICM_END_MARKER}\n"


def _greenfield_template(project_name: str, region_outer: str) -> str:
    """CLAUDE.md root completo para projeto sem CLAUDE.md preexistente."""
    return (
        f"# CLAUDE.md — {project_name}\n"
        "\n"
        "This file provides guidance to Claude Code (claude.ai/code) when working in this repository.\n"
        "\n"
        f"{region_outer}\n"
        "<!-- A região abaixo é livre. Pode ser preenchida pelo `/init` do Claude Code -->\n"
        "<!-- ou manualmente pelo usuário com codebase context (commands, architecture,   -->\n"
        "<!-- conventions, etc). A skill `xp-icm-workflow` NUNCA toca esta região.        -->\n"
    )


def _insert_region_after_first_h1(content: str, region_outer: str) -> str:
    """Brownfield sem marcadores: insere região após primeiro título H1.

    Se não houver H1, prepende ao topo. Demais conteúdo preservado.
    """
    lines = content.split("\n")
    insert_idx: int | None = None
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        if stripped.startswith("# ") and not stripped.startswith("## "):
            # H1 encontrado
            insert_idx = i + 1
            # Skip linhas em branco e descrição imediatamente após o título
            while insert_idx < len(lines) and lines[insert_idx].strip() == "":
                insert_idx += 1
            break
    if insert_idx is None:
        # Sem H1: prepende
        return region_outer + "\n" + content
    before = "\n".join(lines[:insert_idx])
    after = "\n".join(lines[insert_idx:])
    sep_b = "" if before.endswith("\n") else "\n"
    sep_a = "" if after.startswith("\n") else "\n"
    return before + sep_b + "\n" + region_outer + sep_a + after


def _parse_workspace_blocks(claude_md_path: Path) -> dict[str, WorkspaceBlock]:
    """Extrai dict[workspace_id -> WorkspaceBlock] do CLAUDE.md root.

    Parse via JSON em comentários `<!-- ICM-DATA:... -->`. Round-trip seguro.
    Arquivo ausente ou sem marcadores -> dict vazio.
    """
    if not claude_md_path.exists():
        return {}
    content = claude_md_path.read_text(encoding="utf-8")
    pattern = re.compile(
        r"<!-- ICM-WORKSPACE:([^\s>]+) -->\n<!-- ICM-DATA:(.+?) -->\n",
    )
    out: dict[str, WorkspaceBlock] = {}
    for match in pattern.finditer(content):
        ws_id = match.group(1)
        try:
            data = json.loads(match.group(2))
            out[ws_id] = WorkspaceBlock(**data)
        except (json.JSONDecodeError, TypeError):
            # Bloco corrompido -> ignora; recovery wizard detecta depois
            continue
    return out


def _write_icm_region(
    claude_md: Path,
    project_name: str,
    blocks: list[WorkspaceBlock],
    skill_dir: str,
    *,
    idle_outcome: str = "A",
    idle_spawn_to: str | None = None,
    idle_closed_at: str = "",
) -> None:
    """Helper: escreve região ICM completa preservando conteúdo fora dos marcadores.

    - Greenfield (arquivo ausente) -> cria via _greenfield_template.
    - Brownfield com marcadores -> substitui apenas conteúdo entre marcadores.
    - Brownfield sem marcadores -> insere após primeiro H1.

    Se `blocks` vazio: usa `_render_icm_idle` com outcome+spawn_to do caller.
    """
    if blocks:
        region_inner = _render_full_icm_region(blocks, skill_dir)
    else:
        region_inner = _render_icm_idle(
            idle_closed_at, outcome=idle_outcome, spawn_to=idle_spawn_to,
        )
    region_outer = _wrap_outer(region_inner)

    if not claude_md.exists():
        content = _greenfield_template(project_name, region_outer.rstrip("\n"))
        _atomic_write(claude_md, content)
        return

    current = claude_md.read_text(encoding="utf-8")
    start = current.find(ICM_START_MARKER)
    end = current.find(ICM_END_MARKER)
    if start < 0 or end <= start:
        # Brownfield sem marcadores
        new_content = _insert_region_after_first_h1(current, region_outer)
    else:
        end_after = end + len(ICM_END_MARKER)
        # Pular newline imediatamente após ICM_END_MARKER (se houver) para
        # não acumular blank lines a cada update.
        if end_after < len(current) and current[end_after] == "\n":
            end_after += 1
        new_content = current[:start] + region_outer + current[end_after:]
    _atomic_write(claude_md, new_content)


def update_project_claude_md(
    project_root: Path,
    workspace_block: WorkspaceBlock,
    skill_dir: str,
) -> Path:
    """Insere ou atualiza o bloco do workspace no CLAUDE.md do project_root.

    Idempotente. Brownfield-safe. Preserva blocos de outros workspaces.
    Retorna path absoluto do arquivo escrito.
    """
    claude_md = project_root / "CLAUDE.md"
    blocks = _parse_workspace_blocks(claude_md)
    blocks[workspace_block.workspace] = workspace_block
    _write_icm_region(claude_md, project_root.name, list(blocks.values()), skill_dir)
    return claude_md


def _update_index_status(
    project_root: Path,
    workspace: str,
    new_status: str,
) -> bool:
    """Reescreve linha do workspace em `workspaces/.index.md` mudando status.

    `.index.md` formato canônico:
      | NNN | slug | profile/tier | created_at | status |

    `workspace` = "NNN-slug". Localiza linha cujo NNN+slug bate, substitui
    último campo (status). Se index ausente ou linha não encontrada, no-op.

    Retorna True se atualizou, False se no-op (idempotente).

    v3.7.1: corrige bug `.index.md` stale após saída A/C — antes do fix,
    `update_index` (bootstrap.py) só appendava `active`; saída A/C
    nunca reescrevia status pra `COMPLETED`. Hook SessionStart lia index
    stale e detectava workspace fechado como ativo.
    """
    index_path = project_root / "workspaces" / ".index.md"
    if not index_path.exists():
        return False
    nnn, _, slug = workspace.partition("-")
    nnn = nnn.strip()
    slug = slug.strip()
    if not nnn or not slug:
        return False
    text = index_path.read_text(encoding="utf-8")
    lines = text.split("\n")
    changed = False
    for idx, line in enumerate(lines):
        if not re.match(r"^\| *[0-9]{3} *\|", line):
            continue
        cols = [c.strip() for c in line.split("|")]
        # cols[0]=='', cols[1]=NNN, cols[2]=slug, cols[3]=profile/tier,
        # cols[4]=created, cols[5]=status, cols[6]=='' (trailing)
        if len(cols) < 6:
            continue
        if cols[1] == nnn and cols[2] == slug:
            cols[5] = new_status
            new_line = "| " + " | ".join(cols[1:6]) + " |"
            if line != new_line:
                lines[idx] = new_line
                changed = True
            break
    if changed:
        index_path.write_text("\n".join(lines), encoding="utf-8")
    return changed


def _unregister_workspace_hooks(
    project_root: Path,
    workspace: str,
) -> bool:
    """Remove entries do workspace fechado de `.claude/settings.local.json`.

    Bootstrap (`_merge_project_settings_local`) registra hooks por workspace
    com command path `$CLAUDE_PROJECT_DIR/workspaces/<workspace>/.claude/hooks/...`.
    Saída A/C precisa remover esses entries pra evitar acúmulo (settings com
    hooks duplicados após múltiplos workspaces fechados).

    Detecta entries via substring `workspaces/<workspace>/.claude/hooks/` no
    command. Se evento fica vazio (zero entries) após remoção, remove o
    evento. Se settings inteiro fica sem `hooks`, deixa estrutura vazia.

    Idempotente: ausência de entries = no-op. Settings inválido = no-op.

    Retorna True se modificou, False se no-op.
    """
    settings_path = project_root / ".claude" / "settings.local.json"
    if not settings_path.exists():
        return False
    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    if not isinstance(settings, dict):
        return False
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return False

    target_substr = f"workspaces/{workspace}/.claude/hooks/"
    changed = False
    events_to_remove: list[str] = []
    for event, entries in list(hooks.items()):
        if not isinstance(entries, list):
            continue
        kept_entries: list[dict] = []
        for entry in entries:
            if not isinstance(entry, dict):
                kept_entries.append(entry)
                continue
            inner_hooks = entry.get("hooks", []) or []
            kept_inner: list[dict] = []
            for h in inner_hooks:
                if not isinstance(h, dict):
                    kept_inner.append(h)
                    continue
                cmd = h.get("command", "")
                if isinstance(cmd, str) and target_substr in cmd:
                    changed = True
                    continue
                kept_inner.append(h)
            if kept_inner:
                if kept_inner != inner_hooks:
                    entry = {**entry, "hooks": kept_inner}
                kept_entries.append(entry)
            else:
                changed = True
        if kept_entries != entries:
            if kept_entries:
                hooks[event] = kept_entries
            else:
                events_to_remove.append(event)
    for event in events_to_remove:
        hooks.pop(event, None)

    if changed:
        try:
            settings_path.write_text(
                json.dumps(settings, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            sys.stderr.write(
                f"warning: falha ao escrever {settings_path}: {exc}\n"
            )
            return False
    return changed


def remove_workspace_block(
    project_root: Path,
    workspace: str,
    skill_dir: str,
    *,
    closed_at: str = "",
    outcome: str = "A",
    spawn_to: str | None = None,
) -> Path:
    """Remove o bloco do workspace do CLAUDE.md root.

    Se workspace não existia: no-op (return path sem escrever).
    Se era o último: substitui região por mensagem idle (deactivate).

    v3.7.0:
    - `outcome` ∈ {"A", "C"}. A = close, C = spawn novo workspace.
    - `spawn_to` requerido se outcome="C" (mensagem idle cita slug).

    v3.7.1:
    - Atualiza `workspaces/.index.md` marcando workspace como COMPLETED.
    - Remove entries do workspace de `.claude/settings.local.json` (hooks).

    Saída B usa `update_project_claude_md` (fase 08 transita pra outro stage,
    não fecha workspace).
    """
    if outcome not in ("A", "C"):
        raise ValueError(
            f"outcome inválido: {outcome!r} (esperado 'A' ou 'C'). "
            "Saída B não remove bloco — usa update_project_claude_md."
        )
    if outcome == "C" and not spawn_to:
        raise ValueError("outcome='C' requer spawn_to não-vazio")
    claude_md = project_root / "CLAUDE.md"
    blocks = _parse_workspace_blocks(claude_md)
    if workspace not in blocks:
        return claude_md
    del blocks[workspace]
    if blocks:
        _write_icm_region(claude_md, project_root.name, list(blocks.values()), skill_dir)
    else:
        deactivate_project_claude_md(
            project_root,
            closed_at=closed_at,
            outcome=outcome,
            spawn_to=spawn_to,
        )

    # v3.7.1: cleanup pós-saída A/C
    _update_index_status(project_root, workspace, "COMPLETED")
    _unregister_workspace_hooks(project_root, workspace)

    return claude_md


def deactivate_project_claude_md(
    project_root: Path,
    *,
    closed_at: str = "",
    outcome: str = "A",
    spawn_to: str | None = None,
) -> Path:
    """Substitui região ICM por mensagem 'nenhum workspace ativo'.

    Usado após Saída A (close) ou Saída C (spawn) quando não restam workspaces
    ativos. Conteúdo fora dos marcadores preservado intacto.

    v3.4.1: também migra CLAUDE.md root para a base branch via worktree
    `.icm-main/`. Sem isso, o CLAUDE.md idle some quando workspace branch
    é deletada (todo dashboard ICM perdido). Doc:
    references/project-root-claude-md.md.

    v3.7.0:
    - `outcome` ∈ {"A", "C"}. Render mensagem específica do tipo.
    - `spawn_to` requerido se outcome="C".
    """
    if outcome not in ("A", "C"):
        raise ValueError(
            f"outcome inválido: {outcome!r} (esperado 'A' ou 'C')"
        )
    if outcome == "C" and not spawn_to:
        raise ValueError("outcome='C' requer spawn_to não-vazio")
    claude_md = project_root / "CLAUDE.md"
    region_inner = _render_icm_idle(
        closed_at, outcome=outcome, spawn_to=spawn_to,
    )
    region_outer = _wrap_outer(region_inner)

    if not claude_md.exists():
        # Greenfield idle: criar arquivo com região idle
        content = _greenfield_template(project_root.name, region_outer.rstrip("\n"))
        _atomic_write(claude_md, content)
    else:
        current = claude_md.read_text(encoding="utf-8")
        start = current.find(ICM_START_MARKER)
        end = current.find(ICM_END_MARKER)
        if start < 0 or end <= start:
            new_content = _insert_region_after_first_h1(current, region_outer)
        else:
            end_after = end + len(ICM_END_MARKER)
            if end_after < len(current) and current[end_after] == "\n":
                end_after += 1
            new_content = current[:start] + region_outer + current[end_after:]
        _atomic_write(claude_md, new_content)

    # v3.4.1: persistir mesma versao idle em .icm-main/CLAUDE.md (base branch)
    # para sobreviver delecao da workspace branch.
    _persist_claude_md_to_base_via_worktree(project_root, claude_md)

    return claude_md


def _persist_claude_md_to_base_via_worktree(
    project_root: Path,
    claude_md_src: Path,
) -> None:
    """Copia CLAUDE.md do project_root para `.icm-main/CLAUDE.md` + commit em base.

    Idempotente: se conteúdo identico, git status detecta e nao commita.
    Silently no-op se `.icm-main/` ausente (projeto pre-v3.4.0 ou worktree
    removido manualmente).

    Doc: references/worktree-model.md (v3.4.0) +
    references/project-root-claude-md.md (owner transition saída A).
    """
    import subprocess  # noqa: PLC0415

    worktree = project_root / ".icm-main"
    if not worktree.is_dir():
        return  # worktree ausente — projeto provavelmente pre-v3.4.0

    if not claude_md_src.is_file():
        return

    dst = worktree / "CLAUDE.md"
    src_text = claude_md_src.read_text(encoding="utf-8")
    if dst.exists() and dst.read_text(encoding="utf-8") == src_text:
        return  # idempotente

    dst.write_text(src_text, encoding="utf-8")

    # Commit em base branch via worktree linkada
    try:
        subprocess.run(
            ["git", "-C", str(worktree), "add", "CLAUDE.md"],
            check=False, capture_output=True, text=True,
        )
        subprocess.run(
            ["git", "-C", str(worktree), "commit", "--no-verify", "-m",
             "docs(claude.md): persist idle/active state to base (saida A handoff)"],
            check=False, capture_output=True, text=True,
        )
    except Exception:
        # Falha de git nao deve quebrar handoff — humano pode commitar manualmente
        pass


def list_active_workspace_ids(project_root: Path) -> list[str]:
    """Lista IDs de workspaces presentes na região ICM do CLAUDE.md root.

    Usado por bootstrap para detectar workspaces preexistentes em multi-workspace
    e por recovery wizard para checar consistência com .index.md.
    """
    return sorted(_parse_workspace_blocks(project_root / "CLAUDE.md").keys())


# ============================================================================
# CLI
# ============================================================================

def _parse_prev_outputs_arg(raw: str | None) -> tuple[PrevOutput, ...]:
    """Parse `path1:summary1,path2:summary2` -> tuple[PrevOutput]."""
    if not raw:
        return ()
    items: list[PrevOutput] = []
    for chunk in raw.split(","):
        if ":" not in chunk:
            raise HandoffError(f"prev-outputs chunk sem ':' -> {chunk!r}")
        path, summary = chunk.split(":", 1)
        items.append(PrevOutput(path=path.strip(), summary=summary.strip()))
    return tuple(items)


def _parse_pending_arg(raw: str | None) -> tuple[str, ...]:
    """Parse `p1|p2|p3` -> tuple[str]."""
    if not raw:
        return ()
    return tuple(p.strip() for p in raw.split("|") if p.strip())


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="handoff.py")
    sub = parser.add_subparsers(dest="cmd", required=True)

    render = sub.add_parser("render", help="Renderiza e escreve _kickoff.md")
    render.add_argument("--workspace-root", type=Path, required=True)
    render.add_argument("--prev-stage", required=True)
    render.add_argument("--prev-stage-name", required=True)
    render.add_argument("--stage-target", required=True)
    render.add_argument("--stage-target-name", required=True)
    render.add_argument("--commit-sha", required=True)
    render.add_argument("--prev-outputs", default=None,
                        help="path1:summary1,path2:summary2")
    render.add_argument("--pending", default=None, help="p1|p2|p3")
    render.add_argument("--decisions-summary", default="")
    render.add_argument("--prev-state-prose", default="")
    render.add_argument("--next-tasks-prose", default="")
    render.add_argument("--project-root", type=Path, default=None,
                        help="default = workspace_root.parent.parent")

    update = sub.add_parser(
        "update-project-md",
        help="Insere/atualiza bloco do workspace no CLAUDE.md root",
    )
    update.add_argument("--project-root", type=Path, required=True)
    update.add_argument("--workspace", required=True, help="NNN-slug")
    update.add_argument("--profile", required=True)
    update.add_argument("--tier", required=True)
    update.add_argument("--stage-atual", required=True)
    update.add_argument("--stage-dir", required=True, help="ex 03_wave_planner")
    update.add_argument("--sub-stage", required=True)
    update.add_argument("--iteration", type=int, default=0)
    update.add_argument("--status", required=True)
    update.add_argument("--last-action", default="")
    update.add_argument("--last-action-at", default="")
    update.add_argument("--next-action", default="")
    update.add_argument("--skill-dir", required=True)

    remove = sub.add_parser(
        "remove-block",
        help="Remove bloco do workspace do CLAUDE.md root (Saída A ou C)",
    )
    remove.add_argument("--project-root", type=Path, required=True)
    remove.add_argument("--workspace", required=True)
    remove.add_argument("--skill-dir", required=True)
    remove.add_argument("--closed-at", default="", help="ISO 8601 UTC")
    remove.add_argument(
        "--outcome", choices=("A", "C"), default="A",
        help="A=close (default), C=spawn novo workspace",
    )
    remove.add_argument(
        "--spawn-to", default=None,
        help="slug do workspace novo (requerido se outcome=C)",
    )
    remove.add_argument(
        "--exit-2-if-last-active", action="store_true",
        help=(
            "Retorna exit code 2 se workspace removido era o último ativo "
            "(deactivate disparou). Útil pra stage 08 detectar quando "
            "auto-invocar /init na sessão. Default: sempre exit 0."
        ),
    )

    deactivate = sub.add_parser(
        "deactivate-project-md",
        help="Substitui região ICM por mensagem 'nenhum workspace ativo'",
    )
    deactivate.add_argument("--project-root", type=Path, required=True)
    deactivate.add_argument("--closed-at", default="")
    deactivate.add_argument(
        "--outcome", choices=("A", "C"), default="A",
    )
    deactivate.add_argument("--spawn-to", default=None)

    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.cmd == "render":
        ws_root: Path = args.workspace_root.resolve()
        workspace_id = ws_root.name
        project_root = (
            args.project_root.resolve()
            if args.project_root
            else ws_root.parent.parent
        )
        data = HandoffData(
            workspace=workspace_id,
            project_root=str(project_root),
            prev_stage=args.prev_stage,
            prev_stage_name=args.prev_stage_name,
            stage_target=args.stage_target,
            stage_target_name=args.stage_target_name,
            stage_target_dir=stage_target_dir(
                args.stage_target, args.stage_target_name
            ),
            generated_at=utc_now_iso(),
            generator_commit_sha=args.commit_sha,
            prev_outputs=_parse_prev_outputs_arg(args.prev_outputs),
            prev_decisions_summary=args.decisions_summary,
            pending_for_this_stage=_parse_pending_arg(args.pending),
            prev_state_prose=args.prev_state_prose,
            next_tasks_prose=args.next_tasks_prose,
        )
        out = write_kickoff(ws_root, data)
        print(out)
        return 0

    if args.cmd == "update-project-md":
        block = WorkspaceBlock(
            workspace=args.workspace,
            profile=args.profile,
            tier=args.tier,
            stage_atual=args.stage_atual,
            stage_dir=args.stage_dir,
            sub_stage=args.sub_stage,
            iteration=int(args.iteration),
            status=args.status,
            last_action=args.last_action,
            last_action_at=args.last_action_at or utc_now_iso(),
            next_action=args.next_action,
        )
        out = update_project_claude_md(args.project_root.resolve(), block, args.skill_dir)
        print(out)
        return 0

    if args.cmd == "remove-block":
        project_root = args.project_root.resolve()
        claude_md_path = project_root / "CLAUDE.md"
        pre_blocks = _parse_workspace_blocks(claude_md_path) if claude_md_path.exists() else {}
        target_existed = args.workspace in pre_blocks
        out = remove_workspace_block(
            project_root,
            args.workspace,
            args.skill_dir,
            closed_at=args.closed_at,
            outcome=args.outcome,
            spawn_to=args.spawn_to,
        )
        print(out)
        if args.exit_2_if_last_active:
            post_blocks = _parse_workspace_blocks(claude_md_path) if claude_md_path.exists() else {}
            was_last_active = target_existed and len(post_blocks) == 0
            return 2 if was_last_active else 0
        return 0

    if args.cmd == "deactivate-project-md":
        out = deactivate_project_claude_md(
            args.project_root.resolve(),
            closed_at=args.closed_at,
            outcome=args.outcome,
            spawn_to=args.spawn_to,
        )
        print(out)
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
