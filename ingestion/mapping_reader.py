"""Raw mapping-table extraction from a mapping workbook sheet.

Purpose
-------
Read a mapping sheet (local account bridge, Ayra semantic mapping, or Iraq
balance-sheet mapping) into plain row dicts keyed by the expected mapping
field names, using exact (case/whitespace-insensitive) header-name matching
rather than the keyword-scoring used for TB/FS tables, because mapping
sheets have well-known, explicit column headers. Converting these row dicts
into validated :class:`iraq_recon.models.mapping.MappingRecord` objects is
the job of ``mapping.mapping_loader`` -- this module does no interpretation.

Public contents
----------------
``extract_mapping_rows(source_file, sheet_name=None)`` -- returns
``(rows, warnings)`` where each row is a ``dict[str, Any]``.

Dependencies: ``ingestion.excel_reader``.
"""

from __future__ import annotations

import re

from iraq_recon.exceptions import IngestionError
from iraq_recon.ingestion.excel_reader import read_workbook
from iraq_recon.logging_utils import get_logger
from iraq_recon.models.source import SourceFile

logger = get_logger(__name__)

_WHITESPACE_RE = re.compile(r"\s+")

#: Maps a normalized header text to the canonical mapping-field name it fills.
_FIELD_ALIASES: dict[str, str] = {
    "local account": "local_account",
    "account": "local_account",
    "local description": "local_description",
    "description": "local_description",
    "local account group": "local_account_group",
    "account group": "local_account_group",
    "statement type": "statement_type",
    "natural side": "natural_side",
    "economic role": "economic_role",
    "ayra category": "ayra_category",
    "ayra semantic category": "ayra_category",
    "iraq reporting bucket": "iraq_reporting_bucket",
    "reporting bucket": "iraq_reporting_bucket",
    "financial statement line": "financial_statement_line",
    "statement line": "financial_statement_line",
    "schedule code": "schedule_code",
    "schedule": "schedule_code",
    "schedule row": "schedule_row",
    "presentation sign": "presentation_sign",
    "sign": "presentation_sign",
    "inclusion status": "inclusion_status",
    "inclusion": "inclusion_status",
    "unit factor": "unit_factor",
    "mapping method": "mapping_method",
    "mapping confidence": "mapping_confidence",
    "effective from": "effective_from",
    "effective to": "effective_to",
    "mapping rationale": "mapping_rationale",
    "rationale": "mapping_rationale",
}

_REQUIRED_FIELDS = ("local_account",)


def _normalize_header(value: object) -> str:
    if value is None:
        return ""
    return _WHITESPACE_RE.sub(" ", str(value).strip().lower())


def _is_row_blank(row: list) -> bool:
    return all(v is None or (isinstance(v, str) and v.strip() == "") for v in row)


def extract_mapping_rows(
    source_file: SourceFile,
    *,
    sheet_name: str | None = None,
) -> tuple[list[dict[str, object]], list[str]]:
    """Extract raw mapping rows keyed by canonical field name.

    Args:
        source_file: The mapping :class:`SourceFile`; ``source_file.content``
            must hold the workbook bytes.
        sheet_name: Sheet to read. If omitted, the first sheet containing a
            recognizable ``local_account`` header is used.

    Returns:
        ``(rows, warnings)``. Each row dict only contains keys for headers
        that were recognized; unrecognized columns are dropped with a
        warning rather than silently kept under an arbitrary key.

    Raises:
        IngestionError: if content is missing or no sheet has a recognizable
            local-account header.
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
        if not grid:
            continue

        header_row_index = None
        column_fields: dict[int, str] = {}
        for row_index, row in enumerate(grid[:10]):
            candidate_fields: dict[int, str] = {}
            for col_index, cell in enumerate(row):
                normalized = _normalize_header(cell)
                field_name = _FIELD_ALIASES.get(normalized)
                if field_name:
                    candidate_fields[col_index] = field_name
            if any(field == "local_account" for field in candidate_fields.values()):
                header_row_index = row_index
                column_fields = candidate_fields
                break

        if header_row_index is None:
            continue

        rows: list[dict[str, object]] = []
        for physical_row_index in range(header_row_index + 1, len(grid)):
            row = grid[physical_row_index]
            if _is_row_blank(row):
                continue
            row_dict: dict[str, object] = {}
            for col_index, field_name in column_fields.items():
                row_dict[field_name] = row[col_index] if col_index < len(row) else None

            if not any(row_dict.get(field) not in (None, "") for field in _REQUIRED_FIELDS):
                continue

            row_dict["_source_sheet"] = candidate_sheet
            row_dict["_source_row"] = physical_row_index + 1
            rows.append(row_dict)

        logger.info(
            "Extracted %d mapping row(s) from '%s'!'%s'.",
            len(rows),
            source_file.filename,
            candidate_sheet,
        )
        return rows, warnings

    raise IngestionError(
        f"No mapping table with a recognizable 'local account' column could "
        f"be found in '{source_file.filename}'.",
        details={"source_id": source_file.source_id, "sheets_scanned": candidate_sheet_names},
    )
