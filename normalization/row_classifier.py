"""Row-type classification for normalized source rows.

Purpose
-------
Decide whether a trial-balance row is a posting account, a parent/control
row, a subtotal/total/grand-total, a heading, a blank separator, a template
placeholder, or unclassifiable -- so that parent and control rows are never
summed together with their own detailed children (spec success criterion
#3), and non-posting rows never leak into account-level calculations.

Public contents
----------------
``classify_row(...)`` -- classify one row from its normalized fields.

Dependencies: ``iraq_recon.constants.RowType``, standard library.
"""

from __future__ import annotations

from decimal import Decimal

from iraq_recon.constants import RowType

_GRAND_TOTAL_MARKERS = ("GRAND TOTAL",)
_SUBTOTAL_MARKERS = ("SUB TOTAL", "SUBTOTAL")
_TOTAL_MARKERS = ("TOTAL",)
_TEMPLATE_MARKERS = ("TEMPLATE", "SAMPLE ACCOUNT", "XXXXXX", "TBD")


def classify_row(
    *,
    account: str | None,
    description_matching_form: str,
    amount_is_blank: bool,
    amount_value: Decimal | None,
    has_known_children: bool = False,
    is_independently_posting: bool = False,
) -> RowType:
    """Classify a single normalized row.

    Args:
        account: Normalized account number, or ``None`` if blank/unparsable.
        description_matching_form: Uppercase, punctuation-normalized
            description (see ``normalization.description_normalizer``).
        amount_is_blank: Whether the amount cell was empty (not zero).
        amount_value: Parsed amount, or ``None`` if blank/invalid.
        has_known_children: Whether this account number is a parent of other
            accounts present in the same trial balance (Level-1 hierarchy
            knowledge supplied by the caller).
        is_independently_posting: Whether this parent/control account is
            explicitly marked (via mapping metadata) as also carrying its
            own postings, independent of its children.

    Returns:
        The best-matching :class:`iraq_recon.constants.RowType`.
    """
    no_account = account is None or account == ""
    no_description = description_matching_form == ""

    if no_account and no_description and amount_is_blank:
        return RowType.BLANK

    if any(marker in description_matching_form for marker in _GRAND_TOTAL_MARKERS):
        return RowType.GRAND_TOTAL

    if any(marker in description_matching_form for marker in _SUBTOTAL_MARKERS):
        return RowType.SUBTOTAL

    if any(marker in description_matching_form for marker in _TOTAL_MARKERS):
        return RowType.TOTAL

    if any(marker in description_matching_form for marker in _TEMPLATE_MARKERS):
        return RowType.TEMPLATE

    if no_account and not no_description and amount_is_blank:
        return RowType.HEADER

    if has_known_children and not is_independently_posting:
        return RowType.PARENT

    if no_account:
        return RowType.UNKNOWN

    if amount_value is None:
        # Covers both a blank amount and unparsable amount text -- neither
        # can be posted, so the row is left for review rather than summed.
        return RowType.UNKNOWN

    return RowType.POSTING


def is_summable(row_type: RowType) -> bool:
    """Return whether a row of this type should be summed into totals.

    Only ``POSTING`` rows (and parent rows explicitly marked as
    independently posting, which callers pass in as ``POSTING`` already)
    contribute to account-level aggregation; everything else -- including
    ``PARENT`` -- is excluded to avoid double counting.
    """
    return row_type == RowType.POSTING
