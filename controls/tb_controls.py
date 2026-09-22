"""Trial-balance-level controls (spec section 18).

Purpose
-------
Verify structural properties of the trial balance itself: posting accounts
tie to a caller-supplied control total, no account posts twice, no parent
row double-counts its own children, assets tie to liabilities plus equity,
and a gross-to-net bridge (e.g. fixed assets) reconciles.

Public contents
----------------
``check_control_total``, ``check_duplicate_accounts``,
``check_parent_child_double_counting``, ``check_balance_sheet_equation``,
``check_gross_to_net_bridge``.

Dependencies: ``iraq_recon.rules.tolerance_rules``, ``iraq_recon.models.*``.
"""

from __future__ import annotations

from decimal import Decimal

from iraq_recon.constants import ControlStatus, RowType, Severity, StatementType
from iraq_recon.models.configuration import ToleranceConfiguration
from iraq_recon.models.controls import ControlResult
from iraq_recon.models.source import TrialBalanceRecord
from iraq_recon.normalization.row_classifier import is_summable
from iraq_recon.rules.tolerance_rules import classify_variance_by_tolerance

_PASS_STATUSES = frozenset({"EXACT_MATCH", "PRECISION_MATCH", "ROUNDING_MATCH"})


def _status_from_variance(variance: Decimal, tolerances: ToleranceConfiguration) -> ControlStatus:
    classification = classify_variance_by_tolerance(variance, tolerances).value
    if classification in _PASS_STATUSES:
        return ControlStatus.PASS
    if classification == "PARTIAL_MATCH":
        return ControlStatus.WARN
    return ControlStatus.FAIL


def check_control_total(
    control_code: str,
    description: str,
    expected_total: Decimal,
    records: list[TrialBalanceRecord],
    tolerances: ToleranceConfiguration,
    *,
    statement_type: StatementType | None = None,
) -> ControlResult:
    """Compare a caller-supplied control total to the sum of posting balances.

    Args:
        control_code: Stable control identifier.
        description: Human-readable control description.
        expected_total: The trial balance's own declared control total (e.g.
            a TOTAL/GRAND_TOTAL row's value), supplied by the caller rather
            than guessed from row descriptions.
        records: Trial-balance records to sum.
        tolerances: Configured variance tolerances.
        statement_type: If given, only records with this statement type are
            summed.

    Returns:
        A :class:`ControlResult`.
    """
    actual_total = sum(
        (
            r.normalized_balance
            for r in records
            if is_summable(r.row_type) and (statement_type is None or r.statement_type == statement_type)
        ),
        Decimal("0"),
    )
    variance = actual_total - expected_total
    return ControlResult(
        control_code=control_code,
        control_description=description,
        status=_status_from_variance(variance, tolerances),
        severity=Severity.HIGH,
        expected_amount=expected_total,
        actual_amount=actual_total,
        variance=variance,
    )


def check_duplicate_accounts(records: list[TrialBalanceRecord]) -> ControlResult:
    """Flag any posting account number that appears more than once."""
    seen: dict[str, int] = {}
    for record in records:
        if not is_summable(record.row_type):
            continue
        seen[record.account_number] = seen.get(record.account_number, 0) + 1
    duplicates = sorted(account for account, count in seen.items() if count > 1)
    return ControlResult(
        control_code="TB_DUPLICATE_ACCOUNT_CONTROL",
        control_description="No posting account number appears more than once in the trial balance.",
        status=ControlStatus.FAIL if duplicates else ControlStatus.PASS,
        severity=Severity.HIGH,
        details={"duplicate_accounts": duplicates},
    )


def check_parent_child_double_counting(records: list[TrialBalanceRecord]) -> ControlResult:
    """Flag any account classified as both a parent row and a posting row."""
    parent_accounts = {r.account_number for r in records if r.row_type == RowType.PARENT}
    conflicting = sorted(
        {r.account_number for r in records if r.row_type == RowType.POSTING and r.account_number in parent_accounts}
    )
    return ControlResult(
        control_code="TB_PARENT_CHILD_DOUBLE_COUNT_CONTROL",
        control_description="No account is classified as both a parent row and a posting row.",
        status=ControlStatus.FAIL if conflicting else ControlStatus.PASS,
        severity=Severity.HIGH,
        details={"conflicting_accounts": conflicting},
    )


def check_balance_sheet_equation(
    asset_total: Decimal,
    liability_total: Decimal,
    equity_total: Decimal,
    tolerances: ToleranceConfiguration,
) -> ControlResult:
    """Check assets == liabilities + equity."""
    variance = asset_total - (liability_total + equity_total)
    return ControlResult(
        control_code="TB_ASSETS_EQUAL_LIABILITIES_PLUS_EQUITY_CONTROL",
        control_description="Total assets equal total liabilities plus equity.",
        status=_status_from_variance(variance, tolerances),
        severity=Severity.CRITICAL,
        expected_amount=liability_total + equity_total,
        actual_amount=asset_total,
        variance=variance,
    )


def check_gross_to_net_bridge(
    control_code: str,
    description: str,
    gross_amount: Decimal,
    contra_amount: Decimal,
    reported_net_amount: Decimal,
    tolerances: ToleranceConfiguration,
) -> ControlResult:
    """Check ``gross_amount - contra_amount == reported_net_amount``.

    Used for gross-to-net asset bridges such as fixed-asset cost less
    accumulated depreciation versus the reported net carrying value.
    """
    computed_net = gross_amount - contra_amount
    variance = computed_net - reported_net_amount
    return ControlResult(
        control_code=control_code,
        control_description=description,
        status=_status_from_variance(variance, tolerances),
        severity=Severity.HIGH,
        expected_amount=reported_net_amount,
        actual_amount=computed_net,
        variance=variance,
    )
