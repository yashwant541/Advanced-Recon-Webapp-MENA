"""Snapshot service: load trial balances/statements and compare TB candidates.

Purpose
-------
Give the public API one place to turn uploaded trial-balance and
financial-statement workbooks into normalized records, and to compare
multiple candidate trial balances against high-confidence anchors (spec
section 12), without callers touching ``iraq_recon.ingestion`` or
``iraq_recon.engine.snapshot_selector`` directly.

Public contents
----------------
``load_trial_balances(source_files)``
``load_financial_statement(source_file)``
``compare_tb_snapshots(candidates, mapping_records, configuration, ...)``
``select_best_snapshot(evidence)``

Dependencies: ``iraq_recon.ingestion.trial_balance_reader``,
``iraq_recon.ingestion.financial_statement_reader``,
``iraq_recon.normalization.schema_normalizer``, ``iraq_recon.engine.snapshot_selector``.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from iraq_recon.engine.snapshot_selector import (
    AnchorDefinition,
    DEFAULT_ANCHORS,
    SnapshotEvidence,
    compare_tb_snapshots as _compare_tb_snapshots,
    select_best_snapshot as _select_best_snapshot,
)
from iraq_recon.ingestion.financial_statement_reader import extract_financial_statement_lines
from iraq_recon.ingestion.trial_balance_reader import extract_trial_balance_rows
from iraq_recon.models.configuration import ReconciliationConfiguration
from iraq_recon.models.mapping import MappingRecord
from iraq_recon.models.source import SourceFile, StatementLineRecord, TrialBalanceRecord
from iraq_recon.normalization.schema_normalizer import normalize_trial_balance_rows


def load_trial_balances(
    source_files: list[SourceFile],
) -> tuple[dict[str, list[TrialBalanceRecord]], dict[str, list[str]]]:
    """Extract and normalize every candidate trial-balance source file.

    Args:
        source_files: One or more trial-balance workbooks (e.g. W1..W4).

    Returns:
        ``(candidates, warnings_by_source)`` -- ``candidates`` maps each
        source file's id to its normalized :class:`TrialBalanceRecord` list;
        ``warnings_by_source`` maps the same key to ingestion/normalization
        warnings.
    """
    candidates: dict[str, list[TrialBalanceRecord]] = {}
    warnings_by_source: dict[str, list[str]] = {}

    for source_file in source_files:
        raw_rows, extraction_warnings = extract_trial_balance_rows(source_file)
        records, normalization_warnings = normalize_trial_balance_rows(
            raw_rows, source_unit=source_file.source_unit
        )
        candidates[source_file.source_id] = records
        warnings_by_source[source_file.source_id] = extraction_warnings + normalization_warnings

    return candidates, warnings_by_source


def load_financial_statement(
    source_file: SourceFile,
) -> tuple[dict[str, StatementLineRecord], list[str]]:
    """Extract every reported line from a financial-statement source file.

    Args:
        source_file: The financial-statement workbook.

    Returns:
        ``({line_code: StatementLineRecord}, warnings)``.
    """
    lines, warnings = extract_financial_statement_lines(source_file)
    return {line.line_code: line for line in lines}, warnings


def compare_tb_snapshots(
    candidates: dict[str, list[TrialBalanceRecord]],
    mapping_records: list[MappingRecord],
    configuration: ReconciliationConfiguration,
    *,
    anchors: list[AnchorDefinition] | None = None,
    anchor_reported_amounts: dict[str, Decimal] | None = None,
    as_of: date | None = None,
) -> list[SnapshotEvidence]:
    """Score every candidate trial balance against the anchor set.

    Args:
        candidates: ``{snapshot_id: trial_balance_records}``.
        mapping_records: All loaded mapping records.
        configuration: The run configuration.
        anchors: Anchor set to evaluate; defaults to
            :data:`iraq_recon.engine.snapshot_selector.DEFAULT_ANCHORS`.
        anchor_reported_amounts: ``{anchor_code: reported_amount}``; anchors
            with no entry are skipped rather than inferred.
        as_of: Effective date for mapping resolution.

    Returns:
        A ranked list of :class:`SnapshotEvidence`, best candidate first.
    """
    return _compare_tb_snapshots(
        candidates,
        anchors if anchors is not None else list(DEFAULT_ANCHORS),
        anchor_reported_amounts or {},
        mapping_records,
        configuration,
        as_of=as_of,
    )


def select_best_snapshot(evidence: list[SnapshotEvidence]) -> str | None:
    """Return the top-ranked snapshot id from :func:`compare_tb_snapshots` output."""
    return _select_best_snapshot(evidence)
