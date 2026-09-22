"""Validation service: configuration and source-file structural checks.

Purpose
-------
Validate a run's configuration payload and the set of uploaded source
files before any ingestion is attempted, surfacing problems as a
:class:`ValidationResult` rather than a raised exception wherever the
problem is something a reviewer can fix by re-uploading or reconfiguring.

Public contents
----------------
``validate_configuration(configuration_payload)``
``validate_source_files(source_files, required_roles)``
``validate_inputs(configuration_payload, source_files, required_roles)``

Dependencies: ``iraq_recon.models.configuration``, ``iraq_recon.models.validation``.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from iraq_recon.constants import Severity
from iraq_recon.exceptions import ConfigurationError
from iraq_recon.models.configuration import ReconciliationConfiguration
from iraq_recon.models.source import SourceFile
from iraq_recon.models.validation import MappingValidationIssue, ValidationResult


def validate_configuration(configuration_payload: dict[str, Any] | None) -> ValidationResult:
    """Validate a configuration payload's structure and value ranges.

    Args:
        configuration_payload: Raw JSON-compatible configuration dict, as
            received from the WebApp.

    Returns:
        A :class:`ValidationResult`. Structural/type errors (e.g. not a
        JSON object) are surfaced as a ``CRITICAL`` issue rather than
        propagating :class:`ConfigurationError`, since this function's job
        is precisely to turn that failure into a reviewable result.
    """
    issues: list[MappingValidationIssue] = []

    try:
        configuration = ReconciliationConfiguration.from_dict(configuration_payload)
    except ConfigurationError as exc:
        issues.append(
            MappingValidationIssue(
                issue_code="INVALID_CONFIGURATION_PAYLOAD",
                severity=Severity.CRITICAL,
                description=exc.message,
                details=exc.details,
            )
        )
        return ValidationResult(is_valid=False, issues=tuple(issues))

    if configuration.units.conversion_factor <= Decimal("0"):
        issues.append(
            MappingValidationIssue(
                issue_code="INVALID_CONVERSION_FACTOR",
                severity=Severity.HIGH,
                description="units.conversion_factor must be positive.",
                details={"conversion_factor": str(configuration.units.conversion_factor)},
            )
        )

    for field_name, value in (
        ("precision", configuration.tolerances.precision),
        ("rounding", configuration.tolerances.rounding),
        ("materiality", configuration.tolerances.materiality),
    ):
        if value < Decimal("0"):
            issues.append(
                MappingValidationIssue(
                    issue_code="INVALID_TOLERANCE",
                    severity=Severity.HIGH,
                    description=f"tolerances.{field_name} must not be negative.",
                    details={field_name: str(value)},
                )
            )

    if configuration.tolerances.precision > configuration.tolerances.rounding:
        issues.append(
            MappingValidationIssue(
                issue_code="INCONSISTENT_TOLERANCE_ORDERING",
                severity=Severity.MEDIUM,
                description="tolerances.precision should not exceed tolerances.rounding.",
                details={
                    "precision": str(configuration.tolerances.precision),
                    "rounding": str(configuration.tolerances.rounding),
                },
            )
        )

    if configuration.tolerances.rounding > configuration.tolerances.materiality:
        issues.append(
            MappingValidationIssue(
                issue_code="INCONSISTENT_TOLERANCE_ORDERING",
                severity=Severity.MEDIUM,
                description="tolerances.rounding should not exceed tolerances.materiality.",
                details={
                    "rounding": str(configuration.tolerances.rounding),
                    "materiality": str(configuration.tolerances.materiality),
                },
            )
        )

    is_valid = not any(issue.severity in (Severity.HIGH, Severity.CRITICAL) for issue in issues)
    return ValidationResult(is_valid=is_valid, issues=tuple(issues))


def validate_source_files(
    source_files: list[SourceFile],
    required_roles: tuple[str, ...] = ("FINANCIAL_STATEMENT", "TRIAL_BALANCE"),
) -> ValidationResult:
    """Validate that the uploaded source files are structurally usable.

    Args:
        source_files: Uploaded source files.
        required_roles: Roles that must be present at least once.

    Returns:
        A :class:`ValidationResult`.
    """
    issues: list[MappingValidationIssue] = []

    present_roles = {sf.source_role for sf in source_files}
    for role in required_roles:
        if role not in present_roles:
            issues.append(
                MappingValidationIssue(
                    issue_code="MISSING_REQUIRED_SOURCE_ROLE",
                    severity=Severity.CRITICAL,
                    description=f"No source file with role '{role}' was supplied.",
                    details={"required_role": role},
                )
            )

    for source_file in source_files:
        if source_file.content is None and source_file.content_reference is None:
            issues.append(
                MappingValidationIssue(
                    issue_code="EMPTY_SOURCE_FILE",
                    severity=Severity.HIGH,
                    description=f"Source file '{source_file.filename}' has no content or content reference.",
                    details={"source_id": source_file.source_id},
                )
            )
        if not source_file.filename.lower().endswith((".xlsx", ".xlsm")):
            issues.append(
                MappingValidationIssue(
                    issue_code="UNSUPPORTED_SOURCE_FILE_TYPE",
                    severity=Severity.HIGH,
                    description=f"Source file '{source_file.filename}' is not a supported Excel workbook.",
                    details={"source_id": source_file.source_id},
                )
            )

    is_valid = not any(issue.severity in (Severity.HIGH, Severity.CRITICAL) for issue in issues)
    return ValidationResult(is_valid=is_valid, issues=tuple(issues))


def validate_inputs(
    configuration_payload: dict[str, Any] | None,
    source_files: list[SourceFile] | None = None,
    required_roles: tuple[str, ...] = ("FINANCIAL_STATEMENT", "TRIAL_BALANCE"),
) -> ValidationResult:
    """Validate both configuration and source files in one call.

    Args:
        configuration_payload: Raw configuration dict.
        source_files: Uploaded source files, if already known at this point.
        required_roles: Roles that must be present among ``source_files``.

    Returns:
        A combined :class:`ValidationResult`.
    """
    config_result = validate_configuration(configuration_payload)
    if source_files is None:
        return config_result

    files_result = validate_source_files(source_files, required_roles)
    combined_issues = config_result.issues + files_result.issues
    combined_warnings = config_result.warnings + files_result.warnings
    return ValidationResult(
        is_valid=config_result.is_valid and files_result.is_valid,
        issues=combined_issues,
        warnings=combined_warnings,
    )
