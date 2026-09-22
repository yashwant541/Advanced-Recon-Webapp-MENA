"""Currency-breakdown schedule.

Purpose
-------
Control that the sum of an account population's currency buckets equals
the corresponding reported financial-statement line (spec section 11).
Currency classification comes from each account's approved mapping
metadata (``metadata["currency"]``) -- raw currency amounts are never
combined without an approved exchange rate already baked into the trial
balance's normalized amount; this schedule only groups, it never converts.

Public contents: ``CurrencyScheduleBuilder``.
Dependencies: ``schedules.base``.
"""

from __future__ import annotations

from iraq_recon.models.mapping import MappingRecord
from iraq_recon.schedules.base import BucketScheduleBuilder


def _currency_label(mapping_record: MappingRecord) -> str:
    return str(mapping_record.metadata.get("currency", "UNSPECIFIED"))


class CurrencyScheduleBuilder(BucketScheduleBuilder):
    """Groups approved accounts by declared currency and ties to a statement line."""

    def __init__(
        self,
        schedule_code: str,
        statement_line_code: str,
        target_iraq_reporting_buckets: frozenset[str] | set[str] = frozenset(),
    ) -> None:
        super().__init__(
            schedule_code=schedule_code,
            schedule_description=f"Currency breakdown for '{statement_line_code}'",
            target_iraq_reporting_buckets=target_iraq_reporting_buckets,
            bucket_label_resolver=_currency_label,
            statement_line_code=statement_line_code,
        )
