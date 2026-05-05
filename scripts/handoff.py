"""Python backend for the session handoff protocol (1 stage = 1 session).

Renders `_kickoff.md` in the next stage directory using the template at
`templates/workspace/stages/_kickoff.md.tpl`. Deterministic helpers are
tested in `tests/unit/test_handoff.py`. Canonical doc at
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
# Constants
# ============================================================================

PLACEHOLDER_RE = re.compile(r"\{\{([A-Z_][A-Z0-9_]*)\}\}")

# Fixed mapping: stage_id -> directory name (canonical id + name)
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

# Canonical indent for the YAML literal block `prev_decisions_summary: |`
DECISIONS_INDENT = "  "


# ============================================================================
# Types
# ============================================================================

class HandoffError(Exception):
    """Handoff protocol error (template, render, parse, IO)."""


@dataclass(frozen=True)
class PrevOutput:
    """Output declared by the previous session, listed in prev_outputs."""
    path: str       # path relative to workspace, e.g. "stages/02_design/output/plan.md"
    summary: str    # 1-2 lines


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
# Deterministic helpers
# ============================================================================

def stage_target_dir(stage_id: str, stage_name: str) -> str:
    """Resolve canonical directory name (`<id>_<name>`).

    Validates that `stage_id` exists in the mapping and that `stage_name` matches canonical.
    """
    if stage_id not in STAGE_DIR_BY_ID:
        raise HandoffError(
            f"unknown stage_id: {stage_id!r} (valid: "
            f"{sorted(STAGE_DIR_BY_ID)})"
        )
    canonical = STAGE_DIR_BY_ID[stage_id]
    expected_name = canonical[3:]  # strip "NN_"
    if stage_name != expected_name:
        raise HandoffError(
            f"stage_name {stage_name!r} does not match canonical {expected_name!r} "
            f"for stage_id {stage_id}"
        )
    return canonical


def utc_now_iso() -> str:
    """UTC ISO 8601 timestamp with Z suffix."""
    return _dt.datetime.now(_dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _yaml_inline_list(items: Sequence[str]) -> str:
    """Inline YAML list. Empty -> `[]`. Strings in double quotes."""
    if not items:
        return "[]"
    quoted = ", ".join(f'"{_yaml_escape(s)}"' for s in items)
    return f"[{quoted}]"


def _yaml_escape(s: str) -> str:
    """Minimal escape for a double-quoted YAML string."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _prev_outputs_yaml(outputs: Sequence[PrevOutput]) -> str:
    """Serialize prev_outputs as a YAML block.

    Empty -> inline `[]`. Otherwise, list of objects on subsequent lines
    with zero indent because the key was already written in the template.
    """
    if not outputs:
        return "[]"
    lines: list[str] = [""]  # break immediately after `prev_outputs:`
    for item in outputs:
        lines.append(f'  - path: "{_yaml_escape(item.path)}"')
        lines.append(f'    summary: "{_yaml_escape(item.summary)}"')
    return "\n".join(lines)


def _indent_multiline(text: str, indent: str) -> str:
    """Apply indent to each line (for YAML literal block)."""
    if not text:
        return ""
    lines = text.split("\n")
    return ("\n" + indent).join(lines)


def _build_placeholders(data: HandoffData) -> dict[str, str]:
    """Map HandoffData -> placeholder dict for the template."""
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
# Public API
# ============================================================================

def render_kickoff(template_path: Path, data: HandoffData) -> str:
    """Substitute `{{KEY}}` placeholders with values derived from `data`.

    Raises `HandoffError` if template is absent or any placeholder is
    left unresolved.
    """
    if not template_path.exists():
        raise HandoffError(f"template absent: {template_path}")

    placeholders = _build_placeholders(data)
    content = template_path.read_text(encoding="utf-8")

    def _sub(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in placeholders:
            raise HandoffError(
                f"unresolved placeholder: {{{{{key}}}}} in {template_path.name}"
            )
        return placeholders[key]

    rendered = PLACEHOLDER_RE.sub(_sub, content)
    leftover = PLACEHOLDER_RE.search(rendered)
    if leftover:
        raise HandoffError(
            f"unresolved placeholder: {leftover.group(0)} in {template_path.name}"
        )
    return rendered


def write_kickoff(
    workspace_root: Path,
    data: HandoffData,
    *,
    template_path: Path | None = None,
) -> Path:
    """Write `<workspace_root>/stages/<stage_target_dir>/_kickoff.md`.

    Creates the directory if absent. Idempotent (overwrites with same content).
    Returns the absolute path written.
    """
    tpl = template_path or _default_template_path()
    rendered = render_kickoff(tpl, data)
    target_dir = workspace_root / "stages" / data.stage_target_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    out_path = (target_dir / "_kickoff.md").resolve()
    out_path.write_text(rendered, encoding="utf-8")
    return out_path


def extract_kickoff_metadata(kickoff_path: Path) -> dict:
    """Parse YAML frontmatter from `_kickoff.md`. Returns dict.

    Raises `HandoffError` if file absent, frontmatter absent, or YAML invalid.
    """
    if not kickoff_path.exists():
        raise HandoffError(f"kickoff absent: {kickoff_path}")
    text = kickoff_path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise HandoffError(f"frontmatter absent in {kickoff_path}")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise HandoffError(f"frontmatter malformed (no end marker) in {kickoff_path}")
    fm_text = text[4:end]
    try:
        meta = yaml.safe_load(fm_text)
    except yaml.YAMLError as exc:
        raise HandoffError(f"invalid YAML in {kickoff_path}: {exc}") from exc
    if not isinstance(meta, dict):
        raise HandoffError(f"frontmatter is not a dict in {kickoff_path}")
    return meta


def validate_kickoff_present(workspace_root: Path, stage_atual: str) -> bool:
    """New-session pre-flight: checks whether `_kickoff.md` exists.

    Returns True if present, False if absent. Unknown stage_id -> raises.
    """
    if stage_atual not in STAGE_DIR_BY_ID:
        raise HandoffError(
            f"unknown stage_atual: {stage_atual!r}"
        )
    kickoff = (
        workspace_root
        / "stages"
        / STAGE_DIR_BY_ID[stage_atual]
        / "_kickoff.md"
    )
    return kickoff.is_file()


# ============================================================================
# Internal helpers
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
# CLAUDE.md at project_root: dynamic block for the active workspace
# ============================================================================

ICM_START_MARKER = "<!-- ICM-START -->"
ICM_END_MARKER = "<!-- ICM-END -->"


@dataclass(frozen=True)
class WorkspaceBlock:
    """Rendered state of a workspace in the ICM region of the root CLAUDE.md.

    Serialized as JSON in a `<!-- ICM-DATA:... -->` comment for deterministic
    round-trip (parse + re-render preserve all fields).
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
    """Write tmp + fsync + rename — crash mid-write does not corrupt the file (G15).

    `.tmp` suffix in the same directory guarantees atomic rename even across filesystems.
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
        # fsync may fail on non-POSIX filesystems (Windows network drives,
        # some kernels' tmpfs). Rename is still atomic in those cases.
        pass
    tmp.replace(path)


def _render_workspace_block_md(b: WorkspaceBlock) -> str:
    """Markdown for the workspace block (without HTML markers)."""
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
    """Markdown block wrapped with HTML markers + serialized JSON.

    Structure:
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
        "> This section is maintained automatically by the `xp-icm-workflow` skill.\n"
        "> Do not edit manually — updated at every stage handoff.\n"
        "> **Do not run `/init` while a workspace is active.**\n"
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
    """'No active workspace' message (Exit A close or Exit C spawn).

    v3.7.0: branches by outcome.
    - A (default): workspace closed cleanly. Next step `/init`.
    - C: workspace transitioned to spawn_to. Next step bootstrap in
      a new session (human pastes `/xp-icm-workflow spawn_from=<old>`).
    """
    if outcome not in ("A", "C"):
        raise ValueError(
            f"invalid outcome: {outcome!r} (expected 'A' or 'C')"
        )
    if outcome == "C" and not spawn_to:
        raise ValueError("outcome='C' requires non-empty spawn_to")
    closed = closed_at if closed_at else "unknown"
    if outcome == "A":
        return (
            "## ICM — No active workspace\n"
            "\n"
            f"> Last workspace was closed at `{closed}` (Exit A — close).\n"
            "> History in `workspaces/`.\n"
            ">\n"
            "> **Next step:** run `/init` to regenerate the region below with\n"
            "> information about the built codebase. This ICM region will remain\n"
            "> empty until a new workspace is bootstrapped.\n"
        )
    # outcome == "C"
    return (
        "## ICM — No active workspace\n"
        "\n"
        f"> Last workspace transitioned at `{closed}` "
        f"(Exit C — spawn `{spawn_to}`).\n"
        "> Bootstrap in a new session: `/xp-icm-workflow` detects "
        "`.icm/spawn-pending.json` automatically,\n"
        f"> or pass the explicit arg `--spawn-from=<NNN>` for `{spawn_to}`.\n"
        "> History in `workspaces/`.\n"
    )


def _render_full_icm_region(blocks: Sequence[WorkspaceBlock], skill_dir: str) -> str:
    """Full ICM region content (without outer START/END markers).

    Empty -> idle message (default Exit A). For outcome-aware idle (Exit C),
    use `_write_icm_region` with `outcome` + `spawn_to` kwargs.
    1+ workspaces -> header + blocks + footer.
    """
    if not blocks:
        return _render_icm_idle("")
    sorted_blocks = sorted(blocks, key=lambda b: b.workspace)
    body = "\n".join(_wrap_block_with_markers(b) for b in sorted_blocks)
    return _render_icm_header() + body + _render_icm_footer(skill_dir)


def _wrap_outer(region_inner: str) -> str:
    """Wrap region in <!-- ICM-START --> ... <!-- ICM-END -->."""
    return f"{ICM_START_MARKER}\n{region_inner}{ICM_END_MARKER}\n"


def _greenfield_template(project_name: str, region_outer: str) -> str:
    """Full root CLAUDE.md for a project with no pre-existing CLAUDE.md.

    Uses templates/project_root/CLAUDE.md.tpl as the canonical template.
    """
    import os as _os
    skill_root = Path(_os.environ.get("SKILL_DIR", Path(__file__).resolve().parent.parent))
    tpl_path = skill_root / "templates" / "project_root" / "CLAUDE.md.tpl"
    if tpl_path.is_file():
        template = tpl_path.read_text(encoding="utf-8")
        return template.replace("{{PROJECT_NAME}}", project_name).replace(
            "{{ICM_REGION}}", region_outer
        )
    # Fallback (template missing — should not happen in production)
    return (
        f"# CLAUDE.md — {project_name}\n"
        "\n"
        "This file provides guidance to Claude Code (claude.ai/code) when working in this repository.\n"
        "\n"
        f"{region_outer}\n"
        "<!-- The region below is free. It can be filled in by Claude Code's `/init` -->\n"
        "<!-- or manually by the user with codebase context (commands, architecture,   -->\n"
        "<!-- conventions, etc). The `xp-icm-workflow` skill NEVER touches this region. -->\n"
    )


def _insert_region_after_first_h1(content: str, region_outer: str) -> str:
    """Brownfield without markers: insert region after the first H1 heading.

    If no H1 is found, prepend to the top. All other content is preserved.
    """
    lines = content.split("\n")
    insert_idx: int | None = None
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        if stripped.startswith("# ") and not stripped.startswith("## "):
            # H1 found
            insert_idx = i + 1
            # Skip blank lines and description immediately after the heading
            while insert_idx < len(lines) and lines[insert_idx].strip() == "":
                insert_idx += 1
            break
    if insert_idx is None:
        # No H1: prepend
        return region_outer + "\n" + content
    before = "\n".join(lines[:insert_idx])
    after = "\n".join(lines[insert_idx:])
    sep_b = "" if before.endswith("\n") else "\n"
    sep_a = "" if after.startswith("\n") else "\n"
    return before + sep_b + "\n" + region_outer + sep_a + after


def _parse_workspace_blocks(claude_md_path: Path) -> dict[str, WorkspaceBlock]:
    """Extract dict[workspace_id -> WorkspaceBlock] from the root CLAUDE.md.

    Parsed via JSON in `<!-- ICM-DATA:... -->` comments. Safe round-trip.
    File absent or no markers -> empty dict.
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
            # Corrupted block -> skip; recovery wizard detects later
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
    """Write full ICM region, preserving content outside the markers.

    - Greenfield (file absent) -> create via _greenfield_template.
    - Brownfield with markers -> replace only content between markers.
    - Brownfield without markers -> insert after first H1.

    If `blocks` is empty: uses `_render_icm_idle` with caller's outcome+spawn_to.
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
        # Skip newline immediately after ICM_END_MARKER (if present) to
        # avoid accumulating blank lines on each update.
        if end_after < len(current) and current[end_after] == "\n":
            end_after += 1
        new_content = current[:start] + region_outer + current[end_after:]
    _atomic_write(claude_md, new_content)


def update_project_claude_md(
    project_root: Path,
    workspace_block: WorkspaceBlock,
    skill_dir: str,
) -> Path:
    """Insert or update the workspace block in the project_root CLAUDE.md.

    Idempotent. Brownfield-safe. Preserves blocks from other workspaces.
    Returns the absolute path of the file written.
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
    """Rewrite the workspace row in `workspaces/.index.md` changing status.

    `.index.md` canonical format:
      | NNN | slug | profile/tier | created_at | status |

    `workspace` = "NNN-slug". Locates the row whose NNN+slug matches and
    replaces the last field (status). If index absent or row not found: no-op.

    Returns True if updated, False if no-op (idempotent).

    v3.7.1: fixes stale `.index.md` bug after Exit A/C — before the fix,
    `update_index` (bootstrap.py) only appended `active`; Exit A/C
    never rewrote status to `COMPLETED`. SessionStart hook read the stale
    index and detected a closed workspace as active.
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
    """Remove the closed workspace's entries from `.claude/settings.local.json`.

    Bootstrap (`_merge_project_settings_local`) registers hooks per workspace
    with command path `$CLAUDE_PROJECT_DIR/workspaces/<workspace>/.claude/hooks/...`.
    Exit A/C must remove these entries to prevent accumulation (settings with
    duplicate hooks after multiple closed workspaces).

    Detects entries via substring `workspaces/<workspace>/.claude/hooks/` in
    the command. If an event becomes empty (zero entries) after removal, removes
    the event. If the entire settings loses `hooks`, leaves the empty structure.

    Idempotent: missing entries = no-op. Invalid settings = no-op.

    Returns True if modified, False if no-op.
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
                f"warning: failed to write {settings_path}: {exc}\n"
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
    """Remove the workspace block from the root CLAUDE.md.

    If workspace did not exist: no-op (return path without writing).
    If it was the last: replace region with idle message (deactivate).

    v3.7.0:
    - `outcome` ∈ {"A", "C"}. A = close, C = spawn new workspace.
    - `spawn_to` required if outcome="C" (idle message cites the slug).

    v3.7.1:
    - Updates `workspaces/.index.md` marking workspace as COMPLETED.
    - Removes workspace entries from `.claude/settings.local.json` (hooks).

    Exit B uses `update_project_claude_md` (phase 08 transitions to another stage,
    does not close the workspace).
    """
    if outcome not in ("A", "C"):
        raise ValueError(
            f"invalid outcome: {outcome!r} (expected 'A' or 'C'). "
            "Exit B does not remove the block — use update_project_claude_md."
        )
    if outcome == "C" and not spawn_to:
        raise ValueError("outcome='C' requires non-empty spawn_to")
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

    # v3.7.1: cleanup after Exit A/C
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
    """Replace the ICM region with a 'no active workspace' message.

    Used after Exit A (close) or Exit C (spawn) when no workspaces remain
    active. Content outside the markers is preserved intact.

    v3.4.1: also migrates root CLAUDE.md to the base branch via worktree
    `.icm-main/`. Without this, the idle CLAUDE.md disappears when the
    workspace branch is deleted (entire ICM dashboard lost). Doc:
    references/project-root-claude-md.md.

    v3.7.0:
    - `outcome` ∈ {"A", "C"}. Renders type-specific message.
    - `spawn_to` required if outcome="C".
    """
    if outcome not in ("A", "C"):
        raise ValueError(
            f"invalid outcome: {outcome!r} (expected 'A' or 'C')"
        )
    if outcome == "C" and not spawn_to:
        raise ValueError("outcome='C' requires non-empty spawn_to")
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

    # v3.4.1: persist the same idle version in .icm-main/CLAUDE.md (base branch)
    # to survive deletion of the workspace branch.
    _persist_claude_md_to_base_via_worktree(project_root, claude_md)

    return claude_md


def _persist_claude_md_to_base_via_worktree(
    project_root: Path,
    claude_md_src: Path,
) -> None:
    """Copy CLAUDE.md from project_root to `.icm-main/CLAUDE.md` + commit on base.

    Idempotent: if content is identical, git status detects no changes and skips the commit.
    Silently no-op if `.icm-main/` is absent (pre-v3.4.0 project or worktree
    removed manually).

    Doc: references/worktree-model.md (v3.4.0) +
    references/project-root-claude-md.md (owner transition Exit A).
    """
    import subprocess  # noqa: PLC0415

    worktree = project_root / ".icm-main"
    if not worktree.is_dir():
        return  # worktree absent — project is probably pre-v3.4.0

    if not claude_md_src.is_file():
        return

    dst = worktree / "CLAUDE.md"
    src_text = claude_md_src.read_text(encoding="utf-8")
    if dst.exists() and dst.read_text(encoding="utf-8") == src_text:
        return  # idempotent

    dst.write_text(src_text, encoding="utf-8")

    # Commit on base branch via linked worktree
    try:
        subprocess.run(
            ["git", "-C", str(worktree), "add", "CLAUDE.md"],
            check=False, capture_output=True, text=True,
        )
        subprocess.run(
            ["git", "-C", str(worktree), "commit", "--no-verify", "-m",
             "docs(claude.md): persist idle/active state to base (exit A handoff)"],
            check=False, capture_output=True, text=True,
        )
    except Exception:
        # git failure must not break handoff — human can commit manually
        pass


def list_active_workspace_ids(project_root: Path) -> list[str]:
    """List workspace IDs present in the ICM region of the root CLAUDE.md.

    Used by bootstrap to detect pre-existing workspaces in multi-workspace mode
    and by recovery wizard to check consistency with .index.md.
    """
    return sorted(_parse_workspace_blocks(project_root / "CLAUDE.md").keys())


# ============================================================================
# CLI
# ============================================================================

def _parse_prev_outputs_arg(raw: str | None) -> tuple[PrevOutput, ...]:
    """Parse `path1:summary1,path2:summary2` -> tuple[PrevOutput].

    Splits on commas that precede path entries (stages/NN_name/...),
    so commas inside summaries do not break the parse.
    """
    if not raw:
        return ()
    items: list[PrevOutput] = []
    # Split only on commas that precede path-like entries
    for chunk in re.split(r',(?=\s*stages/\d+)', raw):
        chunk = chunk.strip()
        if ":" not in chunk:
            raise HandoffError(
                f"prev-outputs entry missing ':' — expected 'path:summary', got {chunk!r}"
            )
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

    render = sub.add_parser("render", help="Render and write _kickoff.md")
    render.add_argument("--workspace-root", type=Path, required=True)
    render.add_argument("--prev-stage", required=True)
    render.add_argument("--prev-stage-name", required=True)
    render.add_argument("--stage-target", required=True)
    render.add_argument("--stage-target-name", required=True)
    render.add_argument("--commit-sha", required=True)
    render.add_argument("--prev-outputs", default=None,
                        help="path1:summary1,path2:summary2 (commas in summaries OK)")
    render.add_argument("--pending", default=None, help="item1|item2|item3")
    render.add_argument("--decisions-summary", default="")
    render.add_argument("--prev-state-prose", default="")
    render.add_argument("--next-tasks-prose", default="")
    render.add_argument("--project-root", type=Path, default=None,
                        help="default = workspace_root.parent.parent")

    update = sub.add_parser(
        "update-project-md",
        help="Insert/update workspace block in root CLAUDE.md",
    )
    update.add_argument("--project-root", type=Path, required=True)
    update.add_argument("--workspace", required=True, help="NNN-slug")
    update.add_argument("--profile", required=True)
    update.add_argument("--tier", required=True)
    update.add_argument("--stage-atual", required=True)
    update.add_argument("--stage-dir", required=True, help="e.g. 03_wave_planner")
    update.add_argument("--sub-stage", required=True)
    update.add_argument("--iteration", type=int, default=0)
    update.add_argument("--status", required=True)
    update.add_argument("--last-action", default="")
    update.add_argument("--last-action-at", default="")
    update.add_argument("--next-action", default="")
    update.add_argument("--skill-dir", required=True)

    remove = sub.add_parser(
        "remove-block",
        help="Remove workspace block from root CLAUDE.md (Exit A or C)",
    )
    remove.add_argument("--project-root", type=Path, required=True)
    remove.add_argument("--workspace", required=True)
    remove.add_argument("--skill-dir", required=True)
    remove.add_argument("--closed-at", default="", help="ISO 8601 UTC")
    remove.add_argument(
        "--outcome", choices=("A", "C"), default="A",
        help="A=close (default), C=spawn new workspace",
    )
    remove.add_argument(
        "--spawn-to", default=None,
        help="slug of the new workspace (required if outcome=C)",
    )
    remove.add_argument(
        "--exit-2-if-last-active", action="store_true",
        help=(
            "Return exit code 2 if the removed workspace was the last active one "
            "(deactivate fired). Useful for stage 08 to detect when to "
            "auto-invoke /init in the session. Default: always exit 0."
        ),
    )

    deactivate = sub.add_parser(
        "deactivate-project-md",
        help="Replace ICM region with 'no active workspace' message",
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
