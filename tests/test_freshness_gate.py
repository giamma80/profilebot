"""Tests for freshness gate behavior."""

from __future__ import annotations

import time

from fakeredis import FakeRedis

from src.services.embedding.freshness import FreshnessGate


def test_freshness_gate__acquire_sets_key_and_reports_fresh() -> None:
    client = FakeRedis(decode_responses=True)
    gate = FreshnessGate(client=client, ttl_seconds=60, key_prefix="test:freshness")

    assert gate.is_fresh(1001) is False
    assert gate.acquire(1001) is True
    assert gate.is_fresh(1001) is True


def test_freshness_gate__lock_contention__second_acquire_fails() -> None:
    client = FakeRedis(decode_responses=True)
    gate = FreshnessGate(client=client, ttl_seconds=60, key_prefix="test:freshness")

    assert gate.acquire(2002) is True
    assert gate.acquire(2002) is False


def test_freshness_gate__ttl_expiry_allows_reacquire() -> None:
    client = FakeRedis(decode_responses=True)
    gate = FreshnessGate(client=client, ttl_seconds=1, key_prefix="test:freshness")

    assert gate.acquire(3003) is True
    time.sleep(1.1)
    assert gate.is_fresh(3003) is False
    assert gate.acquire(3003) is True
