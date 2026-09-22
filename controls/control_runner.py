"""Central control-framework runner (spec section 18).

Purpose
-------
Give the reconciliation engine one call that runs every applicable control
family (TB, mapping, schedule, statement, off-balance-sheet) and returns
the combined list plus an overall pass/warn/fail status -- each control
family runs only when its required inputs are supplied, so selective
reconciliation runs still get whatever controls are meaningful for the
lines actually calculated.

Public contents
----------------
``ControlRunInputs`` -- optional inputs for each control family.
``run_all_controls(inputs)`` -- returns ``(controls, overall_status)``.

Dependencies: ``iraq_recon.controls.*``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from iraq_recon.constants import ControlStatus
from iraq_recon.controls.mapping_controls import build_mapping_controls
from iraq_recon.controls.off_balance_sheet_controls import (
    check_guarantee_and_contingent_classification,
    check_off_balance_sheet_debit_credit_totals,
)
from iraq_recon.controls.schedule_controls import build_schedule_controls
from iraq_recon.controls.statement_controls import (
    check_off_balance_sheet_exclusion,
    check_subtotal_reconstruction,
)
from iraq_recon.controls.tb_controls import (
    check_balance_sheet_equation,
    check_duplicate_accounts,
    check_parent_child_double_counting,
)
from iraq_recon.mapping.local_bridge import LocalAccountBridge
from iraq_recon.mapping.mapping_coverage import MappingCoverageResult
from iraq_recon.models.calculation import CalculationResult
from iraq_recon.models.configuration import ToleranceConfiguration
from iraq_recon.models.controls import ControlResult
from iraq_recon.models.reconciliation import LineReconciliationResult, ScheduleReconciliationResult
from iraq_recon.models.source import TrialBalanceRecord
from iraq_recon.models.validation import ValidationResult


@dataclass(frozen=True)
class ControlRunInputs:
    """Optional inputs for each control family; unset fields skip that family.

    Attributes:
        tb_records: Trial-balance records, for TB structural controls.
        mapping_coverage: For mapping coverage controls.
        mapping_validation: For mapping issue controls.
        line_results: Calculated line results, for statement controls.
        schedule_results: Built schedules, for schedule controls.
        bridge: Resolved local-account bridge, needed for the OFF BS
            exclusion statement control.
        off_balance_sheet_line_codes: Line codes that are themselves OFF BS.
        off_balance_sheet_calc_result: The OBS calculator's result, for OBS
            debit/credit/classification controls.
        asset_total: Total assets, for the balance-sheet equation control.
        liability_total: Total liabilities, for the balance-sheet equation control.
        equity_total: Total equity, for the balance-sheet equation control.
        subtotal_checks: ``[(control_code, description, component_lines,
            grand_total_reported), ...]`` for subtotal reconstruction controls.
        expected_schedule_buckets: ``{schedule_code: expected_bucket_labels}``.
    """

    tb_records: list[TrialBalanceRecord] | None = None
    mapping_coverage: MappingCoverageResult | None = None
    mapping_validation: ValidationResult | None = None
    line_results: list[LineReconciliationResult] | None = None
    schedule_results: list[ScheduleReconciliationResult] | None = None
    bridge: LocalAccountBridge | None = None
    off_balance_sheet_line_codes: set[str] = field(default_factory=set)
    off_balance_sheet_calc_result: CalculationResult | None = None
    asset_total: Decimal | None = None
    liability_total: Decimal | None = None
    equity_total: Decimal | None = None
    subtotal_checks: tuple[tuple[str, str, list[LineReconciliationResult], Decimal], ...] = ()
    expected_schedule_buckets: dict[str, set[str]] | None = None


def run_all_controls(
    inputs: ControlRunInputs,
    tolerances: ToleranceConfiguration,
) -> tuple[list[ControlResult], ControlStatus]:
    """Run every control family for which ``inputs`` supplies data.

    Args:
        inputs: The optional per-family inputs (see :class:`ControlRunInputs`).
        tolerances: Configured variance tolerances.

    Returns:
        ``(controls, overall_status)`` -- ``overall_status`` is ``FAIL`` if
        any control failed, else ``WARN`` if any warned, else ``PASS``.
    """
    controls: list[ControlResult] = []

    if inputs.tb_records is not None:
        controls.append(check_duplicate_accounts(inputs.tb_records))
        controls.append(check_parent_child_double_counting(inputs.tb_records))

    if inputs.asset_total is not None and inputs.liability_total is not None and inputs.equity_total is not None:
        controls.append(
            check_balance_sheet_equation(inputs.asset_total, inputs.liability_total, inputs.equity_total, tolerances)
        )

    if inputs.mapping_coverage is not None and inputs.mapping_validation is not None:
        controls.extend(build_mapping_controls(inputs.mapping_coverage, inputs.mapping_validation))

    if inputs.schedule_results is not None:
        controls.extend(
            build_schedule_controls(inputs.schedule_results, tolerances, inputs.expected_schedule_buckets)
        )

    for control_code, description, component_lines, grand_total_reported in inputs.subtotal_checks:
        controls.append(
            check_subtotal_reconstruction(control_code, description, component_lines, grand_total_reported, tolerances)
        )

    if inputs.line_results is not None and inputs.bridge is not None:
        controls.append(
            check_off_balance_sheet_exclusion(
                inputs.line_results, inputs.bridge, off_balance_sheet_line_codes=inputs.off_balance_sheet_line_codes
            )
        )

    if inputs.off_balance_sheet_calc_result is not None:
        controls.extend(check_off_balance_sheet_debit_credit_totals(inputs.off_balance_sheet_calc_result))
        controls.append(check_guarantee_and_contingent_classification(inputs.off_balance_sheet_calc_result))

    overall_status = ControlStatus.PASS
    for control in controls:
        if control.status == ControlStatus.FAIL:
            overall_status = ControlStatus.FAIL
            break
        if control.status == ControlStatus.WARN:
            overall_status = ControlStatus.WARN

    return controls, overall_status
