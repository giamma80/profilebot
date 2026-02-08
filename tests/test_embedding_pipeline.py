from __future__ import annotations

from datetime import date, datetime
from unittest.mock import MagicMock

import pytest

from src.core.embedding.pipeline import EmbeddingPipeline
from src.core.parser.schemas import CVMetadata, ExperienceItem, ParsedCV, SkillSection
from src.core.skills.schemas import NormalizedSkill, SkillExtractionResult


@pytest.fixture(autouse=True)
def _stub_ensure_collections(monkeypatch):
    monkeypatch.setattr("src.core.embedding.pipeline.ensure_collections", lambda *_: None)


class DummyEmbeddingService:
    def __init__(self) -> None:
        self._model = "text-embedding-3-small"
        self._dimensions = 3
        self.embed_calls: list[str] = []
        self.embed_batch_calls: list[list[str]] = []

    @property
    def model(self) -> str:
        return self._model

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed(self, text: str) -> list[float]:
        self.embed_calls.append(text)
        return [0.1, 0.2, 0.3]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        self.embed_batch_calls.append(texts)
        return [[0.1, 0.2, 0.3] for _ in texts]


def _make_parsed_cv() -> ParsedCV:
    metadata = CVMetadata(cv_id="cv-123", res_id=12345, file_name="cv.docx")
    skills = SkillSection(raw_text="Python, FastAPI", skill_keywords=["Python", "FastAPI"])
    experiences = [
        ExperienceItem(
            company="Acme",
            role="Engineer",
            start_date=date(2020, 1, 1),
            end_date=date(2022, 1, 1),
            description="Built APIs",
            is_current=False,
        ),
        ExperienceItem(
            company="Beta",
            role="Senior Engineer",
            start_date=date(2022, 2, 1),
            end_date=None,
            description="Leading backend team",
            is_current=True,
        ),
    ]
    return ParsedCV(
        metadata=metadata,
        skills=skills,
        experiences=experiences,
        education=[],
        certifications=[],
        raw_text="",
    )


def _make_skill_result() -> SkillExtractionResult:
    skills = [
        NormalizedSkill(
            original="Python",
            canonical="python",
            domain="backend",
            confidence=1.0,
            match_type="exact",
        ),
        NormalizedSkill(
            original="FastAPI",
            canonical="fastapi",
            domain="backend",
            confidence=1.0,
            match_type="exact",
        ),
        NormalizedSkill(
            original="PostgreSQL",
            canonical="postgresql",
            domain="data",
            confidence=1.0,
            match_type="exact",
        ),
    ]
    return SkillExtractionResult(
        cv_id="cv-123",
        normalized_skills=skills,
        unknown_skills=[],
        dictionary_version="1.0.0",
    )


def test_process_cv__dry_run__returns_counts_and_skips_upsert(monkeypatch):
    parsed_cv = _make_parsed_cv()
    skill_result = _make_skill_result()
    embedding_service = DummyEmbeddingService()
    qdrant_client = MagicMock()

    pipeline = EmbeddingPipeline(
        embedding_service=embedding_service,
        qdrant_client=qdrant_client,
    )

    result = pipeline.process_cv(parsed_cv, skill_result, dry_run=True)

    assert result["cv_skills"] == 1
    assert result["cv_experiences"] == 2
    assert result["total"] == 3
    qdrant_client.upsert.assert_not_called()


def test_process_cv__no_skills__skips_cv_skills(monkeypatch):
    parsed_cv = _make_parsed_cv()
    skill_result = SkillExtractionResult(
        cv_id="cv-123",
        normalized_skills=[],
        unknown_skills=["x"],
        dictionary_version="1.0.0",
    )
    embedding_service = DummyEmbeddingService()
    qdrant_client = MagicMock()

    pipeline = EmbeddingPipeline(
        embedding_service=embedding_service,
        qdrant_client=qdrant_client,
    )

    result = pipeline.process_cv(parsed_cv, skill_result, dry_run=True)

    assert result["cv_skills"] == 0
    assert result["cv_experiences"] == 2
    assert result["total"] == 2
    assert embedding_service.embed_calls == []


def test_process_cv__upsert_payloads__include_expected_fields(monkeypatch):
    parsed_cv = _make_parsed_cv()
    skill_result = _make_skill_result()
    embedding_service = DummyEmbeddingService()
    qdrant_client = MagicMock()

    pipeline = EmbeddingPipeline(
        embedding_service=embedding_service,
        qdrant_client=qdrant_client,
    )

    result = pipeline.process_cv(parsed_cv, skill_result, dry_run=False)

    assert result["total"] == 3
    assert qdrant_client.upsert.call_count == 2

    cv_skills_call = qdrant_client.upsert.call_args_list[0]
    cv_experiences_call = qdrant_client.upsert.call_args_list[1]

    cv_skills_points = cv_skills_call.kwargs["points"]
    assert len(cv_skills_points) == 1
    cv_skills_payload = cv_skills_points[0].payload
    assert cv_skills_payload["cv_id"] == "cv-123"
    assert cv_skills_payload["res_id"] == 12345
    assert cv_skills_payload["section_type"] == "skills"
    assert cv_skills_payload["dictionary_version"] == "1.0.0"
    assert cv_skills_payload["skill_domain"] == "backend"
    assert cv_skills_payload["seniority_bucket"] == "unknown"
    assert isinstance(cv_skills_payload["created_at"], datetime)

    cv_exp_points = cv_experiences_call.kwargs["points"]
    assert len(cv_exp_points) == 2
    for payload in (point.payload for point in cv_exp_points):
        assert payload["cv_id"] == "cv-123"
        assert payload["res_id"] == 12345
        assert payload["section_type"] == "experience"
        assert isinstance(payload["created_at"], datetime)

    experience_years = [point.payload["experience_years"] for point in cv_exp_points]
    assert experience_years[0] == 2
    assert experience_years[1] >= 0


def test_process_cv__dedupes_skills_in_payload(monkeypatch):
    parsed_cv = _make_parsed_cv()
    skills = [
        NormalizedSkill(
            original="Python",
            canonical="python",
            domain="backend",
            confidence=1.0,
            match_type="exact",
        ),
        NormalizedSkill(
            original="PYTHON",
            canonical="python",
            domain="backend",
            confidence=1.0,
            match_type="exact",
        ),
    ]
    skill_result = SkillExtractionResult(
        cv_id="cv-123",
        normalized_skills=skills,
        unknown_skills=[],
        dictionary_version="1.0.0",
    )
    embedding_service = DummyEmbeddingService()
    qdrant_client = MagicMock()

    pipeline = EmbeddingPipeline(
        embedding_service=embedding_service,
        qdrant_client=qdrant_client,
    )

    pipeline.process_cv(parsed_cv, skill_result, dry_run=False)

    cv_skills_points = qdrant_client.upsert.call_args_list[0].kwargs["points"]
    payload = cv_skills_points[0].payload
    assert payload["normalized_skills"] == ["python"]
