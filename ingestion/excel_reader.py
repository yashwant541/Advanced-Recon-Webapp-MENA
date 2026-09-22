"""Low-level Excel workbook reader.

Purpose
-------
Turn raw workbook bytes into plain-Python sheet grids (lists of lists of
cell values) with no accounting or mapping logic attached. Every other
ingestion module builds on top of :func:`read_workbook`.

Public contents
----------------
``RawWorkbook`` -- sheet list plus raw grids and warnings.
``read_workbook(filename, content, sheet_names=None)`` -- parse bytes.

Inputs/Outputs
--------------
Input: filename (str), workbook bytes, optional sheet-name filter.
Output: :class:`RawWorkbook` (plain data, JSON/pickle friendly except that
cell values may be ``datetime``/``float``/``str``/``None`` as read from
openpyxl).

Dependencies: ``openpyxl`` (declared in ``requirements.txt``). No Dataiku,
no filesystem access -- a temporary file is never written; openpyxl reads
directly from an in-memory buffer.

Error handling
--------------
Raises :class:`iraq_recon.exceptions.UnsupportedFileError` for anything that
is not a readable, unencrypted ``.xlsx``/``.xlsm`` workbook (wrong
extension, corrupt content, or password protection).
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from io import BytesIO
from typing import Any

from iraq_recon.exceptions import UnsupportedFileError
from iraq_recon.logging_utils import get_logger

logger = get_logger(__name__)

_SUPPORTED_EXTENSIONS = (".xlsx", ".xlsm")


@dataclass(frozen=True)
class RawWorkbook:
    """Plain-Python representation of a parsed workbook.

    Attributes:
        filename: Original filename.
        sheet_names: Sheet names in workbook order.
        grids: ``{sheet_name: [[cell, cell, ...], ...]}``, 0-based rows/cols,
            rectangular (short rows padded with ``None``).
        warnings: Non-fatal issues encountered while reading.
    """

    filename: str
    sheet_names: tuple[str, ...]
    grids: dict[str, list[list[Any]]] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()


def read_workbook(
    filename: str,
    content: bytes,
    sheet_names: list[str] | None = None,
) -> RawWorkbook:
    """Read an Excel workbook's cell grids from raw bytes.

    Args:
        filename: Original filename, used only to validate the extension
            and for error messages/lineage.
        content: Raw workbook bytes.
        sheet_names: If given, only these sheets are read (missing names are
            reported as warnings, not errors).

    Returns:
        A :class:`RawWorkbook` with one grid per requested (or all) sheet.

    Raises:
        UnsupportedFileError: if the extension is unsupported, the bytes are
            not a valid zip/xlsx package, or the workbook is encrypted.
    """
    lower_name = filename.lower()
    if not lower_name.endswith(_SUPPORTED_EXTENSIONS):
        raise UnsupportedFileError(
            f"Unsupported file extension for '{filename}'. "
            f"Expected one of {_SUPPORTED_EXTENSIONS}.",
            details={"filename": filename},
        )

    if not content:
        raise UnsupportedFileError(
            f"'{filename}' has no content.", details={"filename": filename}
        )

    buffer = BytesIO(content)

    try:
        import openpyxl
    except ImportError as exc:  # pragma: no cover - environment guard
        raise UnsupportedFileError(
            "openpyxl is required to read Excel workbooks but is not installed.",
        ) from exc

    try:
        workbook = openpyxl.load_workbook(buffer, data_only=True, read_only=True)
    except zipfile.BadZipFile as exc:
        raise UnsupportedFileError(
            f"'{filename}' could not be opened. It may be corrupt, an older "
            f".xls file saved with an .xlsx extension, or password protected.",
            details={"filename": filename},
        ) from exc
    except KeyError as exc:
        # openpyxl raises KeyError for some malformed OOXML packages.
        raise UnsupportedFileError(
            f"'{filename}' does not appear to be a valid Excel workbook.",
            details={"filename": filename},
        ) from exc

    all_sheet_names = list(workbook.sheetnames)
    warnings: list[str] = []

    if sheet_names is None:
        selected_sheet_names = all_sheet_names
    else:
        selected_sheet_names = [name for name in sheet_names if name in all_sheet_names]
        missing = [name for name in sheet_names if name not in all_sheet_names]
        for name in missing:
            warnings.append(f"Requested sheet '{name}' was not found in '{filename}'.")

    grids: dict[str, list[list[Any]]] = {}
    for sheet_name in selected_sheet_names:
        worksheet = workbook[sheet_name]
        grid: list[list[Any]] = []
        max_col = 0
        for row in worksheet.iter_rows(values_only=True):
            row_values = list(row)
            max_col = max(max_col, len(row_values))
            grid.append(row_values)
        for row_values in grid:
            if len(row_values) < max_col:
                row_values.extend([None] * (max_col - len(row_values)))
        grids[sheet_name] = grid

    workbook.close()

    logger.info(
        "Read workbook '%s': %d sheet(s) requested, %d parsed.",
        filename,
        len(selected_sheet_names),
        len(grids),
    )

    return RawWorkbook(
        filename=filename,
        sheet_names=tuple(all_sheet_names),
        grids=grids,
        warnings=tuple(warnings),
    )
