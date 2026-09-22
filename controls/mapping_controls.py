"""Mapping-level controls (spec section 18).

Purpose
-------
Turn mapping coverage metrics and mapping-validation issues into the
control set a reviewer checks before trusting a run's mapping: account and
value coverage thresholds, non-zero unmapped accounts, and counts of
duplicate/conflicting/invalid mapping issues.

Public contents
----------------
``build_mapping_controls(coverage, validation, min_account_coverage=...,
min_value_coverage=...)``.

Dependencies: ``iraq_recon.mapping.mapping_coverage``,
``iraq_recon.models.validation``.
"""

from __future__ import annotations

from decimal import Decimal

from iraq_recon.constants import ControlStatus, Severity
from iraq_recon.mapping.mapping_coverage import MappingCoverageResult
from iraq_recon.models.controls import ControlResult
from iraq_recon.models.validation import ValidationResult

_ISSUE_CONTROL_CODES: dict[str, str] = {
    "DUPLICATE_MAPPING": "MAPPING_DUPLICATE_CONTROL",
    "CONFLICTING_MAPPING": "MAPPING_CONFLICTING_LINE_CONTROL",
    "BS_OFFBS_CONFLICT": "MAPPING_BS_OFFBS_CONFLICT_CONTROL",
    "MISSING_AYRA_CATEGORY": "MAPPING_MISSING_CATEGORY_CONTROL",
    "MISSING_REPORTING_BUCKET": "MAPPING_MISSING_BUCKET_CONTROL",
    "MISSING_STATEMENT_LINE": "MAPPING_MISSING_STATEMENT_LINE_CONTROL",
    "UNKNOWN_SEMANTIC_CATEGORY": "MAPPING_UNKNOWN_CATEGORY_CONTROL",
    "UNKNOWN_REPORTING_BUCKET": "MAPPING_UNKNOWN_BUCKET_CONTROL",
}


def build_mapping_controls(
    coverage: MappingCoverageResult,
    validation: ValidationResult,
    *,
    min_account_coverage: Decimal = Decimal("0.98"),
    min_value_coverage: Decimal = Decimal("0.98"),
) -> list[ControlResult]:
    """Build the mapping control set from coverage and validation results.

    Args:
        coverage: Output of ``mapping.mapping_coverage.calculate_mapping_coverage``.
        validation: Output of ``mapping.mapping_validator.validate_mapping_records``.
        min_account_coverage: Minimum acceptable account-count coverage ratio.
        min_value_coverage: Minimum acceptable value coverage ratio.

    Returns:
        A list of :class:`ControlResult`.
    """
    controls: list[ControlResult] = [
        ControlResult(
            control_code="MAPPING_ACCOUNT_COVERAGE_CONTROL",
            control_description="Account-count coverage meets the minimum threshold.",
            status=ControlStatus.PASS if coverage.account_coverage_ratio >= min_account_coverage else ControlStatus.WARN,
            severity=Severity.MEDIUM,
            expected_amount=min_account_coverage,
            actual_amount=coverage.account_coverage_ratio,
        ),
        ControlResult(
            control_code="MAPPING_VALUE_COVERAGE_CONTROL",
            control_description="Value coverage meets the minimum threshold.",
            status=ControlStatus.PASS if coverage.value_coverage_ratio >= min_value_coverage else ControlStatus.WARN,
            severity=Severity.HIGH,
            expected_amount=min_value_coverage,
            actual_amount=coverage.value_coverage_ratio,
        ),
        ControlResult(
            control_code="MAPPING_NONZERO_UNMAPPED_CONTROL",
            control_description="No posting account with a non-zero balance is unmapped.",
            status=ControlStatus.FAIL if coverage.unmapped_accounts else ControlStatus.PASS,
            severity=Severity.HIGH,
            details={"unmapped_account_count": len(coverage.unmapped_accounts)},
        ),
        ControlResult(
            control_code="MAPPING_CONFLICT_RESOLUTION_CONTROL",
            control_description="No account has more than one mapping active on the run date.",
            status=ControlStatus.FAIL if coverage.conflicted_accounts else ControlStatus.PASS,
            severity=Severity.HIGH,
            details={"conflicted_accounts": list(coverage.conflicted_accounts)},
        ),
    ]

    issue_counts: dict[str, int] = {}
    for issue in validation.issues:
        issue_counts[issue.issue_code] = issue_counts.get(issue.issue_code, 0) + 1

    for issue_code, control_code in _ISSUE_CONTROL_CODES.items():
        count = issue_counts.get(issue_code, 0)
        controls.append(
            ControlResult(
                control_code=control_code,
                control_description=f"No '{issue_code}' mapping-validation issues were found.",
                status=ControlStatus.PASS if count == 0 else ControlStatus.FAIL,
                severity=Severity.HIGH,
                details={"issue_count": count},
            )
        )

    return controls
