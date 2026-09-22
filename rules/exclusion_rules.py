"""Inclusion/exclusion decisions for primary balance-sheet totals.

Purpose
-------
Decide whether a mapped account contributes to primary balance-sheet/P&L
totals, based on its ``inclusion_status`` and off-balance-sheet
classification -- never based on which physical sheet it came from (spec
success criterion #6: "OFF BS accounts do not enter primary BS totals").

Public contents
----------------
``should_include_in_primary_totals(mapping_record, context=None)``.

Dependencies: ``iraq_recon.constants``, ``iraq_recon.models.mapping``.
"""

from __future__ import annotations

from typing import Any

from iraq_recon.constants import InclusionStatus, StatementType
from iraq_recon.models.mapping import MappingRecord


def should_include_in_primary_totals(
    mapping_record: MappingRecord,
    context: dict[str, Any] | None = None,
) -> bool:
    """Decide whether an account contributes to primary BS/P&L totals.

    Args:
        mapping_record: The account's approved mapping.
        context: Optional run-level context used to resolve a
            ``CONDITIONAL`` inclusion status. A ``CONDITIONAL`` mapping is
            included only if ``context["eligible_accounts"]`` (a set of
            local account numbers) contains this account; with no context,
            a ``CONDITIONAL`` mapping is conservatively excluded.

    Returns:
        ``True`` if the account should be summed into primary totals.
    """
    if mapping_record.statement_type == StatementType.OFF_BALANCE_SHEET:
        return False

    if mapping_record.inclusion_status == InclusionStatus.EXCLUDE:
        return False

    if mapping_record.inclusion_status == InclusionStatus.CONDITIONAL:
        eligible_accounts = (context or {}).get("eligible_accounts")
        if not eligible_accounts:
            return False
        return mapping_record.local_account in eligible_accounts

    return True
