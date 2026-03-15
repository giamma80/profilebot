from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

import pytest

from src.core.embedding.pipeline import EmbeddingPipeline
from src.core.parser.schemas import CVMetadata, ParsedCV
from src.core.skills import SkillExtractor
from src.core.skills.schemas import SkillExtractionResult
from src.services.availability.service import AvailabilityService
from src.services.embedding.freshness import FreshnessGate
from src.services.ingestion.profile_service import (
    ProfileIngestionDependencies,
    ProfileIngestionService,
)
from src.services.reskilling.service import ReskillingService
from src.services.scraper.client import ScraperClient


class DummyScraperClient:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.refreshed: list[int] = []
        self.downloaded: list[int] = []

    def refresh_inside_cv(self, res_id: int) -> None:
        self.refreshed.append(res_id)

    def download_inside_cv(self, res_id: int) -> bytes:
        self.downloaded.append(res_id)
        return self.payload

    def __enter__(self) -> DummyScraperClient:
        return self

    def __exit__(self, _exc_type, _exc, _traceback) -> None:
        return None


class DummyExtractor:
    def extract(self, parsed_cv: ParsedCV) -> SkillExtractionResult:
        return SkillExtractionResult(
            cv_id=parsed_cv.metadata.cv_id,
            normalized_skills=[],
            unknown_skills=[],
            dictionary_version="test",
        )


class DummyPipeline:
    def __init__(self) -> None:
        self.calls: list[int] = []

    def process_cv(
        self,
        parsed_cv: ParsedCV,
        skill_result: SkillExtractionResult,
        *,
        dry_run: bool = False,
    ) -> dict[str, int]:
        self.calls.append(parsed_cv.metadata.res_id)
        return {"cv_skills": 1, "cv_experiences": 2, "cv_chunks": 3, "total": 6}


class DummyGate:
    def __init__(self, *, is_fresh: bool = False) -> None:
        self.is_fresh_value = is_fresh
        self.acquired: list[int] = []
        self.released: list[int] = []

    def is_fresh(self, res_id: int) -> bool:
        return self.is_fresh_value

    def acquire(self, res_id: int) -> bool:
        self.acquired.append(res_id)
        return True

    def release(self, res_id: int) -> None:
        self.released.append(res_id)


@dataclass(frozen=True)
class DummyAvailabilityService:
    available: bool

    def get(self, _res_id: int) -> object | None:
        return object() if self.available else None


@dataclass(frozen=True)
class DummyReskillingService:
    available: bool

    def get(self, _res_id: int) -> object | None:
        return object() if self.available else None


def _parser(_docx_bytes: bytes, res_id: int) -> ParsedCV:
    return ParsedCV(
        metadata=CVMetadata(
            cv_id="cv-123",
            res_id=res_id,
            file_name="cv.docx",
        ),
        raw_text="",
    )


def test_ingest_res_id__success_returns_outcome() -> None:
    scraper = DummyScraperClient(b"docx")
    pipeline = DummyPipeline()
    service = ProfileIngestionService(
        dependencies=ProfileIngestionDependencies(
            scraper_client_factory=cast(Callable[[], ScraperClient], lambda: scraper),
            parser=_parser,
            extractor=cast(SkillExtractor, DummyExtractor()),
            pipeline=cast(EmbeddingPipeline, pipeline),
            freshness_gate=cast(FreshnessGate, DummyGate()),
            availability_service=cast(
                AvailabilityService, DummyAvailabilityService(available=True)
            ),
            reskilling_service=cast(ReskillingService, DummyReskillingService(available=False)),
        )
    )

    outcome = service.ingest_res_id(10)

    assert outcome.status == "success"
    assert outcome.res_id == 10
    assert outcome.cv_id == "cv-123"
    assert outcome.totals == {"cv_skills": 1, "cv_experiences": 2, "cv_chunks": 3, "total": 6}
    assert outcome.availability_cached is True
    assert outcome.reskilling_cached is False
    assert scraper.refreshed == [10]
    assert scraper.downloaded == [10]
    assert pipeline.calls == [10]


def test_ingest_res_id__freshness_skips_pipeline() -> None:
    scraper = DummyScraperClient(b"docx")
    service = ProfileIngestionService(
        dependencies=ProfileIngestionDependencies(
            scraper_client_factory=cast(Callable[[], ScraperClient], lambda: scraper),
            parser=_parser,
            extractor=cast(SkillExtractor, DummyExtractor()),
            pipeline=cast(EmbeddingPipeline, DummyPipeline()),
            freshness_gate=cast(FreshnessGate, DummyGate(is_fresh=True)),
            availability_service=cast(
                AvailabilityService, DummyAvailabilityService(available=False)
            ),
            reskilling_service=cast(ReskillingService, DummyReskillingService(available=False)),
        )
    )

    outcome = service.ingest_res_id(10)

    assert outcome.status == "skipped"
    assert outcome.reason == "freshness"
    assert scraper.refreshed == []
    assert scraper.downloaded == []


def test_ingest_res_id__invalid_res_id_raises() -> None:
    service = ProfileIngestionService(
        dependencies=ProfileIngestionDependencies(
            scraper_client_factory=cast(
                Callable[[], ScraperClient], lambda: DummyScraperClient(b"docx")
            ),
            parser=_parser,
            extractor=cast(SkillExtractor, DummyExtractor()),
            pipeline=cast(EmbeddingPipeline, DummyPipeline()),
            freshness_gate=cast(FreshnessGate, DummyGate()),
            availability_service=cast(
                AvailabilityService, DummyAvailabilityService(available=False)
            ),
            reskilling_service=cast(ReskillingService, DummyReskillingService(available=False)),
        )
    )

    with pytest.raises(ValueError):
        service.ingest_res_id(0)
