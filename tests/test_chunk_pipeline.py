from __future__ import annotations

import shutil
from collections.abc import Iterable
from pathlib import Path

import pytest

from src.core.embedding.chunk_pipeline import build_chunk_points
from src.core.embedding.service import EmbeddingService
from src.core.parser import parse_docx
from src.core.parser.schemas import CVMetadata, ParsedCV, SkillSection

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "sample_cvs"


class DummyEmbeddingService(EmbeddingService):
    def __init__(self) -> None:
        self._model = "dummy"
        self._dimensions = 3

    @property
    def model(self) -> str:
        return self._model

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed(self, text: str) -> list[float]:
        return [0.1, 0.2, 0.3]

    def embed_batch(self, texts: Iterable[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3] for _ in texts]


def _copy_fixture_with_res_id(tmp_path: Path, fixture_path: Path, res_id: int) -> Path:
    destination = tmp_path / f"{res_id}_{fixture_path.name}"
    shutil.copy(fixture_path, destination)
    return destination


@pytest.mark.parametrize("fixture_name", ["cv_standard.docx", "cv_unstructured.docx"])
def test_build_chunk_points__fixture_cvs__returns_points(
    tmp_path: Path,
    fixture_name: str,
) -> None:
    docx_path = _copy_fixture_with_res_id(tmp_path, FIXTURES_DIR / fixture_name, 12345)
    parsed = parse_docx(docx_path)

    points = build_chunk_points(parsed, DummyEmbeddingService())

    assert points
    for point in points:
        payload = point.payload
        assert payload["cv_id"] == parsed.metadata.cv_id
        assert payload["res_id"] == parsed.metadata.res_id
        assert payload["section_type"]
        assert payload["chunk_index"] >= 0
        assert payload["text_preview"]


def test_build_chunk_points__multiple_sections__includes_expected_section_types() -> None:
    metadata = CVMetadata(
        cv_id="cv-123",
        res_id=12345,
        file_name="cv.docx",
        full_name="Mario Rossi",
        current_role="Senior Engineer",
    )
    parsed = ParsedCV(
        metadata=metadata,
        skills=SkillSection(raw_text="Python, FastAPI", skill_keywords=["Python", "FastAPI"]),
        experiences=[],
        education=["Politecnico di Milano", "MSc Computer Science"],
        certifications=["AWS Certified Developer", "Scrum Master"],
        raw_text="Esperienza in backend e cloud.",
    )

    points = build_chunk_points(parsed, DummyEmbeddingService())

    section_types = {point.payload["section_type"] for point in points}
    assert {"summary", "education", "certifications", "generic"}.issubset(section_types)


def test_build_chunk_points__empty_text__returns_empty() -> None:
    metadata = CVMetadata(cv_id="cv-123", res_id=12345, file_name="cv.docx")
    parsed = ParsedCV(
        metadata=metadata,
        skills=SkillSection(raw_text="", skill_keywords=[]),
        experiences=[],
        education=[],
        certifications=[],
        raw_text="",
    )

    points = build_chunk_points(parsed, DummyEmbeddingService())

    assert points == []
