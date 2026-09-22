"""Schedule 5: investment instruments schedule.

Purpose
-------
Build and validate the investment schedule by instrument/carrying-value
component, sector, or currency (spec section 11), tying to both the TB and
the main statement's investment line.

Public contents: ``Schedule5Builder``.
Dependencies: ``schedules.base``.
"""

from __future__ import annotations

from iraq_recon.models.mapping import MappingRecord
from iraq_recon.schedules.base import BucketScheduleBuilder

SCHEDULE_CODE = "SCHEDULE_5"
TARGET_BUCKETS = frozenset({"INVESTMENTS_IN_SECURITIES"})


def _instrument_label(mapping_record: MappingRecord) -> str:
    return str(mapping_record.metadata.get("investment_component", "carrying_value"))


class Schedule5Builder(BucketScheduleBuilder):
    """Investment instrument schedule, grouped by carrying-value component."""

    def __init__(self, statement_line_code: str = "INVESTMENTS_IN_SECURITIES") -> None:
        super().__init__(
            schedule_code=SCHEDULE_CODE,
            schedule_description="Investments in securities schedule",
            target_iraq_reporting_buckets=TARGET_BUCKETS,
            bucket_label_resolver=_instrument_label,
            statement_line_code=statement_line_code,
        )
