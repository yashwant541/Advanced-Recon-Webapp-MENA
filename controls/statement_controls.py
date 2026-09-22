"""Financial-statement-level controls (spec section 18).

Purpose
-------
Verify cross-line properties of the reconciled financial statement: a
subtotal reconstructs from its component lines (e.g. total assets from its
constituent asset lines), and no off-balance-sheet account has leaked into
a primary balance-sheet line's supporting accounts.

Public contents
----------------
``check_subtotal_reconstruction(...)``
``check_off_balance_sheet_exclusion(...)``

Dependencies: ``iraq_recon.mapping.local_bridge``,
``iraq_recon.models.reconciliation``, ``iraq_recon.rules.tolerance_rules``.
"""

from __future__ import annotations

from decimal import Decimal

from iraq_recon.constants import ControlStatus, Severity, StatementType
from iraq_recon.mapping.local_bridge import LocalAccountBridge
from iraq_recon.models.configuration import ToleranceConfiguration
from iraq_recon.models.controls import ControlResult
from iraq_recon.models.reconciliation import LineReconciliationResult
from iraq_recon.rules.tolerance_rules import classify_variance_by_tolerance

_PASS_STATUSES = frozenset({"EXACT_MATCH", "PRECISION_MATCH", "ROUNDING_MATCH"})


def _status_from_variance(variance: Decimal, tolerances: ToleranceConfiguration) -> ControlStatus:
    classification = classify_variance_by_tolerance(variance, tolerances).value
    if classification in _PASS_STATUSES:
        return ControlStatus.PASS
    if classification == "PARTIAL_MATCH":
        return ControlStatus.WARN
    return ControlStatus.FAIL


def check_subtotal_reconstruction(
    control_code: str,
    description: str,
    component_lines: list[LineReconciliationResult],
    grand_total_reported: Decimal,
    tolerances: ToleranceConfiguration,
) -> ControlResult:
    """Check that a subtotal reconstructs from its calculated component lines.

    Args:
        control_code: Stable control identifier.
        description: Human-readable description, e.g. "Total assets
            reconstruction".
        component_lines: The lines that should sum to ``grand_total_reported``.
        grand_total_reported: The reported grand-total amount.
        tolerances: Configured variance tolerances.

    Returns:
        A :class:`ControlResult`.
    """
    reconstructed_total = sum((line.calculated_amount for line in component_lines), Decimal("0"))
    variance = reconstructed_total - grand_total_reported
    return ControlResult(
        control_code=control_code,
        control_description=description,
        status=_status_from_variance(variance, tolerances),
        severity=Severity.CRITICAL,
        expected_amount=grand_total_reported,
        actual_amount=reconstructed_total,
        variance=variance,
        details={"component_lines": [line.line_code for line in component_lines]},
    )


def check_off_balance_sheet_exclusion(
    line_results: list[LineReconciliationResult],
    bridge: LocalAccountBridge,
    *,
    off_balance_sheet_line_codes: set[str],
) -> ControlResult:
    """Check that no off-balance-sheet account supports a primary BS/P&L line.

    Args:
        line_results: All calculated line results for the run.
        bridge: Resolved local-account bridge (used to look up each
            supporting account's statement type).
        off_balance_sheet_line_codes: Line codes that are themselves
            off-balance-sheet (and are therefore exempt from this check).

    Returns:
        A :class:`ControlResult`.
    """
    leaked: list[dict[str, str]] = []
    for line in line_results:
        if line.line_code in off_balance_sheet_line_codes:
            continue
        for account in line.supporting_accounts:
            mapping_record = bridge.get(account)
            if mapping_record is not None and mapping_record.statement_type == StatementType.OFF_BALANCE_SHEET:
                leaked.append({"line_code": line.line_code, "account": account})

    return ControlResult(
        control_code="STATEMENT_OFF_BS_EXCLUSION_CONTROL",
        control_description="No off-balance-sheet account contributes to a primary BS/P&L line.",
        status=ControlStatus.FAIL if leaked else ControlStatus.PASS,
        severity=Severity.CRITICAL,
        details={"leaked_contributions": leaked},
    )
