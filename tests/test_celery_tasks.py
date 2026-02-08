"""Tests for Celery embedding tasks with res_id handling."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from src.core.parser.docx_parser import CVParseError
from src.services.embedding import tasks


def test_embed_cv_task__valid_res_id__returns_res_id_and_sets_progress(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Return parsed res_id and report progress metadata."""
    cv_path = tmp_path / "12345_mario_rossi.docx"
    cv_path.write_bytes(b"dummy")

    tasks.embed_cv_task.request.id = "task-12345"
    states: list[dict[str, Any]] = []

    def _update_state(*, state: str, meta: dict[str, Any]) -> None:
        states.append({"state": state, "meta": meta})

    def _embed_cv(*_: Any, **__: Any) -> tuple[str, int, dict[str, int]]:
        return "cv-123", 12345, {"cv_skills": 1, "cv_experiences": 2, "total": 3}

    monkeypatch.setattr(tasks.embed_cv_task, "update_state", _update_state)
    monkeypatch.setattr(tasks, "_embed_cv", _embed_cv)

    result = tasks.embed_cv_task.run(cv_path=str(cv_path), res_id="12345")

    assert result["res_id"] == 12345
    assert result["cv_id"] == "cv-123"
    assert states
    assert states[0]["meta"]["res_id"] == "12345"
    assert states[-1]["meta"]["res_id"] == 12345


def test_embed_cv_task__invalid_filename__raises_cv_parse_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Raise CVParseError when filename lacks res_id prefix."""
    cv_path = tmp_path / "mario_rossi.docx"
    cv_path.write_bytes(b"dummy")

    tasks.embed_cv_task.request.id = "task-invalid"

    def _update_state(*, state: str, meta: dict[str, Any]) -> None:
        return None

    def _embed_cv(*_: Any, **__: Any) -> tuple[str, int, dict[str, int]]:
        raise CVParseError(f"res_id mancante nel filename: {cv_path.name}")

    def _retry(*, exc: Exception, countdown: int) -> Exception:
        raise exc

    monkeypatch.setattr(tasks.embed_cv_task, "update_state", _update_state)
    monkeypatch.setattr(tasks, "_embed_cv", _embed_cv)
    monkeypatch.setattr(tasks.embed_cv_task, "retry", _retry)

    with pytest.raises(CVParseError):
        tasks.embed_cv_task.run(cv_path=str(cv_path), res_id="99999")


def test_embed_cv_task__progress_meta__includes_parsed_res_id(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Include parsed res_id in progress metadata."""
    cv_path = tmp_path / "99999_a_b.docx"
    cv_path.write_bytes(b"dummy")

    tasks.embed_cv_task.request.id = "task-99999"
    states: list[dict[str, Any]] = []

    def _update_state(*, state: str, meta: dict[str, Any]) -> None:
        states.append({"state": state, "meta": meta})

    def _embed_cv(*_: Any, **__: Any) -> tuple[str, int, dict[str, int]]:
        return "cv-999", 99999, {"cv_skills": 1, "cv_experiences": 0, "total": 1}

    monkeypatch.setattr(tasks.embed_cv_task, "update_state", _update_state)
    monkeypatch.setattr(tasks, "_embed_cv", _embed_cv)

    result = tasks.embed_cv_task.run(cv_path=str(cv_path), res_id="99999")

    assert result["res_id"] == 99999
    assert states[-1]["meta"]["res_id"] == 99999
