"""Maturity-breakdown schedule.

Purpose
-------
Control that the sum of an account population's maturity buckets equals
the corresponding schedule or financial-statement line (spec section 11).
Maturity classification comes from each account's approved mapping
metadata (``metadata["maturity_bucket"]``); an account with no declared
maturity is labeled ``"UNCLASSIFIED"`` rather than having a maturity
invented for it.

Public contents: ``MaturityScheduleBuilder``.
Dependencies: ``schedules.base``.
"""

from __future__ import annotations

from iraq_recon.models.mapping import MappingRecord
from iraq_recon.schedules.base import BucketScheduleBuilder


def _maturity_label(mapping_record: MappingRecord) -> str:
    return str(mapping_record.metadata.get("maturity_bucket", "UNCLASSIFIED"))


class MaturityScheduleBuilder(BucketScheduleBuilder):
    """Groups approved accounts by declared maturity bucket."""

    def __init__(
        self,
        schedule_code: str,
        statement_line_code: str,
        target_iraq_reporting_buckets: frozenset[str] | set[str] = frozenset(),
    ) -> None:
        super().__init__(
            schedule_code=schedule_code,
            schedule_description=f"Maturity breakdown for '{statement_line_code}'",
            target_iraq_reporting_buckets=target_iraq_reporting_buckets,
            bucket_label_resolver=_maturity_label,
            statement_line_code=statement_line_code,
        )
