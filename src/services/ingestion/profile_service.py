"""Profile ingestion service orchestrator."""

from __future__ import annotations

import functools
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from src.core.embedding.pipeline import EmbeddingPipeline
from src.core.parser import parse_docx_bytes
from src.core.parser.schemas import ParsedCV
from src.core.redis_utils import build_docx_redis_client
from src.core.skills import SkillExtractor, load_skill_dictionary
from src.services.availability.service import AvailabilityService
from src.services.embedding.freshness import FreshnessGate
from src.services.reskilling.service import ReskillingService
from src.services.scraper.client import ScraperClient

logger = logging.getLogger(__name__)

DEFAULT_DICTIONARY_PATH = "data/skills_dictionary.yaml"


@dataclass(frozen=True)
class IngestionOutcome:
    """Outcome summary for a single res_id ingestion."""

    status: Literal["success", "skipped"]
    res_id: int
    cv_id: str | None
    totals: dict[str, int] | None
    availability_cached: bool
    reskilling_cached: bool
    reason: str | None = None


@dataclass(frozen=True)
class ProfileIngestionDependencies:
    """Optional dependencies for ProfileIngestionService."""

    scraper_client_factory: Callable[[], ScraperClient] | None = None
    parser: Callable[[bytes, int], ParsedCV | None] | None = None
    extractor: SkillExtractor | None = None
    pipeline: EmbeddingPipeline | None = None
    freshness_gate: FreshnessGate | None = None
    availability_service: AvailabilityService | None = None
    reskilling_service: ReskillingService | None = None
    dictionary_path: str | None = None


class ProfileIngestionService:
    """Service that ingests a single profile end-to-end."""

    def __init__(
        self,
        *,
        dependencies: ProfileIngestionDependencies | None = None,
    ) -> None:
        deps = dependencies or ProfileIngestionDependencies()
        self._scraper_client_factory = deps.scraper_client_factory or ScraperClient
        if deps.parser is not None:
            self._parser = deps.parser
        else:
            redis_client = build_docx_redis_client()
            self._parser = functools.partial(parse_docx_bytes, redis_client=redis_client)
        extractor = deps.extractor
        if extractor is None:
            dictionary = load_skill_dictionary(_resolve_dictionary_path(deps.dictionary_path))
            extractor = SkillExtractor(dictionary)
        self._extractor = extractor
        self._pipeline = deps.pipeline or EmbeddingPipeline()
        self._freshness_gate = deps.freshness_gate or FreshnessGate()
        self._availability_service = deps.availability_service or AvailabilityService()
        self._reskilling_service = deps.reskilling_service or ReskillingService()

    def ingest_res_id(self, res_id: int, *, force: bool = False) -> IngestionOutcome:
        """Ingest a single profile by res_id.

        Args:
            res_id: Resource identifier.
            force: When True, bypass the freshness gate.

        Returns:
            IngestionOutcome with summary and cache flags.

        Raises:
            ValueError: When res_id is invalid.
            Exception: Propagates underlying ingestion failures.
        """
        if not res_id or res_id <= 0:
            raise ValueError("res_id must be a positive integer")

        if not self._acquire_freshness(res_id, force=force):
            return IngestionOutcome(
                status="skipped",
                res_id=res_id,
                cv_id=None,
                totals=None,
                availability_cached=False,
                reskilling_cached=False,
                reason="freshness",
            )

        try:
            with self._scraper_client_factory() as client:
                client.refresh_inside_cv(res_id)
                docx_bytes = client.download_inside_cv(res_id)

            parsed_cv = self._parser(docx_bytes, res_id)
            if parsed_cv is None:
                logger.info("Ingestion skipped (cache_hit) for res_id %s", res_id)
                return IngestionOutcome(
                    status="skipped",
                    res_id=res_id,
                    cv_id=None,
                    totals=None,
                    availability_cached=False,
                    reskilling_cached=False,
                    reason="cache_hit",
                )
            skills_keywords_count = (
                len(parsed_cv.skills.skill_keywords)
                if parsed_cv.skills and parsed_cv.skills.skill_keywords
                else 0
            )
            skills_raw_text_len = (
                len(parsed_cv.skills.raw_text.strip())
                if parsed_cv.skills and parsed_cv.skills.raw_text
                else 0
            )
            experiences_total = len(parsed_cv.experiences)
            experiences_with_description = sum(
                1
                for experience in parsed_cv.experiences
                if experience.description and experience.description.strip()
            )
            raw_text_len = len(parsed_cv.raw_text.strip()) if parsed_cv.raw_text else 0
            if skills_keywords_count == 0 and skills_raw_text_len == 0:
                logger.warning(
                    "Parsed CV '%s' has no skill sources: raw_text_len=%d experiences=%d experiences_with_description=%d",
                    parsed_cv.metadata.cv_id,
                    raw_text_len,
                    experiences_total,
                    experiences_with_description,
                )
            if experiences_total > 0 and experiences_with_description == 0:
                logger.warning(
                    "Parsed CV '%s' has experiences without descriptions: experiences=%d",
                    parsed_cv.metadata.cv_id,
                    experiences_total,
                )
            skill_result = self._extractor.extract(parsed_cv)
            if not skill_result.normalized_skills:
                logger.warning(
                    "Extracted skills empty for CV '%s': unknown=%d",
                    parsed_cv.metadata.cv_id,
                    len(skill_result.unknown_skills),
                )
            totals = self._pipeline.process_cv(parsed_cv, skill_result)

            availability = self._availability_service.get(res_id)
            reskilling = self._reskilling_service.get(res_id)

            return IngestionOutcome(
                status="success",
                res_id=res_id,
                cv_id=parsed_cv.metadata.cv_id,
                totals=totals,
                availability_cached=availability is not None,
                reskilling_cached=reskilling is not None,
            )
        except Exception:
            self._freshness_gate.release(res_id)
            logger.exception("Failed ingestion for res_id %s", res_id)
            raise

    def _acquire_freshness(self, res_id: int, *, force: bool = False) -> bool:
        if force:
            self._freshness_gate.release(res_id)
            return self._freshness_gate.acquire(res_id)
        if self._freshness_gate.is_fresh(res_id):
            return False
        return self._freshness_gate.acquire(res_id)


def _resolve_dictionary_path(dictionary_path: str | None) -> Path:
    env_path = os.getenv("SKILLS_DICTIONARY_PATH")
    raw_path = dictionary_path or env_path or DEFAULT_DICTIONARY_PATH
    return Path(raw_path)
