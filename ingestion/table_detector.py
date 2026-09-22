"""Table region detection within a raw sheet grid.

Purpose
-------
Split a sheet's used range into one or more coherent table regions,
separated by blank rows, and reject decorative title bands (a lone
merged-looking title row with no header underneath). This lets a single
sheet contain multiple stacked tables (e.g. a TB followed by a memo
schedule) without the header detector or account extractor confusing them.

Public contents
----------------
``TableRegion`` -- row/column bounds plus the header row within them.
``detect_tables(grid, min_data_rows=1)`` -- find table regions in a grid.

Dependencies: ``iraq_recon.ingestion.header_detector`` (for locating each
region's header), standard library otherwise.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from iraq_recon.ingestion.header_detector import detect_header


@dataclass(frozen=True)
class TableRegion:
    """One coherent table region within a sheet.

    Attributes:
        start_row: 0-based first row of the region (may be a title/header row).
        end_row: 0-based last row of the region, inclusive.
        start_col: 0-based first non-empty column.
        end_col: 0-based last non-empty column, inclusive.
        header_row: 0-based row index of the detected header within the
            region, or ``None`` if no header was found.
    """

    start_row: int
    end_row: int
    start_col: int
    end_col: int
    header_row: int | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "start_row": self.start_row,
            "end_row": self.end_row,
            "start_col": self.start_col,
            "end_col": self.end_col,
            "header_row": self.header_row,
        }


def _is_blank_row(row: list[Any]) -> bool:
    return all(v is None or (isinstance(v, str) and v.strip() == "") for v in row)


def _used_column_bounds(rows: list[list[Any]]) -> tuple[int, int] | None:
    min_col: int | None = None
    max_col: int | None = None
    for row in rows:
        for col_index, value in enumerate(row):
            if value is None or (isinstance(value, str) and value.strip() == ""):
                continue
            if min_col is None or col_index < min_col:
                min_col = col_index
            if max_col is None or col_index > max_col:
                max_col = col_index
    if min_col is None or max_col is None:
        return None
    return min_col, max_col


def detect_tables(grid: list[list[Any]], min_data_rows: int = 1) -> list[TableRegion]:
    """Split a grid into table regions separated by fully blank rows.

    Args:
        grid: Rectangular sheet grid.
        min_data_rows: Minimum number of non-header rows a region must have
            to be kept; smaller regions are treated as decorative titles or
            stray content and discarded.

    Returns:
        A list of :class:`TableRegion`, in row order.
    """
    if not grid:
        return []

    blocks: list[tuple[int, int]] = []
    block_start: int | None = None

    for row_index, row in enumerate(grid):
        blank = _is_blank_row(row)
        if not blank and block_start is None:
            block_start = row_index
        elif blank and block_start is not None:
            blocks.append((block_start, row_index - 1))
            block_start = None
    if block_start is not None:
        blocks.append((block_start, len(grid) - 1))

    regions: list[TableRegion] = []
    for start_row, end_row in blocks:
        block_rows = grid[start_row : end_row + 1]
        bounds = _used_column_bounds(block_rows)
        if bounds is None:
            continue
        start_col, end_col = bounds

        header_result = detect_header(block_rows)
        header_row_offset = header_result.selected.row_index if header_result.selected else None
        header_row = (start_row + header_row_offset) if header_row_offset is not None else None

        data_row_count = (end_row - start_row + 1) - (1 if header_row is not None else 0)
        if data_row_count < min_data_rows:
            continue

        regions.append(
            TableRegion(
                start_row=start_row,
                end_row=end_row,
                start_col=start_col,
                end_col=end_col,
                header_row=header_row,
            )
        )

    return regions
