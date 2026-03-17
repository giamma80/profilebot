"""Embedding pipeline orchestration for CV indexing."""

from __future__ import annotations

import logging
import os
import uuid
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime

from qdrant_client import QdrantClient, models

from src.core.embedding.chunk_pipeline import build_chunk_points
from src.core.embedding.service import EmbeddingService, OpenAIEmbeddingService
from src.core.parser.schemas import ExperienceItem, ParsedCV
from src.core.seniority.calculator import (
    calculate_seniority_bucket,
    calculate_total_experience_years,
)
from src.core.skills.enricher import enrich_skill_metadata
from src.core.skills.schemas import NormalizedSkill, SkillExtractionResult
from src.core.skills.weight import SkillWeight
from src.services.qdrant.client import get_qdrant_client
from src.services.qdrant.collections import ensure_collections

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExperienceCandidate:
    index: int
    experience: ExperienceItem
    text: str


class EmbeddingPipeline:
    """Orchestrate CV embedding and indexing in Qdrant.

    Args:
        embedding_service: Service used to generate embeddings.
        qdrant_client: Optional Qdrant client instance.
    """

    def __init__(
        self,
        embedding_service: EmbeddingService | None = None,
        qdrant_client: QdrantClient | None = None,
    ) -> None:
        self._embedding_service = embedding_service or OpenAIEmbeddingService()
        self._qdrant_client = qdrant_client or get_qdrant_client()
        ensure_collections(self._qdrant_client)

    def process_cv(
        self,
        parsed_cv: ParsedCV,
        skill_result: SkillExtractionResult,
        *,
        dry_run: bool = False,
    ) -> dict[str, int]:
        """Process a parsed CV and upsert embeddings into Qdrant.

        Args:
            parsed_cv: Parsed CV object from the parser.
            skill_result: Skill extraction result for the CV.
            dry_run: When True, compute points without upserting.

        Returns:
            A dict with counts of upserted points.
        """
        cv_id = parsed_cv.metadata.cv_id
        created_at = datetime.now(UTC)

        if not dry_run:
            self._delete_existing_points(parsed_cv.metadata.res_id)

        skills_points = self._build_skills_points(
            parsed_cv=parsed_cv,
            skill_result=skill_result,
            created_at=created_at,
        )
        experience_points = self._build_experience_points(
            parsed_cv=parsed_cv,
            skill_result=skill_result,
            created_at=created_at,
        )
        chunk_points = build_chunk_points(parsed_cv, self._embedding_service, created_at)

        total_points = len(skills_points) + len(experience_points) + len(chunk_points)
        if total_points == 0:
            logger.warning("No points to index for CV '%s'", cv_id)
            return {"cv_skills": 0, "cv_experiences": 0, "cv_chunks": 0, "total": 0}

        if dry_run:
            logger.info(
                "Dry-run enabled for CV '%s' (%d points)",
                cv_id,
                total_points,
            )
            return {
                "cv_skills": len(skills_points),
                "cv_experiences": len(experience_points),
                "cv_chunks": len(chunk_points),
                "total": total_points,
            }

        if skills_points:
            self._qdrant_client.upsert(
                collection_name="cv_skills",
                points=skills_points,
                wait=True,
            )

        if experience_points:
            self._qdrant_client.upsert(
                collection_name="cv_experiences",
                points=experience_points,
                wait=True,
            )

        if chunk_points:
            self._qdrant_client.upsert(
                collection_name="cv_chunks",
                points=chunk_points,
                wait=True,
            )

        logger.info(
            "Indexed CV '%s': %d points",
            cv_id,
            total_points,
        )
        return {
            "cv_skills": len(skills_points),
            "cv_experiences": len(experience_points),
            "cv_chunks": len(chunk_points),
            "total": total_points,
        }

    def _delete_existing_points(self, res_id: int) -> None:
        if not res_id:
            return
        selector = models.FilterSelector(
            filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="res_id",
                        match=models.MatchValue(value=res_id),
                    )
                ]
            )
        )
        for collection_name in ("cv_skills", "cv_experiences", "cv_chunks"):
            self._qdrant_client.delete(
                collection_name=collection_name,
                points_selector=selector,
                wait=True,
            )

    def _build_skills_points(
        self,
        parsed_cv: ParsedCV,
        skill_result: SkillExtractionResult,
        created_at: datetime,
    ) -> list[models.PointStruct]:
        """Build cv_skills points with enriched payload fields.

        Payload includes: cv_id, res_id, normalized_skills, skill_domain, seniority_bucket,
        dictionary_version, created_at, full_name, current_role, skill_details,
        unknown_skills, experiences_compact, years_experience_estimate.
        """
        cv_id = parsed_cv.metadata.cv_id
        if not skill_result.normalized_skills:
            logger.warning("CV '%s' has no skills, skipping cv_skills", cv_id)
            return []

        normalized_skills = _dedupe_skills(skill_result.normalized_skills)
        if not normalized_skills:
            logger.warning("CV '%s' has empty skill list, skipping cv_skills", cv_id)
            return []

        skills_text = ", ".join(normalized_skills).strip()
        if not skills_text:
            logger.warning("CV '%s' has empty skill text, skipping cv_skills", cv_id)
            return []

        vector = self._embedding_service.embed(skills_text)

        role_titles = [experience.role for experience in parsed_cv.experiences if experience.role]
        if parsed_cv.metadata.current_role:
            role_titles.append(parsed_cv.metadata.current_role)

        years_experience_estimate = calculate_total_experience_years(parsed_cv.experiences)
        seniority_bucket = calculate_seniority_bucket(
            years_experience_estimate,
            skill_result.skill_count,
            role_titles,
            summary_text=parsed_cv.raw_text,
        )

        weighted_skills = []
        for skill in skill_result.normalized_skills:
            metadata = enrich_skill_metadata(
                skill_name=skill.canonical,
                experiences=parsed_cv.experiences,
                certifications=parsed_cv.certifications,
            )
            weighted_skills.append(
                SkillWeight(
                    name=skill.canonical,
                    years=metadata["years"],
                    level=metadata["level"],
                    certified=metadata["certified"],
                    from_experience=metadata["years"] > 0.0,
                    years_factor=0.0,
                    cert_bonus=0.0,
                    weight=0.0,
                ).model_dump()
            )
        skill_details = [
            {
                "canonical": skill.canonical,
                "domain": skill.domain,
                "confidence": skill.confidence,
                "match_type": skill.match_type,
            }
            for skill in skill_result.normalized_skills
        ]
        experiences_compact = [
            {
                "company": experience.company,
                "role": experience.role,
                "start_year": experience.start_date.year if experience.start_date else None,
                "end_year": experience.end_date.year if experience.end_date else None,
                "is_current": experience.is_current,
                "description_summary": _summarize_description(experience.description),
            }
            for experience in parsed_cv.experiences
        ]

        payload = {
            "cv_id": cv_id,
            "res_id": parsed_cv.metadata.res_id,
            "section_type": "skills",
            "normalized_skills": normalized_skills,
            "skill_domain": _get_primary_domain(skill_result.normalized_skills),
            "domain_primary": _get_primary_domain(skill_result.normalized_skills),
            "seniority_bucket": seniority_bucket,
            "seniority": seniority_bucket,
            "dictionary_version": skill_result.dictionary_version,
            "total_experience_years": years_experience_estimate,
            "created_at": created_at,
            "ingested_at": created_at,
            "full_name": parsed_cv.metadata.full_name,
            "current_role": parsed_cv.metadata.current_role,
            "weighted_skills": weighted_skills,
            "skill_details": skill_details,
            "unknown_skills": skill_result.unknown_skills,
            "experiences_compact": experiences_compact,
            "years_experience_estimate": years_experience_estimate,
        }
        point_id = _generate_point_id(cv_id, "skills")
        return [models.PointStruct(id=point_id, vector=vector, payload=payload)]

    def _build_experience_points(
        self,
        parsed_cv: ParsedCV,
        skill_result: SkillExtractionResult,
        created_at: datetime,
    ) -> list[models.PointStruct]:
        cv_id = parsed_cv.metadata.cv_id
        candidates = _collect_experience_texts(parsed_cv.experiences)

        if not candidates:
            logger.warning("CV '%s' has no experience descriptions to embed", cv_id)
            return []

        related_skills = _dedupe_skills(skill_result.normalized_skills)

        points: list[models.PointStruct] = []
        for batch in _chunked(candidates, _get_batch_size()):
            texts = [item.text for item in batch]
            vectors = self._embedding_service.embed_batch(texts)

            if len(vectors) != len(texts):
                logger.warning(
                    "Embedding batch size mismatch for CV '%s': %d texts, %d vectors",
                    cv_id,
                    len(texts),
                    len(vectors),
                )

            for candidate, vector in zip(batch, vectors, strict=False):
                experience: ExperienceItem = candidate.experience
                index: int = candidate.index
                point_id = _generate_experience_id(cv_id, index)

                payload = {
                    "cv_id": cv_id,
                    "res_id": parsed_cv.metadata.res_id,
                    "section_type": "experience",
                    "related_skills": related_skills,
                    "experience_years": _calc_experience_years(experience),
                    "created_at": created_at,
                    "ingested_at": created_at,
                }
                points.append(models.PointStruct(id=point_id, vector=vector, payload=payload))

        return points


def _get_primary_domain(skills: Iterable[NormalizedSkill]) -> str:
    """Return the most common domain among normalized skills."""
    domain_list = [skill.domain for skill in skills if skill.domain]
    if not domain_list:
        return "unknown"
    most_common = Counter(domain_list).most_common(1)
    return most_common[0][0] if most_common else "unknown"


def _summarize_description(description: str, max_chars: int = 200) -> str:
    cleaned = description.strip()
    if not cleaned:
        return ""
    if len(cleaned) <= max_chars:
        return cleaned
    return f"{cleaned[:max_chars].rstrip()}..."


def _dedupe_skills(skills: Iterable[NormalizedSkill]) -> list[str]:
    """Return unique canonical skills preserving order."""
    seen: set[str] = set()
    deduped: list[str] = []
    for skill in skills:
        canonical = skill.canonical.strip().lower()
        if not canonical or canonical in seen:
            continue
        seen.add(canonical)
        deduped.append(canonical)
    return deduped


def _chunked(
    items: list[ExperienceCandidate],
    batch_size: int,
) -> Iterable[list[ExperienceCandidate]]:
    """Yield items in batches."""
    if batch_size <= 0:
        return
    for i in range(0, len(items), batch_size):
        yield items[i : i + batch_size]


def _get_batch_size() -> int:
    """Return embedding batch size from environment."""
    raw = os.getenv("EMBEDDING_BATCH_SIZE", "100")
    try:
        value = int(raw)
    except ValueError:
        value = 100
    return max(1, value)


def _calc_experience_years(experience: ExperienceItem) -> int | None:
    """Calculate experience years when dates are available."""
    if experience.start_date and experience.end_date:
        delta_days = (experience.end_date - experience.start_date).days
        return delta_days // 365 if delta_days >= 0 else None
    if experience.start_date and experience.is_current:
        delta_days = (date.today() - experience.start_date).days
        return delta_days // 365 if delta_days >= 0 else None
    return None


def _collect_experience_texts(experiences: list[ExperienceItem]) -> list[ExperienceCandidate]:
    """Collect experience descriptions for embedding."""
    collected: list[ExperienceCandidate] = []
    for index, experience in enumerate(experiences):
        text = experience.description.strip() if experience.description else ""
        if not text:
            continue
        collected.append(ExperienceCandidate(index=index, experience=experience, text=text))
    return collected


def _generate_point_id(cv_id: str, section: str) -> str:
    """Generate deterministic point IDs for idempotency."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{cv_id}:{section}"))


def _generate_experience_id(cv_id: str, index: int) -> str:
    """Generate deterministic experience IDs for idempotency."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{cv_id}:exp:{index}"))
