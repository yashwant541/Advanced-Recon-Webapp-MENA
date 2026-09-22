"""Domain-level operations over Dataiku managed folders.

Purpose
-------
Sit one layer above ``adapters.dataiku_io``: turn "read every file in this
folder" into typed :class:`SourceFile` objects, and give the export/run
repositories a small JSON read/write helper -- so callers work in terms of
source files and JSON payloads, never raw folder ids and byte streams
directly (those stay inside this module and ``dataiku_io``).

Public contents
----------------
``load_source_files_from_folder(folder_id, source_role, source_unit="IQD")``
``save_export_file(folder_id, filename, content)``
``save_json(folder_id, file_path, payload)``
``load_json(folder_id, file_path)``

Dependencies: ``iraq_recon.adapters.dataiku_io``.
"""

from __future__ import annotations

import json
from typing import Any

from iraq_recon.adapters.dataiku_io import (
    list_managed_folder_files,
    read_managed_folder_file,
    write_managed_folder_file,
)
from iraq_recon.models.source import SourceFile


def load_source_files_from_folder(
    folder_id: str,
    source_role: str,
    *,
    source_unit: str = "IQD",
    extensions: tuple[str, ...] = (".xlsx", ".xlsm"),
) -> list[SourceFile]:
    """Load every matching file in a managed folder as a :class:`SourceFile`.

    Args:
        folder_id: The managed folder's id.
        source_role: Role to tag every loaded file with (e.g.
            ``"TRIAL_BALANCE"``).
        source_unit: Declared unit for every loaded file.
        extensions: Only files with one of these extensions are loaded.

    Returns:
        One :class:`SourceFile` per matching file, with ``content`` populated.
    """
    source_files: list[SourceFile] = []
    for file_path in list_managed_folder_files(folder_id):
        if not file_path.lower().endswith(extensions):
            continue
        content = read_managed_folder_file(folder_id, file_path)
        filename = file_path.rsplit("/", 1)[-1]
        file_type = filename.rsplit(".", 1)[-1].lower()
        source_files.append(
            SourceFile(
                source_id=f"{folder_id}:{file_path}",
                filename=filename,
                file_type=file_type,
                source_role=source_role,
                content=content,
                source_unit=source_unit,
                content_reference=f"{folder_id}/{file_path}",
            )
        )
    return source_files


def save_export_file(folder_id: str, filename: str, content: bytes) -> str:
    """Write export bytes to a managed folder and return the stored path.

    Args:
        folder_id: The export managed folder's id.
        filename: File name to write.
        content: Raw file bytes (e.g. an Excel export workbook).

    Returns:
        The path the file was written to, as ``"{folder_id}/{filename}"``.
    """
    write_managed_folder_file(folder_id, filename, content)
    return f"{folder_id}/{filename}"


def save_json(folder_id: str, file_path: str, payload: dict[str, Any]) -> None:
    """Serialize ``payload`` as JSON and write it to a managed folder."""
    write_managed_folder_file(folder_id, file_path, json.dumps(payload).encode("utf-8"))


def load_json(folder_id: str, file_path: str) -> dict[str, Any]:
    """Read and deserialize a JSON file from a managed folder."""
    return json.loads(read_managed_folder_file(folder_id, file_path).decode("utf-8"))
