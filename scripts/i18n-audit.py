#!/usr/bin/env python3
"""i18n-audit — heuristic detector for residual pt-BR text in canonical files.

Scans the skill repo (references/, scripts/, templates/, SKILL.md, README.md,
CLAUDE.md) and reports lines containing frequent pt-BR markers. Used as a
drift gate enforcing the v3.12.0 zero-pt-BR policy.

Zero-pt-BR policy (v3.12.0): the skill has a single en-US canonical source
with NO pt-BR carry-overs. All previously preserved keywords (4-block headers
`O QUE` / `COMO` / `NÃO QUERO` / `VALIDAÇÃO`, retrospective headers, ADR
field `ADRs aplicáveis`, historical changelog) have been translated.

Heuristic regex matches common Portuguese tokens (see ``PT_BR_PATTERNS``
constant below for the full list — kept as compiled regex objects to avoid
embedding pt-BR literals in this docstring). False positives in code blocks
or proper nouns are added to the whitelist via ``# i18n-allow: <reason>``
inline comments.

CLI:

    python scripts/i18n-audit.py [--root <repo-root>] [--format text|json]
                                 [--exclude-changelog]

Exit codes:
    0  no residual pt-BR detected (after whitelist)
    1  residual pt-BR detected — listed on stdout

The complete decision rationale lives in `references/ubiquitous-language-adr.md`.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Iterable


# ============================================================================
# Heuristic detection regex
# ============================================================================

# High-confidence pt-BR markers. Each pattern is a Portuguese-specific token
# unlikely to appear in en-US prose or in code identifiers.
PT_BR_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"\bnão\b", re.IGNORECASE),
    re.compile(r"\bsão\b", re.IGNORECASE),
    re.compile(r"\bestão\b", re.IGNORECASE),
    re.compile(r"\bestá\b", re.IGNORECASE),
    re.compile(r"\bção\b", re.IGNORECASE),
    re.compile(r"\bções\b", re.IGNORECASE),
    re.compile(r"\bõe[sm]\b", re.IGNORECASE),
    re.compile(r"\bem\b\s+\bportuguês\b", re.IGNORECASE),
    re.compile(r"\bpara\b\s+\bo\b", re.IGNORECASE),
    re.compile(r"\bpara\b\s+\bque\b", re.IGNORECASE),
    re.compile(r"\bquando\b\s+\bnão\b", re.IGNORECASE),
    re.compile(r"\busar\b", re.IGNORECASE),
    re.compile(r"\bcaso\b\s+\bde\b", re.IGNORECASE),
    re.compile(r"\bdeve\b\s+\bser\b", re.IGNORECASE),
    re.compile(r"\bpode\b\s+\bser\b", re.IGNORECASE),
    re.compile(r"\bsem\b\s+\bque\b", re.IGNORECASE),
    re.compile(r"\bcom\b\s+\bque\b", re.IGNORECASE),
    re.compile(r"\bnessa\b", re.IGNORECASE),
    re.compile(r"\bnesse\b", re.IGNORECASE),
    re.compile(r"\bdesta\b", re.IGNORECASE),
    re.compile(r"\bdeste\b", re.IGNORECASE),
    re.compile(r"\baqui\b", re.IGNORECASE),
    re.compile(r"\bagora\b", re.IGNORECASE),
    re.compile(r"\bporque\b", re.IGNORECASE),
    re.compile(r"\benquanto\b", re.IGNORECASE),
)

# Whitelisted phrases — allowed under the zero-pt-BR policy.
# Each entry is checked as a substring; matched lines containing only these
# tokens are not reported.
PRESERVED_KEYWORDS: tuple[str, ...] = (
    "ambiguous_feedback",    # stop point ID (en-US — kept literal in scripts)
    "design_system_cascade", # stop point ID (en-US — kept literal)
    # Meta-references discussing the migration itself.
    "pt-BR",
    "Portuguese",
    "Brazilian",
    "ubiquitous-language-adr",
)

# Inline allow marker — suppresses report on the same line.
# Accepts both Python/shell comment style (`# i18n-allow`) and HTML comment
# style (`<!-- i18n-allow:`) so the marker works in both .py/.sh and .md files.
ALLOW_MARKER_RE = re.compile(r"(?:#|<!--)\s*i18n-allow", re.IGNORECASE)


# ============================================================================
# Path filters
# ============================================================================

# Whole files exempted from scanning (historical content).
FILE_WHITELIST: frozenset[str] = frozenset(
    {
        "scripts/migrate-v3.3-to-v3.4.py",  # historical migration with original prose
        "_KICKOFF-v3.4.0-finish.md",  # archived kickoff
        "references/v2.4-snapshot",  # legacy snapshot folder
        "scripts/i18n-audit.py",  # self-referential — PRESERVED_KEYWORDS literals trigger patterns
    }
)

# Path prefixes to scan. Anything else is ignored.
SCAN_PREFIXES: tuple[str, ...] = (
    "references/",
    "scripts/",
    "templates/",
    "SKILL.md",
    "README.md",
    "CLAUDE.md",
)

# Extensions actually scanned (skip binary, lockfiles, etc).
SCAN_EXTENSIONS: tuple[str, ...] = (
    ".md",
    ".py",
    ".tpl",
    ".sh",
    ".bat",
    ".yaml",
    ".yml",
)


def _should_scan(rel_path: str) -> bool:
    if rel_path in FILE_WHITELIST:
        return False
    if any(rel_path.startswith(w) for w in FILE_WHITELIST if "/" in w):
        return False
    if not any(rel_path.startswith(p) or rel_path == p for p in SCAN_PREFIXES):
        return False
    if not rel_path.endswith(SCAN_EXTENSIONS):
        return False
    return True


# ============================================================================
# Line analysis
# ============================================================================

def _line_is_whitelisted(line: str) -> bool:
    """True if the only pt-BR-shaped tokens on this line are preserved keywords."""
    if ALLOW_MARKER_RE.search(line):
        return True
    # If line contains preserved keyword AND no other pt-BR markers, allow.
    has_keyword = any(kw in line for kw in PRESERVED_KEYWORDS)
    if not has_keyword:
        return False
    # Strip preserved keywords and re-check. Sort longest-first so compound
    # phrases (e.g. "O QUE NÃO FUNCIONOU") are removed before their substrings
    # (e.g. "O QUE"), avoiding false positives from partial strips.
    stripped = line
    for kw in sorted(PRESERVED_KEYWORDS, key=len, reverse=True):
        stripped = stripped.replace(kw, "")
    return not any(p.search(stripped) for p in PT_BR_PATTERNS)


def scan_file(path: Path, repo_root: Path) -> list[dict]:
    """Return a list of {line, lineno, matches} for residual pt-BR lines."""
    rel = path.relative_to(repo_root).as_posix()
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []
    findings: list[dict] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if not any(p.search(line) for p in PT_BR_PATTERNS):
            continue
        if _line_is_whitelisted(line):
            continue
        findings.append(
            {
                "file": rel,
                "line": lineno,
                "text": line.strip()[:200],
            }
        )
    return findings


def scan_repo(repo_root: Path, extra_exclude: frozenset[str] = frozenset()) -> list[dict]:
    findings: list[dict] = []
    for path in sorted(repo_root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(repo_root).as_posix()
        if rel in extra_exclude:
            continue
        if not _should_scan(rel):
            continue
        findings.extend(scan_file(path, repo_root))
    return findings


# ============================================================================
# CLI
# ============================================================================

def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root to scan (default: skill root)",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
    )
    parser.add_argument(
        "--exclude-changelog",
        action="store_true",
        help=(
            "Exclude references/changelog.md from scan. "
            "v3.12.0+ changelog is entirely en-US so this flag is no longer needed; "
            "kept for backward compatibility with CI scripts."
        ),
    )
    args = parser.parse_args(argv)

    extra_exclude: frozenset[str] = frozenset()
    if args.exclude_changelog:
        extra_exclude = frozenset({"references/changelog.md"})

    findings = scan_repo(args.root, extra_exclude=extra_exclude)

    if args.format == "json":
        sys.stdout.write(json.dumps(findings, indent=2, ensure_ascii=False) + "\n")
    else:
        if not findings:
            sys.stdout.write("i18n-audit: no residual pt-BR detected.\n")
        else:
            sys.stdout.write(
                f"i18n-audit: {len(findings)} residual pt-BR line(s) detected:\n\n"
            )
            for f in findings:
                sys.stdout.write(f"  {f['file']}:{f['line']}: {f['text']}\n")

    return 0 if not findings else 1


if __name__ == "__main__":
    sys.exit(main())
