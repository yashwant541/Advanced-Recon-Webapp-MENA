"""Diagnostics engine: root-cause exceptions from run outputs (spec section 17).

Purpose
-------
Turn the outputs of earlier stages (mapping validation, mapping coverage,
line results, schedule results) into structured
:class:`iraq_recon.models.reconciliation.ReconciliationException` findings
with a root-cause code, severity, and suggested review action -- so a
reviewer gets a triaged list instead of raw variances.

Public contents
----------------
``diagnose_mapping_issues(issues)``
``diagnose_unmapped_accounts(unmapped_accounts, materiality)``
``diagnose_line_results(line_results)``
``diagnose_schedule_results(schedule_results)``
``run_diagnostics(...)`` -- combine all of the above.

Dependencies: ``iraq_recon.constants``, ``iraq_recon.models.*``.
"""

from __future__ import annotations

from decimal import Decimal

from iraq_recon.constants import DiagnosticCode, ReconciliationStatus, Severity
from iraq_recon.mapping.mapping_coverage import UnmappedAccount
from iraq_recon.models.reconciliation import (
    LineReconciliationResult,
    ReconciliationException,
    ScheduleReconciliationResult,
)
from iraq_recon.models.validation import MappingValidationIssue

_MAPPING_ISSUE_TO_DIAGNOSTIC: dict[str, DiagnosticCode] = {
    "DUPLICATE_MAPPING": DiagnosticCode.DUPLICATE_MAPPING,
    "CONFLICTING_MAPPING": DiagnosticCode.CONFLICTING_MAPPING,
    "MISSING_AYRA_CATEGORY": DiagnosticCode.MISSING_PRESENTATION_SIGN,
    "MISSING_REPORTING_BUCKET": DiagnosticCode.MISSING_PRESENTATION_SIGN,
    "MISSING_STATEMENT_LINE": DiagnosticCode.MISSING_PRESENTATION_SIGN,
    "UNKNOWN_SEMANTIC_CATEGORY": DiagnosticCode.MISSING_PRESENTATION_SIGN,
    "UNKNOWN_REPORTING_BUCKET": DiagnosticCode.MISSING_PRESENTATION_SIGN,
    "BS_OFFBS_CONFLICT": DiagnosticCode.OFF_BS_MISCLASSIFICATION,
}

_LINE_STATUS_TO_DIAGNOSTIC: dict[ReconciliationStatus, DiagnosticCode] = {
    ReconciliationStatus.MATERIAL_BREAK: DiagnosticCode.SOURCE_DATA_DIFFERENCE,
    ReconciliationStatus.MAPPING_DIFFERENCE: DiagnosticCode.UNMAPPED_ACCOUNT,
    ReconciliationStatus.PRESENTATION_DIFFERENCE: DiagnosticCode.SIGN_MISMATCH,
    ReconciliationStatus.UNIT_DIFFERENCE: DiagnosticCode.UNIT_MISMATCH,
    ReconciliationStatus.SIGN_DIFFERENCE: DiagnosticCode.SIGN_MISMATCH,
    ReconciliationStatus.SCHEDULE_DIFFERENCE: DiagnosticCode.SCHEDULE_BREAK,
    ReconciliationStatus.SOURCE_DATA_DIFFERENCE: DiagnosticCode.SOURCE_DATA_DIFFERENCE,
    ReconciliationStatus.UNMAPPED_ACCOUNT: DiagnosticCode.UNMAPPED_ACCOUNT,
    ReconciliationStatus.DUPLICATE_MAPPING: DiagnosticCode.DUPLICATE_MAPPING,
    ReconciliationStatus.UNRESOLVED: DiagnosticCode.SOURCE_DATA_DIFFERENCE,
    ReconciliationStatus.ROUNDING_MATCH: DiagnosticCode.ROUNDING_DIFFERENCE,
    ReconciliationStatus.PRECISION_MATCH: DiagnosticCode.PRECISION_DIFFERENCE,
}


def diagnose_mapping_issues(issues: list[MappingValidationIssue]) -> list[ReconciliationException]:
    """Convert mapping-validation issues into diagnostic exceptions."""
    exceptions: list[ReconciliationException] = []
    for issue in issues:
        code = _MAPPING_ISSUE_TO_DIAGNOSTIC.get(issue.issue_code, DiagnosticCode.CONFLICTING_MAPPING)
        exceptions.append(
            ReconciliationException(
                root_cause_code=code,
                likely_cause=issue.description,
                suggested_review_action=(
                    "Review and correct the mapping table entry for this account "
                    "before relying on downstream totals."
                ),
                severity=issue.severity,
                affected_account=issue.local_account,
                supporting_values=dict(issue.details),
                can_continue=issue.severity not in (Severity.CRITICAL,),
            )
        )
    return exceptions


def diagnose_unmapped_accounts(
    unmapped_accounts: list[UnmappedAccount],
    materiality: Decimal,
) -> list[ReconciliationException]:
    """Convert non-zero unmapped accounts into diagnostic exceptions.

    Args:
        unmapped_accounts: From ``mapping.mapping_coverage``.
        materiality: Balances above this magnitude are flagged ``HIGH``
            severity rather than ``MEDIUM``.
    """
    exceptions: list[ReconciliationException] = []
    for account in unmapped_accounts:
        severity = Severity.HIGH if abs(account.balance) > materiality else Severity.MEDIUM
        exceptions.append(
            ReconciliationException(
                root_cause_code=DiagnosticCode.UNMAPPED_ACCOUNT,
                likely_cause=(
                    f"Account '{account.account_number}' ({account.account_description}) "
                    f"has a non-zero balance of {account.balance} but no approved mapping."
                ),
                suggested_review_action=(
                    "Add an approved mapping for this account, or confirm it should "
                    "remain unmapped and document why."
                ),
                severity=severity,
                affected_account=account.account_number,
                supporting_values={"balance": str(account.balance), "source_file": account.source_file},
            )
        )
    return exceptions


def diagnose_line_results(line_results: list[LineReconciliationResult]) -> list[ReconciliationException]:
    """Convert line reconciliation results needing review into exceptions."""
    exceptions: list[ReconciliationException] = []
    for line in line_results:
        if not line.review_required:
            continue
        code = _LINE_STATUS_TO_DIAGNOSTIC.get(line.status, DiagnosticCode.SOURCE_DATA_DIFFERENCE)
        severity = Severity.HIGH if line.status == ReconciliationStatus.MATERIAL_BREAK else Severity.MEDIUM
        exceptions.append(
            ReconciliationException(
                root_cause_code=code,
                likely_cause=(
                    f"Line '{line.line_code}' has status {line.status} with a variance of "
                    f"{line.variance} ({line.reported_amount} reported vs "
                    f"{line.calculated_amount} calculated)."
                ),
                suggested_review_action="Investigate the contributing accounts and mapping for this line.",
                severity=severity,
                affected_line=line.line_code,
                supporting_values={
                    "reported_amount": str(line.reported_amount),
                    "calculated_amount": str(line.calculated_amount),
                    "variance": str(line.variance),
                },
            )
        )
    return exceptions


def diagnose_schedule_results(
    schedule_results: list[ScheduleReconciliationResult],
) -> list[ReconciliationException]:
    """Convert schedule tie-out breaks into exceptions."""
    exceptions: list[ReconciliationException] = []
    for schedule in schedule_results:
        if schedule.status in (ReconciliationStatus.EXACT_MATCH, ReconciliationStatus.PRECISION_MATCH, ReconciliationStatus.ROUNDING_MATCH):
            continue
        exceptions.append(
            ReconciliationException(
                root_cause_code=DiagnosticCode.SCHEDULE_BREAK,
                likely_cause=(
                    f"Schedule '{schedule.schedule_code}' has status {schedule.status}: "
                    f"variance to TB {schedule.variance_to_tb}, variance to statement "
                    f"{schedule.variance_to_statement}."
                ),
                suggested_review_action="Investigate the schedule's bucket breakdown against the TB and statement.",
                severity=Severity.HIGH if schedule.status == ReconciliationStatus.MATERIAL_BREAK else Severity.MEDIUM,
                affected_line=schedule.schedule_code,
                supporting_values={
                    "variance_to_tb": str(schedule.variance_to_tb),
                    "variance_to_statement": str(schedule.variance_to_statement),
                },
            )
        )
    return exceptions


def run_diagnostics(
    *,
    mapping_issues: list[MappingValidationIssue] | None = None,
    unmapped_accounts: list[UnmappedAccount] | None = None,
    materiality: Decimal = Decimal("1000"),
    line_results: list[LineReconciliationResult] | None = None,
    schedule_results: list[ScheduleReconciliationResult] | None = None,
) -> tuple[ReconciliationException, ...]:
    """Run every diagnostic pass and return the combined exception list."""
    exceptions: list[ReconciliationException] = []
    exceptions.extend(diagnose_mapping_issues(mapping_issues or []))
    exceptions.extend(diagnose_unmapped_accounts(unmapped_accounts or [], materiality))
    exceptions.extend(diagnose_line_results(line_results or []))
    exceptions.extend(diagnose_schedule_results(schedule_results or []))
    return tuple(exceptions)
