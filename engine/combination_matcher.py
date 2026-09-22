"""Controlled combination matching: last-resort exception analysis.

Purpose
-------
Attempt to explain an unresolved financial-statement line or a non-zero
unmapped account by finding a small, coherent combination of candidate
accounts whose balances sum close to the target amount (spec section 14).
This is deliberately bounded and conservative: it never runs as a primary
mapping method, never mixes statement types or off-balance-sheet accounts,
excludes parent/control rows, and every match it returns is marked
provisional -- never auto-approved.

Public contents
----------------
``CombinationMatch`` -- one candidate combination and its variance.
``filter_eligible_candidates(records, statement_type, natural_side)`` --
apply the structural exclusions (no parents, no control totals, matching
statement type/natural side).
``find_combination_matches(target_amount, candidates, ...)`` -- search.

Dependencies: ``itertools``, ``iraq_recon.models.source``,
``iraq_recon.normalization.row_classifier``.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from itertools import combinations
from typing import Any

from iraq_recon.constants import NaturalSide, RowType, StatementType
from iraq_recon.models.source import TrialBalanceRecord
from iraq_recon.normalization.row_classifier import is_summable

#: Row types that can never participate in combination matching, regardless
#: of caller-supplied filters -- these are never real postings.
_EXCLUDED_ROW_TYPES = frozenset(
    {
        RowType.PARENT,
        RowType.SUBTOTAL,
        RowType.TOTAL,
        RowType.GRAND_TOTAL,
        RowType.HEADER,
        RowType.BLANK,
        RowType.TEMPLATE,
        RowType.UNKNOWN,
    }
)


@dataclass(frozen=True)
class CombinationMatch:
    """One candidate combination found by :func:`find_combination_matches`.

    Attributes:
        accounts: Contributing account numbers.
        total: Sum of the combination's balances.
        variance: ``total - target_amount``.
        is_provisional: Always ``True`` -- combination matches are never
            auto-approved (spec section 14: "Do not automatically approve
            them.").
    """

    accounts: tuple[str, ...]
    total: Decimal
    variance: Decimal
    is_provisional: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "accounts": list(self.accounts),
            "total": str(self.total),
            "variance": str(self.variance),
            "is_provisional": self.is_provisional,
        }


def filter_eligible_candidates(
    records: list[TrialBalanceRecord],
    *,
    statement_type: StatementType | None = None,
    natural_side: NaturalSide | None = None,
    exclude_accounts: set[str] | None = None,
) -> list[TrialBalanceRecord]:
    """Apply the structural exclusions required before combination matching.

    Args:
        records: Candidate trial-balance records.
        statement_type: If given, only records with this statement type are
            kept (never mixes BS and OFF BS, or P&L and BS).
        natural_side: If given, only records with a compatible natural side
            are kept.
        exclude_accounts: Accounts to exclude outright (e.g. already
            consumed by an approved mapping).

    Returns:
        The filtered, posting-only candidate list.
    """
    exclude_accounts = exclude_accounts or set()
    eligible: list[TrialBalanceRecord] = []
    for record in records:
        if record.row_type in _EXCLUDED_ROW_TYPES or not is_summable(record.row_type):
            continue
        if record.account_number in exclude_accounts:
            continue
        if statement_type is not None and record.statement_type != statement_type:
            continue
        if natural_side is not None and record.natural_side not in (natural_side, NaturalSide.UNKNOWN):
            continue
        eligible.append(record)
    return eligible


def find_combination_matches(
    target_amount: Decimal,
    candidates: list[TrialBalanceRecord],
    *,
    max_combination_size: int = 3,
    tolerance: Decimal = Decimal("0.01"),
    max_candidates: int = 15,
) -> list[CombinationMatch]:
    """Search for small combinations of candidates summing near ``target_amount``.

    Combinations are searched smallest-first (size 1, then 2, then 3, ...)
    and the search stops as soon as any match is found at the smallest
    size that produces one, preferring "the smallest coherent account set"
    per spec section 14. All returned matches are marked provisional.

    Args:
        target_amount: The unexplained amount to try to match.
        candidates: Pre-filtered eligible candidates (see
            :func:`filter_eligible_candidates`); this function does not
            re-apply structural exclusions.
        max_combination_size: Largest combination size to try.
        tolerance: Maximum absolute variance for a combination to count as
            a match.
        max_candidates: Safety cap on the candidate pool size; combination
            search is combinatorial, so a pool larger than this raises
            rather than silently running an expensive search.

    Returns:
        A list of :class:`CombinationMatch` at the smallest size that
        produced any match (empty if nothing matched within
        ``max_combination_size``).

    Raises:
        ValueError: if ``candidates`` exceeds ``max_candidates``.
    """
    if len(candidates) > max_candidates:
        raise ValueError(
            f"Candidate pool of {len(candidates)} exceeds max_candidates="
            f"{max_candidates}; narrow the candidate set before combination matching."
        )

    for size in range(1, min(max_combination_size, len(candidates)) + 1):
        matches: list[CombinationMatch] = []
        for combo in combinations(candidates, size):
            total = sum((record.normalized_balance for record in combo), Decimal("0"))
            variance = total - target_amount
            if abs(variance) <= tolerance:
                matches.append(
                    CombinationMatch(
                        accounts=tuple(record.account_number for record in combo),
                        total=total,
                        variance=variance,
                    )
                )
        if matches:
            return matches

    return []
