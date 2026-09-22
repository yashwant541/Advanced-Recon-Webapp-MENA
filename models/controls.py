"""Model describing a single control-framework evaluation result.

Public contents: ``ControlResult``.
Dependencies: ``decimal`` (standard library only).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from iraq_recon.constants import ControlStatus, Severity


@dataclass(frozen=True)
class ControlResult:
    """Outcome of one control check (see ``iraq_recon.controls``).

    Attributes:
        control_code: Stable identifier, e.g. ``"TB_ASSET_CONTROL_TOTAL"``.
        control_description: Human-readable description of what is checked.
        expected_amount: Expected/control-total amount, if numeric.
        actual_amount: Actual/reconstructed amount, if numeric.
        variance: ``actual_amount - expected_amount``, if both are numeric.
        status: Pass/warn/fail/not-applicable.
        severity: Severity to apply if the control fails.
        details: Structured supporting evidence.
    """

    control_code: str
    control_description: str
    status: ControlStatus
    severity: Severity = Severity.MEDIUM
    expected_amount: Decimal | None = None
    actual_amount: Decimal | None = None
    variance: Decimal | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "control_code": self.control_code,
            "control_description": self.control_description,
            "status": str(self.status),
            "severity": str(self.severity),
            "expected_amount": str(self.expected_amount) if self.expected_amount is not None else None,
            "actual_amount": str(self.actual_amount) if self.actual_amount is not None else None,
            "variance": str(self.variance) if self.variance is not None else None,
            "details": dict(self.details),
        }
