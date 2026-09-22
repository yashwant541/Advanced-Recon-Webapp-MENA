"""The only module in ``iraq_recon`` permitted to import ``dataiku``.

Purpose
-------
Isolate every Dataiku-specific operation (managed folders, datasets,
project variables, project key) behind small, focused functions so that no
calculator, schedule, control, or service module ever needs to know a
folder id, dataset name, or that it is running inside Dataiku at all.

``dataiku`` is imported lazily inside each function body rather than at
module level, so this module can be imported (and the rest of
``iraq_recon`` can depend on its function signatures) in environments where
the ``dataiku`` package is not installed -- e.g. the engine's unit tests,
which must run without a Dataiku installation (spec section 24). Only
*calling* one of these functions outside a Dataiku kernel will fail.

Public contents
----------------
``read_managed_folder_file(folder_id, file_path)``
``list_managed_folder_files(folder_id)``
``write_managed_folder_file(folder_id, file_path, content)``
``read_dataiku_dataset(dataset_name, columns=None)``
``write_dataiku_dataset(dataset_name, dataframe)``
``read_project_variables()``
``resolve_project_configuration()``
``get_current_project_key()``

Dependencies: ``dataiku`` (lazily imported; not required for import).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from iraq_recon.exceptions import ConfigurationError, IngestionError

if TYPE_CHECKING:  # pragma: no cover - typing only, never imported at runtime here
    import pandas as pd


def _import_dataiku() -> Any:
    try:
        import dataiku
    except ImportError as exc:  # pragma: no cover - exercised only outside Dataiku
        raise ConfigurationError(
            "The 'dataiku' package is not available. This function must run "
            "inside a Dataiku kernel (a recipe, WebApp backend, or scenario).",
        ) from exc
    return dataiku


def read_managed_folder_file(folder_id: str, file_path: str) -> bytes:
    """Read one file's full contents from a Dataiku managed folder.

    Args:
        folder_id: The managed folder's id (not its human-readable name).
        file_path: Path within the folder.

    Returns:
        The file's raw bytes.

    Raises:
        IngestionError: if the file cannot be read.
    """
    dataiku = _import_dataiku()
    folder = dataiku.Folder(folder_id)
    try:
        with folder.get_download_stream(file_path) as stream:
            return stream.read()
    except Exception as exc:
        raise IngestionError(
            f"Could not read '{file_path}' from managed folder '{folder_id}'.",
            details={"folder_id": folder_id, "file_path": file_path},
        ) from exc


def list_managed_folder_files(folder_id: str) -> list[str]:
    """List every file path within a Dataiku managed folder.

    Args:
        folder_id: The managed folder's id.

    Returns:
        A list of file paths relative to the folder root.
    """
    dataiku = _import_dataiku()
    folder = dataiku.Folder(folder_id)
    return list(folder.list_paths_in_partition())


def write_managed_folder_file(folder_id: str, file_path: str, content: bytes) -> None:
    """Write bytes to a file within a Dataiku managed folder.

    Args:
        folder_id: The managed folder's id.
        file_path: Path within the folder to write to (overwritten if it exists).
        content: Raw bytes to write.
    """
    dataiku = _import_dataiku()
    folder = dataiku.Folder(folder_id)
    folder.upload_data(file_path, content)


def read_dataiku_dataset(dataset_name: str, columns: list[str] | None = None) -> "pd.DataFrame":
    """Read a Dataiku dataset into a pandas DataFrame.

    Args:
        dataset_name: The dataset's name within the current project.
        columns: If given, only these columns are read.

    Returns:
        A pandas DataFrame.
    """
    dataiku = _import_dataiku()
    dataset = dataiku.Dataset(dataset_name)
    return dataset.get_dataframe(columns=columns) if columns else dataset.get_dataframe()


def write_dataiku_dataset(dataset_name: str, dataframe: "pd.DataFrame") -> None:
    """Overwrite a Dataiku dataset with a pandas DataFrame's contents.

    Args:
        dataset_name: The dataset's name within the current project.
        dataframe: The data to write.
    """
    dataiku = _import_dataiku()
    dataset = dataiku.Dataset(dataset_name)
    dataset.write_with_schema(dataframe)


def read_project_variables() -> dict[str, Any]:
    """Read the current Dataiku project's variables.

    Returns:
        A plain dict of project variables (the ``"standard"`` scope).
    """
    dataiku = _import_dataiku()
    client = dataiku.api_client()
    project = client.get_project(dataiku.default_project_key())
    return dict(project.get_variables().get("standard", {}))


def resolve_project_configuration() -> dict[str, Any]:
    """Build a plain configuration dict from the current project's variables.

    The returned dict is shaped for
    ``iraq_recon.models.configuration.ReconciliationConfiguration.from_dict``,
    reading nested sections (``source``, ``units``, ``tolerances``,
    ``execution``, ``mapping``, ``output``) directly from project variables
    of the same names when present.

    Returns:
        A dict suitable for
        :meth:`iraq_recon.models.configuration.ReconciliationConfiguration.from_dict`.
    """
    variables = read_project_variables()
    return {
        section: variables[section]
        for section in ("source", "units", "tolerances", "execution", "mapping", "output")
        if section in variables
    }


def get_current_project_key() -> str:
    """Return the current Dataiku project's key."""
    dataiku = _import_dataiku()
    return str(dataiku.default_project_key())
