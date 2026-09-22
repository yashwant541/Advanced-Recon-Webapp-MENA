"""Reconciliation engine: the master orchestration sequence (spec section 15).

Purpose
-------
Run the full pipeline -- selected calculators, selected schedules, mapping
coverage/validation, variance classification, the control framework, and
diagnostics -- and assemble the result into one
:class:`iraq_recon.models.reconciliation.ReconciliationRun`. This is the
one function ``services.reconciliation_service`` (and, through it,
``api.run_reconciliation``) calls; it contains no Excel-reading, Dataiku,
or HTTP concerns.

Public contents
----------------
``default_calculator_registry()`` -- the 12 standard calculators, keyed by
line code.
``run_reconciliation(...)`` -- run the full (or selectively scoped)
reconciliation and return a :class:`ReconciliationRun`.

Dependencies: every ``calculators.*``, ``schedules.schedule_builder``,
``controls.control_runner``, ``engine.variance_engine``,
``engine.diagnostics_engine``, ``engine.run_context``,
``mapping.mapping_coverage``, ``mapping.mapping_validator``.
"""

from __future__ import annotations

from iraq_recon.calculators.bank_balances import (
    BankCurrentLiabilitiesCalculator,
    BankDebitBalancesCalculator,
    BankTermLiabilitiesCalculator,
)
from iraq_recon.calculators.base import AccountingCalculator
from iraq_recon.calculators.capital_reserves import CapitalReservesCalculator
from iraq_recon.calculators.central_bank import CentralBankCalculator
from iraq_recon.calculators.customer_deposits import CustomerDepositsCalculator
from iraq_recon.calculators.fixed_assets import FixedAssetsCalculator
from iraq_recon.calculators.investments import InvestmentsCalculator
from iraq_recon.calculators.off_balance_sheet import OffBalanceSheetCalculator
from iraq_recon.calculators.other_assets import OtherAssetsCalculator
from iraq_recon.calculators.provisions import ProvisionsCalculator
from iraq_recon.calculators.spot_position import SpotPositionCalculator
from iraq_recon.controls.control_runner import ControlRunInputs, run_all_controls
from iraq_recon.engine.diagnostics_engine import run_diagnostics
from iraq_recon.engine.run_context import RunContext
from iraq_recon.engine.variance_engine import build_line_results
from iraq_recon.mapping.mapping_coverage import calculate_mapping_coverage
from iraq_recon.mapping.mapping_validator import validate_mapping_records
from iraq_recon.models.reconciliation import AccountTraceEntry, ReconciliationRun
from iraq_recon.models.source import StatementLineRecord, TrialBalanceRecord
from iraq_recon.models.validation import ValidationResult
from iraq_recon.schedules.base import ScheduleBuilder
from iraq_recon.schedules.schedule_builder import DEFAULT_SCHEDULE_REGISTRY, build_schedules

_OFF_BALANCE_SHEET_LINE_CODE = OffBalanceSheetCalculator().line_code


def default_calculator_registry() -> dict[str, AccountingCalculator]:
    """Return the 12 standard accounting calculators, keyed by line code."""
    calculators: list[AccountingCalculator] = [
        CentralBankCalculator(),
        BankDebitBalancesCalculator(),
        BankCurrentLiabilitiesCalculator(),
        BankTermLiabilitiesCalculator(),
        InvestmentsCalculator(),
        FixedAssetsCalculator(),
        OtherAssetsCalculator(),
        CapitalReservesCalculator(),
        CustomerDepositsCalculator(),
        ProvisionsCalculator(),
        SpotPositionCalculator(),
        OffBalanceSheetCalculator(),
    ]
    return {calculator.line_code: calculator for calculator in calculators}


def run_reconciliation(
    run_context: RunContext,
    tb_records: list[TrialBalanceRecord],
    reported_lines: dict[str, StatementLineRecord],
    *,
    selected_tb_snapshot: str = "",
    line_descriptions: dict[str, str] | None = None,
    calculator_registry: dict[str, AccountingCalculator] | None = None,
    schedule_registry: dict[str, ScheduleBuilder] | None = None,
    candidate_snapshot_comparison: dict | None = None,
    warnings: tuple[str, ...] = (),
) -> ReconciliationRun:
    """Run the full reconciliation pipeline and assemble a :class:`ReconciliationRun`.

    Args:
        run_context: Run-scoped state (configuration, mappings, bridge).
        tb_records: Normalized trial-balance records for the selected snapshot.
        reported_lines: Reported financial-statement lines, keyed by line code.
        selected_tb_snapshot: Identifier of the TB snapshot used.
        line_descriptions: ``{line_code: description}`` for the executive
            summary; falls back to the line code itself.
        calculator_registry: Calculators to consider; defaults to
            :func:`default_calculator_registry`. Only calculators whose
            line code is in ``run_context.configuration.execution.statement_sections``
            run, unless that list is empty (meaning "run all").
        schedule_registry: Schedules to consider; defaults to
            :data:`iraq_recon.schedules.schedule_builder.DEFAULT_SCHEDULE_REGISTRY`.
        candidate_snapshot_comparison: Optional snapshot-comparison evidence
            (see ``engine.snapshot_selector``) to carry through for display.
        warnings: Warnings accumulated by earlier pipeline stages (ingestion,
            normalization, mapping loading) to carry through on the run.

    Returns:
        A :class:`ReconciliationRun` with line results, account trace,
        schedule results, control results, and diagnosed exceptions.
    """
    calculator_registry = calculator_registry or default_calculator_registry()
    schedule_registry = schedule_registry if schedule_registry is not None else DEFAULT_SCHEDULE_REGISTRY
    line_descriptions = line_descriptions or {}

    execution = run_context.configuration.execution
    if execution.runs_all_sections():
        active_calculators = list(calculator_registry.values())
    else:
        active_calculators = [
            calculator
            for line_code, calculator in calculator_registry.items()
            if line_code in execution.statement_sections
        ]

    calculator_context = run_context.to_calculator_context()
    calc_results = [
        calculator.calculate(tb_records, reported_lines, calculator_context) for calculator in active_calculators
    ]
    calc_results_by_line = {result.line_code: result for result in calc_results}

    schedule_results = build_schedules(
        list(execution.schedule_codes), tb_records, reported_lines, calculator_context, schedule_registry
    )

    schedule_by_line: dict[str, str] = {}
    for code, builder in schedule_registry.items():
        target_line = getattr(builder, "statement_line_code", None)
        if target_line and target_line not in schedule_by_line:
            schedule_by_line[target_line] = code

    mapping_coverage = calculate_mapping_coverage(tb_records, run_context.bridge)
    mapping_validation: ValidationResult = validate_mapping_records(list(run_context.mapping_records))

    line_results = build_line_results(
        calc_results, line_descriptions, run_context.configuration.tolerances, schedule_by_line=schedule_by_line
    )

    account_trace: list[AccountTraceEntry] = []
    for calc_result in calc_results:
        for contribution in calc_result.contributions:
            account_trace.append(AccountTraceEntry.from_contribution(contribution))

    off_balance_sheet_calc_result = calc_results_by_line.get(_OFF_BALANCE_SHEET_LINE_CODE)

    control_inputs = ControlRunInputs(
        tb_records=tb_records,
        mapping_coverage=mapping_coverage,
        mapping_validation=mapping_validation,
        line_results=line_results,
        schedule_results=schedule_results,
        bridge=run_context.bridge,
        off_balance_sheet_line_codes={_OFF_BALANCE_SHEET_LINE_CODE},
        off_balance_sheet_calc_result=off_balance_sheet_calc_result,
        asset_total=run_context.extra.get("asset_total"),
        liability_total=run_context.extra.get("liability_total"),
        equity_total=run_context.extra.get("equity_total"),
        subtotal_checks=tuple(run_context.extra.get("subtotal_checks", ())),
        expected_schedule_buckets=run_context.extra.get("expected_schedule_buckets"),
    )
    control_results, _overall_control_status = run_all_controls(control_inputs, run_context.configuration.tolerances)

    exceptions = run_diagnostics(
        mapping_issues=list(mapping_validation.issues),
        unmapped_accounts=list(mapping_coverage.unmapped_accounts),
        materiality=run_context.configuration.tolerances.materiality,
        line_results=line_results,
        schedule_results=schedule_results,
    )

    calculation_warnings = tuple(
        f"{calc_result.line_code}: {warning}"
        for calc_result in calc_results
        for warning in calc_result.warnings
    )
    all_warnings = tuple(warnings) + calculation_warnings

    return ReconciliationRun(
        run_id=run_context.run_id,
        configuration=run_context.configuration,
        selected_tb_snapshot=selected_tb_snapshot,
        status="COMPLETED",
        candidate_snapshot_comparison=candidate_snapshot_comparison or {},
        line_results=tuple(line_results),
        account_trace=tuple(account_trace),
        schedule_results=tuple(schedule_results),
        control_results=tuple(control_results),
        exceptions=exceptions,
        warnings=all_warnings,
        trial_balance=tuple(tb_records),
        financial_statement=tuple(reported_lines.values()),
        mapping_records=run_context.mapping_records,
        mapping_validation_issues=mapping_validation.issues,
        mapping_coverage_summary=mapping_coverage.to_dict(),
        calculation_results=tuple(calc_results),
    )
