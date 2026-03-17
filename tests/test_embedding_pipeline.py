from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import date, datetime
from unittest.mock import MagicMock

import pytest

from src.core.embedding.pipeline import EmbeddingPipeline, _generate_point_id
from src.core.embedding.service import EmbeddingService
from src.core.parser.schemas import CVMetadata, ExperienceItem, ParsedCV, SkillSection
from src.core.skills.schemas import NormalizedSkill, SkillExtractionResult


@pytest.fixture(autouse=True)
def _stub_ensure_collections(monkeypatch):
    monkeypatch.setattr("src.core.embedding.pipeline.ensure_collections", lambda *_: None)


class DummyEmbeddingService(EmbeddingService):
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

    def embed_batch(self, texts: Iterable[str]) -> list[list[float]]:
        batch = list(texts)
        self.embed_batch_calls.append(batch)
        return [[0.1, 0.2, 0.3] for _ in batch]


def _make_parsed_cv() -> ParsedCV:
    metadata = CVMetadata(
        cv_id="cv-123",
        res_id=12345,
        file_name="cv.docx",
        full_name="Mario Rossi",
        current_role="Senior Engineer",
    )
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


def test_process_cv__dry_run__returns_counts_and_skips_upsert() -> None:
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
    assert result["cv_chunks"] == 1
    assert result["total"] == 4
    qdrant_client.upsert.assert_not_called()


def test_process_cv__no_skills__skips_cv_skills() -> None:
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
    assert result["cv_chunks"] == 1
    assert result["total"] == 3
    assert embedding_service.embed_calls == []


def _run_pipeline_for_upsert() -> tuple[dict[str, int], list]:
    parsed_cv = _make_parsed_cv()
    skill_result = _make_skill_result()
    embedding_service = DummyEmbeddingService()
    qdrant_client = MagicMock()

    pipeline = EmbeddingPipeline(
        embedding_service=embedding_service,
        qdrant_client=qdrant_client,
    )

    result = pipeline.process_cv(parsed_cv, skill_result, dry_run=False)
    return result, qdrant_client.upsert.call_args_list


def test_process_cv__upsert_counts__includes_all_collections() -> None:
    result, calls = _run_pipeline_for_upsert()

    assert result["total"] == 4
    assert len(calls) == 3


def test_process_cv__upsert_uses_wait_false() -> None:
    _, calls = _run_pipeline_for_upsert()

    waits = [call.kwargs["wait"] for call in calls]
    assert all(wait is False for wait in waits)


def test_process_cv__upsert_payloads__include_skills_fields() -> None:
    _, calls = _run_pipeline_for_upsert()

    cv_skills_points = calls[0].kwargs["points"]
    assert len(cv_skills_points) == 1
    cv_skills_payload = cv_skills_points[0].payload
    assert cv_skills_payload["cv_id"] == "cv-123"
    assert cv_skills_payload["res_id"] == 12345
    assert cv_skills_payload["section_type"] == "skills"
    assert cv_skills_payload["dictionary_version"] == "1.0.0"
    assert cv_skills_payload["skill_domain"] == "backend"
    assert cv_skills_payload["seniority_bucket"] in {"junior", "mid", "senior", "lead"}
    assert cv_skills_payload["seniority"] in {"junior", "mid", "senior", "lead"}
    assert isinstance(cv_skills_payload["created_at"], datetime)
    assert cv_skills_payload["full_name"] == "Mario Rossi"
    assert cv_skills_payload["current_role"] == "Senior Engineer"
    assert isinstance(cv_skills_payload["skill_details"], list)
    assert cv_skills_payload["unknown_skills"] == []
    assert isinstance(cv_skills_payload["experiences_compact"], list)
    assert cv_skills_payload["years_experience_estimate"] is not None
    weighted_skills = cv_skills_payload["weighted_skills"]
    assert isinstance(weighted_skills, list)
    assert weighted_skills
    sample_weight = weighted_skills[0]
    assert "weight" in sample_weight
    assert "years_factor" in sample_weight
    assert "cert_bonus" in sample_weight
    assert "skill_name" in sample_weight or "name" in sample_weight


def test_process_cv__upsert_payloads__include_chunks_and_experiences_fields() -> None:
    _, calls = _run_pipeline_for_upsert()

    cv_chunks_points = calls[2].kwargs["points"]
    assert len(cv_chunks_points) == 1
    chunk_payload = cv_chunks_points[0].payload
    assert chunk_payload["cv_id"] == "cv-123"
    assert chunk_payload["res_id"] == 12345
    assert chunk_payload["section_type"]
    assert chunk_payload["chunk_text"]
    assert chunk_payload["text_preview"]

    cv_exp_points = calls[1].kwargs["points"]
    assert len(cv_exp_points) == 2
    for payload in (point.payload for point in cv_exp_points):
        assert payload["cv_id"] == "cv-123"
        assert payload["res_id"] == 12345
        assert payload["section_type"] == "experience"
        assert isinstance(payload["created_at"], datetime)

    experience_years = [point.payload["experience_years"] for point in cv_exp_points]
    assert experience_years[0] == 2
    assert experience_years[1] >= 0


def test_process_cv__dedupes_skills_in_payload() -> None:
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


def test_process_cv__no_experience_texts__skips_experience_points() -> None:
    metadata = CVMetadata(cv_id="cv-123", res_id=12345, file_name="cv.docx")
    skills = SkillSection(raw_text="Python", skill_keywords=["Python"])
    experiences = [
        ExperienceItem(
            company="Acme",
            role="Engineer",
            start_date=date(2020, 1, 1),
            end_date=date(2022, 1, 1),
            description="",
            is_current=False,
        )
    ]
    parsed_cv = ParsedCV(
        metadata=metadata,
        skills=skills,
        experiences=experiences,
        education=[],
        certifications=[],
        raw_text="",
    )
    skill_result = _make_skill_result()
    embedding_service = DummyEmbeddingService()
    qdrant_client = MagicMock()

    pipeline = EmbeddingPipeline(
        embedding_service=embedding_service,
        qdrant_client=qdrant_client,
    )

    result = pipeline.process_cv(parsed_cv, skill_result, dry_run=True)

    assert result["cv_skills"] == 1
    assert result["cv_experiences"] == 0
    assert result["cv_chunks"] == 1
    assert result["total"] == 2


def test_process_cv__no_skills_and_no_experiences__returns_zero() -> None:
    metadata = CVMetadata(cv_id="cv-123", res_id=12345, file_name="cv.docx")
    skills = SkillSection(raw_text="", skill_keywords=[])
    parsed_cv = ParsedCV(
        metadata=metadata,
        skills=skills,
        experiences=[],
        education=[],
        certifications=[],
        raw_text="",
    )
    skill_result = SkillExtractionResult(
        cv_id="cv-123",
        normalized_skills=[],
        unknown_skills=[],
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
    assert result["cv_experiences"] == 0
    assert result["cv_chunks"] == 0
    assert result["total"] == 0


def test_process_cv__experience_years_handles_current_date() -> None:
    metadata = CVMetadata(cv_id="cv-123", res_id=12345, file_name="cv.docx")
    skills = SkillSection(raw_text="Python", skill_keywords=["Python"])
    experiences = [
        ExperienceItem(
            company="Acme",
            role="Engineer",
            start_date=date(2024, 1, 1),
            end_date=None,
            description="Built APIs",
            is_current=True,
        )
    ]
    parsed_cv = ParsedCV(
        metadata=metadata,
        skills=skills,
        experiences=experiences,
        education=[],
        certifications=[],
        raw_text="",
    )
    skill_result = _make_skill_result()
    embedding_service = DummyEmbeddingService()
    qdrant_client = MagicMock()

    pipeline = EmbeddingPipeline(
        embedding_service=embedding_service,
        qdrant_client=qdrant_client,
    )

    pipeline.process_cv(parsed_cv, skill_result, dry_run=False)

    cv_exp_points = qdrant_client.upsert.call_args_list[1].kwargs["points"]
    experience_years = cv_exp_points[0].payload["experience_years"]
    assert experience_years is not None
    assert experience_years >= 0


def test_generate_point_id__same_inputs__returns_stable_id() -> None:
    expected = str(uuid.uuid5(uuid.NAMESPACE_URL, "cv-123:skills"))
    assert _generate_point_id("cv-123", "skills") == expected
    assert _generate_point_id("cv-123", "skills") == expected
