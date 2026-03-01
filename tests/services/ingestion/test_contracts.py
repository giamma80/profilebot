"""Tests for ingestion contracts and error hierarchy."""

from __future__ import annotations

from src.services.ingestion.contracts import IngestionSource
from src.services.ingestion.errors import (
    FetchError,
    IngestionError,
    NormalizationError,
    ValidationError,
)
from src.services.ingestion.schemas import NormalizedDocument


class _DummyAdapter:
    """Minimal adapter to verify IngestionSource protocol conformance."""

    @property
    def source_type(self) -> str:
        return "test"

    def fetch(self, identifier: str) -> bytes:
        return b"dummy"

    def validate(self, raw: bytes) -> bool:
        return True

    def normalize(self, identifier: str, raw: bytes) -> NormalizedDocument:
        raise NotImplementedError


def test_dummy_adapter__is_instance_of_ingestion_source() -> None:
    adapter = _DummyAdapter()
    assert isinstance(adapter, IngestionSource)


def test_error_hierarchy__fetch_error_is_ingestion_error() -> None:
    err = FetchError("fail", source_type="test")
    assert isinstance(err, IngestionError)
    assert err.source_type == "test"
    assert "fail" in str(err)


def test_error_hierarchy__validation_error_is_ingestion_error() -> None:
    err = ValidationError("bad format", source_type="docx_cv")
    assert isinstance(err, IngestionError)
    assert err.source_type == "docx_cv"


def test_error_hierarchy__normalization_error_is_ingestion_error() -> None:
    err = NormalizationError("parse failed")
    assert isinstance(err, IngestionError)
    assert err.source_type is None


def test_ingestion_error__without_source_type() -> None:
    err = IngestionError("generic")
    assert err.source_type is None
    assert str(err) == "generic"
