"""Whole-workbook inspection: sheets, tables, headers, classification.

Purpose
-------
Provide the single read used by ``api.inspect_workbook`` /
``api.list_workbook_sheets``: read the workbook once, then classify each
sheet and detect its table/header structure, without extracting or mapping
any accounting data yet.

Public contents
----------------
``SheetInspection`` -- per-sheet classification + table regions + header.
``WorkbookInspection`` -- per-workbook aggregate of sheet inspections.
``inspect_workbook(filename, content, sheet_names=None)`` -- run inspection.

Dependencies: ``ingestion.excel_reader``, ``ingestion.table_detector``,
``ingestion.sheet_classifier``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from iraq_recon.ingestion.excel_reader import read_workbook
from iraq_recon.ingestion.sheet_classifier import SheetClassification, classify_sheet
from iraq_recon.ingestion.table_detector import TableRegion, detect_tables
from iraq_recon.logging_utils import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class SheetInspection:
    """Inspection outcome for a single sheet.

    Attributes:
        sheet_name: The sheet's name.
        row_count: Number of physical rows in the sheet's used range.
        column_count: Number of physical columns in the sheet's used range.
        classification: Sheet-type classification.
        tables: Detected table regions within the sheet.
    """

    sheet_name: str
    row_count: int
    column_count: int
    classification: SheetClassification
    tables: tuple[TableRegion, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "sheet_name": self.sheet_name,
            "row_count": self.row_count,
            "column_count": self.column_count,
            "classification": self.classification.to_dict(),
            "tables": [t.to_dict() for t in self.tables],
        }


@dataclass(frozen=True)
class WorkbookInspection:
    """Inspection outcome for a whole workbook.

    Attributes:
        filename: Original filename.
        sheets: One :class:`SheetInspection` per sheet read.
        warnings: Non-fatal issues from the underlying read.
    """

    filename: str
    sheets: tuple[SheetInspection, ...]
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "filename": self.filename,
            "sheets": [s.to_dict() for s in self.sheets],
            "warnings": list(self.warnings),
        }

    def sheet_names(self) -> list[str]:
        return [s.sheet_name for s in self.sheets]


def inspect_workbook(
    filename: str,
    content: bytes,
    sheet_names: list[str] | None = None,
) -> WorkbookInspection:
    """Read and inspect every requested sheet of a workbook.

    Args:
        filename: Original filename.
        content: Raw workbook bytes.
        sheet_names: Optional subset of sheets to inspect; defaults to all.

    Returns:
        A :class:`WorkbookInspection`.

    Raises:
        iraq_recon.exceptions.UnsupportedFileError: propagated from
            :func:`iraq_recon.ingestion.excel_reader.read_workbook`.
    """
    raw = read_workbook(filename, content, sheet_names=sheet_names)

    sheet_inspections: list[SheetInspection] = []
    for sheet_name in raw.sheet_names:
        grid = raw.grids.get(sheet_name)
        if grid is None:
            continue
        classification = classify_sheet(sheet_name, grid)
        tables = detect_tables(grid)
        column_count = max((len(row) for row in grid), default=0)
        sheet_inspections.append(
            SheetInspection(
                sheet_name=sheet_name,
                row_count=len(grid),
                column_count=column_count,
                classification=classification,
                tables=tuple(tables),
            )
        )

    logger.info("Inspected workbook '%s': %d sheet(s).", filename, len(sheet_inspections))

    return WorkbookInspection(
        filename=filename,
        sheets=tuple(sheet_inspections),
        warnings=raw.warnings,
    )


def list_workbook_sheets(filename: str, content: bytes) -> list[str]:
    """Return only the sheet names of a workbook, without full inspection."""
    raw = read_workbook(filename, content)
    return list(raw.sheet_names)
