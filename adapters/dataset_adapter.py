"""Flat DataFrame conversions of run results, for Dataiku dataset output.

Purpose
-------
Turn the pieces of a :class:`ReconciliationRun` into flat pandas
DataFrames matching the logical output tables from spec section 19
(``RECON_LINE_RESULTS``, ``RECON_ACCOUNT_TRACE``, etc.), so downstream BI
tools and other Dataiku recipes can consume reconciliation output as plain
datasets. This module never decides physical dataset names -- see
``repositories.dataiku_repository`` for how logical names resolve to
configured dataset names.

Public contents
----------------
``RESULT_TABLE_NAMES`` -- logical name -> spec-documented dataset name.
``run_control_to_dataframe(run)``
``line_results_to_dataframe(run)``
``account_trace_to_dataframe(run)``
``schedule_results_to_dataframe(run)``
``control_results_to_dataframe(run)``
``exceptions_to_dataframe(run)``
``source_files_to_dataframe(source_files)``
``tb_standardized_to_dataframe(records)``
``mapping_validation_to_dataframe(validation)``
``account_classified_to_dataframe(mapping_records)``

Dependencies: ``pandas``, ``iraq_recon.models.*``.
"""

from __future__ import annotations

import pandas as pd

from iraq_recon.models.mapping import MappingRecord
from iraq_recon.models.reconciliation import ReconciliationRun
from iraq_recon.models.source import SourceFile, TrialBalanceRecord
from iraq_recon.models.validation import ValidationResult

RESULT_TABLE_NAMES: dict[str, str] = {
    "run_control": "RECON_RUN_CONTROL",
    "source_files": "RECON_SOURCE_FILES",
    "tb_standardized": "RECON_TB_STANDARDIZED",
    "mapping_validation": "RECON_MAPPING_VALIDATION",
    "account_classified": "RECON_ACCOUNT_CLASSIFIED",
    "line_results": "RECON_LINE_RESULTS",
    "account_trace": "RECON_ACCOUNT_TRACE",
    "schedule_results": "RECON_SCHEDULE_RESULTS",
    "control_results": "RECON_CONTROL_RESULTS",
    "exceptions": "RECON_EXCEPTIONS",
}


def run_control_to_dataframe(run: ReconciliationRun) -> pd.DataFrame:
    """Build the ``RECON_RUN_CONTROL`` table: one summary row for this run."""
    return pd.DataFrame([run.summary_dict()])


def line_results_to_dataframe(run: ReconciliationRun) -> pd.DataFrame:
    """Build the ``RECON_LINE_RESULTS`` table."""
    rows = [{"run_id": run.run_id, **line.to_dict()} for line in run.line_results]
    return pd.DataFrame(rows)


def account_trace_to_dataframe(run: ReconciliationRun) -> pd.DataFrame:
    """Build the ``RECON_ACCOUNT_TRACE`` table."""
    rows = [{"run_id": run.run_id, **entry.to_dict()} for entry in run.account_trace]
    return pd.DataFrame(rows)


def schedule_results_to_dataframe(run: ReconciliationRun) -> pd.DataFrame:
    """Build the ``RECON_SCHEDULE_RESULTS`` table (bucket/control detail dropped;
    use the run's JSON store for that -- this table is the flat tie-out summary)."""
    rows = []
    for schedule in run.schedule_results:
        row = schedule.to_dict()
        row.pop("bucket_results", None)
        row.pop("control_results", None)
        rows.append({"run_id": run.run_id, **row})
    return pd.DataFrame(rows)


def control_results_to_dataframe(run: ReconciliationRun) -> pd.DataFrame:
    """Build the ``RECON_CONTROL_RESULTS`` table."""
    rows = [{"run_id": run.run_id, **control.to_dict()} for control in run.control_results]
    return pd.DataFrame(rows)


def exceptions_to_dataframe(run: ReconciliationRun) -> pd.DataFrame:
    """Build the ``RECON_EXCEPTIONS`` table."""
    rows = [{"run_id": run.run_id, **exc.to_dict()} for exc in run.exceptions]
    return pd.DataFrame(rows)


def source_files_to_dataframe(source_files: list[SourceFile]) -> pd.DataFrame:
    """Build the ``RECON_SOURCE_FILES`` table (one row per ingested source file)."""
    return pd.DataFrame([sf.to_dict() for sf in source_files])


def tb_standardized_to_dataframe(records: list[TrialBalanceRecord]) -> pd.DataFrame:
    """Build the ``RECON_TB_STANDARDIZED`` table (normalized trial-balance rows)."""
    return pd.DataFrame([r.to_dict() for r in records])


def mapping_validation_to_dataframe(validation: ValidationResult) -> pd.DataFrame:
    """Build the ``RECON_MAPPING_VALIDATION`` table (one row per validation issue)."""
    return pd.DataFrame([issue.to_dict() for issue in validation.issues])


def account_classified_to_dataframe(mapping_records: list[MappingRecord]) -> pd.DataFrame:
    """Build the ``RECON_ACCOUNT_CLASSIFIED`` table (one row per mapped account)."""
    return pd.DataFrame([m.to_dict() for m in mapping_records])
