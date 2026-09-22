"""Export service: turn pipeline data into downloadable bytes.

Purpose
-------
Give the public API one place to call for every kind of export, hiding
which exporter module handles which format:

    - the final reconciliation outcome (audit-ready ``.xlsx`` or raw ``.json``);
    - the "middle process" trace behind a completed run (spec: "show the
      middle process -- how things work");
    - the standardized-format trial balance / financial statement, which
      can be downloaded independently of running a full reconciliation, so
      a reviewer can check the normalized data before committing to it.

Nothing here reruns any calculation -- every function serializes data that
was already computed and passed in.

Public contents
----------------
``export_reconciliation(run, export_format="xlsx")``
``export_standardized_trial_balance(records)``
``export_standardized_financial_statement(lines)``

Dependencies: ``iraq_recon.exporters.*``.
"""

from __future__ import annotations

from iraq_recon.constants import ExportFormat
from iraq_recon.exceptions import ExportError
from iraq_recon.exporters.audit_exporter import export_audit_workbook_bytes
from iraq_recon.exporters.json_exporter import export_to_json
from iraq_recon.exporters.process_trace_exporter import export_process_trace_bytes
from iraq_recon.exporters.standardized_exporter import (
    export_standardized_financial_statement as _export_standardized_financial_statement,
)
from iraq_recon.exporters.standardized_exporter import (
    export_standardized_trial_balance as _export_standardized_trial_balance,
)
from iraq_recon.models.reconciliation import ReconciliationRun
from iraq_recon.models.source import StatementLineRecord, TrialBalanceRecord

_EXPORTERS = {
    ExportFormat.XLSX: export_audit_workbook_bytes,
    ExportFormat.JSON: export_to_json,
    ExportFormat.PROCESS_TRACE: export_process_trace_bytes,
}


def export_reconciliation(run: ReconciliationRun, export_format: str = "xlsx") -> bytes:
    """Export a completed reconciliation run to the requested format.

    Args:
        run: A completed :class:`ReconciliationRun`.
        export_format: ``"xlsx"`` for the full audit workbook, ``"json"``
            for the raw serialized result, or ``"process_trace"`` for the
            "middle process" workbook (standardized data, mapping table,
            mapping validation/coverage, and per-calculator detail).

    Returns:
        The export's raw bytes.

    Raises:
        ExportError: if ``export_format`` is not supported.
    """
    try:
        normalized_format = ExportFormat(export_format.lower())
    except ValueError as exc:
        raise ExportError(
            f"Unsupported export format '{export_format}'. Supported formats: "
            f"{[f.value for f in ExportFormat]}.",
            details={"export_format": export_format},
        ) from exc

    return _EXPORTERS[normalized_format](run)


def export_standardized_trial_balance(records: list[TrialBalanceRecord]) -> bytes:
    """Export a standardized-format workbook for a normalized trial balance."""
    return _export_standardized_trial_balance(records)


def export_standardized_financial_statement(lines: list[StatementLineRecord]) -> bytes:
    """Export a standardized-format workbook for a normalized financial statement."""
    return _export_standardized_financial_statement(lines)
