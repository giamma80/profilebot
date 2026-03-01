from __future__ import annotations

from datetime import UTC, datetime

from src.core.knowledge_profile.ic_sub_state import calculate_ic_sub_state
from src.core.knowledge_profile.schemas import ICSubState
from src.services.availability.schemas import AvailabilityStatus, ProfileAvailability
from src.services.reskilling.schemas import ReskillingRecord, ReskillingStatus


def _availability(
    *,
    status: AvailabilityStatus,
    allocation_pct: int,
) -> ProfileAvailability:
    return ProfileAvailability(
        res_id=123,
        status=status,
        allocation_pct=allocation_pct,
        current_project=None,
        available_from=None,
        available_to=None,
        manager_name=None,
        updated_at=datetime.now(UTC),
    )


def _reskilling(status: ReskillingStatus) -> ReskillingRecord:
    return ReskillingRecord(
        res_id=123,
        course_name="Course",
        skill_target="kubernetes",
        status=status,
        start_date=None,
        end_date=None,
        provider=None,
        completion_pct=50,
    )


def test_calculate_ic_sub_state__not_ic__returns_none() -> None:
    availability = _availability(status=AvailabilityStatus.PARTIAL, allocation_pct=50)

    result = calculate_ic_sub_state(
        availability,
        [],
        is_in_transition=False,
    )

    assert result is None


def test_calculate_ic_sub_state__ic_available__returns_available() -> None:
    availability = _availability(status=AvailabilityStatus.FREE, allocation_pct=0)

    result = calculate_ic_sub_state(
        availability,
        [],
        is_in_transition=False,
    )

    assert result == ICSubState.IC_AVAILABLE


def test_calculate_ic_sub_state__ic_in_reskilling__returns_reskilling() -> None:
    availability = _availability(status=AvailabilityStatus.FREE, allocation_pct=0)
    records = [_reskilling(ReskillingStatus.IN_PROGRESS)]

    result = calculate_ic_sub_state(
        availability,
        records,
        is_in_transition=False,
    )

    assert result == ICSubState.IC_IN_RESKILLING


def test_calculate_ic_sub_state__ic_in_transition__has_priority() -> None:
    availability = _availability(status=AvailabilityStatus.UNAVAILABLE, allocation_pct=0)
    records = [_reskilling(ReskillingStatus.IN_PROGRESS)]

    result = calculate_ic_sub_state(
        availability,
        records,
        is_in_transition=True,
    )

    assert result == ICSubState.IC_IN_TRANSITION
