"""Tests for LLM section classification scaffolding."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from docx import Document
from pydantic import ValidationError

from src.core.config import get_settings
from src.core.parser import docx_parser
from src.core.parser.docx_parser import CVParseError, parse_docx
from src.core.parser.schemas import SectionClassification
from src.core.parser.section_classifier import (
    SectionClassificationError,
    parse_section_classification,
)


def _make_docx(tmp_path: Path, filename: str, lines: list[str]) -> Path:
    document = Document()
    for line in lines:
        document.add_paragraph(line)
    path = tmp_path / filename
    document.save(path)
    return path


def _set_flag(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("LLM_SECTION_CLASSIFICATION_ENABLED", value)
    get_settings.cache_clear()


def test_section_classification__extra_fields__raises() -> None:
    payload = {
        "skills": ["python"],
        "experience": [],
        "education": [],
        "certifications": [],
        "other": [],
        "unexpected": ["oops"],
    }

    with pytest.raises(ValidationError):
        SectionClassification.model_validate(payload)


def test_parse_section_classification__valid_json__returns_model() -> None:
    raw = json.dumps(
        {
            "skills": ["Python"],
            "experience": ["Backend Dev"],
            "education": ["MSc"],
            "certifications": [],
            "other": ["Summary"],
        }
    )

    parsed = parse_section_classification(raw)

    assert parsed.skills == ["Python"]
    assert parsed.experience == ["Backend Dev"]
    assert parsed.education == ["MSc"]
    assert parsed.other == ["Summary"]


def test_docx_parser__feature_flag_off__bypasses_llm(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _set_flag(monkeypatch, "false")

    def _raise(*_: object, **__: object) -> None:
        raise AssertionError("LLM should not be called when flag is disabled")

    monkeypatch.setattr(docx_parser, "classify_sections", _raise)

    path = _make_docx(tmp_path, "12345_test.docx", ["Skills", "Python", "Experience", "Dev"])
    parsed = parse_docx(path)

    assert parsed.skills is not None
    assert parsed.experiences


def test_docx_parser__feature_flag_on__uses_llm(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _set_flag(monkeypatch, "true")
    called = {"value": False}

    def _fake_classify(lines: list[str], raw_text: str) -> SectionClassification:
        called["value"] = True
        return SectionClassification(
            skills=["Python, FastAPI"],
            experience=["Backend Dev"],
            education=[],
            certifications=[],
            other=["Summary"],
        )

    monkeypatch.setattr(docx_parser, "classify_sections", _fake_classify)

    path = _make_docx(tmp_path, "12345_test.docx", ["Summary", "Skills", "Python"])
    parsed = parse_docx(path)

    assert called["value"] is True
    assert parsed.skills is not None
    assert "Python" in parsed.skills.raw_text
    assert parsed.experiences


def test_docx_parser__llm_error__raises_parse_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _set_flag(monkeypatch, "true")

    def _raise(*_: object, **__: object) -> None:
        raise SectionClassificationError("boom")

    monkeypatch.setattr(docx_parser, "classify_sections", _raise)

    path = _make_docx(tmp_path, "12345_test.docx", ["Skills", "Python"])

    with pytest.raises(CVParseError, match="LLM section classification failed"):
        parse_docx(path)
