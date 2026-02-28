"""Reskilling row normalizer."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import date, datetime
from typing import Any

from src.services.reskilling.schemas import ReskillingRecord, ReskillingStatus

logger = logging.getLogger(__name__)


def _normalize_key(value: str) -> str:
    return value.strip().lower()


RES_ID_KEYS = (
    "risorsa:consultant id",
    "consultant id",
    "resid",
    "res_id",
)

COURSE_NAME_KEYS = (
    "course_name",
    "course name",
    "nome corso",
    "titolo corso",
    "corso",
    "training",
    "percorso",
)

SKILL_TARGET_KEYS = (
    "skill_target",
    "skill target",
    "target skill",
    "competenza",
    "competenza target",
    "skill",
)

STATUS_KEYS = (
    "status",
    "stato",
    "course status",
)

START_DATE_KEYS = (
    "start_date",
    "start date",
    "data inizio",
    "inizio",
)

END_DATE_KEYS = (
    "end_date",
    "end date",
    "data fine",
    "fine",
)

PROVIDER_KEYS = (
    "provider",
    "training provider",
    "ente",
    "fornitore",
)

COMPLETION_KEYS = (
    "completion_pct",
    "completion pct",
    "completion %",
    "completion",
    "percentuale completamento",
    "percentuale",
)

UPDATED_AT_KEYS = (
    "updated_at",
    "last updated",
    "ultima modifica",
)

IGNORED_KEYS = ("risorsa",)

KNOWN_KEYS = {
    _normalize_key(key)
    for key in (
        *RES_ID_KEYS,
        *COURSE_NAME_KEYS,
        *SKILL_TARGET_KEYS,
        *STATUS_KEYS,
        *START_DATE_KEYS,
        *END_DATE_KEYS,
        *PROVIDER_KEYS,
        *COMPLETION_KEYS,
        *UPDATED_AT_KEYS,
        *IGNORED_KEYS,
    )
}


def normalize_row_response(payload: dict[str, Any]) -> ReskillingRecord | None:
    """Normalize the scraper RowResponse payload into a reskilling record."""
    if not isinstance(payload, dict):
        logger.warning("Invalid reskilling payload: %s", payload)
        return None

    row = payload.get("row")
    if not isinstance(row, dict):
        logger.warning("Invalid reskilling row for payload: %s", payload)
        return None

    res_id = _coerce_int(payload.get("res_id"))
    return normalize_reskilling_row(row, res_id=res_id)


def normalize_reskilling_row(
    row: dict[str, Any],
    *,
    res_id: int | None = None,
) -> ReskillingRecord | None:
    """Normalize a raw SharePoint row into a reskilling record."""
    normalized_row = _normalize_row(row)
    unknown_keys = _unknown_keys(row)
    if unknown_keys:
        logger.warning(
            "Unknown reskilling fields for res_id '%s': %s",
            res_id or "unknown",
            ", ".join(unknown_keys),
        )

    resolved_res_id = res_id or _coerce_int(_get_first_value(normalized_row, RES_ID_KEYS))
    if not resolved_res_id:
        logger.warning("Skipping reskilling row: missing res_id")
        return None

    course_name = _coerce_str(_get_first_value(normalized_row, COURSE_NAME_KEYS))
    if not course_name:
        logger.warning(
            "Skipping reskilling row for res_id '%s': missing course_name", resolved_res_id
        )
        return None

    status_value = _coerce_str(_get_first_value(normalized_row, STATUS_KEYS))
    status = _coerce_status(status_value)
    if status is None:
        logger.warning(
            "Skipping reskilling row for res_id '%s': invalid status=%s",
            resolved_res_id,
            status_value,
        )
        return None

    skill_target = _coerce_str(_get_first_value(normalized_row, SKILL_TARGET_KEYS))
    provider = _coerce_str(_get_first_value(normalized_row, PROVIDER_KEYS))
    start_date = _coerce_date(_get_first_value(normalized_row, START_DATE_KEYS))
    end_date = _coerce_date(_get_first_value(normalized_row, END_DATE_KEYS))
    completion_pct = _coerce_pct(_get_first_value(normalized_row, COMPLETION_KEYS))

    try:
        return ReskillingRecord(
            res_id=resolved_res_id,
            course_name=course_name,
            skill_target=skill_target,
            status=status,
            start_date=start_date,
            end_date=end_date,
            provider=provider,
            completion_pct=completion_pct,
        )
    except ValueError as exc:
        logger.warning(
            "Skipping reskilling row for res_id '%s': %s",
            resolved_res_id,
            exc,
        )
        return None


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in row.items():
        if not isinstance(key, str):
            continue
        normalized[_normalize_key(key)] = value
    return normalized


def _unknown_keys(row: dict[str, Any]) -> list[str]:
    unknown: list[str] = []
    for key in row:
        if not isinstance(key, str):
            continue
        if _normalize_key(key) not in KNOWN_KEYS:
            unknown.append(key)
    return unknown


def _get_first_value(normalized_row: dict[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        normalized_key = _normalize_key(key)
        if normalized_key in normalized_row:
            return normalized_row[normalized_key]
    return None


def _coerce_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, list | tuple | set):
        cleaned = ", ".join([str(item).strip() for item in value if str(item).strip()])
        return cleaned or None
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    cleaned = str(value).strip()
    return cleaned or None


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    try:
        return int(str(value).strip())
    except (ValueError, TypeError):
        return None


def _coerce_status(value: str | None) -> ReskillingStatus | None:
    if value is None:
        return None
    cleaned = value.strip().lower()
    if not cleaned:
        return None

    mapping = {
        "in_progress": ReskillingStatus.IN_PROGRESS,
        "in progress": ReskillingStatus.IN_PROGRESS,
        "ongoing": ReskillingStatus.IN_PROGRESS,
        "completed": ReskillingStatus.COMPLETED,
        "done": ReskillingStatus.COMPLETED,
        "finished": ReskillingStatus.COMPLETED,
        "planned": ReskillingStatus.PLANNED,
        "scheduled": ReskillingStatus.PLANNED,
    }
    if cleaned in mapping:
        return mapping[cleaned]

    try:
        return ReskillingStatus(cleaned)
    except ValueError:
        return None


def _coerce_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    cleaned = str(value).strip()
    if not cleaned:
        return None
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1]
    if "T" in cleaned:
        cleaned = cleaned.split("T")[0]
    if "+" in cleaned:
        cleaned = cleaned.split("+")[0]
    try:
        return date.fromisoformat(cleaned)
    except ValueError:
        return None


def _normalize_pct_value(value: float) -> int:
    if value <= 1.0:
        return round(value * 100)
    return round(value)


def _coerce_pct(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return _normalize_pct_value(value)
    cleaned = str(value).strip()
    if not cleaned:
        return None
    cleaned = cleaned.replace("%", "").replace(",", ".").strip()
    try:
        parsed = float(cleaned)
    except ValueError:
        return None
    return _normalize_pct_value(parsed)


__all__ = ["normalize_reskilling_row", "normalize_row_response"]
