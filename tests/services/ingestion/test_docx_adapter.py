"""Tests for the DOCX ingestion adapter."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.core.parser.docx_parser import CVParseError
from src.core.parser.schemas import CVMetadata, ExperienceItem, ParsedCV, SkillSection
from src.services.ingestion.adapters.docx_adapter import DocxIngestionAdapter
from src.services.ingestion.contracts import IngestionSource
from src.services.ingestion.errors import FetchError, NormalizationError, ValidationError
from src.services.ingestion.schemas import SourceType


def test_docx_adapter__conforms_to_protocol() -> None:
    adapter = DocxIngestionAdapter()
    assert isinstance(adapter, IngestionSource)


def test_docx_adapter__source_type() -> None:
    adapter = DocxIngestionAdapter()
    assert adapter.source_type == SourceType.DOCX_CV


def test_fetch__file_not_found__raises_fetch_error() -> None:
    adapter = DocxIngestionAdapter()
    with pytest.raises(FetchError, match="File not found"):
        adapter.fetch("/nonexistent/path.docx")


def test_fetch__existing_file__returns_bytes() -> None:
    adapter = DocxIngestionAdapter()
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
        tmp.write(b"PK\x03\x04fake_content")
        tmp.flush()
        result = adapter.fetch(tmp.name)
    assert result.startswith(b"PK\x03\x04")


def test_validate__valid_zip_magic__returns_true() -> None:
    adapter = DocxIngestionAdapter()
    assert adapter.validate(b"PK\x03\x04" + b"\x00" * 100) is True


def test_validate__too_small__raises_validation_error() -> None:
    adapter = DocxIngestionAdapter()
    with pytest.raises(ValidationError, match="too small"):
        adapter.validate(b"PK")


def test_validate__wrong_magic__raises_validation_error() -> None:
    adapter = DocxIngestionAdapter()
    with pytest.raises(ValidationError, match="magic bytes"):
        adapter.validate(b"\x00\x00\x00\x00" + b"\x00" * 100)


def test_normalize__successful_parse__returns_normalized_document() -> None:
    mock_parser = MagicMock()
    mock_parser.parse.return_value = ParsedCV(
        metadata=CVMetadata(
            cv_id="cv-1",
            res_id=123,
            file_name="123_test.docx",
            full_name="Ada Lovelace",
            current_role="Engineer",
        ),
        skills=SkillSection(raw_text="python, java", skill_keywords=["python", "java"]),
        experiences=[
            ExperienceItem(description="Built backend services", is_current=False),
        ],
        education=["MSc Computer Science"],
        certifications=["AWS SAA"],
        raw_text="full text content",
    )

    adapter = DocxIngestionAdapter(parser=mock_parser)
    doc = adapter.normalize("123_test.docx", b"PK\x03\x04fake")

    assert doc.metadata.source_type == SourceType.DOCX_CV
    assert doc.metadata.extra["cv_id"] == "cv-1"
    assert doc.metadata.extra["res_id"] == "123"
    assert doc.content == "full text content"
    assert "skills" in doc.sections
    assert doc.sections["skills"] == ["python", "java"]
    assert "experience" in doc.sections
    assert "education" in doc.sections
    assert "certifications" in doc.sections


def test_normalize__parse_failure__raises_normalization_error() -> None:
    mock_parser = MagicMock()
    mock_parser.parse.side_effect = CVParseError("corrupted file")

    adapter = DocxIngestionAdapter(parser=mock_parser)
    with pytest.raises(NormalizationError, match="DOCX parsing failed"):
        adapter.normalize("bad.docx", b"PK\x03\x04fake")


def test_parse_legacy__delegates_to_docx_parser() -> None:
    mock_parser = MagicMock()
    mock_parser.parse.return_value = MagicMock(spec=ParsedCV)

    adapter = DocxIngestionAdapter(parser=mock_parser)
    adapter.parse_legacy("/some/path.docx")

    mock_parser.parse.assert_called_once_with("/some/path.docx")
