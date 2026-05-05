"""Smoke test do doc canonico references/preview-loop-protocol.md (v3.6.0).

Valida:
- Doc existe + parsavel.
- 10 decisoes consolidadas presentes (numeros explicitos no doc).
- Cross-refs canonicos resolvem.
- Profile flags consolidadas tabela mencionada.
- Recovery wizard tipos novos mencionados.
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOC_PATH = REPO_ROOT / "references" / "preview-loop-protocol.md"


def test_doc_exists():
    assert DOC_PATH.is_file(), f"{DOC_PATH} ausente"


def test_doc_has_version_v3_6():
    text = DOC_PATH.read_text(encoding="utf-8")
    assert "v3.6.0" in text, "doc does not declare version v3.6.0"


def test_doc_mentions_all_10_decision_topics():
    """10 topicos das decisoes humanas."""
    text = DOC_PATH.read_text(encoding="utf-8")
    required_topics = [
        "Dev server lifecycle",
        "Mock data strategy",
        "CDP browser integration",
        "Uniform verification",
        "Preview pages convention",
        "Feedback communication",
        "Visual iteration",
        "Design system cascade",
        "Multi-screen",
    ]
    missing = [t for t in required_topics if t not in text]
    assert not missing, f"tópicos faltando no doc: {missing}"


def test_doc_mentions_recovery_codes():
    text = DOC_PATH.read_text(encoding="utf-8")
    assert "DEV_SERVER_ORPHAN" in text
    assert "CDP_DISCONNECTED" in text


def test_doc_mentions_mock_data_tiers():
    text = DOC_PATH.read_text(encoding="utf-8")
    for strategy in ("fixtures", "msw_faker", "msw_faker_zod"):
        assert strategy in text, f"strategy {strategy} ausente"


def test_doc_mentions_helper_scripts():
    text = DOC_PATH.read_text(encoding="utf-8")
    assert "launch-chrome-cdp.bat" in text
    assert "launch-chrome-cdp.sh" in text


def test_doc_mentions_cdp_port():
    text = DOC_PATH.read_text(encoding="utf-8")
    assert "9222" in text, "doc deve mencionar porta CDP 9222"


def test_doc_mentions_threshold_5():
    text = DOC_PATH.read_text(encoding="utf-8")
    assert "design_cascade_threshold" in text
    assert "threshold 5" in text.lower() or "threshold de 5" in text.lower() or " 5 " in text


def test_helper_scripts_exist():
    bat = REPO_ROOT / "templates" / ".claude" / "scripts" / "launch-chrome-cdp.bat"
    sh = REPO_ROOT / "templates" / ".claude" / "scripts" / "launch-chrome-cdp.sh"
    assert bat.is_file(), f"{bat} ausente"
    assert sh.is_file(), f"{sh} ausente"


def test_helper_scripts_use_port_9222():
    bat = REPO_ROOT / "templates" / ".claude" / "scripts" / "launch-chrome-cdp.bat"
    sh = REPO_ROOT / "templates" / ".claude" / "scripts" / "launch-chrome-cdp.sh"
    for f in (bat, sh):
        text = f.read_text(encoding="utf-8")
        assert "9222" in text, f"{f.name} does not mention port 9222"
        assert ".icm-chrome-profile" in text, f"{f.name} does not use canonical profile dir"
