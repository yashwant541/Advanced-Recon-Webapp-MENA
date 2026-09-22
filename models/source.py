"""Models describing raw source files, rows, and trial-balance records.

Public contents: ``SourceFile``, ``SourceRow``, ``TrialBalanceRecord``,
``StatementLineRecord``.
Dependencies: ``decimal``, ``dataclasses`` (standard library only).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from iraq_recon.constants import NaturalSide, RowType, StatementType


def _decimal_to_str(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


@dataclass(frozen=True)
class SourceFile:
    """A single uploaded/staged source workbook and its role in the run.

    Attributes:
        source_id: Stable identifier for this file within a run (e.g. a hash
            or a caller-supplied slug). Used as the lineage anchor for every
            row and calculation that traces back to this file.
        filename: Original filename as uploaded.
        file_type: File extension/type, e.g. ``"xlsx"``.
        source_role: One of ``"FINANCIAL_STATEMENT"``, ``"TRIAL_BALANCE"``,
            ``"SCHEDULE"``, ``"MAPPING_LOCAL"``, ``"MAPPING_AYRA"``,
            ``"MAPPING_IRAQ"``.
        content: Raw file bytes. May be ``None`` when only a reference is
            held (see ``content_reference``) to avoid duplicating large
            payloads in memory.
        content_reference: Opaque pointer to the bytes (e.g. a managed-folder
            path) when ``content`` is not held in-process.
        reporting_date: ISO date string if explicitly present in the source;
            never inferred.
        source_unit: Declared unit of amounts in this file, e.g. ``"IQD"``,
            ``"IQD_THOUSAND"``, ``"IQD_MILLION"``.
        metadata: Free-form additional metadata (sheet count, uploader, etc).
    """

    source_id: str
    filename: str
    file_type: str
    source_role: str
    content: bytes | None = None
    content_reference: str | None = None
    reporting_date: str | None = None
    source_unit: str = "IQD"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "filename": self.filename,
            "file_type": self.file_type,
            "source_role": self.source_role,
            "has_content": self.content is not None,
            "content_reference": self.content_reference,
            "reporting_date": self.reporting_date,
            "source_unit": self.source_unit,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class SourceRow:
    """One physical row extracted from a source sheet, before mapping.

    Attributes:
        source_file: ``source_id`` of the owning :class:`SourceFile`.
        source_sheet: Sheet name the row came from.
        source_row_number: 1-based physical row number in the sheet.
        original_values: Raw cell values keyed by detected column role
            (e.g. ``"account"``, ``"description"``, ``"balance"``).
        normalized_values: Values after normalization (see
            ``iraq_recon.normalization``), keyed the same way.
    """

    source_file: str
    source_sheet: str
    source_row_number: int
    original_values: dict[str, Any] = field(default_factory=dict)
    normalized_values: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_file": self.source_file,
            "source_sheet": self.source_sheet,
            "source_row_number": self.source_row_number,
            "original_values": dict(self.original_values),
            "normalized_values": dict(self.normalized_values),
        }


@dataclass(frozen=True)
class TrialBalanceRecord:
    """A normalized trial-balance line, prior to financial-statement mapping.

    Attributes:
        account_number: Normalized account number string.
        account_description: Normalized account description.
        original_balance: Balance as parsed from source, in source units.
        normalized_balance: Balance after sign/format normalization, still in
            source units.
        source_unit: Unit the balance is expressed in (e.g. ``"IQD"``).
        converted_balance: Balance after unit conversion to the reporting
            unit; ``None`` until conversion has run.
        source_sheet: Sheet the record was read from.
        source_row: 1-based physical row number.
        statement_type: Balance-sheet/P&L/OFF-BS classification of the
            account, if determinable from the source alone.
        natural_side: Debit or credit natural side of the account.
        row_type: Posting/parent/subtotal/etc. classification.
        posting_status: ``"POSTS"`` or ``"NON_POSTING"``.
        source_file: ``source_id`` of the owning :class:`SourceFile`.
    """

    account_number: str
    account_description: str
    original_balance: Decimal
    normalized_balance: Decimal
    source_unit: str
    source_sheet: str
    source_row: int
    source_file: str
    converted_balance: Decimal | None = None
    statement_type: StatementType = StatementType.UNKNOWN
    natural_side: NaturalSide = NaturalSide.UNKNOWN
    row_type: RowType = RowType.UNKNOWN
    posting_status: str = "POSTS"

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_number": self.account_number,
            "account_description": self.account_description,
            "original_balance": _decimal_to_str(self.original_balance),
            "normalized_balance": _decimal_to_str(self.normalized_balance),
            "source_unit": self.source_unit,
            "converted_balance": _decimal_to_str(self.converted_balance),
            "source_sheet": self.source_sheet,
            "source_row": self.source_row,
            "source_file": self.source_file,
            "statement_type": str(self.statement_type),
            "natural_side": str(self.natural_side),
            "row_type": str(self.row_type),
            "posting_status": self.posting_status,
        }


@dataclass(frozen=True)
class StatementLineRecord:
    """A single reported line extracted from a financial statement workbook,
    prior to any TB-derived calculation or reconciliation.

    Attributes:
        line_code: Stable identifier for this reporting line (derived from a
            configured line-code column, or a normalized description if no
            explicit code column exists).
        line_description: Reported line description/caption.
        reported_amount: Amount exactly as reported (source unit).
        unit: Declared unit of ``reported_amount``, e.g. ``"IQD_THOUSAND"``.
        source_file: ``source_id`` of the owning :class:`SourceFile`.
        source_sheet: Sheet the line came from.
        source_location: Cell/row reference for lineage, e.g. ``"B42"``.
        currency_classification: Currency bucket, if the statement layout
            distinguishes one, else ``None``.
        residency_classification: Resident/non-resident bucket, if the
            statement layout distinguishes one, else ``None``.
        schedule_code: Supporting schedule this line ties to, if identifiable
            from the statement layout itself (e.g. a "Note"/"Schedule ref"
            column); mapping-derived schedule links belong on
            :class:`iraq_recon.models.mapping.MappingRecord` instead.
    """

    line_code: str
    line_description: str
    reported_amount: Decimal
    unit: str
    source_file: str
    source_sheet: str
    source_location: str
    currency_classification: str | None = None
    residency_classification: str | None = None
    schedule_code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "line_code": self.line_code,
            "line_description": self.line_description,
            "reported_amount": _decimal_to_str(self.reported_amount),
            "unit": self.unit,
            "source_file": self.source_file,
            "source_sheet": self.source_sheet,
            "source_location": self.source_location,
            "currency_classification": self.currency_classification,
            "residency_classification": self.residency_classification,
            "schedule_code": self.schedule_code,
        }
