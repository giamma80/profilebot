from __future__ import annotations

import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from celery.exceptions import MaxRetriesExceededError

from src.core.config import Settings
from src.core.embedding import pipeline as embedding_pipeline
from src.core.embedding.pipeline import EmbeddingPipeline
from src.core.embedding.service import EmbeddingService
from src.core.knowledge_profile import builder as kp_builder
from src.core.parser.schemas import CVMetadata, ParsedCV
from src.core.skills.schemas import NormalizedSkill, SkillExtractionResult
from src.services.availability.schemas import AvailabilityStatus, ProfileAvailability
from src.services.embedding import tasks as embedding_tasks
from src.services.matching.candidate_ranker import build_candidates_context_structured
from src.services.matching.schemas import JDAnalysis
from src.services.reskilling.schemas import ReskillingRecord, ReskillingStatus
from src.services.scraper import tasks as scraper_tasks
from src.services.search.skill_search import ProfileMatch, SearchDependencies, search_by_skills

SCRAPER_DLQ_QUEUE = "scraper.dlq"


class DummyFreshnessGate:
    def __init__(self, *args: object, **kwargs: object) -> None:
        return None

    def is_fresh(self, res_id: int) -> bool:
        return False

    def acquire(self, res_id: int) -> bool:
        return True

    def release(self, res_id: int) -> None:
        return None


@pytest.fixture(autouse=True)
def _disable_freshness_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(embedding_tasks, "FreshnessGate", DummyFreshnessGate, raising=True)


@dataclass
class FakeResIdCache:
    stored: list[int] = field(default_factory=list)

    def set_res_ids(self, res_ids: list[int]) -> None:
        self.stored = res_ids

    def get_res_ids(self) -> list[int]:
        return list(self.stored)


class FakeScraperClient:
    def __init__(self, data_by_res_id: dict[int, bytes]) -> None:
        self._data_by_res_id = data_by_res_id
        self.downloaded: list[int] = []

    def __enter__(self) -> FakeScraperClient:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def fetch_inside_res_ids(self) -> list[int]:
        return list(self._data_by_res_id.keys())

    def refresh_inside_cv(self, res_id: int) -> None:
        return None

    def download_inside_cv(self, res_id: int) -> bytes:
        self.downloaded.append(res_id)
        return self._data_by_res_id[res_id]

    def export_availability_csv(self) -> None:
        return None

    def export_reskilling_csv(self) -> None:
        return None


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


@dataclass
class DummyScoredPoint:
    payload: dict[str, Any]
    score: float


class FakeQdrantClient:
    def __init__(self) -> None:
        self.points_by_collection: dict[str, list[Any]] = {}

    def upsert(self, *, collection_name: str, points: list[Any], wait: bool = True) -> None:
        self.points_by_collection.setdefault(collection_name, []).extend(points)

    def delete(
        self,
        *,
        collection_name: str,
        points_selector: Any,
        wait: bool = True,
    ) -> None:
        return None

    def search(
        self,
        *,
        collection_name: str,
        query_vector: list[float],
        query_filter: Any | None,
        limit: int,
        with_payload: bool = True,
    ) -> list[DummyScoredPoint]:
        points = self.points_by_collection.get(collection_name, [])[:limit]
        return [DummyScoredPoint(payload=point.payload, score=0.9) for point in points]


class FakeSkillExtractor:
    def __init__(self, dictionary: Any) -> None:
        self._dictionary = dictionary

    def extract(self, parsed_cv: ParsedCV) -> SkillExtractionResult:
        normalized_skills = [
            NormalizedSkill(
                original="python",
                canonical="python",
                domain="backend",
                confidence=0.9,
                match_type="exact",
            )
        ]
        return SkillExtractionResult(
            cv_id=parsed_cv.metadata.cv_id,
            normalized_skills=normalized_skills,
            unknown_skills=[],
            dictionary_version="test",
        )


def _make_parsed_cv(res_id: int) -> ParsedCV:
    metadata = CVMetadata(
        cv_id=f"cv-{res_id}",
        res_id=res_id,
        file_name=f"{res_id}.docx",
        full_name="Test User",
        current_role="Backend Engineer",
    )
    return ParsedCV(
        metadata=metadata,
        skills=None,
        experiences=[],
        education=[],
        certifications=[],
        raw_text="",
    )


def test_pipeline_complete__fetch_fanout_best_effort_embed_search(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    res_ids = [101, 202]
    data_by_res_id = dict.fromkeys(res_ids, b"cv-bytes")
    fake_cache = FakeResIdCache()

    monkeypatch.setattr(scraper_tasks, "_ensure_scraper_base_url", lambda: "http://scraper")
    monkeypatch.setattr(scraper_tasks, "ScraperResIdCache", lambda: fake_cache, raising=True)
    monkeypatch.setattr(
        scraper_tasks,
        "ScraperClient",
        lambda: FakeScraperClient(data_by_res_id),
        raising=True,
    )

    fetch_result = scraper_tasks.scraper_inside_refresh_task.run()

    assert fetch_result["status"] == "success"
    assert fake_cache.get_res_ids() == res_ids

    fake_qdrant = FakeQdrantClient()
    monkeypatch.setattr(embedding_pipeline, "ensure_collections", lambda *_: None, raising=True)

    pipeline = EmbeddingPipeline(
        embedding_service=DummyEmbeddingService(),
        qdrant_client=fake_qdrant,
    )

    monkeypatch.setattr(embedding_tasks, "_ensure_scraper_base_url", lambda: "http://scraper")
    monkeypatch.setattr(
        embedding_tasks,
        "ScraperClient",
        lambda: FakeScraperClient(data_by_res_id),
        raising=True,
    )
    monkeypatch.setattr(
        embedding_tasks,
        "parse_docx_bytes",
        lambda _data, res_id, filename=None, **_kwargs: _make_parsed_cv(res_id),
        raising=True,
    )
    monkeypatch.setattr(embedding_tasks, "SkillExtractor", FakeSkillExtractor, raising=True)
    monkeypatch.setattr(embedding_tasks, "load_skill_dictionary", lambda _: {}, raising=True)
    monkeypatch.setattr(embedding_tasks, "EmbeddingPipeline", lambda: pipeline, raising=True)

    results = [{"res_id": res_id, "status": "success"} for res_id in res_ids]
    embed_result = embedding_tasks.embed_from_scraper_task.run(_results=results, _errors=[])

    assert embed_result["status"] == "completed"
    assert embed_result["processed"] == len(res_ids)

    time.sleep(0.2)  # eventual consistency — tipicamente < 100ms
    dependencies = SearchDependencies(
        qdrant_client=fake_qdrant,
        embedding_service=DummyEmbeddingService(),
    )
    response = search_by_skills(["python"], limit=10, dependencies=dependencies)

    assert response.total == len(res_ids)
    assert all(match.payload and match.payload.get("skill_details") for match in response.results)


def test_pipeline_partial_failure__chord_continues_with_successes_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    res_ids = [101, 202, 303]
    data_by_res_id = dict.fromkeys(res_ids, b"cv-bytes")
    fake_scraper = FakeScraperClient(data_by_res_id)

    fake_qdrant = FakeQdrantClient()
    monkeypatch.setattr(embedding_pipeline, "ensure_collections", lambda *_: None, raising=True)

    pipeline = EmbeddingPipeline(
        embedding_service=DummyEmbeddingService(),
        qdrant_client=fake_qdrant,
    )

    monkeypatch.setattr(embedding_tasks, "_ensure_scraper_base_url", lambda: "http://scraper")
    monkeypatch.setattr(embedding_tasks, "ScraperClient", lambda: fake_scraper, raising=True)
    monkeypatch.setattr(
        embedding_tasks,
        "parse_docx_bytes",
        lambda _data, res_id, filename=None, **_kwargs: _make_parsed_cv(res_id),
        raising=True,
    )
    monkeypatch.setattr(embedding_tasks, "SkillExtractor", FakeSkillExtractor, raising=True)
    monkeypatch.setattr(embedding_tasks, "load_skill_dictionary", lambda _: {}, raising=True)
    monkeypatch.setattr(embedding_tasks, "EmbeddingPipeline", lambda: pipeline, raising=True)

    results = [
        {"res_id": 101, "status": "success"},
        {"res_id": 202, "status": "failed"},
        {"res_id": 303, "status": "success"},
    ]
    embed_result = embedding_tasks.embed_from_scraper_task.run(_results=results, _errors=[])

    assert embed_result["processed"] == 2
    assert embed_result["failed"] == 0
    assert set(fake_scraper.downloaded) == {101, 303}


def test_pipeline_dlq__max_retries_exceeded_sends_dlq(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(scraper_tasks, "_ensure_scraper_base_url", lambda: "http://scraper")

    class FailingScraperClient:
        def __enter__(self) -> FailingScraperClient:
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def refresh_inside_cv(self, res_id: int) -> None:
            raise httpx.ConnectError("boom", request=httpx.Request("POST", "http://scraper"))

    captured: dict[str, Any] = {}

    def _send_task(name: str, *args: Any, **options: Any) -> None:
        captured["name"] = name
        captured["queue"] = options.get("queue")
        captured["kwargs"] = options.get("kwargs", {})

    def _retry(*, exc: Exception, **_: Any) -> None:
        raise MaxRetriesExceededError()

    monkeypatch.setattr(scraper_tasks, "ScraperClient", FailingScraperClient, raising=True)
    monkeypatch.setattr(scraper_tasks.celery_app, "send_task", _send_task, raising=True)
    monkeypatch.setattr(
        scraper_tasks.scraper_inside_refresh_item_task,
        "retry",
        _retry,
        raising=True,
    )

    with pytest.raises(MaxRetriesExceededError):
        scraper_tasks.scraper_inside_refresh_item_task.run(res_id=999)

    assert captured["name"] == "scraper.refresh_inside_profile_dlq"
    assert captured["queue"] == SCRAPER_DLQ_QUEUE
    assert captured["kwargs"]["res_id"] == 999
    assert captured["kwargs"]["error_type"] == "ConnectError"


def test_kp_context__structured_matching_context_includes_sections(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeAvailabilityService:
        def get(self, res_id: int) -> ProfileAvailability | None:
            return ProfileAvailability(
                res_id=res_id,
                status=AvailabilityStatus.FREE,
                allocation_pct=0,
                current_project=None,
                available_from=None,
                available_to=None,
                manager_name="Manager",
                updated_at=datetime.now(UTC),
            )

    class FakeReskillingService:
        def get(self, res_id: int) -> ReskillingRecord | None:
            return ReskillingRecord(
                res_id=res_id,
                course_name="Kubernetes Fundamentals",
                skill_target="kubernetes",
                status=ReskillingStatus.IN_PROGRESS,
                start_date=None,
                end_date=None,
                provider="CloudAcademy",
                completion_pct=70,
            )

    monkeypatch.setattr(kp_builder, "AvailabilityService", FakeAvailabilityService, raising=True)
    monkeypatch.setattr(kp_builder, "ReskillingService", FakeReskillingService, raising=True)

    payload = {
        "full_name": "Test User",
        "current_role": "Backend Engineer",
        "skill_details": [
            {
                "canonical": "python",
                "domain": "backend",
                "confidence": 0.9,
                "match_type": "exact",
            }
        ],
        "unknown_skills": [],
        "experiences_compact": [
            {
                "company": "Acme",
                "role": "Backend Engineer",
                "start_year": 2020,
                "end_year": 2022,
                "is_current": False,
                "description_summary": "Built Python services with FastAPI.",
            }
        ],
        "years_experience_estimate": 4,
    }

    search_results = [
        ProfileMatch(
            res_id=1001,
            cv_id="cv-1001",
            score=0.9,
            matched_skills=["python"],
            missing_skills=["aws"],
            skill_domain="backend",
            seniority="mid",
            payload=payload,
        )
    ]

    jd_analysis = JDAnalysis(
        must_have=["python"],
        nice_to_have=["aws"],
        seniority="mid",
        domain="backend",
    )
    settings = Settings(llm_max_tokens=2000)

    context = build_candidates_context_structured(
        jd_analysis=jd_analysis,
        search_results=search_results,
        settings=settings,
    )

    assert "═══ CANDIDATO" in context
    assert "▸ DISPONIBILITÀ" in context
    assert "▸ RESKILLING ATTIVO" in context
    assert "▸ SKILL MATCHATE" in context
