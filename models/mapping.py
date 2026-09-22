"""Model describing an approved (or provisional) account mapping record.

Public contents: ``MappingRecord``.
Dependencies: ``decimal``, ``dataclasses`` (standard library only).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from iraq_recon.constants import (
    EconomicRole,
    InclusionStatus,
    MappingMethod,
    NaturalSide,
    StatementType,
)


@dataclass(frozen=True)
class MappingRecord:
    """A single Level-1/2/3 mapping from a local account to reporting lines.

    Attributes:
        local_account: Normalized local account number.
        local_description: Local accounting description/meaning.
        statement_type: Asset/liability/equity/income/expense/off-BS.
        natural_side: Debit or credit natural side.
        economic_role: One of :class:`iraq_recon.constants.EconomicRole`.
        ayra_category: Level-2 semantic category, e.g. ``"A-CBI"``.
        iraq_reporting_bucket: Level-3 roll-up bucket, e.g.
            ``"BALANCES_WITH_CENTRAL_BANK"``.
        financial_statement_line: Target line code on the main statement.
        schedule_code: Supporting schedule this account also feeds, if any.
        schedule_row: Row/bucket identifier within that schedule.
        presentation_sign: ``+1`` or ``-1`` applied when aggregating.
        inclusion_status: Whether the account is included, excluded, or
            conditionally included in primary totals.
        unit_factor: Multiplicative conversion factor applied to this
            account's balance before aggregation (independent of the
            source-file-level unit conversion).
        mapping_method: How this mapping was established (see
            :class:`iraq_recon.constants.MappingMethod`).
        mapping_confidence: 0.0-1.0 confidence score for non-approved
            mappings; approved mappings should use ``1.0``.
        effective_from: First date (inclusive) this mapping applies.
        effective_to: Last date (inclusive) this mapping applies, or ``None``
            for open-ended.
        mapping_rationale: Free-text justification, required for anything
            other than ``APPROVED_ACCOUNT``.
        local_account_group: Optional local grouping key (Level-1 bridge).
        metadata: Free-form additional metadata.
    """

    local_account: str
    local_description: str
    statement_type: StatementType
    natural_side: NaturalSide
    economic_role: EconomicRole
    ayra_category: str
    iraq_reporting_bucket: str
    financial_statement_line: str
    presentation_sign: int
    mapping_method: MappingMethod = MappingMethod.APPROVED_ACCOUNT
    mapping_confidence: float = 1.0
    schedule_code: str | None = None
    schedule_row: str | None = None
    inclusion_status: InclusionStatus = InclusionStatus.INCLUDE
    unit_factor: Decimal = Decimal("1")
    effective_from: date | None = None
    effective_to: date | None = None
    mapping_rationale: str = ""
    local_account_group: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.presentation_sign not in (1, -1):
            raise ValueError(
                f"presentation_sign must be +1 or -1, got {self.presentation_sign!r}"
            )
        if not (0.0 <= self.mapping_confidence <= 1.0):
            raise ValueError(
                f"mapping_confidence must be within [0, 1], got {self.mapping_confidence!r}"
            )

    def is_active_on(self, as_of: date) -> bool:
        """Return whether this mapping is effective on ``as_of``."""
        if self.effective_from is not None and as_of < self.effective_from:
            return False
        if self.effective_to is not None and as_of > self.effective_to:
            return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "local_account": self.local_account,
            "local_description": self.local_description,
            "local_account_group": self.local_account_group,
            "statement_type": str(self.statement_type),
            "natural_side": str(self.natural_side),
            "economic_role": str(self.economic_role),
            "ayra_category": self.ayra_category,
            "iraq_reporting_bucket": self.iraq_reporting_bucket,
            "financial_statement_line": self.financial_statement_line,
            "schedule_code": self.schedule_code,
            "schedule_row": self.schedule_row,
            "presentation_sign": self.presentation_sign,
            "inclusion_status": str(self.inclusion_status),
            "unit_factor": str(self.unit_factor),
            "mapping_method": str(self.mapping_method),
            "mapping_confidence": self.mapping_confidence,
            "effective_from": self.effective_from.isoformat() if self.effective_from else None,
            "effective_to": self.effective_to.isoformat() if self.effective_to else None,
            "mapping_rationale": self.mapping_rationale,
            "metadata": dict(self.metadata),
        }
