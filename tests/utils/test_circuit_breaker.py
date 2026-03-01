"""Tests for circuit breaker state machine."""

from __future__ import annotations

import time

import pytest

from src.utils.circuit_breaker import CircuitBreaker, CircuitBreakerOpen, CircuitState


def test_initial_state_is_closed() -> None:
    cb = CircuitBreaker("test", failure_threshold=3, reset_timeout_s=10)
    assert cb.state == CircuitState.CLOSED


def test_success__keeps_closed() -> None:
    cb = CircuitBreaker("test", failure_threshold=3)
    cb.record_success()
    assert cb.state == CircuitState.CLOSED
    assert cb._failure_count == 0


def test_failures_below_threshold__stays_closed() -> None:
    cb = CircuitBreaker("test", failure_threshold=3)
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitState.CLOSED
    assert cb._failure_count == 2


def test_failures_at_threshold__trips_open() -> None:
    cb = CircuitBreaker("test", failure_threshold=3)
    cb.record_failure()
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitState.OPEN


def test_open__rejects_requests() -> None:
    cb = CircuitBreaker("test", failure_threshold=1, reset_timeout_s=60)
    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    assert cb.allow_request() is False


def test_open__before_call_raises() -> None:
    cb = CircuitBreaker("test", failure_threshold=1, reset_timeout_s=60)
    cb.record_failure()
    with pytest.raises(CircuitBreakerOpen, match="OPEN"):
        cb.before_call()


def test_open__transitions_to_half_open_after_timeout() -> None:
    cb = CircuitBreaker("test", failure_threshold=1, reset_timeout_s=0.1)
    cb.record_failure()
    assert cb.state == CircuitState.OPEN

    time.sleep(0.15)
    assert cb.state == CircuitState.HALF_OPEN
    assert cb.allow_request() is True


def test_half_open__success__transitions_to_closed() -> None:
    cb = CircuitBreaker("test", failure_threshold=1, reset_timeout_s=0.01)
    cb.record_failure()
    time.sleep(0.02)
    assert cb.state == CircuitState.HALF_OPEN

    cb.record_success()
    assert cb.state == CircuitState.CLOSED
    assert cb._failure_count == 0


def test_half_open__failure__trips_back_to_open() -> None:
    cb = CircuitBreaker("test", failure_threshold=1, reset_timeout_s=0.01)
    cb.record_failure()
    time.sleep(0.02)
    assert cb.state == CircuitState.HALF_OPEN

    cb.record_failure()
    assert cb.state == CircuitState.OPEN


def test_reset__forces_closed() -> None:
    cb = CircuitBreaker("test", failure_threshold=1)
    cb.record_failure()
    assert cb.state == CircuitState.OPEN

    cb.reset()
    assert cb.state == CircuitState.CLOSED
    assert cb._failure_count == 0


def test_to_dict__returns_state_info() -> None:
    cb = CircuitBreaker("docx_cv", failure_threshold=5, reset_timeout_s=30)
    cb.record_failure()
    d = cb.to_dict()

    assert d["source_type"] == "docx_cv"
    assert d["state"] == "closed"
    assert d["failure_count"] == 1
    assert d["failure_threshold"] == 5
    assert d["reset_timeout_s"] == 30


def test_circuit_breaker_open_exception__has_attributes() -> None:
    exc = CircuitBreakerOpen("test_source", reset_at=time.time() + 10)
    assert exc.source_type == "test_source"
    assert "OPEN" in str(exc)
    assert "test_source" in str(exc)
