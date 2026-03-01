"""IC sub-state calculator for Knowledge Profile."""

from __future__ import annotations

from collections.abc import Iterable

from src.core.knowledge_profile.schemas import ICSubState
from src.services.availability.schemas import AvailabilityStatus, ProfileAvailability
from src.services.reskilling.schemas import ReskillingRecord, ReskillingStatus


def calculate_ic_sub_state(
    availability: ProfileAvailability | None,
    reskilling_records: Iterable[ReskillingRecord],
    *,
    is_in_transition: bool,
) -> ICSubState | None:
    """Calculate IC sub-state for a resource.

    Args:
        availability: Availability record for the resource, if any.
        reskilling_records: Reskilling records for the resource.
        is_in_transition: Whether the resource is in a transition phase.

    Returns:
        The IC sub-state when applicable, otherwise None.
    """
    if availability is None:
        return None
    if availability.allocation_pct > 0:
        return None
    if availability.status not in (AvailabilityStatus.FREE, AvailabilityStatus.UNAVAILABLE):
        return None

    if is_in_transition:
        return ICSubState.IC_IN_TRANSITION

    if any(record.status == ReskillingStatus.IN_PROGRESS for record in reskilling_records):
        return ICSubState.IC_IN_RESKILLING

    return ICSubState.IC_AVAILABLE


__all__ = ["calculate_ic_sub_state"]
