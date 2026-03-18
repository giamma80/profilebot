"""Tests for Celery embedding tasks with res_id handling."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import httpx
import pytest
from openai import RateLimitError

from src.core.parser.docx_parser import CVParseError
from src.services.embedding import tasks


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
    monkeypatch.setattr(tasks, "FreshnessGate", DummyFreshnessGate, raising=True)


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


def test_embed_cv_task__res_id_mismatch__logs_warning(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Log a warning when res_id differs from parsed value."""
    cv_path = tmp_path / "12345_mismatch.docx"
    cv_path.write_bytes(b"dummy")

    tasks.embed_cv_task.request.id = "task-mismatch"

    def _update_state(*, state: str, meta: dict[str, Any]) -> None:
        return None

    def _embed_cv(*_: Any, **__: Any) -> tuple[str, int, dict[str, int]]:
        return "cv-123", 12345, {"cv_skills": 1, "cv_experiences": 0, "total": 1}

    monkeypatch.setattr(tasks.embed_cv_task, "update_state", _update_state)
    monkeypatch.setattr(tasks, "_embed_cv", _embed_cv)

    with caplog.at_level(logging.WARNING, logger=tasks.__name__):
        tasks.embed_cv_task.run(cv_path=str(cv_path), res_id="99999")

    assert any("res_id mismatch" in record.getMessage() for record in caplog.records)


def test_embed_cv_task__rate_limit_error__retries_with_backoff(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Retry with backoff when OpenAI rate limit is hit."""
    cv_path = tmp_path / "12345_rate_limit.docx"
    cv_path.write_bytes(b"dummy")
    tasks.embed_cv_task.request.id = "task-rate-limit"
    captured: dict[str, int] = {}

    def _update_state(*, state: str, meta: dict[str, Any]) -> None:
        return None

    def _embed_cv(*_: Any, **__: Any) -> tuple[str, int, dict[str, int]]:
        response = httpx.Response(
            status_code=429,
            request=httpx.Request("POST", "https://api.openai.com/v1"),
        )
        raise RateLimitError("rate limit", response=response, body=None)

    def _retry(*, exc: Exception, countdown: int) -> Exception:
        captured["countdown"] = countdown
        raise exc

    monkeypatch.setattr(tasks.embed_cv_task, "update_state", _update_state)
    monkeypatch.setattr(tasks, "_embed_cv", _embed_cv)
    monkeypatch.setattr(tasks.embed_cv_task, "retry", _retry)

    with pytest.raises(RateLimitError):
        tasks.embed_cv_task.run(cv_path=str(cv_path), res_id="12345")

    assert captured["countdown"] == 60


def test_embed_batch_task__multiple_items__spawns_subtasks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Process multiple items and report progress per item."""
    first = tmp_path / "101_first.docx"
    second = tmp_path / "202_second.docx"
    first.write_bytes(b"dummy")
    second.write_bytes(b"dummy")

    calls: list[Path] = []
    states: list[dict[str, Any]] = []

    class DummyExtractor:
        def __init__(self, dictionary: object) -> None:
            self.dictionary = dictionary

    class DummyPipeline:
        def __init__(self) -> None:
            return None

    def _embed_cv(
        cv_path: Path,
        dictionary_path: str | None,
        dry_run: bool,
        *,
        extractor: object,
        pipeline: object,
    ) -> tuple[str, int, dict[str, int]]:
        calls.append(cv_path)
        parsed_res_id = int(cv_path.stem.split("_")[0])
        return (
            f"cv-{parsed_res_id}",
            parsed_res_id,
            {
                "cv_skills": 1,
                "cv_experiences": 0,
                "cv_chunks": 0,
                "total": 1,
            },
        )

    def _update_state(*, state: str, meta: dict[str, Any]) -> None:
        states.append(meta)

    monkeypatch.setattr(tasks, "load_skill_dictionary", lambda *_: {}, raising=True)
    monkeypatch.setattr(tasks, "SkillExtractor", DummyExtractor, raising=True)
    monkeypatch.setattr(tasks, "EmbeddingPipeline", DummyPipeline, raising=True)
    monkeypatch.setattr(tasks, "_embed_cv", _embed_cv, raising=True)
    monkeypatch.setattr(tasks.embed_batch_task, "update_state", _update_state, raising=True)

    items = [
        {"cv_path": str(first), "res_id": "101"},
        {"cv_path": str(second), "res_id": "202"},
    ]

    result = tasks.embed_batch_task.run(items=items)

    assert result["processed"] == 2
    assert result["failed"] == 0
    assert result["totals"]["total"] == 2
    assert len(calls) == 2
    assert states[-1]["percentage"] == 100


def test_embed_all_task__multiple_items__processes_all(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Process multiple items passed into the task."""
    filenames = ["101_alpha.docx", "102_beta.docx", "103_gamma.docx"]
    for name in filenames:
        (tmp_path / name).write_bytes(b"dummy")

    items = [
        {"cv_path": str(path), "res_id": path.stem.split("_")[0]}
        for path in sorted(tmp_path.glob("*.docx"))
    ]

    calls: list[Path] = []
    states: list[dict[str, Any]] = []

    class DummyExtractor:
        def __init__(self, dictionary: object) -> None:
            self.dictionary = dictionary

    class DummyPipeline:
        def __init__(self) -> None:
            return None

    def _embed_cv(
        cv_path: Path,
        dictionary_path: str | None,
        dry_run: bool,
        *,
        extractor: object,
        pipeline: object,
    ) -> tuple[str, int, dict[str, int]]:
        calls.append(cv_path)
        parsed_res_id = int(cv_path.stem.split("_")[0])
        return (
            f"cv-{parsed_res_id}",
            parsed_res_id,
            {
                "cv_skills": 1,
                "cv_experiences": 0,
                "cv_chunks": 0,
                "total": 1,
            },
        )

    def _update_state(*, state: str, meta: dict[str, Any]) -> None:
        states.append(meta)

    monkeypatch.setattr(tasks, "load_skill_dictionary", lambda *_: {}, raising=True)
    monkeypatch.setattr(tasks, "SkillExtractor", DummyExtractor, raising=True)
    monkeypatch.setattr(tasks, "EmbeddingPipeline", DummyPipeline, raising=True)
    monkeypatch.setattr(tasks, "_embed_cv", _embed_cv, raising=True)
    monkeypatch.setattr(tasks.embed_all_task, "update_state", _update_state, raising=True)

    result = tasks.embed_all_task.run(items=items, batch_size=2)

    assert result["processed"] == 3
    assert result["failed"] == 0
    assert result["totals"]["total"] == 3
    assert len(calls) == 3
    assert states[-1]["percentage"] == 100


def test_embed_from_scraper_task__skips_without_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _missing_base_url() -> None:
        return None

    monkeypatch.setattr(tasks, "_ensure_scraper_base_url", _missing_base_url, raising=True)

    result = tasks.embed_from_scraper_task.run()

    assert result == {
        "status": "skipped",
        "reason": "SCRAPER_BASE_URL not configured",
    }


def test_embed_from_scraper_task__processes_res_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _base_url() -> str:
        return "https://scraper"

    monkeypatch.setattr(tasks, "_ensure_scraper_base_url", _base_url, raising=True)
    tasks.embed_from_scraper_task.request.id = "task-embed"

    class FakeCache:
        def get_res_ids(self) -> list[int]:
            return [101, 202]

    class DummyClient:
        def __enter__(self) -> DummyClient:
            return self

        def __exit__(self, exc_type, exc, traceback) -> None:
            return None

        def download_inside_cv(self, res_id: int) -> bytes:
            return f"docx-{res_id}".encode()

    class DummyExtractor:
        def __init__(self, dictionary: object) -> None:
            self.calls: list[object] = []

        def extract(self, parsed_cv: object) -> str:
            self.calls.append(parsed_cv)
            return "skill-result"

    class DummyPipeline:
        def __init__(self) -> None:
            self.calls: list[tuple[object, str]] = []

        def process_cv(self, parsed_cv: object, skill_result: str) -> dict[str, int]:
            self.calls.append((parsed_cv, skill_result))
            return {"cv_skills": 1, "cv_experiences": 0, "total": 1}

    pipeline = DummyPipeline()
    extractor = DummyExtractor(dictionary={})
    states: list[dict[str, Any]] = []

    def _update_state(*, state: str, meta: dict[str, Any]) -> None:
        states.append({"state": state, "meta": meta})

    def _load_dict(*_: object) -> dict:
        return {}

    def _make_extractor(_: object) -> DummyExtractor:
        return extractor

    def _make_pipeline() -> DummyPipeline:
        return pipeline

    def _parse_docx_bytes(data: bytes, res_id: int, **_kwargs: object) -> tuple[bytes, int]:
        return data, res_id

    monkeypatch.setattr(tasks, "ScraperResIdCache", FakeCache, raising=True)
    monkeypatch.setattr(tasks, "ScraperClient", DummyClient, raising=True)
    monkeypatch.setattr(tasks, "load_skill_dictionary", _load_dict, raising=True)
    monkeypatch.setattr(tasks, "SkillExtractor", _make_extractor, raising=True)
    monkeypatch.setattr(tasks, "EmbeddingPipeline", _make_pipeline, raising=True)
    monkeypatch.setattr(tasks, "parse_docx_bytes", _parse_docx_bytes, raising=True)
    monkeypatch.setattr(tasks.embed_from_scraper_task, "update_state", _update_state, raising=True)

    result = tasks.embed_from_scraper_task.run()

    assert result["processed"] == 2
    assert result["failed"] == 0
    assert result["totals"]["total"] == 2
    assert pipeline.calls
    assert states[-1]["meta"]["processed"] == 2
    assert states[-1]["meta"]["failed"] == 0


def test_embed_from_scraper_task__uses_best_effort_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _base_url() -> str:
        return "https://scraper"

    monkeypatch.setattr(tasks, "_ensure_scraper_base_url", _base_url, raising=True)
    tasks.embed_from_scraper_task.request.id = "task-embed-results"

    class FakeCache:
        def get_res_ids(self) -> list[int]:
            raise AssertionError("cache should not be used")

    downloaded: list[int] = []

    class DummyClient:
        def __enter__(self) -> DummyClient:
            return self

        def __exit__(self, exc_type, exc, traceback) -> None:
            return None

        def download_inside_cv(self, res_id: int) -> bytes:
            downloaded.append(res_id)
            return f"docx-{res_id}".encode()

    class DummyExtractor:
        def __init__(self, dictionary: object) -> None:
            return None

        def extract(self, parsed_cv: object) -> str:
            return "skill-result"

    class DummyPipeline:
        def process_cv(self, parsed_cv: object, skill_result: str) -> dict[str, int]:
            return {"cv_skills": 1, "cv_experiences": 0, "total": 1}

    def _load_dict(*_: object) -> dict:
        return {}

    def _make_extractor(_: object) -> DummyExtractor:
        return DummyExtractor({})

    def _parse_docx_bytes(data: bytes, res_id: int, **_kwargs: object) -> tuple[bytes, int]:
        return data, res_id

    monkeypatch.setattr(tasks, "ScraperResIdCache", FakeCache, raising=True)
    monkeypatch.setattr(tasks, "ScraperClient", DummyClient, raising=True)
    monkeypatch.setattr(tasks, "load_skill_dictionary", _load_dict, raising=True)
    monkeypatch.setattr(tasks, "SkillExtractor", _make_extractor, raising=True)
    monkeypatch.setattr(tasks, "EmbeddingPipeline", DummyPipeline, raising=True)
    monkeypatch.setattr(tasks, "parse_docx_bytes", _parse_docx_bytes, raising=True)

    results = [
        {"res_id": 10, "status": "success"},
        {"res_id": 20, "status": "failed"},
        {"res_id": 30},
    ]

    result = tasks.embed_from_scraper_task.run(_results=results)

    assert result["processed"] == 2
    assert result["failed"] == 0
    assert downloaded == [10, 30]


def test_embed_from_scraper_task__continues_on_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _base_url() -> str:
        return "https://scraper"

    monkeypatch.setattr(tasks, "_ensure_scraper_base_url", _base_url, raising=True)

    class FakeCache:
        def get_res_ids(self) -> list[int]:
            return [1, 2, 3]

    class DummyClient:
        def __enter__(self) -> DummyClient:
            return self

        def __exit__(self, exc_type, exc, traceback) -> None:
            return None

        def download_inside_cv(self, res_id: int) -> bytes:
            if res_id == 2:
                raise RuntimeError("boom")
            return f"docx-{res_id}".encode()

    class DummyExtractor:
        def __init__(self, dictionary: object) -> None:
            return None

        def extract(self, parsed_cv: object) -> str:
            return "skill-result"

    class DummyPipeline:
        def process_cv(self, parsed_cv: object, skill_result: str) -> dict[str, int]:
            return {"cv_skills": 1, "cv_experiences": 0, "total": 1}

    def _load_dict(*_: object) -> dict:
        return {}

    def _make_extractor(_: object) -> DummyExtractor:
        return DummyExtractor({})

    def _parse_docx_bytes(data: bytes, res_id: int, **_kwargs: object) -> tuple[bytes, int]:
        return data, res_id

    monkeypatch.setattr(tasks, "ScraperResIdCache", FakeCache, raising=True)
    monkeypatch.setattr(tasks, "ScraperClient", DummyClient, raising=True)
    monkeypatch.setattr(tasks, "load_skill_dictionary", _load_dict, raising=True)
    monkeypatch.setattr(tasks, "SkillExtractor", _make_extractor, raising=True)
    monkeypatch.setattr(tasks, "EmbeddingPipeline", DummyPipeline, raising=True)
    monkeypatch.setattr(tasks, "parse_docx_bytes", _parse_docx_bytes, raising=True)

    result = tasks.embed_from_scraper_task.run()

    assert result["processed"] == 2
    assert result["failed"] == 1
    assert result["errors"][0]["res_id"] == 2
