"""Trial-balance extraction: source rows only, no financial-statement mapping.

Purpose
-------
Turn a trial-balance sheet's raw grid into a list of
:class:`iraq_recon.models.source.SourceRow`, using header/table detection to
locate the account, description, balance/debit/credit columns. This module
must never assign a financial-statement line, Ayra category, or Iraq
reporting bucket -- that is the mapping layer's job.

Public contents
----------------
``extract_trial_balance_rows(source_file, content, sheet_name=None)`` --
returns ``(rows, warnings)``.

Dependencies: ``ingestion.excel_reader``, ``ingestion.table_detector``,
``ingestion.header_detector``.
"""

from __future__ import annotations

from iraq_recon.exceptions import IngestionError
from iraq_recon.ingestion.excel_reader import read_workbook
from iraq_recon.ingestion.header_detector import detect_header
from iraq_recon.ingestion.table_detector import detect_tables
from iraq_recon.logging_utils import get_logger
from iraq_recon.models.source import SourceFile, SourceRow

logger = get_logger(__name__)


def _is_row_blank(row: list) -> bool:
    return all(v is None or (isinstance(v, str) and v.strip() == "") for v in row)


def extract_trial_balance_rows(
    source_file: SourceFile,
    *,
    sheet_name: str | None = None,
) -> tuple[list[SourceRow], list[str]]:
    """Extract raw trial-balance rows from one sheet of a workbook.

    Args:
        source_file: The trial-balance :class:`SourceFile`; ``source_file.content``
            must be populated with the workbook bytes.
        sheet_name: Sheet to read. If omitted, the first sheet whose detected
            table has both an "account" and a "balance" (or debit/credit)
            column is used.

    Returns:
        ``(rows, warnings)`` -- ``rows`` are :class:`SourceRow` with
        ``original_values`` keyed by ``"account"``, ``"description"``,
        ``"balance"``, ``"debit"``, ``"credit"`` (whichever columns were
        found); ``normalized_values`` is left empty for the normalization
        phase to populate.

    Raises:
        IngestionError: if ``source_file.content`` is missing, or no usable
            table with an account/balance column can be found.
    """
    if source_file.content is None:
        raise IngestionError(
            f"Source file '{source_file.filename}' has no content to read.",
            details={"source_id": source_file.source_id},
        )

    requested_sheets = [sheet_name] if sheet_name else None
    raw = read_workbook(source_file.filename, source_file.content, sheet_names=requested_sheets)
    warnings = list(raw.warnings)

    candidate_sheet_names = requested_sheets or list(raw.sheet_names)

    for candidate_sheet in candidate_sheet_names:
        grid = raw.grids.get(candidate_sheet)
        if grid is None:
            continue
        for region in detect_tables(grid):
            if region.header_row is None:
                continue

            region_rows = grid[region.start_row : region.end_row + 1]
            header_result = detect_header(region_rows)
            if header_result.selected is None:
                continue
            roles = header_result.selected.column_roles
            has_account = "account" in roles
            has_amount = "balance" in roles or "debit" in roles or "credit" in roles
            if not (has_account and has_amount):
                continue

            header_row_index_in_region = header_result.selected.row_index
            data_start = region.start_row + header_row_index_in_region + 1
            rows: list[SourceRow] = []
            for physical_row_index in range(data_start, region.end_row + 1):
                row = grid[physical_row_index]
                if _is_row_blank(row):
                    continue
                original_values: dict[str, object] = {}
                for role, col_index in roles.items():
                    original_values[role] = row[col_index] if col_index < len(row) else None
                rows.append(
                    SourceRow(
                        source_file=source_file.source_id,
                        source_sheet=candidate_sheet,
                        source_row_number=physical_row_index + 1,
                        original_values=original_values,
                    )
                )

            logger.info(
                "Extracted %d trial-balance row(s) from '%s'!'%s'.",
                len(rows),
                source_file.filename,
                candidate_sheet,
            )
            return rows, warnings

    raise IngestionError(
        f"No trial-balance table with an account and balance/debit/credit "
        f"column could be found in '{source_file.filename}'.",
        details={"source_id": source_file.source_id, "sheets_scanned": candidate_sheet_names},
    )
