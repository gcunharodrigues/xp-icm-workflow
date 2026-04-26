"""Testes unitários para scripts/lessons-match.py.

Cobre:
- Parsing válido / tolerante (G1: tolerant on read).
- Score determinístico.
- Ordenação top-N com tie-breaks (Q10).
- Critical channel separado (G2).
- Glob match em related_files.
- CLI produzindo JSON parseável.
- Aging detection (G3).
- Edge cases (vazio, 0 matches).
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

# --- Carregamento dinâmico do script com hyphen no nome ----------------------

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "lessons-match.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("lessons_match", SCRIPT_PATH)
    assert spec and spec.loader, f"não consegui carregar {SCRIPT_PATH}"
    module = importlib.util.module_from_spec(spec)
    # Registra antes de exec para que @dataclass consiga resolver
    # cls.__module__ → sys.modules["lessons_match"].
    sys.modules["lessons_match"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def lm():
    return _load_module()


# --- Fixtures de conteúdo ----------------------------------------------------

LESSONS_VALID = """\
---
id: 42
date: "2026-04-23"
tags: [auth, jwt, middleware]
severity: high
profile_match: [app_web_backend, app_web_frontend]
tier_match: [development, production]
related_files: ["src/auth/*.ts"]
---

# Lesson 42 — JWT verify obrigatorio

Nunca confie em JWT decoded sem chamar verify().

---
id: 17
date: "2026-04-15"
tags: [middleware, order]
severity: medium
---

# Lesson 17 — middleware order

cors > auth > rate. Ordem importa.

---
id: 33
date: "2026-04-20"
tags: [logs, security]
severity: critical
---

# Lesson 33 — log policy

Nunca logar PII.
"""


LESSONS_WITH_MALFORMED = """\
---
id: 1
date: "2026-04-01"
tags: [a]
severity: low
---

# Lesson 1 — ok

Body.

---
id: not_an_int
date: "bad"
tags: []
severity: invalid
---

# Lesson broken

---
id: 2
date: "2026-04-02"
tags: [b]
severity: medium
---

# Lesson 2 — ok

Body.
"""


# --- Helpers -----------------------------------------------------------------


def _write(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "lessons.md"
    p.write_text(content, encoding="utf-8")
    return p


# --- Parsing -----------------------------------------------------------------


def test_parse_valid_lessons_returns_three(lm, tmp_path):
    path = _write(tmp_path, LESSONS_VALID)
    lessons, skipped = lm.parse_lessons(path)
    assert len(lessons) == 3
    assert skipped == 0
    ids = {lesson.id for lesson in lessons}
    assert ids == {42, 17, 33}


def test_parse_empty_file(lm, tmp_path):
    path = _write(tmp_path, "")
    lessons, skipped = lm.parse_lessons(path)
    assert lessons == []
    assert skipped == 0


def test_parse_skips_malformed_with_warning(lm, tmp_path, capsys):
    path = _write(tmp_path, LESSONS_WITH_MALFORMED)
    lessons, skipped = lm.parse_lessons(path)
    assert len(lessons) == 2
    assert skipped == 1
    err = capsys.readouterr().err
    assert "WARN: lesson at offset" in err
    assert "malformed" in err


def test_parse_extracts_title(lm, tmp_path):
    path = _write(tmp_path, LESSONS_VALID)
    lessons, _ = lm.parse_lessons(path)
    by_id = {l.id: l for l in lessons}
    assert by_id[42].title == "JWT verify obrigatorio"
    assert by_id[17].title == "middleware order"


def test_parse_optional_fields_default_to_none(lm, tmp_path):
    path = _write(tmp_path, LESSONS_VALID)
    lessons, _ = lm.parse_lessons(path)
    by_id = {l.id: l for l in lessons}
    assert by_id[17].profile_match is None
    assert by_id[17].tier_match is None
    assert by_id[17].related_files is None


# --- Score -------------------------------------------------------------------


def test_score_deterministic_same_input(lm, tmp_path):
    path = _write(tmp_path, LESSONS_VALID)
    lessons, _ = lm.parse_lessons(path)
    ctx = lm.MatchContext(
        profile="app_web_backend",
        tier="development",
        tags=["auth", "jwt"],
        files=["src/auth/middleware.ts"],
    )
    s1 = lm.score_lesson(lessons[0], ctx)
    s2 = lm.score_lesson(lessons[0], ctx)
    assert s1 == s2


def test_score_perfect_match_for_lesson_42(lm, tmp_path):
    path = _write(tmp_path, LESSONS_VALID)
    lessons, _ = lm.parse_lessons(path)
    by_id = {l.id: l for l in lessons}
    ctx = lm.MatchContext(
        profile="app_web_backend",
        tier="development",
        tags=["auth", "jwt"],
        files=["src/auth/middleware.ts"],
    )
    score = lm.score_lesson(by_id[42], ctx)
    # tag overlap = 2/2 = 1, profile match = 1, tier match = 1, glob match = 1
    # -> 0.4 + 0.2 + 0.2 + 0.2 = 1.0
    assert score == pytest.approx(1.0)


def test_score_none_optional_means_full_credit(lm, tmp_path):
    path = _write(tmp_path, LESSONS_VALID)
    lessons, _ = lm.parse_lessons(path)
    by_id = {l.id: l for l in lessons}
    ctx = lm.MatchContext(
        profile="anything",
        tier="anywhere",
        tags=["middleware"],
        files=["wherever.ts"],
    )
    # Lesson 17 tem profile_match=None, tier_match=None, related_files=None.
    # Tag overlap = 1/1 = 1.
    # -> 0.4 * 1 + 0.2 * 1 + 0.2 * 1 + 0.2 * 1 = 1.0
    score = lm.score_lesson(by_id[17], ctx)
    assert score == pytest.approx(1.0)


def test_score_zero_when_nothing_matches(lm, tmp_path):
    path = _write(tmp_path, LESSONS_VALID)
    lessons, _ = lm.parse_lessons(path)
    by_id = {l.id: l for l in lessons}
    ctx = lm.MatchContext(
        profile="other_profile",
        tier="other_tier",
        tags=["nope"],
        files=["other/path.go"],
    )
    # Lesson 42 com profile/tier/files restritos: nenhum bate.
    score = lm.score_lesson(by_id[42], ctx)
    assert score == 0.0


def test_glob_match_in_related_files(lm, tmp_path):
    path = _write(tmp_path, LESSONS_VALID)
    lessons, _ = lm.parse_lessons(path)
    by_id = {l.id: l for l in lessons}
    ctx = lm.MatchContext(
        profile="app_web_backend",
        tier="development",
        tags=["auth"],
        files=["src/auth/middleware.ts"],
    )
    # files glob contribuição = 0.2 (1 hit)
    score = lm.score_lesson(by_id[42], ctx)
    assert score > 0.5


def test_glob_no_match(lm, tmp_path):
    path = _write(tmp_path, LESSONS_VALID)
    lessons, _ = lm.parse_lessons(path)
    by_id = {l.id: l for l in lessons}
    ctx = lm.MatchContext(
        profile="app_web_backend",
        tier="development",
        tags=["auth"],
        files=["src/billing/foo.ts"],
    )
    # related_files=["src/auth/*.ts"] não bate "src/billing/foo.ts".
    # tag overlap = 1/1 = 1 -> 0.4; profile=0.2; tier=0.2; files=0; total=0.8
    score = lm.score_lesson(by_id[42], ctx)
    assert score == pytest.approx(0.8)


# --- Match (top_n + critical) -----------------------------------------------


def test_match_returns_top_n_and_critical_separated(lm, tmp_path):
    path = _write(tmp_path, LESSONS_VALID)
    result = lm.match(
        path,
        lm.MatchContext(
            profile="app_web_backend",
            tier="development",
            tags=["auth", "logs"],
            files=["src/auth/middleware.ts"],
        ),
        top_n=3,
    )
    top_ids = [l["id"] for l in result["top_n"]]
    crit_ids = [l["id"] for l in result["critical"]]
    # 33 é critical, deve estar APENAS no canal critical.
    assert 33 in crit_ids
    assert 33 not in top_ids
    # 42 é high, top_n.
    assert 42 in top_ids


def test_match_zero_matches_returns_empty_lists(lm, tmp_path):
    path = _write(tmp_path, LESSONS_VALID)
    result = lm.match(
        path,
        lm.MatchContext(
            profile="other",
            tier="other",
            tags=["xxx"],
            files=["other.go"],
        ),
        top_n=3,
    )
    # Lesson 17 ainda dá score>0 porque opcionais=None (não restringe).
    # Mas tags=["xxx"] e nenhuma lesson tem essa tag, então tag overlap=0.
    # Lesson 17: 0 + 0.2 + 0.2 + 0.2 = 0.6 -> entra. Vamos testar tudo zerado:
    # forçar por todos os campos:
    result_all_zero = lm.match(
        _write(
            tmp_path,
            """\
---
id: 1
date: "2026-04-01"
tags: [xxx]
severity: low
profile_match: [foo]
tier_match: [bar]
related_files: ["src/foo/*.ts"]
---

# Lesson 1 — none

Body.
""",
        ),
        lm.MatchContext(
            profile="other",
            tier="other",
            tags=["abc"],
            files=["zzz.go"],
        ),
        top_n=3,
    )
    assert result_all_zero["top_n"] == []
    assert result_all_zero["critical"] == []


def test_match_empty_lessons_file(lm, tmp_path):
    path = _write(tmp_path, "")
    result = lm.match(
        path,
        lm.MatchContext(
            profile="x",
            tier="y",
            tags=["z"],
            files=[],
        ),
        top_n=3,
    )
    assert result["top_n"] == []
    assert result["critical"] == []
    assert result["skipped_malformed"] == 0


# --- Tie-break ordering ------------------------------------------------------


def test_tie_break_severity_then_date(lm, tmp_path):
    """Duas lessons com mesmo score: severity desc, depois date desc."""
    content = """\
---
id: 1
date: "2026-01-01"
tags: [x]
severity: low
---

# Lesson 1 — old low

---
id: 2
date: "2026-04-01"
tags: [x]
severity: medium
---

# Lesson 2 — recent medium

---
id: 3
date: "2026-03-01"
tags: [x]
severity: medium
---

# Lesson 3 — older medium
"""
    path = _write(tmp_path, content)
    result = lm.match(
        path,
        lm.MatchContext(profile="p", tier="t", tags=["x"], files=[]),
        top_n=3,
    )
    ids = [l["id"] for l in result["top_n"]]
    # Todos têm mesmo score (tag overlap=1, opcionais=None).
    # Severity desc: 2 e 3 (medium) > 1 (low).
    # Entre 2 e 3 (mesma severity), date desc: 2 (abril) > 3 (março).
    assert ids == [2, 3, 1]


def test_critical_capped_at_three_sorted(lm, tmp_path):
    """Mais de 3 lessons critical: cap em 3 ordenadas por date desc."""
    content = ""
    for i, d in enumerate(["2026-01-01", "2026-02-01", "2026-03-01", "2026-04-01"], start=1):
        content += f"""\
---
id: {i}
date: "{d}"
tags: [x]
severity: critical
---

# Lesson {i} — c

Body.

"""
    path = _write(tmp_path, content)
    result = lm.match(
        path,
        lm.MatchContext(profile="p", tier="t", tags=["x"], files=[]),
        top_n=3,
    )
    crit_ids = [l["id"] for l in result["critical"]]
    assert len(crit_ids) == 3
    # Mais recentes primeiro.
    assert crit_ids == [4, 3, 2]


# --- CLI ---------------------------------------------------------------------


def _run_cli(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args],
        capture_output=True,
        text=True,
    )


def test_cli_outputs_parseable_json(tmp_path):
    path = _write(tmp_path, LESSONS_VALID)
    proc = _run_cli(
        [
            "--lessons", str(path),
            "--profile", "app_web_backend",
            "--tier", "development",
            "--tags", "auth,jwt",
            "--files", "src/auth/middleware.ts",
        ]
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert "top_n" in data
    assert "critical" in data
    assert "skipped_malformed" in data


def test_cli_exit_1_on_missing_file(tmp_path):
    proc = _run_cli(
        [
            "--lessons", str(tmp_path / "nope.md"),
            "--profile", "x",
            "--tier", "y",
            "--tags", "a",
            "--files", "",
        ]
    )
    assert proc.returncode == 1


def test_cli_exit_0_when_some_lessons_skipped(tmp_path):
    path = _write(tmp_path, LESSONS_WITH_MALFORMED)
    proc = _run_cli(
        [
            "--lessons", str(path),
            "--profile", "p",
            "--tier", "t",
            "--tags", "a",
            "--files", "",
        ]
    )
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["skipped_malformed"] == 1


def test_cli_top_n_flag_respected(tmp_path):
    path = _write(tmp_path, LESSONS_VALID)
    proc = _run_cli(
        [
            "--lessons", str(path),
            "--profile", "app_web_backend",
            "--tier", "development",
            "--tags", "auth,jwt,middleware,order",
            "--files", "src/auth/middleware.ts",
            "--top-n", "1",
        ]
    )
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert len(data["top_n"]) <= 1


# --- Aging detection ---------------------------------------------------------


def test_aging_returns_old_unmatched(lm, tmp_path):
    content = """\
---
id: 100
date: "2025-01-01"
tags: [x]
severity: low
---

# Lesson 100 — antiga

Body.

---
id: 101
date: "2026-04-01"
tags: [y]
severity: low
---

# Lesson 101 — recente

Body.
"""
    path = _write(tmp_path, content)
    lessons, _ = lm.parse_lessons(path)
    today = date(2026, 4, 25)
    candidates = lm.find_aging_candidates(lessons, today)
    ids = [c["id"] for c in candidates]
    assert 100 in ids
    assert 101 not in ids
    # Schema do candidato.
    assert "days_since" in candidates[0]
    assert "last_matched" in candidates[0]


def test_aging_excludes_recently_matched(lm, tmp_path):
    content = """\
---
id: 200
date: "2024-01-01"
tags: [x]
severity: low
_match_history: ["2026-04-20", "2026-04-15", "2026-04-10", "2026-04-05", "2026-04-01"]
---

# Lesson 200 — antiga mas matched

Body.
"""
    path = _write(tmp_path, content)
    lessons, _ = lm.parse_lessons(path)
    today = date(2026, 4, 25)
    candidates = lm.find_aging_candidates(lessons, today)
    # Tem 5 matches recentes -> deve ser excluído.
    assert all(c["id"] != 200 for c in candidates)


def test_cli_aging_flag(tmp_path):
    content = """\
---
id: 100
date: "2024-01-01"
tags: [x]
severity: low
---

# Lesson 100 — antiga

Body.
"""
    path = _write(tmp_path, content)
    proc = _run_cli(
        [
            "--lessons", str(path),
            "--profile", "p",
            "--tier", "t",
            "--tags", "x",
            "--files", "",
            "--aging",
        ]
    )
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert "aging" in data
    assert any(c["id"] == 100 for c in data["aging"])
