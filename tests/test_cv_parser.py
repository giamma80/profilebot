"""Tests for the DOCX CV parser (US-003)."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.core.parser.docx_parser import CVParseError, parse_docx

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "sample_cvs"


def _list_docx_fixtures() -> list[Path]:
    return sorted(FIXTURES_DIR.glob("*.docx"))


def test_fixtures_exist() -> None:
    """Ensure we have enough sample CVs to validate parsing."""
    fixtures = _list_docx_fixtures()
    assert len(fixtures) >= 5, "Expected at least 5 DOCX fixtures in tests/fixtures/sample_cvs"


@pytest.mark.parametrize("docx_path", _list_docx_fixtures())
def test_parse_docx_returns_parsed_cv(docx_path: Path) -> None:
    """Parse each DOCX fixture and validate basic structure."""
    parsed = parse_docx(docx_path)

    assert parsed is not None
    assert parsed.metadata is not None
    assert parsed.metadata.cv_id
    assert parsed.metadata.file_name

    if parsed.skills is not None:
        assert isinstance(parsed.skills.raw_text, str)
        assert isinstance(parsed.skills.skill_keywords, list)

    assert isinstance(parsed.experiences, list)
    assert isinstance(parsed.education, list)
    assert isinstance(parsed.certifications, list)
    assert isinstance(parsed.raw_text, str)
    assert parsed.raw_text.strip() != ""


def test_parse_invalid_docx_raises(tmp_path: Path) -> None:
    """Invalid DOCX files should raise a CVParseError."""
    invalid_path = tmp_path / "invalid.docx"
    invalid_path.write_bytes(b"not a docx file")

    with pytest.raises(CVParseError):
        parse_docx(invalid_path)


def test_parse_standard_cv_has_sections() -> None:
    parsed = parse_docx(FIXTURES_DIR / "cv_standard.docx")
    assert parsed.skills is not None
    assert parsed.experiences
    assert parsed.education
    assert parsed.certifications


def test_parse_cv_with_tables_includes_skills() -> None:
    parsed = parse_docx(FIXTURES_DIR / "cv_with_tables.docx")
    assert parsed.skills is not None
    assert parsed.skills.skill_keywords


def test_parse_unstructured_cv_has_raw_text() -> None:
    parsed = parse_docx(FIXTURES_DIR / "cv_unstructured.docx")
    assert parsed.raw_text.strip() != ""


def test_parse_italian_chars_cv() -> None:
    parsed = parse_docx(FIXTURES_DIR / "cv_italian_chars.docx")
    assert "è" in parsed.raw_text or "à" in parsed.raw_text or "ù" in parsed.raw_text


def test_parse_minimal_cv_skills() -> None:
    parsed = parse_docx(FIXTURES_DIR / "cv_minimal.docx")
    assert parsed.skills is not None
    assert parsed.skills.skill_keywords
