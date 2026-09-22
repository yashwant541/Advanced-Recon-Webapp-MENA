"""Variance engine: turn calculator output into line reconciliation results.

Purpose
-------
Convert each calculator's :class:`CalculationResult` into a
:class:`LineReconciliationResult` with a variance percentage and a
review-required flag, without ever overwriting the raw variance (spec
success criterion #10). If a calculator did not already attach a
reported amount/variance/status (e.g. no matching reported line existed
at calculation time), this module fills that gap using the same
tolerance rules calculators use internally.

Public contents
----------------
``build_line_result(calc_result, line_description, tolerances, ...)``.
``build_line_results(calc_results, line_descriptions, tolerances, ...)``.

Dependencies: ``iraq_recon.rules.tolerance_rules``,
``iraq_recon.models.calculation``, ``iraq_recon.models.reconciliation``.
"""

from __future__ import annotations

from decimal import Decimal

from iraq_recon.constants import ReconciliationStatus
from iraq_recon.models.calculation import CalculationResult
from iraq_recon.models.configuration import ToleranceConfiguration
from iraq_recon.models.reconciliation import LineReconciliationResult
from iraq_recon.rules.tolerance_rules import (
    calculate_variance_percentage,
    classify_variance_by_tolerance,
)

_REVIEW_REQUIRED_STATUSES = frozenset(
    {
        ReconciliationStatus.PARTIAL_MATCH,
        ReconciliationStatus.MATERIAL_BREAK,
        ReconciliationStatus.MAPPING_DIFFERENCE,
        ReconciliationStatus.PRESENTATION_DIFFERENCE,
        ReconciliationStatus.UNIT_DIFFERENCE,
        ReconciliationStatus.SIGN_DIFFERENCE,
        ReconciliationStatus.SCHEDULE_DIFFERENCE,
        ReconciliationStatus.SOURCE_DATA_DIFFERENCE,
        ReconciliationStatus.UNMAPPED_ACCOUNT,
        ReconciliationStatus.DUPLICATE_MAPPING,
        ReconciliationStatus.UNRESOLVED,
    }
)


def build_line_result(
    calc_result: CalculationResult,
    line_description: str,
    tolerances: ToleranceConfiguration,
    *,
    supporting_schedule: str | None = None,
) -> LineReconciliationResult:
    """Build a :class:`LineReconciliationResult` from one calculator result.

    Args:
        calc_result: A calculator's output for this line.
        line_description: Human-readable line caption.
        tolerances: Configured variance tolerances (used only if
            ``calc_result`` did not already compute a status, i.e. it had no
            reported amount at calculation time).
        supporting_schedule: The schedule code that also ties to this line,
            if any.

    Returns:
        A :class:`LineReconciliationResult`. The raw calculated/reported
        amounts and variance are always preserved exactly as computed by
        the calculator.
    """
    reported_amount = calc_result.reported_amount if calc_result.reported_amount is not None else Decimal("0")
    variance = (
        calc_result.variance
        if calc_result.variance is not None
        else calc_result.calculated_amount - reported_amount
    )
    absolute_variance = abs(variance)
    variance_percentage = calculate_variance_percentage(variance, reported_amount)

    if calc_result.status is not None:
        status = ReconciliationStatus(calc_result.status)
    else:
        status = classify_variance_by_tolerance(variance, tolerances)

    return LineReconciliationResult(
        line_code=calc_result.line_code,
        line_description=line_description,
        reported_amount=reported_amount,
        calculated_amount=calc_result.calculated_amount,
        variance=variance,
        absolute_variance=absolute_variance,
        variance_percentage=variance_percentage,
        tolerance=tolerances.rounding,
        status=status,
        formula=calc_result.formula,
        supporting_accounts=calc_result.included_accounts + calc_result.deducted_accounts,
        supporting_schedule=supporting_schedule,
        accounting_explanation=calc_result.accounting_explanation,
        review_required=status in _REVIEW_REQUIRED_STATUSES,
    )


def build_line_results(
    calc_results: list[CalculationResult],
    line_descriptions: dict[str, str],
    tolerances: ToleranceConfiguration,
    *,
    schedule_by_line: dict[str, str] | None = None,
) -> list[LineReconciliationResult]:
    """Build line results for every calculator output.

    Args:
        calc_results: One :class:`CalculationResult` per calculator run.
        line_descriptions: ``{line_code: description}``; a missing entry
            falls back to the line code itself.
        tolerances: Configured variance tolerances.
        schedule_by_line: ``{line_code: schedule_code}`` for lines with a
            known supporting schedule.

    Returns:
        A list of :class:`LineReconciliationResult`, same order as input.
    """
    schedule_by_line = schedule_by_line or {}
    return [
        build_line_result(
            calc_result,
            line_descriptions.get(calc_result.line_code, calc_result.line_code),
            tolerances,
            supporting_schedule=schedule_by_line.get(calc_result.line_code),
        )
        for calc_result in calc_results
    ]
