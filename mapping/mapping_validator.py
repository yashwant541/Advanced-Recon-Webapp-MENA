"""Structural validation of a loaded mapping table (spec section 8).

Purpose
-------
Detect mapping-table problems that are visible from the mapping records
alone (no trial-balance data needed): duplicate/overlapping mappings for
the same account, conflicting financial-statement lines without an
allocation rule, missing or unknown semantic categories/buckets, and
balance-sheet/off-balance-sheet role conflicts. Coverage against actual
trial-balance accounts (non-zero unmapped accounts) is a separate concern,
handled by ``mapping.mapping_coverage``.

Public contents
----------------
``validate_mapping_records(records)`` -- returns a
:class:`iraq_recon.models.validation.ValidationResult`.

Dependencies: ``iraq_recon.models.mapping``, ``iraq_recon.models.validation``,
``iraq_recon.mapping.ayra_mapper``, ``iraq_recon.mapping.reporting_mapper``.
"""

from __future__ import annotations

from datetime import date
from itertools import combinations

from iraq_recon.constants import EconomicRole, Severity, StatementType
from iraq_recon.mapping.ayra_mapper import is_known_ayra_category
from iraq_recon.mapping.reporting_mapper import is_known_reporting_bucket
from iraq_recon.models.mapping import MappingRecord
from iraq_recon.models.validation import MappingValidationIssue, ValidationResult

_OFF_BS_ROLES = (EconomicRole.OFF_BALANCE_SHEET_DEBIT, EconomicRole.OFF_BALANCE_SHEET_CREDIT)

_MIN_DATE = date.min
_MAX_DATE = date.max


def _windows_overlap(a: MappingRecord, b: MappingRecord) -> bool:
    a_start = a.effective_from or _MIN_DATE
    a_end = a.effective_to or _MAX_DATE
    b_start = b.effective_from or _MIN_DATE
    b_end = b.effective_to or _MAX_DATE
    return a_start <= b_end and b_start <= a_end


def _has_allocation_rule(record: MappingRecord) -> bool:
    return bool(record.metadata.get("allocation_rule"))


def validate_mapping_records(records: list[MappingRecord]) -> ValidationResult:
    """Validate a full set of loaded mapping records for structural issues.

    Args:
        records: All loaded :class:`MappingRecord` instances (any effective
            window; this validator checks overlaps explicitly rather than
            assuming a single as-of date).

    Returns:
        A :class:`ValidationResult`; ``is_valid`` is ``False`` only if at
        least one ``HIGH`` or ``CRITICAL`` issue was found.
    """
    issues: list[MappingValidationIssue] = []

    by_account: dict[str, list[MappingRecord]] = {}
    for record in records:
        by_account.setdefault(record.local_account, []).append(record)

    for account, account_records in by_account.items():
        for first, second in combinations(account_records, 2):
            if not _windows_overlap(first, second):
                continue

            issues.append(
                MappingValidationIssue(
                    issue_code="DUPLICATE_MAPPING",
                    severity=Severity.HIGH,
                    description=(
                        f"Account '{account}' has more than one mapping active "
                        f"over overlapping effective periods."
                    ),
                    local_account=account,
                    details={
                        "effective_from_1": first.effective_from.isoformat() if first.effective_from else None,
                        "effective_to_1": first.effective_to.isoformat() if first.effective_to else None,
                        "effective_from_2": second.effective_from.isoformat() if second.effective_from else None,
                        "effective_to_2": second.effective_to.isoformat() if second.effective_to else None,
                    },
                )
            )

            if first.financial_statement_line != second.financial_statement_line:
                if _has_allocation_rule(first) or _has_allocation_rule(second):
                    continue
                issues.append(
                    MappingValidationIssue(
                        issue_code="CONFLICTING_MAPPING",
                        severity=Severity.HIGH,
                        description=(
                            f"Account '{account}' maps to multiple financial statement "
                            f"lines ('{first.financial_statement_line}' vs "
                            f"'{second.financial_statement_line}') with no allocation rule."
                        ),
                        local_account=account,
                        details={
                            "line_1": first.financial_statement_line,
                            "line_2": second.financial_statement_line,
                        },
                    )
                )

    for record in records:
        if not record.ayra_category:
            issues.append(
                MappingValidationIssue(
                    issue_code="MISSING_AYRA_CATEGORY",
                    severity=Severity.MEDIUM,
                    description=f"Account '{record.local_account}' has no Ayra semantic category.",
                    local_account=record.local_account,
                )
            )
        elif not is_known_ayra_category(record.ayra_category):
            issues.append(
                MappingValidationIssue(
                    issue_code="UNKNOWN_SEMANTIC_CATEGORY",
                    severity=Severity.MEDIUM,
                    description=(
                        f"Account '{record.local_account}' uses unrecognized Ayra "
                        f"category '{record.ayra_category}'."
                    ),
                    local_account=record.local_account,
                    details={"ayra_category": record.ayra_category},
                )
            )

        if not record.iraq_reporting_bucket:
            issues.append(
                MappingValidationIssue(
                    issue_code="MISSING_REPORTING_BUCKET",
                    severity=Severity.MEDIUM,
                    description=f"Account '{record.local_account}' has no Iraq reporting bucket.",
                    local_account=record.local_account,
                )
            )
        elif not is_known_reporting_bucket(record.iraq_reporting_bucket):
            issues.append(
                MappingValidationIssue(
                    issue_code="UNKNOWN_REPORTING_BUCKET",
                    severity=Severity.MEDIUM,
                    description=(
                        f"Account '{record.local_account}' uses unrecognized reporting "
                        f"bucket '{record.iraq_reporting_bucket}'."
                    ),
                    local_account=record.local_account,
                    details={"iraq_reporting_bucket": record.iraq_reporting_bucket},
                )
            )

        if not record.financial_statement_line:
            issues.append(
                MappingValidationIssue(
                    issue_code="MISSING_STATEMENT_LINE",
                    severity=Severity.MEDIUM,
                    description=f"Account '{record.local_account}' has no financial statement line.",
                    local_account=record.local_account,
                )
            )

        is_off_bs_statement = record.statement_type == StatementType.OFF_BALANCE_SHEET
        is_off_bs_role = record.economic_role in _OFF_BS_ROLES
        if is_off_bs_statement != is_off_bs_role:
            issues.append(
                MappingValidationIssue(
                    issue_code="BS_OFFBS_CONFLICT",
                    severity=Severity.HIGH,
                    description=(
                        f"Account '{record.local_account}' has statement type "
                        f"'{record.statement_type}' but economic role "
                        f"'{record.economic_role}', which is inconsistent between "
                        f"balance-sheet and off-balance-sheet classification."
                    ),
                    local_account=record.local_account,
                    details={
                        "statement_type": str(record.statement_type),
                        "economic_role": str(record.economic_role),
                    },
                )
            )

    is_valid = not any(issue.severity in (Severity.HIGH, Severity.CRITICAL) for issue in issues)
    return ValidationResult(is_valid=is_valid, issues=tuple(issues))
