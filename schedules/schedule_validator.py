"""Common schedule control checks (spec section 11).

Purpose
-------
Apply the same control set to every built schedule: bucket-total
consistency (guards against duplicate contributions), schedule-to-TB tie,
schedule-to-main-statement tie, and a missing-bucket check when the caller
knows which buckets are expected.

Public contents
----------------
``validate_schedule(result, tolerances, expected_buckets=None)`` -- returns
a list of :class:`iraq_recon.models.controls.ControlResult`.

Dependencies: ``iraq_recon.rules.tolerance_rules``,
``iraq_recon.models.controls``, ``iraq_recon.models.reconciliation``.
"""

from __future__ import annotations

from decimal import Decimal

from iraq_recon.constants import ControlStatus, ReconciliationStatus, Severity
from iraq_recon.models.configuration import ToleranceConfiguration
from iraq_recon.models.controls import ControlResult
from iraq_recon.models.reconciliation import ScheduleReconciliationResult
from iraq_recon.rules.tolerance_rules import classify_variance_by_tolerance

_PASS_STATUSES = (
    ReconciliationStatus.EXACT_MATCH,
    ReconciliationStatus.PRECISION_MATCH,
    ReconciliationStatus.ROUNDING_MATCH,
)


def _control_status_for(status: ReconciliationStatus) -> ControlStatus:
    if status == ReconciliationStatus.UNRESOLVED:
        return ControlStatus.NOT_APPLICABLE
    if status in _PASS_STATUSES:
        return ControlStatus.PASS
    if status == ReconciliationStatus.PARTIAL_MATCH:
        return ControlStatus.WARN
    return ControlStatus.FAIL


def validate_schedule(
    result: ScheduleReconciliationResult,
    tolerances: ToleranceConfiguration,
    *,
    expected_buckets: set[str] | None = None,
) -> list[ControlResult]:
    """Run the standard control set against one built schedule.

    Args:
        result: A built :class:`ScheduleReconciliationResult`.
        tolerances: Configured variance tolerances.
        expected_buckets: Bucket labels expected to be present (e.g. every
            currency the bank operates in); ``None`` skips this control.

    Returns:
        A list of :class:`ControlResult`, one per check.
    """
    controls: list[ControlResult] = []
    prefix = result.schedule_code

    bucket_sum = sum((Decimal(b["total"]) for b in result.bucket_results), Decimal("0"))
    grand_total_variance = result.schedule_total - bucket_sum
    controls.append(
        ControlResult(
            control_code=f"{prefix}_GRAND_TOTAL_CONTROL",
            control_description="Schedule grand total equals the sum of its bucket totals.",
            status=ControlStatus.PASS if grand_total_variance == Decimal("0") else ControlStatus.FAIL,
            severity=Severity.HIGH,
            expected_amount=bucket_sum,
            actual_amount=result.schedule_total,
            variance=grand_total_variance,
        )
    )

    seen_accounts: set[str] = set()
    duplicate_accounts: set[str] = set()
    for bucket in result.bucket_results:
        for account in bucket.get("accounts", []):
            if account in seen_accounts:
                duplicate_accounts.add(account)
            seen_accounts.add(account)
    controls.append(
        ControlResult(
            control_code=f"{prefix}_DUPLICATE_CONTRIBUTION_CONTROL",
            control_description="No account contributes to more than one schedule bucket.",
            status=ControlStatus.FAIL if duplicate_accounts else ControlStatus.PASS,
            severity=Severity.HIGH,
            details={"duplicate_accounts": sorted(duplicate_accounts)},
        )
    )

    tb_status = classify_variance_by_tolerance(result.variance_to_tb, tolerances)
    controls.append(
        ControlResult(
            control_code=f"{prefix}_SCHEDULE_TO_TB_CONTROL",
            control_description="Schedule total ties to the trial balance.",
            status=_control_status_for(tb_status),
            severity=Severity.HIGH,
            expected_amount=result.tb_total,
            actual_amount=result.schedule_total,
            variance=result.variance_to_tb,
        )
    )

    controls.append(
        ControlResult(
            control_code=f"{prefix}_SCHEDULE_TO_STATEMENT_CONTROL",
            control_description="Schedule total ties to the main financial statement.",
            status=_control_status_for(result.status),
            severity=Severity.HIGH,
            expected_amount=result.statement_total,
            actual_amount=result.schedule_total,
            variance=result.variance_to_statement,
        )
    )

    if expected_buckets is not None:
        present_buckets = {b["bucket"] for b in result.bucket_results}
        missing_buckets = expected_buckets - present_buckets
        controls.append(
            ControlResult(
                control_code=f"{prefix}_MISSING_BUCKET_CONTROL",
                control_description="Every expected schedule bucket has at least one contribution.",
                status=ControlStatus.WARN if missing_buckets else ControlStatus.PASS,
                severity=Severity.MEDIUM,
                details={"missing_buckets": sorted(missing_buckets)},
            )
        )

    return controls
