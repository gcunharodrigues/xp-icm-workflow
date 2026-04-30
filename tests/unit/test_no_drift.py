"""Drift detection — bloqueia inconsistências cross-file.

6 detectores:
A. Versão consistente (canonical = scripts/bootstrap.py SKILL_VERSION)
B. Profile count consistente (canonical = len(CANONICAL_PROFILES))
C. Status enum sync (validate_state.py ALLOWED_STATUSES vs schema doc)
D. Status canônicos esperados presentes (allow-list anti-typo)
E. Cross-refs markdown resolvem em references/
F. Shell templates sem CRLF (CRLF no shebang quebra exec — kernel
   procura interpretador 'bash\\r' e falha com "No such file or directory")

Whitelist exceptions explícitas — nunca grep-and-update silencioso.
"""
import importlib.util
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ============================================================
# A. Version consistency
# ============================================================

VERSION_RE = re.compile(r"v(\d+\.\d+\.\d+)")

# Whitelist: arquivos que LEGITIMAMENTE mencionam versões antigas
# (changelog histórico, scripts de migração com target específico,
# kickoffs arquivados). Caminho relativo a REPO_ROOT (posix-style).
VERSION_WHITELIST = {
    "references/changelog.md",
    "scripts/migrate-v3.3-to-v3.4.py",
    "_KICKOFF-v3.4.0-finish.md",
    "tests/unit/test_migrate_v3_3_to_v3_4.py",
    "tests/unit/test_bootstrap.py",
    "tests/unit/test_stop_points_render.py",
    "docs/plans",
    "references/v2.4-snapshot",
    "references/example-run.md",  # menciona v3.0.0-beta5 + v2.4 (histórico)
}

# Arquivos que DEVEM mencionar a versão canônica
VERSION_MUST_MATCH = [
    ("SKILL.md", r"# xp-icm-workflow v(\d+\.\d+\.\d+)"),
    ("references/design-system.md", r"format \(v(\d+\.\d+\.\d+)\)"),
    (
        "references/preview-loop-protocol.md",
        r"build-iterate visual \(v(\d+\.\d+\.\d+)\)",
    ),
]


def _canonical_version() -> str:
    bootstrap = _load_module("bootstrap", REPO_ROOT / "scripts" / "bootstrap.py")
    return bootstrap.SKILL_VERSION


def test_version_consistency_canonical_files():
    """Arquivos canônicos devem refletir SKILL_VERSION."""
    canonical = _canonical_version()
    for rel_path, pattern in VERSION_MUST_MATCH:
        path = REPO_ROOT / rel_path
        text = path.read_text(encoding="utf-8")
        match = re.search(pattern, text)
        assert match is not None, f"{rel_path}: pattern '{pattern}' não encontrado"
        assert match.group(1) == canonical, \
            f"{rel_path}: versão {match.group(1)} ≠ canonical {canonical}"


# ============================================================
# B. Profile count consistency
# ============================================================

# Regex captura claims canônicos sobre profile count total. Ignora menções
# context-specific tipo "os 3 profiles X/Y/Z" (subset).
# Match patterns: "N profiles × 4 tiers", "N profiles canônicos", "N profiles
# canonicos x 4 tiers", "N profiles (e.g.,", "Demais N profiles"
PROFILE_COUNT_RE = re.compile(
    r"(\d+)\s+profiles\b\s*(?:×|x\s+\d|canôn|canon|\(e\.g|\(incl)",
    re.IGNORECASE,
)
# Pattern adicional: "Demais N profiles" (= total - listed)
PROFILE_REMAINDER_RE = re.compile(r"Demais\s+(\d+)\s+profiles\b")
PROFILE_COUNT_WHITELIST = {
    "references/changelog.md",
    "docs/plans",
    "references/v2.4-snapshot",
}


def _canonical_profile_count() -> int:
    pm = _load_module("profile_merge", REPO_ROOT / "scripts" / "profile-merge.py")
    return len(pm.CANONICAL_PROFILES)


def _is_whitelisted(rel_path: str, whitelist: set) -> bool:
    return any(
        rel_path == w or rel_path.startswith(w + "/")
        for w in whitelist
    )


def _check_profile_count_in_file(path: Path, canonical: int) -> list:
    """Retorna lista de violações no arquivo."""
    rel = path.relative_to(REPO_ROOT).as_posix()
    if _is_whitelisted(rel, PROFILE_COUNT_WHITELIST):
        return []
    text = path.read_text(encoding="utf-8")
    violations = []
    for match in PROFILE_COUNT_RE.finditer(text):
        n = int(match.group(1))
        if n != canonical:
            violations.append(f"{rel}: '{match.group(0)}' (canonical {canonical})")
    # "Demais N profiles" — remainder, espera-se total - explicit listed na mesma table
    # Heurística simples: se aparecer, deve ser pelo menos 1 a menos que canonical
    for match in PROFILE_REMAINDER_RE.finditer(text):
        n = int(match.group(1))
        if n >= canonical:
            violations.append(
                f"{rel}: '{match.group(0)}' >= canonical {canonical} (impossível)"
            )
    return violations


def test_profile_count_consistency():
    """Toda menção canônica a 'N profiles' deve bater com len(CANONICAL_PROFILES)."""
    canonical = _canonical_profile_count()
    violations = []
    for path in REPO_ROOT.rglob("*.md"):
        violations.extend(_check_profile_count_in_file(path, canonical))
    for path in REPO_ROOT.rglob("*.py"):
        violations.extend(_check_profile_count_in_file(path, canonical))
    assert not violations, "Profile count drift:\n  " + "\n  ".join(violations)


# ============================================================
# C. Status enum sync
# ============================================================

EXPECTED_STATUSES = {
    "IN_PROGRESS",
    "COMPLETED",
    "COMPLETED_AWAITING_HUMAN",
    "BLOCKED_STOP_POINT",
    "BLOCKED_ERROR",
    "BLOCKED_HITL",
}


def _validator_statuses() -> set:
    """Importa ALLOWED_STATUSES do validate_state.py (single source)."""
    vs = _load_module("validate_state", REPO_ROOT / "scripts" / "validate_state.py")
    return set(vs.ALLOWED_STATUSES)


def _schema_statuses() -> set:
    """Extrai status canônicos de state-machine-schema.md table rows."""
    text = (REPO_ROOT / "references" / "state-machine-schema.md").read_text(encoding="utf-8")
    # Pattern: linhas tipo `| \`STATUS_NAME\` | ...`
    return set(re.findall(r"^\|\s*`([A-Z_]+)`\s*\|", text, flags=re.MULTILINE))


def test_validator_has_expected_statuses():
    """validate_state.py ALLOWED_STATUSES cobre todos statuses canônicos."""
    validator = _validator_statuses()
    missing = EXPECTED_STATUSES - validator
    assert not missing, f"validate_state.py falta: {missing}"


def test_schema_doc_has_expected_statuses():
    """state-machine-schema.md table cobre todos statuses canônicos."""
    schema = _schema_statuses()
    missing = EXPECTED_STATUSES - schema
    assert not missing, f"state-machine-schema.md falta rows: {missing}"


def test_validator_schema_in_sync():
    """Validator ↔ schema: todo status no validator está no schema."""
    validator = _validator_statuses()
    schema = _schema_statuses()
    only_validator = validator - schema
    assert not only_validator, \
        f"validator tem statuses ausentes no schema: {only_validator}"


# ============================================================
# D. Markdown cross-ref resolves em references/
# ============================================================

MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


# ============================================================
# F. Shell templates sem CRLF
# ============================================================

# Templates whitelist (CRLF aceitável) — vazio por padrão. Adicionar entry
# APENAS se o arquivo NÃO é executado via shebang (ex: doc/example).
SHELL_CRLF_WHITELIST: set[str] = set()


def test_shell_templates_no_crlf():
    """Templates .sh em templates/ não devem ter CRLF.

    Bug: shutil.copy2 preserva bytes; CRLF do template cai no destino.
    Kernel exec do shebang procura literal 'bash\\r' → "No such file
    or directory". bootstrap.py normaliza na cópia, mas template-source
    com CRLF arrisca regressão se alguma cópia futura voltar a copy2.
    """
    templates_root = REPO_ROOT / "templates"
    if not templates_root.exists():
        pytest.skip("templates/ não existe")
    violations = []
    for sh in templates_root.rglob("*.sh"):
        rel = sh.relative_to(REPO_ROOT).as_posix()
        if rel in SHELL_CRLF_WHITELIST:
            continue
        raw = sh.read_bytes()
        if b"\r\n" in raw:
            violations.append(rel)
    assert not violations, (
        "Templates .sh com CRLF (use LF; rode `python -c \"import "
        "pathlib; [p.write_bytes(p.read_bytes().replace(b'\\r\\n',b'\\n')) "
        "for p in pathlib.Path('templates').rglob('*.sh')]\"`):\n  "
        + "\n  ".join(violations)
    )


def test_git_hook_templates_no_crlf():
    """Templates .git-hooks/ — git executa via shebang exec mesma classe."""
    hooks_root = REPO_ROOT / "templates" / ".git-hooks"
    if not hooks_root.exists():
        pytest.skip("templates/.git-hooks/ não existe")
    violations = []
    for hook in hooks_root.iterdir():
        if not hook.is_file():
            continue
        raw = hook.read_bytes()
        if b"\r\n" in raw:
            violations.append(hook.relative_to(REPO_ROOT).as_posix())
    assert not violations, (
        "Git hook templates com CRLF:\n  " + "\n  ".join(violations)
    )


def test_markdown_cross_refs_resolve_in_references():
    """Links markdown relativos em references/ devem resolver."""
    violations = []
    root = REPO_ROOT / "references"
    if not root.exists():
        pytest.skip("references/ não existe")
    for md in root.rglob("*.md"):
        text = md.read_text(encoding="utf-8")
        for label, target in MD_LINK_RE.findall(text):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            if "{{" in target:
                continue
            path_part = target.split("#", 1)[0]
            if not path_part:
                continue
            # Resolução relativa ao MD; fallback REPO_ROOT
            resolved = (md.parent / path_part).resolve()
            if not resolved.exists():
                alt = (REPO_ROOT / path_part.lstrip("/")).resolve()
                if alt.exists():
                    resolved = alt
            if not resolved.exists():
                violations.append(
                    f"{md.relative_to(REPO_ROOT).as_posix()}: broken link → {target}"
                )
    assert not violations, \
        "Broken cross-refs em references/:\n  " + "\n  ".join(violations)
