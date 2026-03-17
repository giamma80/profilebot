"""Profile analysis service orchestration."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError
from qdrant_client import QdrantClient, models

from src.core.config import Settings, get_settings
from src.core.llm.client import LLMDecisionClient, create_llm_client
from src.core.llm.schemas import LLMRequest
from src.services.analysis.schemas import ProfileAnalysisLLMOutput
from src.services.qdrant.client import get_qdrant_client
from src.services.reskilling.service import ReskillingService
from src.utils.normalization import normalize_string_list

logger = logging.getLogger(__name__)

CV_SKILLS_COLLECTION = "cv_skills"
CV_EXPERIENCES_COLLECTION = "cv_experiences"
LLM_TIMEOUT_SECONDS = 4.0
LLM_MAX_TOKENS = 500
MATCH_SCORE_MIN_WEIGHT = 0.3
TOP_SKILLS_LIMIT = 10
QDRANT_SCROLL_LIMIT = 128

SYSTEM_PROMPT = (
    "Sei un assistente che produce analisi profilo strutturate.\n"
    "Restituisci SOLO un oggetto JSON con le chiavi richieste.\n"
    "Non inventare: se i dati non sono sufficienti, usa null.\n"
)

USER_PROMPT_TEMPLATE = (
    "Dati profilo:\n"
    "skills_context: {skills_context}\n"
    "experience_context: {experience_context}\n"
    "reskilling_context: {reskilling_context}\n\n"
    "Genera JSON con le chiavi:\n"
    "{{\n"
    '  "skill_gaps": ["skill1", "skill2"] or null,\n'
    '  "analysis_notes": "string" or null,\n'
    '  "reskilling_summary": "string" or null\n'
    "}}\n"
    "Skill gaps: skill complementari tipiche per un profilo con queste top_skills e seniority.\n"
    "Analysis notes: sintetizza l'esperienza in modo neutro e basato sui dati forniti.\n"
)


class ProfileAnalysisNotFoundError(Exception):
    """Raised when profile data is not found in Qdrant."""


class ProfileAnalysisUnavailableError(Exception):
    """Raised when profile data cannot be retrieved due to upstream errors."""


class ProfileAnalysisService:
    """Service orchestrating profile analysis retrieval and LLM enrichment."""

    def __init__(
        self,
        *,
        qdrant_client: QdrantClient | None = None,
        llm_client: LLMDecisionClient | None = None,
        settings: Settings | None = None,
        reskilling_service: ReskillingService | None = None,
    ) -> None:
        resolved_settings = settings or get_settings()
        self._qdrant_client = qdrant_client or get_qdrant_client()
        self._reskilling_service = reskilling_service or ReskillingService()
        self._llm_client = llm_client or LLMDecisionClient(
            client=create_llm_client(resolved_settings, timeout=LLM_TIMEOUT_SECONDS),
            settings=resolved_settings,
        )

    def get_analysis(self, res_id: int) -> dict[str, Any]:
        """Return profile analysis for a given res_id."""
        if res_id < 1:
            raise ValueError("res_id must be positive")

        skills_payload = self._fetch_latest_skills_payload(res_id)
        if skills_payload is None:
            raise ProfileAnalysisNotFoundError("res_id not found")

        cv_id = _extract_payload_str(skills_payload, "cv_id")
        experience_payloads = self._fetch_experiences_payloads(res_id, cv_id)

        weighted_skills = _extract_weighted_skills(skills_payload)
        top_skills = _extract_top_skills(weighted_skills, TOP_SKILLS_LIMIT)
        match_score = _calculate_match_score(weighted_skills)
        seniority_inferred = _extract_payload_str(skills_payload, "seniority_bucket")

        experience_summaries = _extract_experience_summaries(skills_payload)
        experience_links = _extract_experience_links(experience_payloads)

        reskilling_record = _safe_fetch_reskilling(self._reskilling_service, res_id)

        llm_output = self._get_llm_output(
            top_skills=top_skills,
            seniority_inferred=seniority_inferred,
            experience_summaries=experience_summaries,
            experience_links=experience_links,
            reskilling_record=reskilling_record,
        )

        if reskilling_record is None and llm_output is not None:
            llm_output.reskilling_summary = None

        return {
            "res_id": res_id,
            "seniority_inferred": seniority_inferred,
            "top_skills": top_skills,
            "skill_gaps": llm_output.skill_gaps if llm_output else None,
            "reskilling_summary": llm_output.reskilling_summary if llm_output else None,
            "match_score": match_score,
            "analysis_notes": llm_output.analysis_notes if llm_output else None,
        }

    def _fetch_latest_skills_payload(self, res_id: int) -> dict[str, Any] | None:
        records = self._scroll_collection(
            collection_name=CV_SKILLS_COLLECTION,
            scroll_filter=_build_res_id_filter(res_id),
        )
        if not records:
            return None
        return _select_latest_payload(records)

    def _fetch_experiences_payloads(
        self,
        res_id: int,
        cv_id: str | None,
    ) -> list[dict[str, Any]]:
        if cv_id is None:
            return []
        records = self._scroll_collection(
            collection_name=CV_EXPERIENCES_COLLECTION,
            scroll_filter=_build_res_id_cv_id_filter(res_id, cv_id),
        )
        return [payload for payload in (_extract_payload(record) for record in records) if payload]

    def _scroll_collection(
        self,
        *,
        collection_name: str,
        scroll_filter: models.Filter,
    ) -> list[Any]:
        records: list[Any] = []
        offset: Any | None = None
        try:
            while True:
                if offset is None:
                    batch, next_offset = self._qdrant_client.scroll(
                        collection_name=collection_name,
                        scroll_filter=scroll_filter,
                        limit=QDRANT_SCROLL_LIMIT,
                        with_payload=True,
                        with_vectors=False,
                    )
                else:
                    batch, next_offset = self._qdrant_client.scroll(
                        collection_name=collection_name,
                        scroll_filter=scroll_filter,
                        limit=QDRANT_SCROLL_LIMIT,
                        with_payload=True,
                        with_vectors=False,
                        offset=offset,
                    )
                records.extend(batch)
                if next_offset is None:
                    break
                offset = next_offset
        except Exception as exc:
            logger.exception("Qdrant scroll failed for %s: %s", collection_name, exc)
            raise ProfileAnalysisUnavailableError("Qdrant unavailable") from exc
        return records

    def _get_llm_output(
        self,
        *,
        top_skills: list[str],
        seniority_inferred: str | None,
        experience_summaries: list[dict[str, Any]],
        experience_links: list[dict[str, Any]],
        reskilling_record: Any | None,
    ) -> ProfileAnalysisLLMOutput | None:
        if (
            not top_skills
            and not experience_summaries
            and not experience_links
            and reskilling_record is None
        ):
            return None

        skills_context = {
            "top_skills": top_skills,
            "seniority_inferred": seniority_inferred,
        }
        experience_context = {
            "experience_summaries": experience_summaries,
            "experience_links": experience_links,
        }
        reskilling_context = (
            reskilling_record.model_dump() if reskilling_record is not None else None
        )

        request = LLMRequest(
            system_prompt=SYSTEM_PROMPT,
            context="",
            user_prompt=USER_PROMPT_TEMPLATE.format(
                skills_context=json.dumps(skills_context, ensure_ascii=False),
                experience_context=json.dumps(experience_context, ensure_ascii=False),
                reskilling_context=json.dumps(reskilling_context, ensure_ascii=False),
            ),
            temperature=0.0,
            max_tokens=LLM_MAX_TOKENS,
        )

        try:
            raw_content = self._llm_client.chat_completion_raw(request)
            return _parse_llm_output(raw_content)
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            logger.warning("Profile analysis LLM parsing failed: %s", exc)
        except Exception as exc:
            logger.warning("Profile analysis LLM call failed: %s", exc)
        return None


def _build_res_id_filter(res_id: int) -> models.Filter:
    return models.Filter(
        must=[
            models.FieldCondition(
                key="res_id",
                match=models.MatchValue(value=res_id),
            )
        ]
    )


def _build_res_id_cv_id_filter(res_id: int, cv_id: str) -> models.Filter:
    return models.Filter(
        must=[
            models.FieldCondition(
                key="res_id",
                match=models.MatchValue(value=res_id),
            ),
            models.FieldCondition(
                key="cv_id",
                match=models.MatchValue(value=cv_id),
            ),
        ]
    )


def _extract_payload(record: Any) -> dict[str, Any] | None:
    if isinstance(record, dict):
        payload = record.get("payload")
        return payload if isinstance(payload, dict) else None
    payload = getattr(record, "payload", None)
    return payload if isinstance(payload, dict) else None


def _select_latest_payload(records: list[Any]) -> dict[str, Any] | None:
    latest_payload: dict[str, Any] | None = None
    latest_ts: datetime | None = None
    for record in records:
        payload = _extract_payload(record)
        if not payload:
            continue
        ts = _coerce_datetime(payload.get("ingested_at")) or _coerce_datetime(
            payload.get("created_at")
        )
        if ts is None:
            ts = datetime.min.replace(tzinfo=UTC)
        if latest_ts is None or ts > latest_ts:
            latest_ts = ts
            latest_payload = payload
    return latest_payload


def _coerce_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        if cleaned.endswith("Z"):
            cleaned = cleaned[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(cleaned)
            return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            return None
    return None


def _extract_weighted_skills(payload: dict[str, Any]) -> list[tuple[str, float]]:
    raw = payload.get("weighted_skills")
    if not isinstance(raw, list):
        return []
    collected: list[tuple[str, float]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = item.get("skill_name") or item.get("name")
        if not isinstance(name, str):
            continue
        cleaned = name.strip().lower()
        if not cleaned:
            continue
        weight = item.get("weight")
        if not isinstance(weight, int | float):
            continue
        collected.append((cleaned, float(weight)))
    return collected


def _extract_top_skills(weighted_skills: list[tuple[str, float]], limit: int) -> list[str]:
    ordered = sorted(weighted_skills, key=lambda item: item[1], reverse=True)
    result: list[str] = []
    seen: set[str] = set()
    for name, _weight in ordered:
        if name in seen:
            continue
        seen.add(name)
        result.append(name)
        if len(result) >= limit:
            break
    return result


def _calculate_match_score(weighted_skills: list[tuple[str, float]]) -> float:
    weights = [weight for _name, weight in weighted_skills if weight > MATCH_SCORE_MIN_WEIGHT]
    if not weights:
        return 0.0
    avg_weight = sum(weights) / len(weights)
    max_weight = max(weights)
    if max_weight <= 0.0:
        return 0.0
    # Formula: avg_weight / max_weight (weights > threshold). Limitation: uniform low weights can yield 1.0.
    normalized = avg_weight / max_weight
    if normalized < 0.0:
        return 0.0
    if normalized > 1.0:
        return 1.0
    return normalized


def _extract_experience_summaries(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw = payload.get("experiences_compact")
    if not isinstance(raw, list):
        return []
    summaries: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        summary = {
            "company": item.get("company") if isinstance(item.get("company"), str) else None,
            "role": item.get("role") if isinstance(item.get("role"), str) else None,
            "start_year": item.get("start_year")
            if isinstance(item.get("start_year"), int)
            else None,
            "end_year": item.get("end_year") if isinstance(item.get("end_year"), int) else None,
            "is_current": bool(item.get("is_current")),
            "description_summary": _normalize_optional_string(item.get("description_summary")),
        }
        summaries.append(summary)
    return summaries


def _extract_experience_links(payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    links: list[dict[str, Any]] = []
    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        experience_years = payload.get("experience_years")
        if not isinstance(experience_years, int | float):
            experience_years = None
        related_skills = payload.get("related_skills")
        normalized_skills = (
            normalize_string_list(related_skills) if isinstance(related_skills, list) else None
        )
        links.append(
            {
                "experience_years": experience_years,
                "related_skills": normalized_skills,
            }
        )
    return links


def _parse_llm_output(raw_content: str) -> ProfileAnalysisLLMOutput:
    payload = json.loads(raw_content)
    if not isinstance(payload, dict):
        raise ValueError("Profile analysis payload is not a JSON object")
    skill_gaps = payload.get("skill_gaps")
    normalized_gaps = normalize_string_list(skill_gaps) if isinstance(skill_gaps, list) else None
    analysis_notes = _normalize_optional_string(payload.get("analysis_notes"))
    reskilling_summary = _normalize_optional_string(payload.get("reskilling_summary"))
    return ProfileAnalysisLLMOutput(
        skill_gaps=normalized_gaps or None,
        analysis_notes=analysis_notes,
        reskilling_summary=reskilling_summary,
    )


def _normalize_optional_string(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if not cleaned or cleaned.lower() in {"null", "none"}:
        return None
    return cleaned


def _extract_payload_str(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _safe_fetch_reskilling(service: ReskillingService, res_id: int) -> Any | None:
    try:
        return service.get(res_id)
    except Exception as exc:
        logger.warning("Reskilling fetch failed for res_id %s: %s", res_id, exc)
        return None


__all__ = [
    "ProfileAnalysisNotFoundError",
    "ProfileAnalysisService",
    "ProfileAnalysisUnavailableError",
]
