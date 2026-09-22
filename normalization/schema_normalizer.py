"""Orchestrates per-field normalizers into standard-schema records.

Purpose
-------
Bridge :class:`iraq_recon.models.source.SourceRow` (raw, ingestion-only
values) to :class:`iraq_recon.models.source.TrialBalanceRecord` (normalized,
Decimal-safe, row-classified). This module contains no accounting mapping
logic -- it only applies account/description/amount normalization and row
classification, in that fixed order, to one row at a time.

Public contents
----------------
``normalize_trial_balance_row(row, source_unit, account_hierarchy=None)`` --
normalize a single :class:`SourceRow`; may return ``None`` for rows that
classify as non-posting/non-informative (blank, header, template) along
with an explanatory warning.
``normalize_trial_balance_rows(rows, source_unit)`` -- convenience wrapper
that also builds the account hierarchy (parent detection) across the whole
sheet before normalizing each row.

Dependencies: ``normalization.account_normalizer``,
``normalization.description_normalizer``, ``normalization.amount_normalizer``,
``normalization.row_classifier``.
"""

from __future__ import annotations

from decimal import Decimal

from iraq_recon.constants import RowType
from iraq_recon.models.source import SourceRow, TrialBalanceRecord
from iraq_recon.normalization.account_normalizer import normalize_account
from iraq_recon.normalization.amount_normalizer import ParsedAmount, normalize_amount
from iraq_recon.normalization.description_normalizer import normalize_description
from iraq_recon.normalization.row_classifier import classify_row


def _resolve_amount(original_values: dict[str, object]) -> ParsedAmount:
    if "balance" in original_values:
        return normalize_amount(original_values.get("balance"))

    debit_parsed = normalize_amount(original_values.get("debit"))
    credit_parsed = normalize_amount(original_values.get("credit"))

    if debit_parsed.is_blank and credit_parsed.is_blank:
        return ParsedAmount(value=None, original_text="", is_blank=True)

    if debit_parsed.warning or credit_parsed.warning:
        combined_warning = " ".join(
            w for w in (debit_parsed.warning, credit_parsed.warning) if w
        )
        return ParsedAmount(value=None, original_text="debit/credit", warning=combined_warning)

    debit_value = debit_parsed.value or Decimal("0")
    credit_value = credit_parsed.value or Decimal("0")
    return ParsedAmount(value=debit_value - credit_value, original_text="debit/credit")


def _derive_account_hierarchy(accounts: list[str]) -> set[str]:
    """Return the subset of ``accounts`` that are string-prefixes of another.

    A simple, conservative parent heuristic: account "1831" is treated as a
    parent of "183110" if both are present in the same trial balance. This
    is intentionally cautious -- it never invents a hierarchy the source
    data does not already contain.
    """
    account_set = set(accounts)
    parents: set[str] = set()
    for account in account_set:
        for other in account_set:
            if other != account and other.startswith(account) and len(other) > len(account):
                parents.add(account)
                break
    return parents


def normalize_trial_balance_row(
    row: SourceRow,
    *,
    source_unit: str,
    account_hierarchy: set[str] | None = None,
) -> tuple[TrialBalanceRecord | None, list[str]]:
    """Normalize one raw trial-balance :class:`SourceRow`.

    Args:
        row: Raw row with ``original_values`` populated by
            ``ingestion.trial_balance_reader``.
        source_unit: Unit the balance is expressed in, e.g. ``"IQD"``.
        account_hierarchy: Account numbers known to be parents of other
            accounts within the same trial balance (see
            :func:`_derive_account_hierarchy`).

    Returns:
        ``(record, warnings)``. ``record`` is ``None`` for rows classified
        as ``BLANK``, ``HEADER``, or ``TEMPLATE``; such rows are reported in
        ``warnings`` rather than silently dropped without a trace.
    """
    warnings: list[str] = []
    account_hierarchy = account_hierarchy or set()

    normalized_account = normalize_account(row.original_values.get("account"))
    if normalized_account.warning:
        warnings.append(f"row {row.source_row_number}: {normalized_account.warning}")

    normalized_description = normalize_description(row.original_values.get("description"))

    parsed_amount = _resolve_amount(row.original_values)
    if parsed_amount.warning:
        warnings.append(f"row {row.source_row_number}: {parsed_amount.warning}")

    row_type = classify_row(
        account=normalized_account.value,
        description_matching_form=normalized_description.matching_form,
        amount_is_blank=parsed_amount.is_blank,
        amount_value=parsed_amount.value,
        has_known_children=(normalized_account.value in account_hierarchy),
    )

    if row_type in (RowType.BLANK, RowType.HEADER, RowType.TEMPLATE):
        warnings.append(
            f"row {row.source_row_number}: classified as {row_type} and excluded from posting totals."
        )
        return None, warnings

    balance_value = parsed_amount.value if parsed_amount.value is not None else Decimal("0")

    record = TrialBalanceRecord(
        account_number=normalized_account.value or "",
        account_description=normalized_description.cleaned_text,
        original_balance=balance_value,
        normalized_balance=balance_value,
        source_unit=source_unit,
        source_sheet=row.source_sheet,
        source_row=row.source_row_number,
        source_file=row.source_file,
        row_type=row_type,
        posting_status="POSTS" if row_type == RowType.POSTING else "NON_POSTING",
    )
    return record, warnings


def normalize_trial_balance_rows(
    rows: list[SourceRow],
    *,
    source_unit: str,
) -> tuple[list[TrialBalanceRecord], list[str]]:
    """Normalize a full sheet's worth of trial-balance rows.

    Derives the account hierarchy across ``rows`` first (so parent rows are
    detected even though rows are processed independently), then normalizes
    each row in turn.

    Args:
        rows: Raw rows from ``ingestion.trial_balance_reader``.
        source_unit: Unit the balances are expressed in.

    Returns:
        ``(records, warnings)`` -- ``records`` excludes blank/header/template
        rows; ``warnings`` covers every row, including excluded ones.
    """
    candidate_accounts = [
        normalize_account(row.original_values.get("account")).value
        for row in rows
    ]
    account_hierarchy = _derive_account_hierarchy([a for a in candidate_accounts if a])

    records: list[TrialBalanceRecord] = []
    all_warnings: list[str] = []
    for row in rows:
        record, warnings = normalize_trial_balance_row(
            row, source_unit=source_unit, account_hierarchy=account_hierarchy
        )
        all_warnings.extend(warnings)
        if record is not None:
            records.append(record)
    return records, all_warnings
