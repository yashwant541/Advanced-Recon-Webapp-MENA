"""Dataiku-backed run repository (spec section 5 and 19).

Purpose
-------
Persist a full :class:`ReconciliationRun` as JSON in a managed folder (the
authoritative store used for exact round-trip retrieval by ``get()``), and
additionally write the flat ``RECON_*`` analytical datasets from spec
section 19 on a best-effort basis for BI/downstream consumption. This
module imports only ``iraq_recon.adapters.dataiku_io`` and
``iraq_recon.adapters.dataset_adapter`` -- never ``dataiku`` directly.

Public contents: ``DataikuRunRepository``.
Dependencies: ``iraq_recon.adapters.dataiku_io``,
``iraq_recon.adapters.dataset_adapter``, ``iraq_recon.adapters.folder_adapter``.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from iraq_recon.adapters.dataiku_io import write_dataiku_dataset
from iraq_recon.adapters.dataset_adapter import (
    RESULT_TABLE_NAMES,
    account_trace_to_dataframe,
    control_results_to_dataframe,
    exceptions_to_dataframe,
    line_results_to_dataframe,
    run_control_to_dataframe,
    schedule_results_to_dataframe,
)
from iraq_recon.adapters.folder_adapter import load_json, save_json
from iraq_recon.constants import (
    ControlStatus,
    DiagnosticCode,
    EconomicRole,
    InclusionStatus,
    MappingMethod,
    NaturalSide,
    ReconciliationStatus,
    RowType,
    Severity,
    StatementType,
)
from iraq_recon.exceptions import NotFoundError
from iraq_recon.models.calculation import CalculationContribution, CalculationResult
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
from iraq_recon.models.validation import MappingValidationIssue
from iraq_recon.repositories.run_repository import RunRepository


def _decimal_or_none(value: str | None) -> Decimal | None:
    return None if value is None else Decimal(value)


def _control_from_dict(data: dict[str, Any]) -> ControlResult:
    return ControlResult(
        control_code=data["control_code"],
        control_description=data["control_description"],
        status=ControlStatus(data["status"]),
        severity=Severity(data["severity"]),
        expected_amount=_decimal_or_none(data.get("expected_amount")),
        actual_amount=_decimal_or_none(data.get("actual_amount")),
        variance=_decimal_or_none(data.get("variance")),
        details=dict(data.get("details", {})),
    )


def _exception_from_dict(data: dict[str, Any]) -> ReconciliationException:
    return ReconciliationException(
        root_cause_code=DiagnosticCode(data["root_cause_code"]),
        likely_cause=data["likely_cause"],
        suggested_review_action=data["suggested_review_action"],
        severity=Severity(data["severity"]),
        affected_account=data.get("affected_account"),
        affected_line=data.get("affected_line"),
        supporting_values=dict(data.get("supporting_values", {})),
        can_continue=data.get("can_continue", True),
    )


def _line_from_dict(data: dict[str, Any]) -> LineReconciliationResult:
    return LineReconciliationResult(
        line_code=data["line_code"],
        line_description=data["line_description"],
        reported_amount=Decimal(data["reported_amount"]),
        calculated_amount=Decimal(data["calculated_amount"]),
        variance=Decimal(data["variance"]),
        absolute_variance=Decimal(data["absolute_variance"]),
        variance_percentage=_decimal_or_none(data.get("variance_percentage")),
        tolerance=Decimal(data["tolerance"]),
        status=ReconciliationStatus(data["status"]),
        formula=data["formula"],
        supporting_accounts=tuple(data.get("supporting_accounts", [])),
        supporting_schedule=data.get("supporting_schedule"),
        accounting_explanation=data.get("accounting_explanation", ""),
        review_required=data.get("review_required", False),
    )


def _trace_entry_from_dict(data: dict[str, Any]) -> AccountTraceEntry:
    return AccountTraceEntry(
        source_file=data["source_file"],
        source_sheet=data["source_sheet"],
        source_row=data["source_row"],
        account=data["account"],
        description=data["description"],
        original_balance=Decimal(data["original_balance"]),
        source_unit=data["source_unit"],
        conversion_factor=Decimal(data["conversion_factor"]),
        converted_balance=Decimal(data["converted_balance"]),
        statement_type=data["statement_type"],
        natural_side=data["natural_side"],
        economic_role=data["economic_role"],
        ayra_category=data["ayra_category"],
        iraq_reporting_bucket=data["iraq_reporting_bucket"],
        financial_statement_line=data["financial_statement_line"],
        schedule_code=data.get("schedule_code"),
        presentation_sign=data["presentation_sign"],
        presented_amount=Decimal(data["presented_amount"]),
        mapping_method=data["mapping_method"],
        mapping_confidence=data["mapping_confidence"],
        mapping_rationale=data["mapping_rationale"],
        review_status=data.get("review_status", "OK"),
    )


def _schedule_from_dict(data: dict[str, Any]) -> ScheduleReconciliationResult:
    return ScheduleReconciliationResult(
        schedule_code=data["schedule_code"],
        schedule_description=data["schedule_description"],
        schedule_total=Decimal(data["schedule_total"]),
        tb_total=Decimal(data["tb_total"]),
        statement_total=Decimal(data["statement_total"]),
        variance_to_tb=Decimal(data["variance_to_tb"]),
        variance_to_statement=Decimal(data["variance_to_statement"]),
        status=ReconciliationStatus(data["status"]),
        bucket_results=tuple(data.get("bucket_results", [])),
        control_results=tuple(_control_from_dict(c) for c in data.get("control_results", [])),
    )


def _trial_balance_record_from_dict(data: dict[str, Any]) -> TrialBalanceRecord:
    return TrialBalanceRecord(
        account_number=data["account_number"],
        account_description=data["account_description"],
        original_balance=Decimal(data["original_balance"]),
        normalized_balance=Decimal(data["normalized_balance"]),
        source_unit=data["source_unit"],
        source_sheet=data["source_sheet"],
        source_row=data["source_row"],
        source_file=data["source_file"],
        converted_balance=_decimal_or_none(data.get("converted_balance")),
        statement_type=StatementType(data.get("statement_type", "UNKNOWN")),
        natural_side=NaturalSide(data.get("natural_side", "UNKNOWN")),
        row_type=RowType(data.get("row_type", "UNKNOWN")),
        posting_status=data.get("posting_status", "POSTS"),
    )


def _statement_line_record_from_dict(data: dict[str, Any]) -> StatementLineRecord:
    return StatementLineRecord(
        line_code=data["line_code"],
        line_description=data["line_description"],
        reported_amount=Decimal(data["reported_amount"]),
        unit=data["unit"],
        source_file=data["source_file"],
        source_sheet=data["source_sheet"],
        source_location=data["source_location"],
        currency_classification=data.get("currency_classification"),
        residency_classification=data.get("residency_classification"),
        schedule_code=data.get("schedule_code"),
    )


def _mapping_record_from_dict(data: dict[str, Any]) -> MappingRecord:
    from datetime import date as _date

    effective_from = _date.fromisoformat(data["effective_from"]) if data.get("effective_from") else None
    effective_to = _date.fromisoformat(data["effective_to"]) if data.get("effective_to") else None
    return MappingRecord(
        local_account=data["local_account"],
        local_description=data["local_description"],
        local_account_group=data.get("local_account_group"),
        statement_type=StatementType(data["statement_type"]),
        natural_side=NaturalSide(data["natural_side"]),
        economic_role=EconomicRole(data["economic_role"]),
        ayra_category=data["ayra_category"],
        iraq_reporting_bucket=data["iraq_reporting_bucket"],
        financial_statement_line=data["financial_statement_line"],
        schedule_code=data.get("schedule_code"),
        schedule_row=data.get("schedule_row"),
        presentation_sign=data["presentation_sign"],
        inclusion_status=InclusionStatus(data.get("inclusion_status", "INCLUDE")),
        unit_factor=Decimal(data.get("unit_factor", "1")),
        mapping_method=MappingMethod(data.get("mapping_method", "APPROVED_ACCOUNT")),
        mapping_confidence=data.get("mapping_confidence", 1.0),
        effective_from=effective_from,
        effective_to=effective_to,
        mapping_rationale=data.get("mapping_rationale", ""),
        metadata=dict(data.get("metadata", {})),
    )


def _mapping_validation_issue_from_dict(data: dict[str, Any]) -> MappingValidationIssue:
    return MappingValidationIssue(
        issue_code=data["issue_code"],
        severity=Severity(data["severity"]),
        description=data["description"],
        local_account=data.get("local_account"),
        details=dict(data.get("details", {})),
    )


def _contribution_from_dict(data: dict[str, Any]) -> CalculationContribution:
    return CalculationContribution(
        line_code=data["line_code"],
        account=data["account"],
        description=data["description"],
        converted_amount=Decimal(data["converted_amount"]),
        presentation_sign=data["presentation_sign"],
        presented_amount=Decimal(data["presented_amount"]),
        formula_component=data["formula_component"],
        source_lineage=dict(data.get("source_lineage", {})),
    )


def _calculation_result_from_dict(data: dict[str, Any]) -> CalculationResult:
    return CalculationResult(
        line_code=data["line_code"],
        calculated_amount=Decimal(data["calculated_amount"]),
        contributions=tuple(_contribution_from_dict(c) for c in data.get("contributions", [])),
        formula=data["formula"],
        included_accounts=tuple(data.get("included_accounts", [])),
        deducted_accounts=tuple(data.get("deducted_accounts", [])),
        excluded_accounts=tuple(data.get("excluded_accounts", [])),
        reported_amount=_decimal_or_none(data.get("reported_amount")),
        variance=_decimal_or_none(data.get("variance")),
        status=data.get("status"),
        accounting_explanation=data.get("accounting_explanation", ""),
        warnings=tuple(data.get("warnings", [])),
    )


def _run_from_dict(data: dict[str, Any]) -> ReconciliationRun:
    return ReconciliationRun(
        run_id=data["run_id"],
        configuration=ReconciliationConfiguration.from_dict(data["configuration"]),
        selected_tb_snapshot=data["selected_tb_snapshot"],
        status=data.get("status", "COMPLETED"),
        candidate_snapshot_comparison=dict(data.get("candidate_snapshot_comparison", {})),
        line_results=tuple(_line_from_dict(x) for x in data.get("line_results", [])),
        account_trace=tuple(_trace_entry_from_dict(x) for x in data.get("account_trace", [])),
        schedule_results=tuple(_schedule_from_dict(x) for x in data.get("schedule_results", [])),
        control_results=tuple(_control_from_dict(x) for x in data.get("control_results", [])),
        exceptions=tuple(_exception_from_dict(x) for x in data.get("exceptions", [])),
        warnings=tuple(data.get("warnings", [])),
        trial_balance=tuple(_trial_balance_record_from_dict(x) for x in data.get("trial_balance", [])),
        financial_statement=tuple(
            _statement_line_record_from_dict(x) for x in data.get("financial_statement", [])
        ),
        mapping_records=tuple(_mapping_record_from_dict(x) for x in data.get("mapping_records", [])),
        mapping_validation_issues=tuple(
            _mapping_validation_issue_from_dict(x) for x in data.get("mapping_validation_issues", [])
        ),
        mapping_coverage_summary=dict(data.get("mapping_coverage_summary", {})),
        calculation_results=tuple(
            _calculation_result_from_dict(x) for x in data.get("calculation_results", [])
        ),
    )


class DataikuRunRepository(RunRepository):
    """Stores each run as a JSON file in a Dataiku managed folder.

    Args:
        folder_id: Managed folder id used as the authoritative run store.
        dataset_names: Optional override of :data:`RESULT_TABLE_NAMES` for
            the best-effort analytical dataset writes.
        write_analytical_datasets: When ``True`` (default), also write the
            flat ``RECON_*`` datasets on every ``save()``.
    """

    def __init__(
        self,
        folder_id: str,
        *,
        dataset_names: dict[str, str] | None = None,
        write_analytical_datasets: bool = True,
    ) -> None:
        self._folder_id = folder_id
        self._dataset_names = {**RESULT_TABLE_NAMES, **(dataset_names or {})}
        self._write_analytical_datasets = write_analytical_datasets

    def _run_file_path(self, run_id: str) -> str:
        return f"runs/{run_id}.json"

    def save(self, run: ReconciliationRun) -> None:
        save_json(self._folder_id, self._run_file_path(run.run_id), run.to_dict())

        if not self._write_analytical_datasets:
            return

        write_dataiku_dataset(self._dataset_names["run_control"], run_control_to_dataframe(run))
        write_dataiku_dataset(self._dataset_names["line_results"], line_results_to_dataframe(run))
        write_dataiku_dataset(self._dataset_names["account_trace"], account_trace_to_dataframe(run))
        write_dataiku_dataset(self._dataset_names["schedule_results"], schedule_results_to_dataframe(run))
        write_dataiku_dataset(self._dataset_names["control_results"], control_results_to_dataframe(run))
        write_dataiku_dataset(self._dataset_names["exceptions"], exceptions_to_dataframe(run))

    def get(self, run_id: str) -> ReconciliationRun:
        try:
            data = load_json(self._folder_id, self._run_file_path(run_id))
        except Exception as exc:
            raise NotFoundError(
                f"No reconciliation run found with id '{run_id}'.",
                details={"run_id": run_id},
            ) from exc
        return _run_from_dict(data)

    def list_run_ids(self) -> list[str]:
        from iraq_recon.adapters.dataiku_io import list_managed_folder_files

        paths = list_managed_folder_files(self._folder_id)
        return [
            path.rsplit("/", 1)[-1][: -len(".json")]
            for path in paths
            if path.startswith("runs/") and path.endswith(".json")
        ]

    def delete(self, run_id: str) -> None:
        # Managed-folder deletion is intentionally not exposed by
        # adapters.dataiku_io (spec lists only read/list/write); deleting a
        # persisted run is an explicit, reviewer-triggered action handled at
        # the WebApp/service layer, not silently supported here.
        raise NotImplementedError(
            "Deleting a persisted Dataiku run is not supported by this repository."
        )
