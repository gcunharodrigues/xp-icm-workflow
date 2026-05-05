"""Drift detection — blocks cross-file inconsistencies.

7 detectors:
A. Version consistency (canonical = scripts/bootstrap.py SKILL_VERSION)
B. Profile count consistency (canonical = len(CANONICAL_PROFILES))
C. Status enum sync (validate_state.py ALLOWED_STATUSES vs schema doc)
D. Expected canonical statuses present (allow-list anti-typo)
E. Markdown cross-refs resolve in references/
F. Shell templates without CRLF (CRLF in shebang breaks exec — kernel
   looks for interpreter 'bash\\r' and fails with "No such file or directory")
H. Scripts source-of-truth version sync — `CURRENT_SKILL_VERSION = "X.Y.Z"`
   + last entry of `SUPPORTED_VERSIONS = (...)` in scripts/*.py must
   match canonical (rule v3.7.2: catches drift in helper scripts like
   migrate-workspace.py that were not in VERSION_MUST_MATCH).

Explicit whitelist exceptions — never silent grep-and-update.
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

# Whitelist: files that LEGITIMATELY mention old versions
# (historical changelog, migration scripts with specific target,
# archived kickoffs). Path relative to REPO_ROOT (posix-style).
VERSION_WHITELIST = {
    "references/changelog.md",
    "scripts/migrate-v3.3-to-v3.4.py",
    "_KICKOFF-v3.4.0-finish.md",
    "tests/unit/test_migrate_v3_3_to_v3_4.py",
    "tests/unit/test_bootstrap.py",
    "tests/unit/test_stop_points_render.py",
    "docs/plans",
    "references/v2.4-snapshot",
    "references/example-run.md",  # mentions v3.0.0-beta5 + v2.4 (historical)
}

# Files that MUST mention the canonical version.
# Any change to SKILL_VERSION requires bumping ALL of these (rule v3.7.0).
VERSION_MUST_MATCH = [
    ("SKILL.md", r"# xp-icm-workflow v(\d+\.\d+\.\d+)"),
    ("README.md", r"version-v(\d+\.\d+\.\d+)"),
    ("references/design-system.md", r"format \(v(\d+\.\d+\.\d+)\)"),
    (
        "references/preview-loop-protocol.md",
        r"build-iterate visual \(v(\d+\.\d+\.\d+)\)",
    ),
    # v3.7.2: canonical orchestration scripts must also match
    (
        "scripts/migrate-workspace.py",
        r'CURRENT_SKILL_VERSION\s*=\s*"(\d+\.\d+\.\d+)"',
    ),
]


def _canonical_version() -> str:
    bootstrap = _load_module("bootstrap", REPO_ROOT / "scripts" / "bootstrap.py")
    return bootstrap.SKILL_VERSION


def test_version_consistency_canonical_files():
    """Canonical files must reflect SKILL_VERSION."""
    canonical = _canonical_version()
    for rel_path, pattern in VERSION_MUST_MATCH:
        path = REPO_ROOT / rel_path
        text = path.read_text(encoding="utf-8")
        match = re.search(pattern, text)
        assert match is not None, f"{rel_path}: pattern '{pattern}' not found"
        assert match.group(1) == canonical, \
            f"{rel_path}: version {match.group(1)} ≠ canonical {canonical}"


def test_changelog_has_entry_for_canonical_version():
    """Every new SKILL_VERSION requires an entry in references/changelog.md.

    Rule v3.7.0: bumping SKILL_VERSION without a changelog entry is drift.
    Pattern accepts "## vX.Y.Z" at the start of a line (section header).
    """
    canonical = _canonical_version()
    changelog = (REPO_ROOT / "references" / "changelog.md").read_text(encoding="utf-8")
    pattern = re.compile(rf"^## v{re.escape(canonical)}\b", re.MULTILINE)
    assert pattern.search(changelog), (
        f"references/changelog.md has no entry '## v{canonical}'. "
        f"Every SKILL_VERSION change requires a changelog entry "
        f"(drift rule v3.7.0)."
    )


# ============================================================
# B. Profile count consistency
# ============================================================

# Captures canonical claims about total profile count. Ignores context-specific
# mentions like "the 3 profiles X/Y/Z" (subset).
# Match patterns: "N profiles × 4 tiers", "N profiles canônicos", "N profiles
# canonicos x 4 tiers", "N profiles (e.g.,", "Demais N profiles"
PROFILE_COUNT_RE = re.compile(
    r"(\d+)\s+profiles\b\s*(?:×|x\s+\d|canôn|canon|\(e\.g|\(incl)",
    re.IGNORECASE,
)
# Additional pattern: "Demais N profiles" (= total - listed)
PROFILE_REMAINDER_RE = re.compile(r"Demais\s+(\d+)\s+profiles\b")

# Hardened (v3.7.0): catches formats missed by the original PROFILE_COUNT_RE.
# Covers:
#   - "Profiles canônicos (N):" / "Profiles canonicos (N)"
#   - "(N × 4 = M combos)" / "(N x 4 = M combos)"
PROFILE_COUNT_PARENS_RE = re.compile(
    r"Profiles\s+can(?:ô|o)nicos\s*\((\d+)\)",
    re.IGNORECASE,
)
PROFILE_COMBO_RE = re.compile(
    r"\((\d+)\s*[×x]\s*(\d+)\s*=\s*(\d+)\s*combos?\)",
    re.IGNORECASE,
)

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


CANONICAL_TIERS_COUNT = 4  # CANONICAL_TIERS em profile-merge.py


def _check_profile_count_in_file(path: Path, canonical: int) -> list:
    """Return list of violations in the file."""
    rel = path.relative_to(REPO_ROOT).as_posix()
    if _is_whitelisted(rel, PROFILE_COUNT_WHITELIST):
        return []
    text = path.read_text(encoding="utf-8")
    violations = []
    for match in PROFILE_COUNT_RE.finditer(text):
        n = int(match.group(1))
        if n != canonical:
            violations.append(f"{rel}: '{match.group(0)}' (canonical {canonical})")
    # "Demais N profiles" — remainder; expected to be total - explicit listed in same table.
    # Simple heuristic: if it appears, must be at least 1 less than canonical.
    for match in PROFILE_REMAINDER_RE.finditer(text):
        n = int(match.group(1))
        if n >= canonical:
            violations.append(
                f"{rel}: '{match.group(0)}' >= canonical {canonical} (impossible)"
            )
    # Hardened v3.7.0: "Profiles canônicos (N):" format
    for match in PROFILE_COUNT_PARENS_RE.finditer(text):
        n = int(match.group(1))
        if n != canonical:
            violations.append(
                f"{rel}: '{match.group(0)}' (canonical {canonical})"
            )
    # Hardened v3.7.0: "(N × T = M combos)" format
    for match in PROFILE_COMBO_RE.finditer(text):
        n_profiles = int(match.group(1))
        n_tiers = int(match.group(2))
        n_combos = int(match.group(3))
        if n_profiles != canonical:
            violations.append(
                f"{rel}: '{match.group(0)}' profile count {n_profiles} ≠ "
                f"canonical {canonical}"
            )
        if n_tiers != CANONICAL_TIERS_COUNT:
            violations.append(
                f"{rel}: '{match.group(0)}' tier count {n_tiers} ≠ "
                f"canonical {CANONICAL_TIERS_COUNT}"
            )
        if n_combos != canonical * CANONICAL_TIERS_COUNT:
            violations.append(
                f"{rel}: '{match.group(0)}' combos {n_combos} ≠ "
                f"{canonical}×{CANONICAL_TIERS_COUNT}={canonical * CANONICAL_TIERS_COUNT}"
            )
    return violations


def test_profile_count_consistency():
    """Every canonical mention of 'N profiles' must match len(CANONICAL_PROFILES)."""
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
    """Import ALLOWED_STATUSES from validate_state.py (single source)."""
    vs = _load_module("validate_state", REPO_ROOT / "scripts" / "validate_state.py")
    return set(vs.ALLOWED_STATUSES)


def _schema_statuses() -> set:
    """Extract canonical statuses from state-machine-schema.md table rows."""
    text = (REPO_ROOT / "references" / "state-machine-schema.md").read_text(encoding="utf-8")
    # Pattern: lines like `| \`STATUS_NAME\` | ...`
    return set(re.findall(r"^\|\s*`([A-Z_]+)`\s*\|", text, flags=re.MULTILINE))


def test_validator_has_expected_statuses():
    """validate_state.py ALLOWED_STATUSES must cover all canonical statuses."""
    validator = _validator_statuses()
    missing = EXPECTED_STATUSES - validator
    assert not missing, f"validate_state.py missing: {missing}"


def test_schema_doc_has_expected_statuses():
    """state-machine-schema.md table must cover all canonical statuses."""
    schema = _schema_statuses()
    missing = EXPECTED_STATUSES - schema
    assert not missing, f"state-machine-schema.md missing rows: {missing}"


def test_validator_schema_in_sync():
    """Validator ↔ schema: every status in the validator must be in the schema."""
    validator = _validator_statuses()
    schema = _schema_statuses()
    only_validator = validator - schema
    assert not only_validator, \
        f"validator has statuses absent from schema: {only_validator}"


# ============================================================
# D. Markdown cross-refs resolve in references/
# ============================================================

MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


# ============================================================
# F. Shell templates without CRLF
# ============================================================

# Templates whitelist (CRLF acceptable) — empty by default. Add entry ONLY
# if the file is NOT executed via shebang (e.g. doc/example).
SHELL_CRLF_WHITELIST: set[str] = set()


def test_shell_templates_no_crlf():
    """Templates .sh in templates/ must not have CRLF.

    Bug: shutil.copy2 preserves bytes; CRLF from template lands in destination.
    Kernel exec of shebang looks for literal 'bash\\r' → "No such file
    or directory". bootstrap.py normalizes on copy, but template-source
    with CRLF risks regression if any future copy reverts to copy2.
    """
    templates_root = REPO_ROOT / "templates"
    if not templates_root.exists():
        pytest.skip("templates/ does not exist")
    violations = []
    for sh in templates_root.rglob("*.sh"):
        rel = sh.relative_to(REPO_ROOT).as_posix()
        if rel in SHELL_CRLF_WHITELIST:
            continue
        raw = sh.read_bytes()
        if b"\r\n" in raw:
            violations.append(rel)
    assert not violations, (
        "Templates .sh with CRLF (use LF; run `python -c \"import "
        "pathlib; [p.write_bytes(p.read_bytes().replace(b'\\r\\n',b'\\n')) "
        "for p in pathlib.Path('templates').rglob('*.sh')]\"`):\n  "
        + "\n  ".join(violations)
    )


def test_git_hook_templates_no_crlf():
    """Templates .git-hooks/ — git executes via shebang exec same class."""
    hooks_root = REPO_ROOT / "templates" / ".git-hooks"
    if not hooks_root.exists():
        pytest.skip("templates/.git-hooks/ does not exist")
    violations = []
    for hook in hooks_root.iterdir():
        if not hook.is_file():
            continue
        raw = hook.read_bytes()
        if b"\r\n" in raw:
            violations.append(hook.relative_to(REPO_ROOT).as_posix())
    assert not violations, (
        "Git hook templates with CRLF:\n  " + "\n  ".join(violations)
    )


# ============================================================
# G. Plan.md schema sync — parser regex ↔ template doc
# ============================================================
#
# Historical bug: LLM (stage 02 designer) generates plan.md with headings in
# h4/h5 instead of h2/h3 of the canonical schema. Wave-planner in stage 03
# fails with "no tasks found" or returns an empty list silently.
# Frequent root cause: template schema changed without updating parser
# (or vice-versa). These tests freeze the contract.

def _wave_planner_module():
    """Import wave-planner-script.py with registration in sys.modules BEFORE
    exec_module — required by @dataclass on Task to resolve type annotations
    via lookup in sys.modules[cls.__module__].
    """
    import sys
    name = "wave_planner_script_drift"
    spec = importlib.util.spec_from_file_location(
        name, REPO_ROOT / "scripts" / "wave-planner-script.py",
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_4block_template_uses_canonical_heading_levels():
    """4-block-contract-template.md must declare schema with h2 (Task) and
    h3 (subsections). Changing this without adjusting the parser breaks generation.
    """
    template = (REPO_ROOT / "references" / "4-block-contract-template.md").read_text(
        encoding="utf-8"
    )
    assert "## Task <SLUG>:" in template, \
        "4-block-contract-template.md missing '## Task <SLUG>:' (schema h2)"
    for section in ("### WHAT", "### HOW", "### OUT OF SCOPE", "### VALIDATION"):
        assert section in template, \
            f"4-block-contract-template.md missing '{section}' (h3)"
    for section in ("### Files touched", "### Depends on"):
        assert section in template, \
            f"4-block-contract-template.md missing '{section}' (h3)"


def test_parser_regex_matches_template_canonical_example():
    """SLUG_RE must match the concrete example header in §6.1
    (`## Task auth-middleware: JWT validation middleware`). Drift between
    parser and canonical schema means LLM follows template but parser rejects it.
    """
    module = _wave_planner_module()
    template = (REPO_ROOT / "references" / "4-block-contract-template.md").read_text(
        encoding="utf-8"
    )
    matches = module.SLUG_RE.findall(template)
    assert "auth-middleware" in matches, (
        f"parser SLUG_RE does not match template example (got {matches}). "
        "Canonical schema in references/4-block-contract-template.md §6.1."
    )


def test_parser_drift_detector_rejects_h4_task():
    """`_detect_heading_drift` must abort on '#### Task ...' (h4).
    Ensures the guard in parse_plan stays active.
    """
    module = _wave_planner_module()
    bad = "#### Task foo: bar\n\n##### WHAT\n- x\n"
    with pytest.raises(module.WavePlannerError, match="heading drift"):
        module._detect_heading_drift(bad)


def test_parser_drift_detector_passes_canonical_h2():
    """Correct plan.md (h2 + h3) must not trigger drift detector."""
    module = _wave_planner_module()
    good = (
        "## Task foo: Foo\n\n"
        "### WHAT\n- x\n\n"
        "### Files touched\n- src/foo.ts\n\n"
        "### Depends on\n\n"
    )
    module._detect_heading_drift(good)  # must not raise


# ============================================================
# H. Scripts source-of-truth version sync (v3.7.2)
# ============================================================
#
# Detects helper scripts that maintain a local copy of SKILL_VERSION
# (e.g.: migrate-workspace.py CURRENT_SKILL_VERSION + SUPPORTED_VERSIONS
# tuple). VERSION_MUST_MATCH covers canonical files with a fixed pattern;
# this detector is generic — scans scripts/**/*.py for two patterns and
# validates == canonical.

SCRIPT_CURRENT_VERSION_RE = re.compile(
    r'CURRENT_SKILL_VERSION\s*=\s*"(\d+\.\d+\.\d+)"'
)
SCRIPT_SUPPORTED_LAST_RE = re.compile(
    r'SUPPORTED_VERSIONS[^=]*=\s*\((?P<body>[^)]*)\)',
    re.DOTALL,
)
SEMVER_RE = re.compile(r'"(\d+\.\d+\.\d+)"')


def _scripts_version_violations(canonical: str) -> list[str]:
    violations = []
    scripts_dir = REPO_ROOT / "scripts"
    if not scripts_dir.is_dir():
        return violations
    for py in scripts_dir.rglob("*.py"):
        rel = py.relative_to(REPO_ROOT).as_posix()
        # migrate-v3.3-to-v3.4.py is historical (fixed target) — whitelist
        if rel == "scripts/migrate-v3.3-to-v3.4.py":
            continue
        text = py.read_text(encoding="utf-8")
        m = SCRIPT_CURRENT_VERSION_RE.search(text)
        if m and m.group(1) != canonical:
            violations.append(
                f"{rel}: CURRENT_SKILL_VERSION={m.group(1)} ≠ {canonical}"
            )
        m2 = SCRIPT_SUPPORTED_LAST_RE.search(text)
        if m2:
            versions = SEMVER_RE.findall(m2.group("body"))
            if versions and versions[-1] != canonical:
                violations.append(
                    f"{rel}: SUPPORTED_VERSIONS last entry "
                    f"{versions[-1]} ≠ {canonical}"
                )
    return violations


def test_scripts_skill_version_sync():
    """Helper scripts (migrate-workspace.py etc) must reflect SKILL_VERSION.

    Rule v3.7.2: hunts drift in CURRENT_SKILL_VERSION and SUPPORTED_VERSIONS
    tuple across scripts/. Covers future scripts that copy the pattern without
    being in VERSION_MUST_MATCH.
    """
    canonical = _canonical_version()
    violations = _scripts_version_violations(canonical)
    assert not violations, (
        "Scripts version drift:\n  " + "\n  ".join(violations)
    )


def test_markdown_cross_refs_resolve_in_references():
    """Relative markdown links in references/ must resolve."""
    violations = []
    root = REPO_ROOT / "references"
    if not root.exists():
        pytest.skip("references/ does not exist")
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
            # Resolve relative to the MD file; fallback to REPO_ROOT
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
        "Broken cross-refs in references/:\n  " + "\n  ".join(violations)


def test_state_machine_schema_documents_v3_8_0_error_types():
    """Schema doc must list new forensic_* error_type values."""
    path = REPO_ROOT / "references" / "state-machine-schema.md"
    text = path.read_text(encoding="utf-8")
    assert "forensic_max_retries" in text
    assert "forensic_script_crash" in text


def test_wave_execution_protocol_has_forensic_substeps():
    """Pipeline canonical doc must reflect step 8 expansion."""
    path = REPO_ROOT / "references" / "wave-execution-protocol.md"
    text = path.read_text(encoding="utf-8")
    assert "**8a Forensic+**" in text
    assert "**8b Existing audit**" in text
    assert "**8c Forensic git log**" in text
    assert "**8d Decision**" in text
    assert "forensic-plus-protocol.md" in text


def test_l2_stage_04_mentions_max_forensic_retries():
    """L2 stage 04 template must reference the cap value (sourced from forensic-plus.py)."""
    l2_path = (
        REPO_ROOT
        / "templates"
        / "workspace"
        / "stages"
        / "04_implementation_waves"
        / "CONTEXT.md.tpl"
    )
    text = l2_path.read_text(encoding="utf-8")
    # The L2 template must mention the constant by name AND value to allow drift detection.
    assert "MAX_FORENSIC_RETRIES" in text
    assert "= 2" in text  # value embedded so reading the prompt is self-explanatory


def test_forensic_plus_doc_canonical_exists():
    """Sanity: the canonical doc must exist and contain expected H1 + sections.

    v3.9.0: section header renamed from "The 4 checks" to "The 7 checks" with
    Checks 5/6/7 added (acceptance↔test mapping, OUT OF SCOPE violations,
    ADR import drift). v3.10.0: "The 8 checks" — Check 8 user-journey coverage.
    """
    path = REPO_ROOT / "references" / "forensic-plus-protocol.md"
    assert path.is_file(), "forensic-plus-protocol.md missing"
    text = path.read_text(encoding="utf-8")
    assert "# Forensic+ Protocol" in text
    assert "## The 8 checks" in text
    assert "## JSON schema" in text


def test_forensic_plus_in_bootstrap_runtime_refs():
    """bootstrap.py runtime_refs tuple must list forensic-plus-protocol.md."""
    path = REPO_ROOT / "scripts" / "bootstrap.py"
    text = path.read_text(encoding="utf-8")
    assert '"forensic-plus-protocol.md"' in text


def test_l2_stage_04_references_forensic_plus_protocol():
    """L2 stage 04 must cross-ref the canonical doc."""
    path = (
        REPO_ROOT / "templates" / "workspace" / "stages"
        / "04_implementation_waves" / "CONTEXT.md.tpl"
    )
    text = path.read_text(encoding="utf-8")
    assert "forensic-plus-protocol.md" in text


# Canonical docs that `SKILL.md` must index (section "Algorithm References"
# / bootstrap runtime_refs list). Growing list: when introducing a new
# canonical doc in `references/`, add it here.
SKILL_MD_INDEXED_DOCS: tuple[str, ...] = (
    "wave-planner-algorithm.md",
    "subagent-protocol.md",
    "stop-points-canonical.md",
    "4-block-contract-template.md",
    "feedback-intake-stage08.md",
    "forensic-plus-protocol.md",
    "critic-protocol.md",            # v3.9.0
    "lead-resolution-protocol.md",   # v3.9.0
    "mocking-guidelines.md",         # v3.9.0
    "e2e-coverage-protocol.md",      # v3.10.0
)


def test_skill_md_indexes_canonical_docs():
    """SKILL.md must mention every canonical doc in SKILL_MD_INDEXED_DOCS.

    Opposite direction of detector E (cross-refs link→file): here it is
    file→mention. Ensures new canonical docs are discoverable from
    SKILL.md (skill entry point).
    """
    skill_md = REPO_ROOT / "SKILL.md"
    text = skill_md.read_text(encoding="utf-8")
    missing = [doc for doc in SKILL_MD_INDEXED_DOCS if doc not in text]
    assert not missing, (
        "SKILL.md does not mention canonical docs:\n  "
        + "\n  ".join(missing)
        + "\nAdd bullet in § 'Algorithm References' or remove from "
        "SKILL_MD_INDEXED_DOCS if the omission is intentional."
    )


# ============================================================================
# v3.9.0 — Layered QA loop drift detectors
# ============================================================================

def test_critic_protocol_doc_canonical_exists():
    """v3.9.0 critic-protocol.md must exist with H1 + key sections."""
    path = REPO_ROOT / "references" / "critic-protocol.md"
    assert path.is_file(), "critic-protocol.md missing"
    text = path.read_text(encoding="utf-8")
    assert "# Critic Protocol" in text
    assert "## Triplet output schema" in text
    assert "TIER_CEILING" in text


def test_lead_resolution_protocol_doc_canonical_exists():
    """v3.9.0 lead-resolution-protocol.md must exist with B1/B3/B4 sections."""
    path = REPO_ROOT / "references" / "lead-resolution-protocol.md"
    assert path.is_file(), "lead-resolution-protocol.md missing"
    text = path.read_text(encoding="utf-8")
    assert "# Lead Resolution Protocol" in text
    assert "B1 — REWRITE_SPEC" in text
    assert "B3 — DIRECT_IMPL" in text
    assert "B4 — VOID_TASK" in text


def test_mocking_guidelines_doc_canonical_exists():
    """v3.9.0 mocking-guidelines.md must exist."""
    path = REPO_ROOT / "references" / "mocking-guidelines.md"
    assert path.is_file(), "mocking-guidelines.md missing"
    text = path.read_text(encoding="utf-8")
    assert "# Mocking Guidelines" in text
    assert "boundaries" in text.lower()


def test_l2_stage_04_references_v3_9_0_docs():
    """L2 stage 04 must cross-ref critic-protocol + lead-resolution-protocol + mocking-guidelines."""
    path = (
        REPO_ROOT / "templates" / "workspace" / "stages"
        / "04_implementation_waves" / "CONTEXT.md.tpl"
    )
    text = path.read_text(encoding="utf-8")
    assert "critic-protocol.md" in text, "L2 stage 04 must cite critic-protocol.md"
    assert "lead-resolution-protocol.md" in text, (
        "L2 stage 04 must cite lead-resolution-protocol.md"
    )
    assert "mocking-guidelines.md" in text, (
        "L2 stage 04 must cite mocking-guidelines.md"
    )


def test_l2_stage_04_mentions_buckets():
    """L2 stage 04 must mention all 3 buckets B1/B3/B4."""
    path = (
        REPO_ROOT / "templates" / "workspace" / "stages"
        / "04_implementation_waves" / "CONTEXT.md.tpl"
    )
    text = path.read_text(encoding="utf-8")
    assert "B1" in text and "REWRITE_SPEC" in text
    assert "B3" in text and "DIRECT_IMPL" in text
    assert "B4" in text and "VOID_TASK" in text


def test_l2_stage_05_audits_lead_resolutions():
    """L2 stage 05 must contain audit lead resolutions sub-step (v3.9.0)."""
    path = (
        REPO_ROOT / "templates" / "workspace" / "stages"
        / "05_verification" / "CONTEXT.md.tpl"
    )
    text = path.read_text(encoding="utf-8")
    assert "Lead resolutions" in text or "lead resolutions" in text.lower(), (
        "L2 stage 05 must contain audit lead resolutions sub-step"
    )
    assert "lead-resolution-protocol.md" in text


def test_status_enum_includes_lead_resolution():
    """validate_state.py VALID_STATUSES + state-machine-schema.md must include LEAD_RESOLUTION_IN_PROGRESS."""
    vs_path = REPO_ROOT / "scripts" / "validate_state.py"
    vs_text = vs_path.read_text(encoding="utf-8")
    assert '"LEAD_RESOLUTION_IN_PROGRESS"' in vs_text

    schema_path = REPO_ROOT / "references" / "state-machine-schema.md"
    schema_text = schema_path.read_text(encoding="utf-8")
    assert "LEAD_RESOLUTION_IN_PROGRESS" in schema_text


def test_state_machine_schema_lists_v3_9_0_error_types():
    """state-machine-schema.md must list v3.9.0 error_type values."""
    path = REPO_ROOT / "references" / "state-machine-schema.md"
    text = path.read_text(encoding="utf-8")
    assert "lead_resolution_audit_failed" in text
    assert "lead_resolution_all_buckets_failed" in text
    assert "critic_unavailable" in text
    assert "critic_abstain_loop" in text


# ============================================================================
# v3.10.0 — E2E coverage drift detectors
# ============================================================================

def test_e2e_coverage_protocol_doc_canonical_exists():
    """v3.10.0 e2e-coverage-protocol.md must exist with H1 + key sections."""
    path = REPO_ROOT / "references" / "e2e-coverage-protocol.md"
    assert path.is_file(), "e2e-coverage-protocol.md missing"
    text = path.read_text(encoding="utf-8")
    assert "# E2E Coverage Protocol" in text
    assert "## User-facing path detection" in text
    assert "## Forensic+ Check 8" in text


def test_l2_stage_04_references_e2e_protocol():
    """L2 stage 04 must cross-ref e2e-coverage-protocol.md."""
    path = (
        REPO_ROOT / "templates" / "workspace" / "stages"
        / "04_implementation_waves" / "CONTEXT.md.tpl"
    )
    text = path.read_text(encoding="utf-8")
    assert "e2e-coverage-protocol.md" in text


def test_l2_stage_05_references_e2e_protocol():
    """L2 stage 05 must cross-ref e2e-coverage-protocol.md (sub-step 4.7 audit)."""
    path = (
        REPO_ROOT / "templates" / "workspace" / "stages"
        / "05_verification" / "CONTEXT.md.tpl"
    )
    text = path.read_text(encoding="utf-8")
    assert "e2e-coverage-protocol.md" in text


def test_state_machine_schema_lists_v3_10_0_error_types():
    """state-machine-schema.md must list v3.10.0 e2e error_type values."""
    path = REPO_ROOT / "references" / "state-machine-schema.md"
    text = path.read_text(encoding="utf-8")
    assert "e2e_suite_failed" in text
    assert "e2e_suite_missing" in text
    assert "e2e_suite_stale" in text
    assert "e2e_skip_unjustified" in text


def test_4block_template_has_requires_e2e_field():
    """4-block-contract-template.md must document Requires E2E update field."""
    path = REPO_ROOT / "references" / "4-block-contract-template.md"
    text = path.read_text(encoding="utf-8")
    assert "Requires E2E update" in text


def test_wave_planner_has_user_facing_paths_constant():
    """wave-planner-script.py must expose USER_FACING_PATHS_BY_PROFILE."""
    path = REPO_ROOT / "scripts" / "wave-planner-script.py"
    text = path.read_text(encoding="utf-8")
    assert "USER_FACING_PATHS_BY_PROFILE" in text
    assert "_task_requires_e2e" in text


# ============================================================================
# v3.11.0 — en-US migration drift detector
# ============================================================================

def test_no_pt_br_in_canonical():
    """Canonical en-US files contain no residual pt-BR markers (post-v3.11.0).

    Invokes scripts/i18n-audit.py programmatically against canonical files
    (references/, scripts/, templates/, SKILL.md, README.md, CLAUDE.md),
    excluding changelog historical entries (--exclude-changelog).
    Fails if any residual pt-BR is detected outside the preserved-keywords
    whitelist documented in references/ubiquitous-language-adr.md.
    """
    import json
    import subprocess
    result = subprocess.run(
        [
            "python",
            str(REPO_ROOT / "scripts" / "i18n-audit.py"),
            "--root", str(REPO_ROOT),
            "--exclude-changelog",
            "--format", "json",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        try:
            hits = json.loads(result.stdout)
            formatted = "\n".join(
                f"  {h['file']}:{h['line']}: {h['text']}"
                for h in hits
            )
        except (json.JSONDecodeError, KeyError, TypeError):
            formatted = result.stdout or result.stderr
        pytest.fail(f"Residual pt-BR detected in canonical files:\n{formatted}")
