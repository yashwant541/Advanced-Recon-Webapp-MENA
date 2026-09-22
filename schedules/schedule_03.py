"""Schedule 3: Central Bank balance tie-out.

Purpose
-------
Validate that current/free balance + statutory reserve + approved term
balance equals both the schedule's own total and the main statement's
Central Bank line (spec section 11).

Public contents: ``Schedule3Builder``.
Dependencies: ``schedules.base``.
"""

from __future__ import annotations

from iraq_recon.schedules.base import BucketScheduleBuilder

SCHEDULE_CODE = "SCHEDULE_3"
TARGET_BUCKETS = frozenset({"BALANCES_WITH_CENTRAL_BANK"})


class Schedule3Builder(BucketScheduleBuilder):
    """Central Bank schedule: current/free balance + statutory reserve."""

    def __init__(self, statement_line_code: str = "BALANCES_WITH_CENTRAL_BANK") -> None:
        super().__init__(
            schedule_code=SCHEDULE_CODE,
            schedule_description="Central Bank balance schedule",
            target_iraq_reporting_buckets=TARGET_BUCKETS,
            statement_line_code=statement_line_code,
        )
