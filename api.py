"""Public API: the only recommended entry point for the Dataiku WebApp.

Purpose
-------
Hide every internal module (ingestion, normalization, mapping, rules,
calculators, schedules, engine, controls, services) behind one flat,
stable surface. The thin WebApp ``backend.py`` should import only from
this module (plus ``iraq_recon.exceptions`` for error handling) -- never
from ``iraq_recon.ingestion``, ``iraq_recon.engine``, etc. directly.

Every function here delegates to exactly one ``iraq_recon.services.*``
function; this module adds no business logic of its own, only a default
in-memory repository pair so callers (including unit tests) do not have to
wire up persistence just to run a reconciliation. A Dataiku deployment
passes its own ``repositories.dataiku_repository.DataikuRunRepository``
via ``run_repository``/``result_repository`` instead.

Dependencies: ``iraq_recon.services.*``, ``iraq_recon.repositories.*``.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from iraq_recon.calculators.base import AccountingCalculator
from iraq_recon.engine.combination_matcher import CombinationMatch
from iraq_recon.engine.snapshot_selector import AnchorDefinition, SnapshotEvidence
from iraq_recon.ingestion.workbook_inspector import WorkbookInspection
from iraq_recon.mapping.mapping_coverage import MappingCoverageResult
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
from iraq_recon.models.source import SourceFile, StatementLineRecord, TrialBalanceRecord
from iraq_recon.models.validation import ValidationResult
from iraq_recon.repositories.in_memory_repository import InMemoryRunRepository
from iraq_recon.repositories.result_repository import GenericResultRepository, ResultRepository
from iraq_recon.repositories.run_repository import RunRepository
from iraq_recon.schedules.base import ScheduleBuilder
from iraq_recon.services import (
    export_service,
    inspection_service,
    mapping_service,
    reconciliation_service,
    review_service,
    snapshot_service,
    validation_service,
)

#: Default in-memory repositories, used when a caller does not supply its
#: own (e.g. a Dataiku-backed pair). Local/standalone use and unit tests
#: never need to construct a repository just to call this API.
_default_run_repository = InMemoryRunRepository()
_default_result_repository = GenericResultRepository(_default_run_repository)


def inspect_source_file(filename: str, content: bytes) -> WorkbookInspection:
    """Inspect every sheet of an uploaded source workbook."""
    return inspection_service.inspect_source_file(filename, content)


def inspect_workbook(
    filename: str, content: bytes, sheet_names: list[str] | None = None
) -> WorkbookInspection:
    """Inspect specific (or all) sheets of an uploaded source workbook."""
    return inspection_service.inspect_workbook(filename, content, sheet_names=sheet_names)


def list_workbook_sheets(filename: str, content: bytes) -> list[str]:
    """Return only the sheet names of an uploaded source workbook."""
    return inspection_service.list_workbook_sheets(filename, content)


def validate_inputs(
    configuration: dict[str, Any] | None,
    source_files: list[SourceFile] | None = None,
    required_roles: tuple[str, ...] = ("FINANCIAL_STATEMENT", "TRIAL_BALANCE"),
) -> ValidationResult:
    """Validate a configuration payload and (optionally) uploaded source files."""
    return validation_service.validate_inputs(configuration, source_files, required_roles)


def load_trial_balances(
    source_files: list[SourceFile],
) -> tuple[dict[str, list[TrialBalanceRecord]], dict[str, list[str]]]:
    """Extract and normalize every candidate trial-balance source file."""
    return snapshot_service.load_trial_balances(source_files)


def load_financial_statement(
    source_file: SourceFile,
) -> tuple[dict[str, StatementLineRecord], list[str]]:
    """Extract every reported line from a financial-statement source file."""
    return snapshot_service.load_financial_statement(source_file)


def load_mapping_files(source_files: list[SourceFile]) -> tuple[list[MappingRecord], list[str]]:
    """Extract and load mapping records from every mapping source file."""
    return mapping_service.load_mapping_files(source_files)


def validate_mappings(mapping_records: list[MappingRecord]) -> ValidationResult:
    """Validate a set of loaded mapping records for structural issues."""
    return mapping_service.validate_mappings(mapping_records)


def calculate_mapping_coverage(
    records: list[TrialBalanceRecord],
    mapping_records: list[MappingRecord],
    as_of: date | None = None,
) -> MappingCoverageResult:
    """Resolve a local-account bridge and calculate its coverage over ``records``."""
    return mapping_service.calculate_mapping_coverage(records, mapping_records, as_of)


def compare_tb_snapshots(
    trial_balances: dict[str, list[TrialBalanceRecord]],
    mappings: list[MappingRecord],
    configuration: ReconciliationConfiguration,
    *,
    anchors: list[AnchorDefinition] | None = None,
    anchor_reported_amounts: dict[str, Decimal] | None = None,
    as_of: date | None = None,
) -> list[SnapshotEvidence]:
    """Score every candidate trial balance against the anchor set."""
    return snapshot_service.compare_tb_snapshots(
        trial_balances, mappings, configuration,
        anchors=anchors, anchor_reported_amounts=anchor_reported_amounts, as_of=as_of,
    )


def select_best_snapshot(evidence: list[SnapshotEvidence]) -> str | None:
    """Return the top-ranked snapshot id from :func:`compare_tb_snapshots` output."""
    return snapshot_service.select_best_snapshot(evidence)


def override_snapshot_selection(evidence: list[SnapshotEvidence], override_snapshot_id: str) -> str:
    """Validate and accept a reviewer's manual TB snapshot override."""
    return review_service.override_snapshot_selection(evidence, override_snapshot_id)


def review_combination_match(
    match: CombinationMatch, *, decision: str, reviewed_by: str, notes: str = ""
) -> dict[str, Any]:
    """Record a reviewer's approve/reject decision on a provisional combination match."""
    return review_service.review_combination_match(
        match, decision=decision, reviewed_by=reviewed_by, notes=notes  # type: ignore[arg-type]
    )


def run_reconciliation(
    *,
    trial_balance: list[TrialBalanceRecord],
    financial_statement: dict[str, StatementLineRecord],
    mappings: list[MappingRecord],
    configuration: ReconciliationConfiguration,
    run_repository: RunRepository | None = None,
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
        run_repository: Where to persist the run; defaults to this module's
            shared in-memory repository (fine for local use and tests, but
            a Dataiku deployment should pass a
            ``repositories.dataiku_repository.DataikuRunRepository``).
        (see ``services.reconciliation_service.run_reconciliation`` for the
        remaining parameters.)

    Returns:
        The completed, persisted :class:`ReconciliationRun`.
    """
    return reconciliation_service.run_reconciliation(
        trial_balance=trial_balance,
        financial_statement=financial_statement,
        mappings=mappings,
        configuration=configuration,
        run_repository=run_repository or _default_run_repository,
        run_id=run_id,
        selected_tb_snapshot=selected_tb_snapshot,
        line_descriptions=line_descriptions,
        calculator_registry=calculator_registry,
        schedule_registry=schedule_registry,
        candidate_snapshot_comparison=candidate_snapshot_comparison,
        warnings=warnings,
    )


def get_run_summary(run_id: str, run_repository: RunRepository | None = None) -> dict[str, Any]:
    """Return a completed run's compact summary."""
    return reconciliation_service.get_run_summary(run_id, run_repository or _default_run_repository)


def get_full_run(run_id: str, run_repository: RunRepository | None = None) -> ReconciliationRun:
    """Return the complete, persisted :class:`ReconciliationRun` (e.g. for export).

    Prefer :func:`get_run_summary` and the drill-down getters for anything
    the WebApp renders directly -- this returns the full object graph and
    exists mainly so callers like ``export_reconciliation`` never need to
    reach into a repository's internals themselves.
    """
    return reconciliation_service.get_full_run(run_id, run_repository or _default_run_repository)


def get_line_breakdown(
    run_id: str, line_code: str, result_repository: ResultRepository | None = None
) -> LineReconciliationResult:
    """Return one line's full reconciliation result."""
    return reconciliation_service.get_line_breakdown(
        run_id, line_code, result_repository or _default_result_repository
    )


def list_line_results(
    run_id: str, result_repository: ResultRepository | None = None
) -> list[LineReconciliationResult]:
    """Return every line result for a run, for populating an initial results table."""
    return reconciliation_service.list_line_results(run_id, result_repository or _default_result_repository)


def get_account_trace(
    run_id: str,
    result_repository: ResultRepository | None = None,
    *,
    line_code: str | None = None,
    account: str | None = None,
    offset: int = 0,
    limit: int = 100,
) -> tuple[list[AccountTraceEntry], int]:
    """Return a filtered, paginated page of account-trace entries."""
    return reconciliation_service.get_account_trace(
        run_id, result_repository or _default_result_repository,
        line_code=line_code, account=account, offset=offset, limit=limit,
    )


def get_schedule_reconciliation(
    run_id: str, schedule_code: str, result_repository: ResultRepository | None = None
) -> ScheduleReconciliationResult:
    """Return one schedule's reconciliation result."""
    return reconciliation_service.get_schedule_reconciliation(
        run_id, schedule_code, result_repository or _default_result_repository
    )


def get_calculation_detail(
    run_id: str, line_code: str, result_repository: ResultRepository | None = None
) -> CalculationResult:
    """Return one line's raw calculator output: formula, included/deducted/
    excluded accounts with reasons, and warnings ("how did we get this
    number" -- the finer detail behind :func:`get_line_breakdown`)."""
    return reconciliation_service.get_calculation_detail(
        run_id, line_code, result_repository or _default_result_repository
    )


def get_control_results(
    run_id: str, result_repository: ResultRepository | None = None
) -> list[ControlResult]:
    """Return every control result for a run."""
    return reconciliation_service.get_control_results(run_id, result_repository or _default_result_repository)


def get_exceptions(
    run_id: str,
    result_repository: ResultRepository | None = None,
    *,
    severity: str | None = None,
    offset: int = 0,
    limit: int = 100,
) -> tuple[list[ReconciliationException], int]:
    """Return a filtered, paginated page of diagnosed exceptions."""
    return reconciliation_service.get_exceptions(
        run_id, result_repository or _default_result_repository,
        severity=severity, offset=offset, limit=limit,
    )


def export_reconciliation(run: ReconciliationRun, export_format: str = "xlsx") -> bytes:
    """Export a completed reconciliation run to the requested format.

    ``export_format`` accepts ``"xlsx"`` (the full audit workbook),
    ``"json"`` (raw serialized result), or ``"process_trace"`` (the
    "middle process" workbook: standardized data, mapping table, mapping
    validation/coverage, and per-calculator detail).
    """
    return export_service.export_reconciliation(run, export_format)


def export_standardized_trial_balance(records: list[TrialBalanceRecord]) -> bytes:
    """Export a standardized-format workbook for a normalized trial balance.

    Usable independently of running a full reconciliation, so a reviewer
    can check how the engine parsed and classified an uploaded trial
    balance before committing to mapping.
    """
    return export_service.export_standardized_trial_balance(records)


def export_standardized_financial_statement(lines: list[StatementLineRecord]) -> bytes:
    """Export a standardized-format workbook for a normalized financial statement.

    Usable independently of running a full reconciliation, so a reviewer
    can check how the engine parsed an uploaded submission before running
    the reconciliation.
    """
    return export_service.export_standardized_financial_statement(lines)
