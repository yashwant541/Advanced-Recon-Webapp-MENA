"""Schedule controls aggregator (spec section 18).

Purpose
-------
Run the common schedule control set (see
``schedules.schedule_validator.validate_schedule``) across every built
schedule for a run, so the control framework has one call to make rather
than iterating schedules itself.

Public contents
----------------
``build_schedule_controls(schedule_results, tolerances, expected_buckets_by_schedule=None)``.

Dependencies: ``iraq_recon.schedules.schedule_validator``.
"""

from __future__ import annotations

from iraq_recon.models.configuration import ToleranceConfiguration
from iraq_recon.models.controls import ControlResult
from iraq_recon.models.reconciliation import ScheduleReconciliationResult
from iraq_recon.schedules.schedule_validator import validate_schedule


def build_schedule_controls(
    schedule_results: list[ScheduleReconciliationResult],
    tolerances: ToleranceConfiguration,
    expected_buckets_by_schedule: dict[str, set[str]] | None = None,
) -> list[ControlResult]:
    """Run the standard control set against every built schedule.

    Args:
        schedule_results: Every schedule built for the run.
        tolerances: Configured variance tolerances.
        expected_buckets_by_schedule: ``{schedule_code: expected_bucket_labels}``
            for schedules where a missing-bucket check applies.

    Returns:
        The concatenated list of :class:`ControlResult` across all schedules.
    """
    expected_buckets_by_schedule = expected_buckets_by_schedule or {}
    controls: list[ControlResult] = []
    for schedule_result in schedule_results:
        controls.extend(
            validate_schedule(
                schedule_result,
                tolerances,
                expected_buckets=expected_buckets_by_schedule.get(schedule_result.schedule_code),
            )
        )
    return controls
