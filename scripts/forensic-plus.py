#!/usr/bin/env python3
"""Forensic+ — anti-fraud structural audit per task in stage 04 wave-reviewer.

Reads CLI args + plan.md + git state. Runs 7 checks (4 v3.8.0 + 3 v3.9.0).
Emits JSON to stdout. Exit 0 always when script completes normally
(regardless of violations). Exit 1 on script crash (git missing, plan
malformed, etc.).

v3.9.0 additions: Check 5 (acceptance ↔ test mapping), Check 6
(NÃO QUERO violations), Check 7 (ADR import drift).

Spec: docs/superpowers/specs/2026-05-03-forensic-plus-wave-reviewer-design.md
Canonical: references/forensic-plus-protocol.md
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


# ============================================================================
# Constants
# ============================================================================

VALID_TIERS = ("experimental", "tool", "development", "production")

# Per spec §6.2 — cap on Forensic+-driven re-spawns before BLOCKED_ERROR.
# Referenced by L2 stage 04 template + canonical forensic-plus-protocol.md.
# Drift-checked in tests/unit/test_no_drift.py.
MAX_FORENSIC_RETRIES = 2


# ============================================================================
# Constants — Check 1 language-aware regex
# ============================================================================

ASSERT_PATTERNS_BY_EXT: dict[str, str] = {
    ".py":   r"\bassert\b|pytest\.raises|self\.assert\w+",
    ".ts":   r"\b(expect|assert|should|it\(|test\()\b",
    ".tsx":  r"\b(expect|assert|should|it\(|test\()\b",
    ".js":   r"\b(expect|assert|should|it\(|test\()\b",
    ".jsx":  r"\b(expect|assert|should|it\(|test\()\b",
    ".go":   r"\bt\.(Errorf|Fatal|Run)\b",
    ".rb":   r"\b(expect|assert|should)\b",
    ".rs":   r"\bassert(_eq|_ne)?!\b",
    ".java": r"\b(assert|@Test|assertEquals)",
    ".kt":   r"\b(assert|@Test|assertEquals)",
    ".cs":   r"\b(Assert\.|\[Test\]|\[Fact\]|\[Theory\])",
}

ASSERT_THRESHOLD = 2

# Test file path patterns (mirror wave-planner-algorithm.md §2)
TEST_PATH_PATTERNS = [
    re.compile(r"(^|/)tests?/"),
    re.compile(r"(^|/)__tests__/"),
    re.compile(r"(^|/)spec/"),
    re.compile(r"_test\.[a-z]+$"),
    re.compile(r"\.test\.[a-z]+$"),
    re.compile(r"\.spec\.[a-z]+$"),
    re.compile(r"^test_.*\.py$"),
]


def _is_test_file(path: str) -> bool:
    """True if path matches any TEST_PATH_PATTERNS."""
    return any(p.search(path) for p in TEST_PATH_PATTERNS)


# ============================================================================
# Plan parser
# ============================================================================

class PlanParseError(Exception):
    """Raised when plan.md cannot be read or task slug not found."""
    pass


def parse_plan_for_task(plan_path: Path, task_slug: str) -> dict:
    """Extract task metadata from plan.md.

    Returns dict with keys: files_touched, conventions_extras, estimated_lines, type.
    Raises PlanParseError if plan unreadable or task slug not found.
    """
    if not plan_path.is_file():
        raise PlanParseError(f"plan.md not found: {plan_path}")
    text = plan_path.read_text(encoding="utf-8")

    # Find task header
    header_re = re.compile(rf"^## Task {re.escape(task_slug)}:", re.MULTILINE)
    m = header_re.search(text)
    if not m:
        raise PlanParseError(f"task slug not found in plan: {task_slug}")

    # Slice from this header to next ## or EOF
    start = m.start()
    next_m = re.search(r"^## ", text[m.end():], re.MULTILINE)
    end = m.end() + next_m.start() if next_m else len(text)
    section = text[start:end]

    def _bullets_under(heading: str) -> list[str]:
        """Return bullet items under a `### {heading}` block, stripped of `- ` prefix."""
        h_re = re.compile(rf"^### {re.escape(heading)}\s*\n", re.MULTILINE)
        h_m = h_re.search(section)
        if not h_m:
            return []
        rest = section[h_m.end():]
        next_h = re.search(r"^### ", rest, re.MULTILINE)
        block = rest[: next_h.start()] if next_h else rest
        return [
            re.sub(r"^-\s+", "", ln).strip()
            for ln in block.splitlines()
            if ln.strip().startswith("-")
        ]

    files_touched = _bullets_under("Files touched")
    conventions = _bullets_under("Conventions extras")
    type_field = _bullets_under("Type")
    nao_quero = _bullets_under("NÃO QUERO")
    validacao = _bullets_under("VALIDAÇÃO")
    adrs_aplicaveis = _bullets_under("ADRs aplicáveis")

    # Estimated lines: parse "~250" or "250" from block (not bullet)
    est_lines = None
    est_h = re.search(r"^### Estimated lines\s*\n", section, re.MULTILINE)
    if est_h:
        rest = section[est_h.end():]
        next_h = re.search(r"^### ", rest, re.MULTILINE)
        block = rest[: next_h.start()] if next_h else rest
        # Extract first int from block
        num_m = re.search(r"\d+", block)
        if num_m:
            est_lines = int(num_m.group(0))

    return {
        "files_touched": files_touched,
        "conventions_extras": conventions,
        "estimated_lines": est_lines,
        "type": type_field[0].upper() if type_field else "AFK",
        "nao_quero": nao_quero,
        "validacao": validacao,
        "adrs_aplicaveis": adrs_aplicaveis,
    }


# ============================================================================
# Git subprocess wrapper
# ============================================================================

class GitError(Exception):
    """Raised when a git subprocess invocation fails."""
    pass


def _git_run(cwd: Path, *args: str) -> str:
    """Run git command. Returns stdout. Raises GitError on non-zero exit."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as e:
        raise GitError(f"git binary not found: {e}") from e
    if result.returncode != 0:
        raise GitError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def _git_show_file(cwd: Path, ref: str, path: str) -> str | None:
    """Return file content at ref, or None if missing/binary."""
    try:
        return _git_run(cwd, "show", f"{ref}:{path}")
    except GitError:
        return None


# ============================================================================
# Check 1 — test assertions
# ============================================================================

def check_test_assertions(
    cwd: Path,
    branch: str,
    files_touched: list[str],
    conventions_extras: list[str],
) -> list[dict]:
    """Verify each declared test file has >= ASSERT_THRESHOLD assertion-shaped tokens.

    The check is purely count-based — it does not distinguish `assert True` from
    `assert x == y`. Rationale (spec §4.1): a single assertion is too easily a
    placeholder; >=2 indicates a minimal real suite. Quality of the assertion is
    out of scope for forensic+; the wave-reviewer's acceptance audit (step 8c)
    catches semantic emptiness.

    Severity is HARD across all tiers (spec §4.1), so this check does not take
    a tier parameter — unlike future checks (files_outside_declared, scope_creep,
    todo_added) which vary severity by tier.

    Returns list of violation dicts (empty if pass).
    """
    if any(c.lower().strip() in ("doc-only", "config-only") for c in conventions_extras):
        return []

    violations: list[dict] = []
    for path in files_touched:
        if not _is_test_file(path):
            continue
        ext_idx = path.rfind(".")
        ext = path[ext_idx:] if ext_idx >= 0 else ""
        pattern = ASSERT_PATTERNS_BY_EXT.get(ext)
        if pattern is None:
            continue  # unsupported extension, skip silently
        content = _git_show_file(cwd, branch, path)
        if content is None:
            violations.append({
                "check": "test_assertions_too_few",
                "severity": "HARD",
                "evidence": f"test file missing on branch: {path}",
            })
            continue
        count = len(re.findall(pattern, content))
        if count < ASSERT_THRESHOLD:
            violations.append({
                "check": "test_assertions_too_few",
                "severity": "HARD",
                "evidence": f"{path}: {count} non-trivial assertion(s) found, need >={ASSERT_THRESHOLD}",
            })
    return violations


# ============================================================================
# Tier × violation severity matrix (spec §4.2)
# ============================================================================

TIER_SEVERITY: dict[str, dict[str, str]] = {
    "test_assertions_too_few":   {"experimental": "HARD", "tool": "HARD", "development": "HARD", "production": "HARD"},
    "files_outside_declared":    {"experimental": "SOFT", "tool": "SOFT", "development": "HARD", "production": "HARD"},
    "scope_creep":               {"experimental": "SOFT", "tool": "SOFT", "development": "SOFT", "production": "HARD"},
    "todo_added":                {"experimental": "SOFT", "tool": "SOFT", "development": "SOFT", "production": "HARD"},
    # v3.9.0 — extended checks
    "acceptance_test_unmapped":  {"experimental": "SOFT", "tool": "SOFT", "development": "HARD", "production": "HARD"},
    "nao_quero_violation":       {"experimental": "SOFT", "tool": "HARD", "development": "HARD", "production": "HARD"},
    "adr_import_drift":          {"experimental": "SOFT", "tool": "HARD", "development": "HARD", "production": "HARD"},
}


def _severity_for(check: str, tier: str) -> str:
    """Look up severity per (check, tier). Raises ValueError on unknown combos.

    Defensive over `KeyError` to give better diagnostics when Checks 3/4 land
    in subsequent tasks.
    """
    try:
        return TIER_SEVERITY[check][tier]
    except KeyError as e:
        raise ValueError(f"unknown check/tier: {check}/{tier}") from e


# ============================================================================
# Allowlists — Check 2
# ============================================================================

LOCKFILE_ALLOWLIST = frozenset({
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "bun.lockb",
    "Cargo.lock",
    "Gemfile.lock",
    "poetry.lock",
    "go.sum",
    ".prettierrc.cache",
    ".eslintcache",
})


def _basename(path: str) -> str:
    """Basename of a git-emitted path (always forward-slash, even on Windows)."""
    return path.rsplit("/", 1)[-1]


# ============================================================================
# Check 2 — files outside declared
# ============================================================================

def check_files_outside_declared(
    cwd: Path,
    branch: str,
    base_branch: str,
    files_touched: list[str],
    tier: str,
) -> list[dict]:
    """Compare actual git diff filenames against declared files_touched.

    Files in actual but not declared (excluding lockfile allowlist) → violation.
    """
    declared = set(files_touched)
    raw = _git_run(cwd, "diff", "--name-only", f"{base_branch}...{branch}")
    actual = {ln.strip() for ln in raw.splitlines() if ln.strip()}
    extras = {p for p in actual - declared if _basename(p) not in LOCKFILE_ALLOWLIST}
    if not extras:
        return []
    sev = _severity_for("files_outside_declared", tier)
    return [{
        "check": "files_outside_declared",
        "severity": sev,
        "evidence": f"{len(extras)} undeclared file(s): {', '.join(sorted(extras))}",
    }]


# ============================================================================
# Check 3 — scope creep vs estimate
# ============================================================================

SCOPE_CREEP_MULTIPLIER = 3

_SHORTSTAT_RE = re.compile(r"(\d+)\s+insertion")


def check_scope_creep(
    cwd: Path,
    branch: str,
    base_branch: str,
    estimated_lines: int | None,
    tier: str,
) -> list[dict]:
    """If estimated_lines declared, flag when insertions > N × estimate."""
    if estimated_lines is None:
        return []
    raw = _git_run(cwd, "diff", "--shortstat", f"{base_branch}...{branch}")
    m = _SHORTSTAT_RE.search(raw)
    if not m:
        return []
    insertions = int(m.group(1))
    threshold = SCOPE_CREEP_MULTIPLIER * estimated_lines
    if insertions <= threshold:
        return []
    sev = _severity_for("scope_creep", tier)
    return [{
        "check": "scope_creep",
        "severity": sev,
        "evidence": f"+{insertions} lines vs {estimated_lines} estimate ({SCOPE_CREEP_MULTIPLIER}× threshold = {threshold})",
    }]


# ============================================================================
# Check 4 — TODO/FIXME/HACK added
# ============================================================================

TODO_FILE_GLOBS = (
    "*.py", "*.ts", "*.tsx", "*.js", "*.jsx",
    "*.go", "*.rb", "*.rs", "*.java", "*.kt", "*.cs",
)
TODO_PATTERN = re.compile(r"\b(TODO|FIXME|HACK|XXX)\b")


def check_todo_added(
    cwd: Path,
    branch: str,
    base_branch: str,
    tier: str,
) -> list[dict]:
    """Count + lines containing TODO/FIXME/HACK/XXX in code files."""
    raw = _git_run(
        cwd, "diff", f"{base_branch}...{branch}", "--", *TODO_FILE_GLOBS,
    )
    added: list[str] = []
    for ln in raw.splitlines():
        if not ln.startswith("+") or ln.startswith("+++"):
            continue
        if TODO_PATTERN.search(ln):
            added.append(ln[1:].strip())
    if not added:
        return []
    sev = _severity_for("todo_added", tier)
    sample = "; ".join(added[:3])
    suffix = f" (+{len(added) - 3} more)" if len(added) > 3 else ""
    return [{
        "check": "todo_added",
        "severity": sev,
        "evidence": f"{len(added)} TODO/FIXME/HACK added: {sample}{suffix}",
    }]


# ============================================================================
# Check 5 — acceptance ↔ test mapping (v3.9.0)
# ============================================================================

# Test name patterns extracted from VALIDAÇÃO bullets.
# Order matters — try direct test_name patterns first, fallback to weaker hints.
_TEST_NAME_PATTERNS = (
    re.compile(r"`(test_[a-zA-Z0-9_]+)`"),               # `test_foo_bar`
    re.compile(r"\b(test_[a-zA-Z0-9_]+)\b"),             # bare test_foo_bar
    re.compile(r"`([a-z][a-zA-Z0-9_]*Test)`"),           # `fooBarTest`
    re.compile(r'it\("([^"]+)"'),                         # it("describes...")
    re.compile(r"should\s+([a-z][a-z0-9_\- ]{4,})"),     # should foo bar
)

# Bullets matching these patterns are skipped (not test mappings).
_VALIDACAO_SKIP_PATTERNS = (
    re.compile(r"^\s*Cobertura\s+", re.IGNORECASE),
    re.compile(r"^\s*Coverage\s+", re.IGNORECASE),
    re.compile(r"^\s*Performance\s+", re.IGNORECASE),
)


def _extract_test_names_from_bullet(bullet: str) -> list[str]:
    """Try patterns in order, return list of candidate names found."""
    names: list[str] = []
    for pat in _TEST_NAME_PATTERNS:
        for m in pat.finditer(bullet):
            names.append(m.group(1))
    return names


def check_acceptance_test_mapping(
    cwd: Path,
    branch: str,
    files_touched: list[str],
    validacao: list[str],
    conventions_extras: list[str],
    tier: str,
) -> list[dict]:
    """Each VALIDAÇÃO bullet should map to >=1 test name found in test files.

    Skip when task is doc-only/config-only. Skip bullets matching coverage/perf
    patterns (not test mappings).

    For each bullet:
    1. Extract candidate test names via regex.
    2. If no candidates found, treat bullet as descriptive (skip silently).
    3. If candidates exist, grep test files for any match.
    4. No match → violation.
    """
    if any(c.lower().strip() in ("doc-only", "config-only") for c in conventions_extras):
        return []
    if not validacao:
        return []

    test_files = [p for p in files_touched if _is_test_file(p)]
    if not test_files:
        return []

    # Concatenate all test file contents for grep
    combined_test_content = ""
    for path in test_files:
        content = _git_show_file(cwd, branch, path)
        if content is not None:
            combined_test_content += content + "\n"

    violations: list[dict] = []
    for bullet in validacao:
        if any(p.search(bullet) for p in _VALIDACAO_SKIP_PATTERNS):
            continue
        candidates = _extract_test_names_from_bullet(bullet)
        if not candidates:
            continue
        # Match if any candidate substring appears in test content
        if not any(c in combined_test_content for c in candidates):
            sev = _severity_for("acceptance_test_unmapped", tier)
            sample = ", ".join(candidates[:3])
            violations.append({
                "check": "acceptance_test_unmapped",
                "severity": sev,
                "evidence": f"VALIDAÇÃO bullet candidates [{sample}] not found in declared test files",
            })
    return violations


# ============================================================================
# Check 6 — NÃO QUERO violations (v3.9.0)
# ============================================================================

# Pattern: detect imports/mocks/literal keywords from NÃO QUERO bullets.
_MOCK_BULLET_RE = re.compile(
    r"^\s*Mock\s+interno\s+de\s+`?([\w./\-@]+)`?",
    re.IGNORECASE,
)
_IMPORT_BULLET_RE = re.compile(
    r"^\s*Import\s+`?([\w./\-@]+)`?",
    re.IGNORECASE,
)
_KEYWORD_BULLET_RE = re.compile(r"^\s*`([A-Z][A-Z0-9_]{5,})`")


def _diff_added_lines(cwd: Path, branch: str, base_branch: str) -> str:
    """Return concatenated added lines from full diff (no path filter)."""
    raw = _git_run(cwd, "diff", f"{base_branch}...{branch}")
    return "\n".join(
        ln for ln in raw.splitlines()
        if ln.startswith("+") and not ln.startswith("+++")
    )


def check_nao_quero_violations(
    cwd: Path,
    branch: str,
    base_branch: str,
    nao_quero: list[str],
    tier: str,
) -> list[dict]:
    """Bullets in NÃO QUERO declaring detectable patterns are checked.

    Supported:
    - "Mock interno de <module>" → grep diff for jest.mock("<module>") /
      mocker.patch("<module>")
    - "Import <lib>" → grep diff for import statements with <lib>
    - `KEYWORD` (uppercase, ≥6 chars) → grep diff for literal occurrence
    """
    if not nao_quero:
        return []

    added = _diff_added_lines(cwd, branch, base_branch)
    if not added:
        return []

    violations: list[dict] = []
    sev = _severity_for("nao_quero_violation", tier)

    for bullet in nao_quero:
        m = _MOCK_BULLET_RE.search(bullet)
        if m:
            module = m.group(1)
            # Detect jest.mock("module") / mocker.patch("module") / vi.mock("module")
            patterns = [
                rf'(jest|vi)\.mock\(["\']({re.escape(module)})["\']',
                rf'mocker\.patch\(["\']({re.escape(module)})["\']',
                rf'mock\.patch\(["\']({re.escape(module)})["\']',
            ]
            for pat in patterns:
                if re.search(pat, added):
                    violations.append({
                        "check": "nao_quero_violation",
                        "severity": sev,
                        "evidence": f"NÃO QUERO violated: mock interno de {module} (pattern: {pat[:40]}...)",
                    })
                    break
            continue

        m = _IMPORT_BULLET_RE.search(bullet)
        if m:
            lib = m.group(1)
            # ES modules + Python import patterns
            patterns = [
                rf'\b(import|require)\b.*["\']({re.escape(lib)})["\']',
                rf'\b(import|from)\s+{re.escape(lib)}\b',
            ]
            for pat in patterns:
                if re.search(pat, added):
                    violations.append({
                        "check": "nao_quero_violation",
                        "severity": sev,
                        "evidence": f"NÃO QUERO violated: import de {lib} detected in diff",
                    })
                    break
            continue

        m = _KEYWORD_BULLET_RE.search(bullet)
        if m:
            kw = m.group(1)
            if re.search(rf"\b{re.escape(kw)}\b", added):
                violations.append({
                    "check": "nao_quero_violation",
                    "severity": sev,
                    "evidence": f"NÃO QUERO violated: keyword `{kw}` present in added lines",
                })

    return violations


# ============================================================================
# Check 7 — ADR import drift (v3.9.0)
# ============================================================================

_ADR_FORBIDDEN_HEADER_RE = re.compile(
    r"^##\s+Forbidden\s+imports\s*\n",
    re.MULTILINE | re.IGNORECASE,
)
_ADR_LIB_BULLET_RE = re.compile(r"^\s*-\s+`([\w./\-@]+)`")


def _parse_adr_forbidden_imports(adr_path: Path) -> list[str]:
    """Parse ADR markdown for `## Forbidden imports` section, return libs.

    Returns empty list if section absent (backward compat — silent skip).
    """
    if not adr_path.is_file():
        return []
    text = adr_path.read_text(encoding="utf-8")
    h = _ADR_FORBIDDEN_HEADER_RE.search(text)
    if not h:
        return []
    rest = text[h.end():]
    next_h = re.search(r"^## ", rest, re.MULTILINE)
    block = rest[: next_h.start()] if next_h else rest
    libs: list[str] = []
    for ln in block.splitlines():
        m = _ADR_LIB_BULLET_RE.match(ln)
        if m:
            libs.append(m.group(1))
    return libs


def check_adr_import_drift(
    cwd: Path,
    branch: str,
    base_branch: str,
    adrs_aplicaveis: list[str],
    tier: str,
) -> list[dict]:
    """For each ADR with `## Forbidden imports`, grep diff for forbidden libs.

    ADR paths in `adrs_aplicaveis` are relative to project root (cwd).
    Backward compat: ADR sem seção = silently skipped.
    """
    if not adrs_aplicaveis:
        return []

    violations: list[dict] = []
    sev = _severity_for("adr_import_drift", tier)
    added = _diff_added_lines(cwd, branch, base_branch)
    if not added:
        return []

    for adr_ref in adrs_aplicaveis:
        # Bullet format: "docs/decisions/0001-stack.md" or with leading whitespace
        adr_path_str = adr_ref.strip()
        if not adr_path_str:
            continue
        adr_path = cwd / adr_path_str
        forbidden = _parse_adr_forbidden_imports(adr_path)
        if not forbidden:
            continue
        for lib in forbidden:
            patterns = [
                rf'\b(import|require)\b.*["\']({re.escape(lib)})["\']',
                rf'\b(import|from)\s+{re.escape(lib)}\b',
                rf'\buse\s+{re.escape(lib)}\b',
            ]
            for pat in patterns:
                if re.search(pat, added):
                    violations.append({
                        "check": "adr_import_drift",
                        "severity": sev,
                        "evidence": f"ADR {adr_path_str} forbids `{lib}`; import detected in diff",
                    })
                    break

    return violations


# ============================================================================
# CLI
# ============================================================================

def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Forensic+ structural audit for stage 04 wave-reviewer."
    )
    p.add_argument("--workspace-num", required=True, help="Workspace number (NNN).")
    p.add_argument("--wave", required=True, type=int, help="Wave index (1-based).")
    p.add_argument("--task-slug", required=True, help="Task slug (kebab-case).")
    p.add_argument("--base-branch", required=True, help="Base branch (e.g. main).")
    p.add_argument("--plan", required=True, help="Path to plan.md.")
    p.add_argument("--tier", required=True, choices=VALID_TIERS, help="Workspace tier.")
    p.add_argument("--output", default="json", choices=("json",), help="Output format.")
    return p.parse_args(argv)


# ============================================================================
# Main
# ============================================================================

def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])

    cwd = Path.cwd()
    branch = f"wave-{args.workspace_num}-{args.wave}/{args.task_slug}"
    plan_path = Path(args.plan)

    try:
        task_meta = parse_plan_for_task(plan_path, args.task_slug)
    except PlanParseError as e:
        sys.stderr.write(f"forensic-plus: {e}\n")
        return 1

    # HITL skip: spec §6.5 EC4 / Q4=A
    if task_meta["type"] == "HITL":
        result = {
            "task_slug": args.task_slug,
            "violations": [],
            "forensic_passed": None,
            "max_severity": None,
            "skipped_reason": "task type=HITL",
        }
        sys.stdout.write(json.dumps(result, indent=2) + "\n")
        return 0

    violations: list[dict] = []
    try:
        violations.extend(check_test_assertions(
            cwd, branch, task_meta["files_touched"], task_meta["conventions_extras"]
        ))
    except GitError as e:
        sys.stderr.write(f"forensic-plus: {e}\n")
        return 1

    try:
        violations.extend(check_files_outside_declared(
            cwd, branch, args.base_branch, task_meta["files_touched"], args.tier,
        ))
    except GitError as e:
        sys.stderr.write(f"forensic-plus: {e}\n")
        return 1

    try:
        violations.extend(check_scope_creep(
            cwd, branch, args.base_branch, task_meta["estimated_lines"], args.tier,
        ))
    except GitError as e:
        sys.stderr.write(f"forensic-plus: {e}\n")
        return 1

    try:
        violations.extend(check_todo_added(cwd, branch, args.base_branch, args.tier))
    except GitError as e:
        sys.stderr.write(f"forensic-plus: {e}\n")
        return 1

    # v3.9.0 — extended checks 5/6/7
    try:
        violations.extend(check_acceptance_test_mapping(
            cwd, branch,
            task_meta["files_touched"],
            task_meta["validacao"],
            task_meta["conventions_extras"],
            args.tier,
        ))
    except GitError as e:
        sys.stderr.write(f"forensic-plus: {e}\n")
        return 1

    try:
        violations.extend(check_nao_quero_violations(
            cwd, branch, args.base_branch, task_meta["nao_quero"], args.tier,
        ))
    except GitError as e:
        sys.stderr.write(f"forensic-plus: {e}\n")
        return 1

    try:
        violations.extend(check_adr_import_drift(
            cwd, branch, args.base_branch, task_meta["adrs_aplicaveis"], args.tier,
        ))
    except GitError as e:
        sys.stderr.write(f"forensic-plus: {e}\n")
        return 1

    # Reduce to result schema
    has_hard = any(v["severity"] == "HARD" for v in violations)
    has_soft = any(v["severity"] == "SOFT" for v in violations)
    max_severity = "HARD" if has_hard else ("SOFT" if has_soft else "NONE")

    result: dict[str, Any] = {
        "task_slug": args.task_slug,
        "violations": violations,
        "forensic_passed": not has_hard,
        "max_severity": max_severity,
    }
    sys.stdout.write(json.dumps(result, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
