"""Models for input and mapping validation results.

Public contents: ``MappingValidationIssue``, ``ValidationResult``.
Dependencies: standard library only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from iraq_recon.constants import Severity


@dataclass(frozen=True)
class MappingValidationIssue:
    """A single mapping-validation finding (see ``mapping.mapping_validator``).

    Attributes:
        issue_code: e.g. ``"DUPLICATE_MAPPING"``, ``"MISSING_PRESENTATION_SIGN"``.
        local_account: Affected account, if applicable.
        severity: Issue severity.
        description: Human-readable description.
        details: Structured supporting values.
    """

    issue_code: str
    severity: Severity
    description: str
    local_account: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "issue_code": self.issue_code,
            "severity": str(self.severity),
            "description": self.description,
            "local_account": self.local_account,
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class ValidationResult:
    """Aggregate result of validating inputs, a configuration, or mappings.

    Attributes:
        is_valid: ``True`` only if there are no ``HIGH``/``CRITICAL`` issues.
        issues: All findings, of any severity.
        warnings: Free-text warnings that are not structured issues.
    """

    is_valid: bool
    issues: tuple[MappingValidationIssue, ...] = ()
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "issues": [i.to_dict() for i in self.issues],
            "warnings": list(self.warnings),
        }

    def summary_dict(self) -> dict[str, Any]:
        by_severity: dict[str, int] = {}
        for issue in self.issues:
            key = str(issue.severity)
            by_severity[key] = by_severity.get(key, 0) + 1
        return {
            "is_valid": self.is_valid,
            "issue_count": len(self.issues),
            "issue_count_by_severity": by_severity,
            "warning_count": len(self.warnings),
        }
