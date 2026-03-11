"""Integration tests for anonymous CV fixtures."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import pytest

from src.core.embedding import pipeline as embedding_pipeline
from src.core.embedding.pipeline import EmbeddingPipeline
from src.core.embedding.service import EmbeddingService
from src.core.parser.docx_parser import parse_docx
from src.core.skills import SkillExtractor, load_skill_dictionary
from src.core.skills.schemas import SkillExtractionResult

ANON_DIR = Path(__file__).parent / "fixtures" / "sample_cvs"
SKILLS_DICTIONARY_PATH = Path("data/skills_dictionary.yaml")


class DummyEmbeddingService(EmbeddingService):
    @property
    def model(self) -> str:
        return "dummy"

    @property
    def dimensions(self) -> int:
        return 3

    def embed(self, text: str) -> list[float]:
        return [0.1, 0.2, 0.3]

    def embed_batch(self, texts: Iterable[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3] for _ in texts]


def _list_anonymous_fixtures() -> list[Path]:
    return sorted(ANON_DIR.glob("1000*_*.docx"))


def _get_res_id_from_filename(path: Path) -> int:
    return int(path.name.split("_", 1)[0])


def test_anonymous_fixtures_exist() -> None:
    fixtures = _list_anonymous_fixtures()
    assert len(fixtures) >= 10, "Expected anonymous CV fixtures 100000-100009"


@pytest.mark.parametrize("docx_path", _list_anonymous_fixtures())
def test_parse_anonymous_cvs__extracts_correct_res_id(docx_path: Path) -> None:
    parsed = parse_docx(docx_path)
    expected = _get_res_id_from_filename(docx_path)
    assert parsed.metadata.res_id == expected


def test_anonymous_cv__skill_extraction__works() -> None:
    fixtures = _list_anonymous_fixtures()
    if not fixtures:
        pytest.skip("Anonymous fixtures not available")
    parsed = parse_docx(fixtures[0])
    dictionary = load_skill_dictionary(SKILLS_DICTIONARY_PATH)
    extractor = SkillExtractor(dictionary)
    result = extractor.extract(parsed)

    assert isinstance(result, SkillExtractionResult)
    assert result.cv_id == parsed.metadata.cv_id
    assert isinstance(result.normalized_skills, list)
    assert isinstance(result.unknown_skills, list)
    assert result.dictionary_version


def test_anonymous_cv__e2e__pipeline_completes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixtures = _list_anonymous_fixtures()
    if not fixtures:
        pytest.skip("Anonymous fixtures not available")
    parsed = parse_docx(fixtures[0])

    dictionary = load_skill_dictionary(SKILLS_DICTIONARY_PATH)
    extractor = SkillExtractor(dictionary)
    skill_result = extractor.extract(parsed)

    monkeypatch.setattr(embedding_pipeline, "ensure_collections", lambda *_: None, raising=True)

    pipeline = EmbeddingPipeline(
        embedding_service=DummyEmbeddingService(),
        qdrant_client=object(),
    )
    result = pipeline.process_cv(parsed, skill_result, dry_run=True)

    assert {"cv_skills", "cv_experiences", "cv_chunks", "total"}.issubset(result.keys())
    assert isinstance(result["total"], int)
