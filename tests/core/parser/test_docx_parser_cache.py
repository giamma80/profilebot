from __future__ import annotations

import hashlib
from io import BytesIO
from unittest.mock import Mock, patch

import redis
from docx import Document

from src.core.parser.docx_parser import DocxParser


def _make_docx_bytes(text: str) -> bytes:
    document = Document()
    document.add_paragraph(text)
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_parse_bytes__cache_hit__returns_none_and_skips_parsing() -> None:
    data = b"cached-docx"
    res_id = 12
    expected_hash = hashlib.sha256(data).hexdigest()
    redis_client = Mock()
    redis_client.get.return_value = expected_hash
    parser = DocxParser(redis_client=redis_client)

    with patch("src.core.parser.docx_parser.Document") as document_mock:
        parsed = parser.parse_bytes(data, res_id)

    assert parsed is None
    document_mock.assert_not_called()
    redis_client.get.assert_called_once_with("cv_hash:12")
    redis_client.setex.assert_not_called()


def test_parse_bytes__cache_miss__parses_and_sets_hash() -> None:
    data = _make_docx_bytes("Test CV")
    res_id = 34
    redis_client = Mock()
    redis_client.get.return_value = None
    parser = DocxParser(redis_client=redis_client)

    with patch("src.core.parser.docx_parser.os.getenv", return_value="86400"):
        parsed = parser.parse_bytes(data, res_id)

    assert parsed is not None
    assert parsed.metadata.res_id == res_id
    expected_hash = hashlib.sha256(data).hexdigest()
    redis_client.setex.assert_called_once_with("cv_hash:34", 86400, expected_hash)


def test_parse_bytes__hash_changed__parses_and_updates_hash() -> None:
    data = _make_docx_bytes("Test CV")
    res_id = 56
    redis_client = Mock()
    redis_client.get.return_value = "old-hash"
    parser = DocxParser(redis_client=redis_client)

    with patch("src.core.parser.docx_parser.os.getenv", return_value="86400"):
        parsed = parser.parse_bytes(data, res_id)

    assert parsed is not None
    expected_hash = hashlib.sha256(data).hexdigest()
    redis_client.setex.assert_called_once_with("cv_hash:56", 86400, expected_hash)


def test_parse_bytes__redis_unavailable__parses_without_error() -> None:
    data = _make_docx_bytes("Test CV")
    res_id = 78
    redis_client = Mock()
    redis_client.get.side_effect = redis.RedisError("down")
    redis_client.setex.side_effect = redis.RedisError("down")
    parser = DocxParser(redis_client=redis_client)

    parsed = parser.parse_bytes(data, res_id)

    assert parsed is not None
