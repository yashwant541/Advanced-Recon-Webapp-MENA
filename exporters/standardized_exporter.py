"""Standardized-format export of a trial balance or financial statement.

Purpose
-------
Let a reviewer download the *normalized* trial balance ("standardized
format") and the *normalized* financial statement/submission independently
of running a full reconciliation -- so they can sanity-check how the
engine parsed and classified their upload (header row found, account
numbers cleaned, amounts parsed, row types classified) before committing
to mapping and reconciliation. Every account/line from every uploaded
source is kept, mapped or not -- this is a parsing/normalization view, not
a reconciliation outcome.

Public contents
----------------
``export_standardized_trial_balance(records, *, source_label="Trial Balance")``
``export_standardized_financial_statement(lines, *, source_label="Financial Statement")``

Dependencies: ``exporters.excel_exporter``.
"""

from __future__ import annotations

from iraq_recon.exporters.excel_exporter import add_table_sheet, export_workbook_bytes, new_workbook
from iraq_recon.models.source import StatementLineRecord, TrialBalanceRecord

_TB_HEADERS = [
    "Account Number", "Account Description", "Row Type", "Posting Status", "Statement Type",
    "Natural Side", "Original Balance", "Source Unit", "Converted Balance", "Source File",
    "Source Sheet", "Source Row",
]

_FS_HEADERS = [
    "Line Code", "Line Description", "Reported Amount", "Unit", "Currency Classification",
    "Residency Classification", "Schedule", "Source File", "Source Sheet", "Source Location",
]


def trial_balance_rows(records: list[TrialBalanceRecord]) -> list[list[object]]:
    return [
        [
            r.account_number, r.account_description, str(r.row_type), r.posting_status,
            str(r.statement_type), str(r.natural_side), r.original_balance, r.source_unit,
            r.converted_balance, r.source_file, r.source_sheet, r.source_row,
        ]
        for r in records
    ]


def financial_statement_rows(lines: list[StatementLineRecord]) -> list[list[object]]:
    return [
        [
            line.line_code, line.line_description, line.reported_amount, line.unit,
            line.currency_classification or "", line.residency_classification or "",
            line.schedule_code or "", line.source_file, line.source_sheet, line.source_location,
        ]
        for line in lines
    ]


def export_standardized_trial_balance(
    records: list[TrialBalanceRecord],
    *,
    source_label: str = "Trial Balance",
) -> bytes:
    """Build a one-sheet standardized-format workbook for a trial balance.

    Args:
        records: Normalized trial-balance records (any row type -- parent,
            subtotal, and posting rows are all included so a reviewer can
            see exactly how every row was classified).
        source_label: Sheet title.

    Returns:
        ``.xlsx`` bytes.
    """
    workbook = new_workbook()
    add_table_sheet(
        workbook, source_label, _TB_HEADERS, trial_balance_rows(records),
        currency_columns=("Original Balance", "Converted Balance"),
        column_widths={"Account Description": 32},
    )
    return export_workbook_bytes(workbook)


def export_standardized_financial_statement(
    lines: list[StatementLineRecord],
    *,
    source_label: str = "Financial Statement",
) -> bytes:
    """Build a one-sheet standardized-format workbook for a financial statement.

    Args:
        lines: Every reported line extracted from the statement.
        source_label: Sheet title.

    Returns:
        ``.xlsx`` bytes.
    """
    workbook = new_workbook()
    add_table_sheet(
        workbook, source_label, _FS_HEADERS, financial_statement_rows(lines),
        currency_columns=("Reported Amount",),
        column_widths={"Line Description": 32},
    )
    return export_workbook_bytes(workbook)
