"""Convert raw mapping rows into validated ``MappingRecord`` objects.

Purpose
-------
Bridge ``ingestion.mapping_reader`` output (plain dicts with string/None
values as read from Excel) into typed, validated
:class:`iraq_recon.models.mapping.MappingRecord` instances. Per-row
coercion failures are collected as issues rather than raising, so one bad
row in a 500-row mapping table does not abort the whole load.

Public contents
----------------
``load_mapping_records(raw_rows)`` -- returns ``(records, issues)``.

Dependencies: ``iraq_recon.models.mapping``, ``iraq_recon.constants``,
``iraq_recon.normalization.account_normalizer``,
``iraq_recon.normalization.description_normalizer``,
``iraq_recon.normalization.unit_normalizer``.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from iraq_recon.constants import (
    EconomicRole,
    InclusionStatus,
    MappingMethod,
    NaturalSide,
    StatementType,
)
from iraq_recon.models.mapping import MappingRecord
from iraq_recon.normalization.account_normalizer import normalize_account
from iraq_recon.normalization.description_normalizer import normalize_description


def _coerce_enum(enum_cls: type, raw_value: Any, default: Any) -> tuple[Any, str | None]:
    if raw_value is None or str(raw_value).strip() == "":
        return default, None
    text = str(raw_value).strip().upper().replace(" ", "_").replace("-", "_")
    try:
        return enum_cls(text), None
    except ValueError:
        for member in enum_cls:
            if member.value.replace("_", "") == text.replace("_", ""):
                return member, None
        return default, f"Unrecognized {enum_cls.__name__} value '{raw_value}', defaulted to {default}."


def _coerce_sign(raw_value: Any) -> tuple[int | None, str | None]:
    if raw_value is None or str(raw_value).strip() == "":
        return None, "Missing presentation sign."
    text = str(raw_value).strip()
    if text in ("+1", "1", "+"):
        return 1, None
    if text in ("-1", "-"):
        return -1, None
    try:
        parsed = int(float(text))
    except ValueError:
        return None, f"Could not parse presentation sign '{raw_value}'."
    if parsed not in (1, -1):
        return None, f"Presentation sign must be +1 or -1, got '{raw_value}'."
    return parsed, None


def _coerce_decimal(raw_value: Any, default: Decimal) -> Decimal:
    if raw_value is None or str(raw_value).strip() == "":
        return default
    try:
        return Decimal(str(raw_value))
    except InvalidOperation:
        return default


def _coerce_date(raw_value: Any) -> date | None:
    if raw_value is None or str(raw_value).strip() == "":
        return None
    if isinstance(raw_value, date):
        return raw_value
    text = str(raw_value).strip()
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _coerce_float(raw_value: Any, default: float) -> float:
    if raw_value is None or str(raw_value).strip() == "":
        return default
    try:
        value = float(raw_value)
    except ValueError:
        return default
    return max(0.0, min(1.0, value))


def load_mapping_records(
    raw_rows: list[dict[str, Any]],
) -> tuple[list[MappingRecord], list[str]]:
    """Coerce raw mapping-table rows into :class:`MappingRecord` objects.

    Args:
        raw_rows: Rows as produced by
            ``ingestion.mapping_reader.extract_mapping_rows``.

    Returns:
        ``(records, issues)``. A row that is missing its local account, or
        whose presentation sign cannot be resolved, is skipped and reported
        as an issue rather than raising.
    """
    records: list[MappingRecord] = []
    issues: list[str] = []

    for row in raw_rows:
        row_ref = f"{row.get('_source_sheet', '?')}!row{row.get('_source_row', '?')}"

        normalized_account = normalize_account(row.get("local_account"))
        if normalized_account.value is None:
            issues.append(f"{row_ref}: skipped -- {normalized_account.warning}")
            continue

        presentation_sign, sign_warning = _coerce_sign(row.get("presentation_sign"))
        if presentation_sign is None:
            issues.append(f"{row_ref}: skipped -- {sign_warning}")
            continue

        statement_type, st_warning = _coerce_enum(
            StatementType, row.get("statement_type"), StatementType.UNKNOWN
        )
        if st_warning:
            issues.append(f"{row_ref}: {st_warning}")

        natural_side, ns_warning = _coerce_enum(
            NaturalSide, row.get("natural_side"), NaturalSide.UNKNOWN
        )
        if ns_warning:
            issues.append(f"{row_ref}: {ns_warning}")

        economic_role, role_warning = _coerce_enum(
            EconomicRole, row.get("economic_role"), EconomicRole.INFORMATIONAL_ONLY
        )
        if role_warning:
            issues.append(f"{row_ref}: {role_warning}")

        inclusion_status, inclusion_warning = _coerce_enum(
            InclusionStatus, row.get("inclusion_status"), InclusionStatus.INCLUDE
        )
        if inclusion_warning:
            issues.append(f"{row_ref}: {inclusion_warning}")

        mapping_method_raw = row.get("mapping_method")
        if mapping_method_raw:
            mapping_method, method_warning = _coerce_enum(
                MappingMethod, mapping_method_raw, MappingMethod.APPROVED_ACCOUNT
            )
            if method_warning:
                issues.append(f"{row_ref}: {method_warning}")
        else:
            mapping_method = MappingMethod.APPROVED_ACCOUNT

        ayra_category = str(row.get("ayra_category") or "").strip()
        iraq_reporting_bucket = str(row.get("iraq_reporting_bucket") or "").strip()
        financial_statement_line = str(row.get("financial_statement_line") or "").strip()

        try:
            record = MappingRecord(
                local_account=normalized_account.value,
                local_description=normalize_description(row.get("local_description")).cleaned_text,
                local_account_group=(
                    normalize_account(row.get("local_account_group")).value
                    if row.get("local_account_group")
                    else None
                ),
                statement_type=statement_type,
                natural_side=natural_side,
                economic_role=economic_role,
                ayra_category=ayra_category,
                iraq_reporting_bucket=iraq_reporting_bucket,
                financial_statement_line=financial_statement_line,
                schedule_code=(str(row["schedule_code"]).strip() if row.get("schedule_code") else None),
                schedule_row=(str(row["schedule_row"]).strip() if row.get("schedule_row") else None),
                presentation_sign=presentation_sign,
                inclusion_status=inclusion_status,
                unit_factor=_coerce_decimal(row.get("unit_factor"), Decimal("1")),
                mapping_method=mapping_method,
                mapping_confidence=_coerce_float(row.get("mapping_confidence"), 1.0),
                effective_from=_coerce_date(row.get("effective_from")),
                effective_to=_coerce_date(row.get("effective_to")),
                mapping_rationale=str(row.get("mapping_rationale") or "").strip(),
            )
        except ValueError as exc:
            issues.append(f"{row_ref}: skipped -- {exc}")
            continue

        records.append(record)

    return records, issues
