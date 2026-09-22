"""Mapping service: load, validate, and score coverage of mapping tables.

Purpose
-------
Give the public API one place to turn uploaded mapping workbooks (local
account bridge, Ayra semantic mapping, Iraq balance-sheet mapping) into
validated :class:`MappingRecord` objects and a coverage report against a
trial balance, without callers touching ``iraq_recon.ingestion`` or
``iraq_recon.mapping`` directly.

Public contents
----------------
``load_mapping_files(source_files)``
``validate_mappings(mapping_records)``
``calculate_mapping_coverage(records, mapping_records, as_of=None)``

Dependencies: ``iraq_recon.ingestion.mapping_reader``,
``iraq_recon.mapping.mapping_loader``, ``iraq_recon.mapping.mapping_validator``,
``iraq_recon.mapping.mapping_coverage``, ``iraq_recon.mapping.local_bridge``.
"""

from __future__ import annotations

from datetime import date

from iraq_recon.ingestion.mapping_reader import extract_mapping_rows
from iraq_recon.mapping.local_bridge import build_local_account_bridge
from iraq_recon.mapping.mapping_coverage import MappingCoverageResult, calculate_mapping_coverage as _calculate_coverage
from iraq_recon.mapping.mapping_loader import load_mapping_records as _load_mapping_records
from iraq_recon.mapping.mapping_validator import validate_mapping_records as _validate_mapping_records
from iraq_recon.models.mapping import MappingRecord
from iraq_recon.models.source import SourceFile, TrialBalanceRecord
from iraq_recon.models.validation import ValidationResult


def load_mapping_files(source_files: list[SourceFile]) -> tuple[list[MappingRecord], list[str]]:
    """Extract and load mapping records from every mapping source file.

    Args:
        source_files: Mapping workbooks (local bridge, Ayra, Iraq buckets --
            any file with a recognizable mapping header layout).

    Returns:
        ``(records, issues)`` -- ``records`` from every file combined;
        ``issues`` includes both extraction warnings and per-row load issues.
    """
    all_records: list[MappingRecord] = []
    all_issues: list[str] = []

    for source_file in source_files:
        raw_rows, extraction_warnings = extract_mapping_rows(source_file)
        all_issues.extend(f"{source_file.filename}: {w}" for w in extraction_warnings)

        records, load_issues = _load_mapping_records(raw_rows)
        all_records.extend(records)
        all_issues.extend(f"{source_file.filename}: {issue}" for issue in load_issues)

    return all_records, all_issues


def validate_mappings(mapping_records: list[MappingRecord]) -> ValidationResult:
    """Validate a set of loaded mapping records for structural issues."""
    return _validate_mapping_records(mapping_records)


def calculate_mapping_coverage(
    records: list[TrialBalanceRecord],
    mapping_records: list[MappingRecord],
    as_of: date | None = None,
) -> MappingCoverageResult:
    """Resolve a local-account bridge and calculate its coverage over ``records``.

    Args:
        records: Trial-balance records for the selected snapshot.
        mapping_records: All loaded mapping records.
        as_of: Effective date for mapping resolution; defaults to today.

    Returns:
        A :class:`MappingCoverageResult`.
    """
    bridge = build_local_account_bridge(mapping_records, as_of=as_of)
    return _calculate_coverage(records, bridge)
