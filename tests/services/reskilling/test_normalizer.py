from __future__ import annotations

import logging
from datetime import date
from typing import Any

import pytest

from src.services.reskilling.normalizer import normalize_row_response
from src.services.reskilling.schemas import ReskillingStatus


def _base_payload() -> dict[str, Any]:
    return {
        "res_id": "210513",
        "row": {
            "Risorsa:Consultant ID": "210513",
            "Nome Corso": "Kubernetes Fundamentals",
            "Skill Target": "kubernetes",
            "Stato": "In Progress",
            "Data Inizio": "2025-10-01",
            "Data Fine": "2026-01-15",
            "Provider": "CloudAcademy",
            "Percentuale Completamento": "75%",
        },
    }


def test_normalize_row_response__valid_payload__returns_record() -> None:
    record = normalize_row_response(_base_payload())

    assert record is not None
    assert record.res_id == 210513
    assert record.course_name == "Kubernetes Fundamentals"
    assert record.skill_target == "kubernetes"
    assert record.status == ReskillingStatus.IN_PROGRESS
    assert record.completion_pct == 75


def test_normalize_row_response__unknown_fields__logs_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    payload = _base_payload()
    payload["row"]["Extra Field"] = "ignored"

    with caplog.at_level(logging.WARNING):
        record = normalize_row_response(payload)

    assert record is not None
    assert any("Unknown reskilling fields" in message for message in caplog.messages)


def test_normalize_row_response__invalid_status__returns_none() -> None:
    payload = _base_payload()
    payload["row"]["Stato"] = "paused"

    record = normalize_row_response(payload)

    assert record is None


def test_normalize_row_response__timestamp_date__truncates_to_date() -> None:
    payload = _base_payload()
    payload["row"]["Data Inizio"] = "2025-10-01T12:34:56Z"

    record = normalize_row_response(payload)

    assert record is not None
    assert record.start_date == date(2025, 10, 1)


def test_normalize_row_response__completion_pct_float__normalizes() -> None:
    payload = _base_payload()
    payload["row"]["Percentuale Completamento"] = 0.8

    record = normalize_row_response(payload)

    assert record is not None
    assert record.completion_pct == 80
