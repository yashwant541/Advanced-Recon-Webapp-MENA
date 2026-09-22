"""Models describing reconciliation outcomes: lines, traces, runs.

Public contents
----------------
``AccountTraceEntry`` -- one fully-traceable account contribution row (the
audit lineage required by the spec: source file/sheet/row through to
presented amount and reconciliation status).
``ScheduleReconciliationResult`` -- tie-out outcome for one supporting
schedule.
``ReconciliationException`` -- one diagnostics-engine finding.
``LineReconciliationResult`` -- reported vs. calculated outcome for one
financial-statement line.
``ReconciliationRun`` -- the aggregate root returned by
``iraq_recon.api.run_reconciliation``.

Dependencies: ``decimal`` (standard library only).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from iraq_recon.constants import DiagnosticCode, ReconciliationStatus, Severity
from iraq_recon.models.calculation import CalculationContribution, CalculationResult
from iraq_recon.models.configuration import ReconciliationConfiguration
from iraq_recon.models.controls import ControlResult
from iraq_recon.models.mapping import MappingRecord
from iraq_recon.models.source import StatementLineRecord, TrialBalanceRecord
from iraq_recon.models.validation import MappingValidationIssue


@dataclass(frozen=True)
class AccountTraceEntry:
    """One fully-traceable account row, from source cell to presented amount.

    Field set matches the "Account Trace" export sheet (spec section 20) and
    the audit lineage requirement (spec section 5).
    """

    source_file: str
    source_sheet: str
    source_row: int
    account: str
    description: str
    original_balance: Decimal
    source_unit: str
    conversion_factor: Decimal
    converted_balance: Decimal
    statement_type: str
    natural_side: str
    economic_role: str
    ayra_category: str
    iraq_reporting_bucket: str
    financial_statement_line: str
    schedule_code: str | None
    presentation_sign: int
    presented_amount: Decimal
    mapping_method: str
    mapping_confidence: float
    mapping_rationale: str
    review_status: str = "OK"

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_file": self.source_file,
            "source_sheet": self.source_sheet,
            "source_row": self.source_row,
            "account": self.account,
            "description": self.description,
            "original_balance": str(self.original_balance),
            "source_unit": self.source_unit,
            "conversion_factor": str(self.conversion_factor),
            "converted_balance": str(self.converted_balance),
            "statement_type": self.statement_type,
            "natural_side": self.natural_side,
            "economic_role": self.economic_role,
            "ayra_category": self.ayra_category,
            "iraq_reporting_bucket": self.iraq_reporting_bucket,
            "financial_statement_line": self.financial_statement_line,
            "schedule_code": self.schedule_code,
            "presentation_sign": self.presentation_sign,
            "presented_amount": str(self.presented_amount),
            "mapping_method": self.mapping_method,
            "mapping_confidence": self.mapping_confidence,
            "mapping_rationale": self.mapping_rationale,
            "review_status": self.review_status,
        }

    @classmethod
    def from_contribution(
        cls,
        contribution: CalculationContribution,
        *,
        review_status: str = "OK",
    ) -> "AccountTraceEntry":
        """Build an entry from a calculator contribution's ``source_lineage``.

        The lineage dict is produced by calculators and is expected to carry
        every field this model needs; missing keys default conservatively
        rather than raising, since trace entries must never block a run.
        """
        lineage = contribution.source_lineage
        return cls(
            source_file=str(lineage.get("source_file", "")),
            source_sheet=str(lineage.get("source_sheet", "")),
            source_row=int(lineage.get("source_row", 0)),
            account=contribution.account,
            description=contribution.description,
            original_balance=Decimal(str(lineage.get("original_balance", "0"))),
            source_unit=str(lineage.get("source_unit", "")),
            conversion_factor=Decimal(str(lineage.get("conversion_factor", "1"))),
            converted_balance=contribution.converted_amount,
            statement_type=str(lineage.get("statement_type", "")),
            natural_side=str(lineage.get("natural_side", "")),
            economic_role=str(lineage.get("economic_role", "")),
            ayra_category=str(lineage.get("ayra_category", "")),
            iraq_reporting_bucket=str(lineage.get("iraq_reporting_bucket", "")),
            financial_statement_line=contribution.line_code,
            schedule_code=lineage.get("schedule_code"),
            presentation_sign=contribution.presentation_sign,
            presented_amount=contribution.presented_amount,
            mapping_method=str(lineage.get("mapping_method", "")),
            mapping_confidence=float(lineage.get("mapping_confidence", 1.0)),
            mapping_rationale=str(lineage.get("mapping_rationale", "")),
            review_status=review_status,
        )


@dataclass(frozen=True)
class ScheduleReconciliationResult:
    """Tie-out outcome for one supporting schedule.

    Attributes:
        schedule_code: e.g. ``"SCHEDULE_3"``.
        schedule_description: Human-readable name.
        schedule_total: Total computed from the schedule's own buckets.
        tb_total: Corresponding total reconstructed from the trial balance.
        statement_total: Corresponding amount on the main financial statement.
        variance_to_tb: ``schedule_total - tb_total``.
        variance_to_statement: ``schedule_total - statement_total``.
        status: Reconciliation status of the weakest of the two ties.
        bucket_results: Per-bucket breakdown (row/column/grand totals, etc).
        control_results: Control checks specific to this schedule.
    """

    schedule_code: str
    schedule_description: str
    schedule_total: Decimal
    tb_total: Decimal
    statement_total: Decimal
    variance_to_tb: Decimal
    variance_to_statement: Decimal
    status: ReconciliationStatus
    bucket_results: tuple[dict[str, Any], ...] = ()
    control_results: tuple[ControlResult, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schedule_code": self.schedule_code,
            "schedule_description": self.schedule_description,
            "schedule_total": str(self.schedule_total),
            "tb_total": str(self.tb_total),
            "statement_total": str(self.statement_total),
            "variance_to_tb": str(self.variance_to_tb),
            "variance_to_statement": str(self.variance_to_statement),
            "status": str(self.status),
            "bucket_results": [dict(b) for b in self.bucket_results],
            "control_results": [c.to_dict() for c in self.control_results],
        }


@dataclass(frozen=True)
class ReconciliationException:
    """One diagnostics-engine finding (spec section 17).

    Attributes:
        root_cause_code: See :class:`iraq_recon.constants.DiagnosticCode`.
        affected_account: Account number, if the finding is account-level.
        affected_line: Financial-statement line code, if line-level.
        supporting_values: Structured values backing the finding.
        likely_cause: Plain-language explanation.
        suggested_review_action: What a reviewer should do next.
        severity: Finding severity.
        can_continue: Whether the engine could proceed past this finding.
    """

    root_cause_code: DiagnosticCode
    likely_cause: str
    suggested_review_action: str
    severity: Severity = Severity.MEDIUM
    affected_account: str | None = None
    affected_line: str | None = None
    supporting_values: dict[str, Any] = field(default_factory=dict)
    can_continue: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "root_cause_code": str(self.root_cause_code),
            "affected_account": self.affected_account,
            "affected_line": self.affected_line,
            "supporting_values": dict(self.supporting_values),
            "likely_cause": self.likely_cause,
            "suggested_review_action": self.suggested_review_action,
            "severity": str(self.severity),
            "can_continue": self.can_continue,
        }


@dataclass(frozen=True)
class LineReconciliationResult:
    """Reported vs. calculated outcome for one financial-statement line."""

    line_code: str
    line_description: str
    reported_amount: Decimal
    calculated_amount: Decimal
    variance: Decimal
    absolute_variance: Decimal
    variance_percentage: Decimal | None
    tolerance: Decimal
    status: ReconciliationStatus
    formula: str
    supporting_accounts: tuple[str, ...] = ()
    supporting_schedule: str | None = None
    accounting_explanation: str = ""
    review_required: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "line_code": self.line_code,
            "line_description": self.line_description,
            "reported_amount": str(self.reported_amount),
            "calculated_amount": str(self.calculated_amount),
            "variance": str(self.variance),
            "absolute_variance": str(self.absolute_variance),
            "variance_percentage": str(self.variance_percentage) if self.variance_percentage is not None else None,
            "tolerance": str(self.tolerance),
            "status": str(self.status),
            "formula": self.formula,
            "supporting_accounts": list(self.supporting_accounts),
            "supporting_schedule": self.supporting_schedule,
            "accounting_explanation": self.accounting_explanation,
            "review_required": self.review_required,
        }


@dataclass(frozen=True)
class ReconciliationRun:
    """Aggregate root: the complete outcome of one reconciliation execution.

    In addition to the final reconciliation outcome, this retains the
    "middle process" artifacts a reviewer needs to see *how* a result was
    reached -- the standardized trial balance and financial statement as
    actually used, the mapping table and its validation findings, mapping
    coverage, and the raw per-calculator :class:`CalculationResult` list
    (formula, included/excluded/deducted accounts, warnings) that
    ``line_results``/``account_trace`` were themselves derived from. None of
    this is recomputed later -- it is captured once, at run time, and never
    mutated.
    """

    run_id: str
    configuration: ReconciliationConfiguration
    selected_tb_snapshot: str
    status: str = "COMPLETED"
    candidate_snapshot_comparison: dict[str, Any] = field(default_factory=dict)
    line_results: tuple[LineReconciliationResult, ...] = ()
    account_trace: tuple[AccountTraceEntry, ...] = ()
    schedule_results: tuple[ScheduleReconciliationResult, ...] = ()
    control_results: tuple[ControlResult, ...] = ()
    exceptions: tuple[ReconciliationException, ...] = ()
    warnings: tuple[str, ...] = ()
    trial_balance: tuple[TrialBalanceRecord, ...] = ()
    financial_statement: tuple[StatementLineRecord, ...] = ()
    mapping_records: tuple[MappingRecord, ...] = ()
    mapping_validation_issues: tuple[MappingValidationIssue, ...] = ()
    mapping_coverage_summary: dict[str, Any] = field(default_factory=dict)
    calculation_results: tuple[CalculationResult, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "configuration": self.configuration.to_dict(),
            "selected_tb_snapshot": self.selected_tb_snapshot,
            "candidate_snapshot_comparison": dict(self.candidate_snapshot_comparison),
            "line_results": [line.to_dict() for line in self.line_results],
            "account_trace": [entry.to_dict() for entry in self.account_trace],
            "schedule_results": [s.to_dict() for s in self.schedule_results],
            "control_results": [c.to_dict() for c in self.control_results],
            "exceptions": [e.to_dict() for e in self.exceptions],
            "warnings": list(self.warnings),
            "trial_balance": [r.to_dict() for r in self.trial_balance],
            "financial_statement": [line.to_dict() for line in self.financial_statement],
            "mapping_records": [m.to_dict() for m in self.mapping_records],
            "mapping_validation_issues": [i.to_dict() for i in self.mapping_validation_issues],
            "mapping_coverage_summary": dict(self.mapping_coverage_summary),
            "calculation_results": [c.to_dict() for c in self.calculation_results],
        }

    def summary_dict(self) -> dict[str, Any]:
        """Compact summary suitable for a WebApp response (no bulk data)."""
        status_counts: dict[str, int] = {}
        for line in self.line_results:
            key = str(line.status)
            status_counts[key] = status_counts.get(key, 0) + 1

        exception_counts: dict[str, int] = {}
        for exc in self.exceptions:
            key = str(exc.severity)
            exception_counts[key] = exception_counts.get(key, 0) + 1

        control_status = "PASS"
        for control in self.control_results:
            if str(control.status) == "FAIL":
                control_status = "FAIL"
                break
            if str(control.status) == "WARN" and control_status != "FAIL":
                control_status = "WARN"

        return {
            "run_id": self.run_id,
            "status": self.status,
            "selected_tb_snapshot": self.selected_tb_snapshot,
            "line_count": len(self.line_results),
            "line_status_counts": status_counts,
            "schedule_count": len(self.schedule_results),
            "control_count": len(self.control_results),
            "overall_control_status": control_status,
            "exception_count": len(self.exceptions),
            "exception_count_by_severity": exception_counts,
            "warning_count": len(self.warnings),
        }
