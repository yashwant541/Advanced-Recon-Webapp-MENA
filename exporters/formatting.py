"""Shared openpyxl formatting helpers for audit-ready workbooks.

Purpose
-------
Give every exported sheet the same look (bold frozen header row, consistent
currency/percentage number formats, status color coding, autofilter, sane
column widths) without repeating openpyxl boilerplate in every sheet
builder.

Public contents
----------------
``STATUS_FILL_COLORS`` -- reconciliation/control status -> fill color.
``style_header_row(worksheet, header_row=1)``
``apply_column_widths(worksheet, widths)``
``apply_number_format(worksheet, column_letter, number_format, start_row=2, end_row=None)``
``fill_status_column(worksheet, column_letter, start_row=2, end_row=None)``
``freeze_and_filter(worksheet, header_row=1)``

Dependencies: ``openpyxl``.
"""

from __future__ import annotations

from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

CURRENCY_FORMAT = "#,##0.00;[Red](#,##0.00)"
PERCENTAGE_FORMAT = "0.00%"

STATUS_FILL_COLORS: dict[str, str] = {
    "EXACT_MATCH": "C6EFCE",
    "PRECISION_MATCH": "C6EFCE",
    "ROUNDING_MATCH": "FFEB9C",
    "PARTIAL_MATCH": "FFEB9C",
    "MATERIAL_BREAK": "FFC7CE",
    "UNMAPPED_ACCOUNT": "FFC7CE",
    "DUPLICATE_MAPPING": "FFC7CE",
    "UNRESOLVED": "FFC7CE",
    "PASS": "C6EFCE",
    "WARN": "FFEB9C",
    "FAIL": "FFC7CE",
    "NOT_APPLICABLE": "D9D9D9",
}

_HEADER_FILL = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
_HEADER_FONT = Font(color="FFFFFF", bold=True)


def style_header_row(worksheet: Worksheet, header_row: int = 1) -> None:
    """Bold, white-on-blue style the header row and wrap/align it."""
    for cell in worksheet[header_row]:
        if cell.value is None:
            continue
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def apply_column_widths(worksheet: Worksheet, widths: dict[str, int]) -> None:
    """Set explicit column widths.

    Args:
        widths: ``{column_letter: width}``, e.g. ``{"A": 18, "B": 40}``.
    """
    for column_letter, width in widths.items():
        worksheet.column_dimensions[column_letter].width = width


def apply_number_format(
    worksheet: Worksheet,
    column_letter: str,
    number_format: str,
    *,
    start_row: int = 2,
    end_row: int | None = None,
) -> None:
    """Apply a number format to every cell in a column range."""
    last_row = end_row if end_row is not None else worksheet.max_row
    for row in range(start_row, last_row + 1):
        worksheet[f"{column_letter}{row}"].number_format = number_format


def fill_status_column(
    worksheet: Worksheet,
    column_letter: str,
    *,
    start_row: int = 2,
    end_row: int | None = None,
) -> None:
    """Color-fill a status column's cells according to :data:`STATUS_FILL_COLORS`."""
    last_row = end_row if end_row is not None else worksheet.max_row
    for row in range(start_row, last_row + 1):
        cell = worksheet[f"{column_letter}{row}"]
        color = STATUS_FILL_COLORS.get(str(cell.value))
        if color:
            cell.fill = PatternFill(start_color=color, end_color=color, fill_type="solid")


def freeze_and_filter(worksheet: Worksheet, header_row: int = 1) -> None:
    """Freeze panes above/left of the header row and enable autofilter."""
    worksheet.freeze_panes = worksheet.cell(row=header_row + 1, column=1).coordinate
    if worksheet.max_row >= header_row and worksheet.max_column >= 1:
        last_column_letter = get_column_letter(worksheet.max_column)
        worksheet.auto_filter.ref = f"A{header_row}:{last_column_letter}{worksheet.max_row}"


def write_table(worksheet: Worksheet, headers: list[str], rows: list[list[object]]) -> None:
    """Write a simple header + data-rows table starting at A1, then style it."""
    worksheet.append(headers)
    for row in rows:
        worksheet.append(row)
    style_header_row(worksheet)
    freeze_and_filter(worksheet)
