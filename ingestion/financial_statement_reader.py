"""Financial-statement extraction: reported lines, no TB-derived calculation.

Purpose
-------
Turn a financial-statement sheet's raw grid into a list of
:class:`iraq_recon.models.source.StatementLineRecord`. Amount parsing here
is intentionally minimal (delegated fully to
``normalization.amount_normalizer`` downstream); this module's job is only
to locate the right columns and rows and to preserve the raw values with
their source location for lineage.

Public contents
----------------
``extract_financial_statement_lines(source_file, sheet_name=None)`` --
returns ``(lines, warnings)``.

Dependencies: ``ingestion.excel_reader``, ``ingestion.table_detector``,
``ingestion.header_detector``, ``normalization.amount_normalizer``.
"""

from __future__ import annotations

import re

from iraq_recon.exceptions import IngestionError
from iraq_recon.ingestion.excel_reader import read_workbook
from iraq_recon.ingestion.header_detector import detect_header
from iraq_recon.ingestion.table_detector import detect_tables
from iraq_recon.logging_utils import get_logger
from iraq_recon.models.source import SourceFile, StatementLineRecord
from iraq_recon.normalization.amount_normalizer import normalize_amount

logger = get_logger(__name__)

_SLUG_RE = re.compile(r"[^A-Z0-9]+")


def _is_row_blank(row: list) -> bool:
    return all(v is None or (isinstance(v, str) and v.strip() == "") for v in row)


def _slugify(description: str) -> str:
    slug = _SLUG_RE.sub("_", description.strip().upper()).strip("_")
    return slug or "UNSPECIFIED_LINE"


def _column_letter(col_index: int) -> str:
    letters = ""
    n = col_index + 1
    while n > 0:
        n, remainder = divmod(n - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def extract_financial_statement_lines(
    source_file: SourceFile,
    *,
    sheet_name: str | None = None,
) -> tuple[list[StatementLineRecord], list[str]]:
    """Extract raw reported lines from one sheet of a financial statement.

    Args:
        source_file: The financial-statement :class:`SourceFile`;
            ``source_file.content`` must hold the workbook bytes.
        sheet_name: Sheet to read. If omitted, the first sheet whose detected
            table has a description/line-code column and a balance/amount
            column is used.

    Returns:
        ``(lines, warnings)``.

    Raises:
        IngestionError: if content is missing or no usable table is found.
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
            has_description = "description" in roles or "account" in roles
            has_amount = "balance" in roles
            if not (has_description and has_amount):
                continue

            header_row_index_in_region = header_result.selected.row_index
            data_start = region.start_row + header_row_index_in_region + 1

            description_col = roles.get("description", roles.get("account"))
            line_code_col = roles.get("account")
            amount_col = roles["balance"]
            currency_col = roles.get("currency")
            residency_col = roles.get("residency")
            schedule_col = roles.get("schedule")

            lines: list[StatementLineRecord] = []
            for physical_row_index in range(data_start, region.end_row + 1):
                row = grid[physical_row_index]
                if _is_row_blank(row):
                    continue

                description_value = row[description_col] if description_col < len(row) else None
                description = str(description_value).strip() if description_value else ""
                if not description:
                    continue

                amount_raw = row[amount_col] if amount_col < len(row) else None
                parsed_amount = normalize_amount(amount_raw)
                if parsed_amount.value is None:
                    if parsed_amount.warning:
                        warnings.append(
                            f"{candidate_sheet}!row{physical_row_index + 1}: {parsed_amount.warning}"
                        )
                    continue

                if line_code_col is not None and row[line_code_col]:
                    line_code = str(row[line_code_col]).strip()
                else:
                    line_code = _slugify(description)

                currency_classification = (
                    str(row[currency_col]).strip()
                    if currency_col is not None and currency_col < len(row) and row[currency_col]
                    else None
                )
                residency_classification = (
                    str(row[residency_col]).strip()
                    if residency_col is not None and residency_col < len(row) and row[residency_col]
                    else None
                )
                schedule_code = (
                    str(row[schedule_col]).strip()
                    if schedule_col is not None and schedule_col < len(row) and row[schedule_col]
                    else None
                )

                lines.append(
                    StatementLineRecord(
                        line_code=line_code,
                        line_description=description,
                        reported_amount=parsed_amount.value,
                        unit=source_file.source_unit,
                        source_file=source_file.source_id,
                        source_sheet=candidate_sheet,
                        source_location=f"{_column_letter(amount_col)}{physical_row_index + 1}",
                        currency_classification=currency_classification,
                        residency_classification=residency_classification,
                        schedule_code=schedule_code,
                    )
                )

            logger.info(
                "Extracted %d financial-statement line(s) from '%s'!'%s'.",
                len(lines),
                source_file.filename,
                candidate_sheet,
            )
            return lines, warnings

    raise IngestionError(
        f"No financial-statement table with a description and amount column "
        f"could be found in '{source_file.filename}'.",
        details={"source_id": source_file.source_id, "sheets_scanned": candidate_sheet_names},
    )
