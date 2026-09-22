"""Reconciliation service: run, persist, and drill into reconciliation runs.

Purpose
-------
Give the public API one place to call to execute a full reconciliation
(building the run context, invoking the engine, persisting the result) and
to fetch summaries or detail slices afterward, so no caller depends on
``iraq_recon.engine`` or ``iraq_recon.repositories`` directly.

Public contents
----------------
``run_reconciliation(...)``
``get_run_summary(run_id, run_repository)``
``get_line_breakdown(run_id, line_code, result_repository)``
``get_account_trace(run_id, result_repository, ...)``
``get_schedule_reconciliation(run_id, schedule_code, result_repository)``
``get_control_results(run_id, result_repository)``
``get_exceptions(run_id, result_repository, ...)``

Dependencies: ``iraq_recon.engine.run_context``,
``iraq_recon.engine.reconciliation_engine``, ``iraq_recon.repositories.*``.
"""

from __future__ import annotations

from typing import Any

from iraq_recon.calculators.base import AccountingCalculator
from iraq_recon.engine.reconciliation_engine import run_reconciliation as _run_reconciliation
from iraq_recon.engine.run_context import build_run_context
from iraq_recon.models.calculation import CalculationResult
from iraq_recon.models.configuration import ReconciliationConfiguration
from iraq_recon.models.controls import ControlResult
from iraq_recon.models.mapping import MappingRecord
from iraq_recon.models.reconciliation import (
    AccountTraceEntry,
    LineReconciliationResult,
    ReconciliationException,
    ReconciliationRun,
    ScheduleReconciliationResult,
)
from iraq_recon.models.source import StatementLineRecord, TrialBalanceRecord
from iraq_recon.repositories.result_repository import ResultRepository
from iraq_recon.repositories.run_repository import RunRepository
from iraq_recon.schedules.base import ScheduleBuilder


def run_reconciliation(
    *,
    trial_balance: list[TrialBalanceRecord],
    financial_statement: dict[str, StatementLineRecord],
    mappings: list[MappingRecord],
    configuration: ReconciliationConfiguration,
    run_repository: RunRepository,
    run_id: str | None = None,
    selected_tb_snapshot: str = "",
    line_descriptions: dict[str, str] | None = None,
    calculator_registry: dict[str, AccountingCalculator] | None = None,
    schedule_registry: dict[str, ScheduleBuilder] | None = None,
    candidate_snapshot_comparison: dict[str, Any] | None = None,
    warnings: tuple[str, ...] = (),
) -> ReconciliationRun:
    """Run the full reconciliation pipeline and persist the result.

    Args:
        trial_balance: Normalized trial-balance records for the selected
            snapshot.
        financial_statement: Reported financial-statement lines, keyed by
            line code.
        mappings: All loaded mapping records.
        configuration: The run configuration.
        run_repository: Where to persist the completed run.
        run_id: Stable run identifier; generated if omitted.
        selected_tb_snapshot: Identifier of the TB snapshot used.
        line_descriptions: ``{line_code: description}`` for display.
        calculator_registry: Calculators to run; defaults to the 12 standard
            calculators.
        schedule_registry: Schedules to run; defaults to the standard registry.
        candidate_snapshot_comparison: Snapshot-comparison evidence to carry
            through for display.
        warnings: Warnings from earlier pipeline stages to carry through.

    Returns:
        The completed, persisted :class:`ReconciliationRun`.
    """
    run_context = build_run_context(configuration, mappings, run_id=run_id)
    run = _run_reconciliation(
        run_context,
        trial_balance,
        financial_statement,
        selected_tb_snapshot=selected_tb_snapshot,
        line_descriptions=line_descriptions,
        calculator_registry=calculator_registry,
        schedule_registry=schedule_registry,
        candidate_snapshot_comparison=candidate_snapshot_comparison,
        warnings=warnings,
    )
    run_repository.save(run)
    return run


def get_run_summary(run_id: str, run_repository: RunRepository) -> dict[str, Any]:
    """Return a completed run's compact summary (see ``ReconciliationRun.summary_dict``)."""
    return run_repository.get(run_id).summary_dict()


def get_line_breakdown(
    run_id: str, line_code: str, result_repository: ResultRepository
) -> LineReconciliationResult:
    """Return one line's full reconciliation result."""
    return result_repository.get_line_result(run_id, line_code)


def list_line_results(run_id: str, result_repository: ResultRepository) -> list[LineReconciliationResult]:
    """Return every line result for a run (small, fixed-size list -- one per
    calculator that ran), for populating an initial results table."""
    return result_repository.list_line_results(run_id)


def get_account_trace(
    run_id: str,
    result_repository: ResultRepository,
    *,
    line_code: str | None = None,
    account: str | None = None,
    offset: int = 0,
    limit: int = 100,
) -> tuple[list[AccountTraceEntry], int]:
    """Return a filtered, paginated page of account-trace entries."""
    return result_repository.get_account_trace(
        run_id, line_code=line_code, account=account, offset=offset, limit=limit
    )


def get_schedule_reconciliation(
    run_id: str, schedule_code: str, result_repository: ResultRepository
) -> ScheduleReconciliationResult:
    """Return one schedule's reconciliation result."""
    return result_repository.get_schedule_result(run_id, schedule_code)


def get_calculation_detail(
    run_id: str, line_code: str, result_repository: ResultRepository
) -> CalculationResult:
    """Return one line's raw calculator output: formula, included/deducted/
    excluded accounts with reasons, and warnings -- the finer detail behind
    the line result's reported/calculated/variance summary."""
    return result_repository.get_calculation_result(run_id, line_code)


def get_full_run(run_id: str, run_repository: RunRepository) -> ReconciliationRun:
    """Return the complete, persisted :class:`ReconciliationRun` (e.g. for export)."""
    return run_repository.get(run_id)


def get_control_results(run_id: str, result_repository: ResultRepository) -> list[ControlResult]:
    """Return every control result for a run."""
    return result_repository.get_control_results(run_id)


def get_exceptions(
    run_id: str,
    result_repository: ResultRepository,
    *,
    severity: str | None = None,
    offset: int = 0,
    limit: int = 100,
) -> tuple[list[ReconciliationException], int]:
    """Return a filtered, paginated page of diagnosed exceptions."""
    return result_repository.get_exceptions(run_id, severity=severity, offset=offset, limit=limit)
