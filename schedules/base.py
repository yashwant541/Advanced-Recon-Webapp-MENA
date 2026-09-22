"""Standard supporting-schedule interface and generic bucket-tie-out builder.

Purpose
-------
Give every schedule family the same shape: build a schedule from trial
balance + mappings, tie it to both the TB and the main statement, and run
row/column/grand-total controls. As with calculators, a single generic
implementation, :class:`BucketScheduleBuilder`, does the metadata-driven
work; concrete schedules (Schedule 3, 4, 5, currency, maturity) configure it.

Public contents
----------------
``ScheduleBuilder`` -- abstract interface.
``BucketScheduleBuilder`` -- generic bucket-grouped schedule builder.

Dependencies: ``iraq_recon.calculators.base`` (reuses ``CalculatorContext``),
``iraq_recon.models.reconciliation.ScheduleReconciliationResult``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any, Callable

from iraq_recon.calculators.base import CalculatorContext
from iraq_recon.constants import ReconciliationStatus
from iraq_recon.models.mapping import MappingRecord
from iraq_recon.models.reconciliation import ScheduleReconciliationResult
from iraq_recon.models.source import StatementLineRecord, TrialBalanceRecord
from iraq_recon.normalization.row_classifier import is_summable
from iraq_recon.rules.presentation_rules import apply_presentation_sign
from iraq_recon.rules.tolerance_rules import classify_variance_by_tolerance
from iraq_recon.rules.unit_rules import compute_effective_unit_factor, convert_balance


class ScheduleBuilder(ABC):
    """Standard interface every supporting-schedule builder must implement."""

    schedule_code: str
    schedule_description: str

    @abstractmethod
    def build(
        self,
        records: list[TrialBalanceRecord],
        reported_lines: dict[str, StatementLineRecord],
        context: CalculatorContext,
    ) -> ScheduleReconciliationResult:
        """Build and tie out this schedule.

        Args:
            records: Trial-balance records for the selected snapshot.
            reported_lines: Reported financial-statement lines, keyed by
                line code.
            context: Shared per-run dependencies (bridge, unit config,
                tolerances).

        Returns:
            A :class:`ScheduleReconciliationResult`.
        """
        raise NotImplementedError


def _default_bucket_label(mapping_record: MappingRecord) -> str:
    return mapping_record.ayra_category


class BucketScheduleBuilder(ScheduleBuilder):
    """Generic schedule: groups approved accounts into named buckets and
    ties the schedule total to both the TB and the main statement.

    A "bucket" here is a schedule-internal grouping (e.g. current/term for
    Schedule 4, or a currency/maturity band) distinct from the Iraq
    reporting bucket used by calculators, though it is frequently derived
    from the same mapping metadata.
    """

    def __init__(
        self,
        schedule_code: str,
        schedule_description: str,
        target_iraq_reporting_buckets: frozenset[str] | set[str],
        bucket_label_resolver: Callable[[MappingRecord], str] = _default_bucket_label,
        statement_line_code: str | None = None,
    ) -> None:
        """Configure a generic bucket-based schedule.

        Args:
            schedule_code: Stable schedule identifier, e.g. ``"SCHEDULE_3"``.
            schedule_description: Human-readable schedule name.
            target_iraq_reporting_buckets: Iraq reporting buckets whose
                mapped accounts feed this schedule; an empty set matches
                accounts in any bucket (used by cross-cutting schedules like
                currency/maturity breakdowns).
            bucket_label_resolver: Maps a mapping record to its schedule
                bucket label (defaults to Ayra category).
            statement_line_code: The main-statement line this schedule ties
                to; defaults to the sole entry of
                ``target_iraq_reporting_buckets`` when there is exactly one.
        """
        self.schedule_code = schedule_code
        self.schedule_description = schedule_description
        self.target_iraq_reporting_buckets = frozenset(target_iraq_reporting_buckets)
        self.bucket_label_resolver = bucket_label_resolver
        if statement_line_code is not None:
            self.statement_line_code = statement_line_code
        elif len(self.target_iraq_reporting_buckets) == 1:
            self.statement_line_code = next(iter(self.target_iraq_reporting_buckets))
        else:
            self.statement_line_code = schedule_code

    def build(
        self,
        records: list[TrialBalanceRecord],
        reported_lines: dict[str, StatementLineRecord],
        context: CalculatorContext,
    ) -> ScheduleReconciliationResult:
        bucket_totals: dict[str, Decimal] = {}
        bucket_accounts: dict[str, list[str]] = {}
        tb_total = Decimal("0")

        for tb_record in records:
            if not is_summable(tb_record.row_type):
                continue
            mapping_record = context.bridge.get(tb_record.account_number)
            if mapping_record is None:
                continue
            if (
                self.target_iraq_reporting_buckets
                and mapping_record.iraq_reporting_bucket not in self.target_iraq_reporting_buckets
            ):
                continue

            effective_factor = compute_effective_unit_factor(
                context.unit_config.conversion_factor, mapping_record.unit_factor
            )
            converted = convert_balance(tb_record.normalized_balance, effective_factor)
            presented = apply_presentation_sign(converted, mapping_record)

            label = self.bucket_label_resolver(mapping_record)
            bucket_totals[label] = bucket_totals.get(label, Decimal("0")) + presented
            bucket_accounts.setdefault(label, []).append(tb_record.account_number)
            tb_total += presented

        schedule_total = sum(bucket_totals.values(), Decimal("0"))

        reported_line = reported_lines.get(self.statement_line_code)
        statement_total = reported_line.reported_amount if reported_line else Decimal("0")

        variance_to_tb = schedule_total - tb_total
        variance_to_statement = schedule_total - statement_total if reported_line else Decimal("0")

        if reported_line is None:
            status = ReconciliationStatus.UNRESOLVED
        else:
            status_to_tb = classify_variance_by_tolerance(variance_to_tb, context.tolerances)
            status_to_statement = classify_variance_by_tolerance(variance_to_statement, context.tolerances)
            status = status_to_tb if status_to_tb != ReconciliationStatus.EXACT_MATCH else status_to_statement

        bucket_results: list[dict[str, Any]] = [
            {
                "bucket": label,
                "total": str(total),
                "account_count": len(bucket_accounts.get(label, [])),
                "accounts": list(bucket_accounts.get(label, [])),
            }
            for label, total in bucket_totals.items()
        ]

        return ScheduleReconciliationResult(
            schedule_code=self.schedule_code,
            schedule_description=self.schedule_description,
            schedule_total=schedule_total,
            tb_total=tb_total,
            statement_total=statement_total,
            variance_to_tb=variance_to_tb,
            variance_to_statement=variance_to_statement,
            status=status,
            bucket_results=tuple(bucket_results),
        )
