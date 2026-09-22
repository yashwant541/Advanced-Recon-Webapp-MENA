"""Models describing calculator inputs/outputs at the account level.

Public contents: ``CalculationContribution``, ``CalculationResult``.
Dependencies: ``decimal`` (standard library only).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class CalculationContribution:
    """One account's signed contribution to a calculated line total.

    Attributes:
        line_code: Target financial-statement or schedule line code.
        account: Local account number.
        description: Local account description.
        converted_amount: Balance after unit conversion, unsigned (i.e. the
            value as carried in the trial balance after conversion only).
        presentation_sign: ``+1`` or ``-1`` applied to reach ``presented_amount``.
        presented_amount: ``converted_amount * presentation_sign``.
        formula_component: Which part of the calculator's formula this
            contribution belongs to, e.g. ``"cost"``, ``"accumulated_depreciation"``.
        source_lineage: Full audit trail dict (source file/sheet/row, Ayra
            category, Iraq bucket, mapping method, rationale, etc).
    """

    line_code: str
    account: str
    description: str
    converted_amount: Decimal
    presentation_sign: int
    presented_amount: Decimal
    formula_component: str
    source_lineage: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "line_code": self.line_code,
            "account": self.account,
            "description": self.description,
            "converted_amount": str(self.converted_amount),
            "presentation_sign": self.presentation_sign,
            "presented_amount": str(self.presented_amount),
            "formula_component": self.formula_component,
            "source_lineage": dict(self.source_lineage),
        }


@dataclass(frozen=True)
class CalculationResult:
    """Standard output of every accounting calculator (see ``calculators.base``).

    Attributes:
        line_code: The financial-statement line this calculator produces.
        calculated_amount: Sum of all ``contributions[*].presented_amount``.
        contributions: Account-level contributions with full lineage.
        formula: Human-readable formula description, e.g. ``"A-CBI + A-CRR"``.
        included_accounts: Accounts included in ``calculated_amount``.
        deducted_accounts: Accounts included with a negative presentation sign.
        excluded_accounts: Accounts considered but excluded, with reasons.
        reported_amount: Reported amount from the financial statement, if
            supplied to the calculator; ``None`` if not yet compared.
        variance: ``calculated_amount - reported_amount``, or ``None``.
        status: Reconciliation status string, or ``None`` before comparison.
        accounting_explanation: Plain-language explanation of the formula.
        warnings: Non-fatal warnings raised while calculating.
    """

    line_code: str
    calculated_amount: Decimal
    contributions: tuple[CalculationContribution, ...]
    formula: str
    included_accounts: tuple[str, ...] = ()
    deducted_accounts: tuple[str, ...] = ()
    excluded_accounts: tuple[dict[str, Any], ...] = ()
    reported_amount: Decimal | None = None
    variance: Decimal | None = None
    status: str | None = None
    accounting_explanation: str = ""
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "line_code": self.line_code,
            "calculated_amount": str(self.calculated_amount),
            "contributions": [c.to_dict() for c in self.contributions],
            "formula": self.formula,
            "included_accounts": list(self.included_accounts),
            "deducted_accounts": list(self.deducted_accounts),
            "excluded_accounts": list(self.excluded_accounts),
            "reported_amount": str(self.reported_amount) if self.reported_amount is not None else None,
            "variance": str(self.variance) if self.variance is not None else None,
            "status": self.status,
            "accounting_explanation": self.accounting_explanation,
            "warnings": list(self.warnings),
        }

    def summary_dict(self) -> dict[str, Any]:
        return {
            "line_code": self.line_code,
            "calculated_amount": str(self.calculated_amount),
            "reported_amount": str(self.reported_amount) if self.reported_amount is not None else None,
            "variance": str(self.variance) if self.variance is not None else None,
            "status": self.status,
            "account_count": len(self.contributions),
            "warning_count": len(self.warnings),
        }
