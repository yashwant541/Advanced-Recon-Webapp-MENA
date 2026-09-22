"""Inspection service: workbook/sheet inspection for the WebApp's upload step.

Purpose
-------
Give the public API (and, through it, the thin WebApp backend) one place to
call for "what is in this file" without reaching into
``iraq_recon.ingestion`` directly.

Public contents
----------------
``inspect_source_file(filename, content)``
``inspect_workbook(filename, content, sheet_names=None)``
``list_workbook_sheets(filename, content)``

Dependencies: ``iraq_recon.ingestion.workbook_inspector``.
"""

from __future__ import annotations

from iraq_recon.ingestion.workbook_inspector import (
    WorkbookInspection,
    inspect_workbook as _inspect_workbook,
    list_workbook_sheets as _list_workbook_sheets,
)


def inspect_source_file(filename: str, content: bytes) -> WorkbookInspection:
    """Inspect every sheet of an uploaded source workbook.

    Args:
        filename: Original filename.
        content: Raw workbook bytes.

    Returns:
        A :class:`iraq_recon.ingestion.workbook_inspector.WorkbookInspection`.
    """
    return _inspect_workbook(filename, content)


def inspect_workbook(
    filename: str,
    content: bytes,
    sheet_names: list[str] | None = None,
) -> WorkbookInspection:
    """Inspect specific (or all) sheets of an uploaded source workbook."""
    return _inspect_workbook(filename, content, sheet_names=sheet_names)


def list_workbook_sheets(filename: str, content: bytes) -> list[str]:
    """Return only the sheet names of an uploaded source workbook."""
    return _list_workbook_sheets(filename, content)
