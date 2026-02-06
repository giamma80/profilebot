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

    assert parsed.skills is not None
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
