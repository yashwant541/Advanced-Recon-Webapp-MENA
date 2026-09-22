"""Generic many-to-one account clubbing for arbitrary grouping dimensions.

Purpose
-------
Group already-calculated :class:`CalculationContribution` records by any
dimension recorded in their ``source_lineage`` (financial statement line,
Ayra category, Iraq reporting bucket, schedule, currency, residency,
maturity) or by ``formula_component`` (used as a proxy for
product/economic-role groupings), always retaining the contributing
accounts (spec section 13: "Every clubbing result must include
account-level traceability."). This is a read-only view over calculator
output -- it never recomputes amounts.

Public contents
----------------
``ClubbingGroup`` -- one grouped total with its contributing accounts.
``club_contributions(contributions, key_resolver)`` -- generic grouping.
``lineage_key(field_name, default="UNSPECIFIED")`` -- resolver factory for
grouping by a ``source_lineage`` field.
``by_formula_component`` -- resolver for grouping by formula component.

Dependencies: ``iraq_recon.models.calculation``.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Callable

from iraq_recon.models.calculation import CalculationContribution


@dataclass(frozen=True)
class ClubbingGroup:
    """One grouped total produced by :func:`club_contributions`.

    Attributes:
        group_key: The grouping label (e.g. a currency code, a schedule
            code, an Ayra category).
        total: Sum of ``presented_amount`` across the group's contributions.
        accounts: Contributing account numbers, in contribution order.
        contributions: The full contributions in this group, for lineage.
    """

    group_key: str
    total: Decimal
    accounts: tuple[str, ...]
    contributions: tuple[CalculationContribution, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "group_key": self.group_key,
            "total": str(self.total),
            "accounts": list(self.accounts),
            "contributions": [c.to_dict() for c in self.contributions],
        }


def lineage_key(field_name: str, default: str = "UNSPECIFIED") -> Callable[[CalculationContribution], str]:
    """Build a key resolver that reads ``field_name`` from a contribution's lineage.

    Args:
        field_name: Key to read from ``contribution.source_lineage``.
        default: Label used when the field is missing or empty.

    Returns:
        A callable suitable for :func:`club_contributions`.
    """

    def _resolver(contribution: CalculationContribution) -> str:
        value = contribution.source_lineage.get(field_name)
        return str(value) if value not in (None, "") else default

    return _resolver


def by_formula_component(contribution: CalculationContribution) -> str:
    """Group by a contribution's ``formula_component`` label."""
    return contribution.formula_component


def club_contributions(
    contributions: list[CalculationContribution],
    key_resolver: Callable[[CalculationContribution], str],
) -> list[ClubbingGroup]:
    """Group contributions by an arbitrary caller-supplied dimension.

    Args:
        contributions: Contributions from one or more
            :class:`iraq_recon.models.calculation.CalculationResult`.
        key_resolver: Function mapping a contribution to its group label
            (see :func:`lineage_key` and :data:`by_formula_component`).

    Returns:
        A list of :class:`ClubbingGroup`, in first-seen order.
    """
    order: list[str] = []
    totals: dict[str, Decimal] = {}
    accounts_by_key: dict[str, list[str]] = {}
    contributions_by_key: dict[str, list[CalculationContribution]] = {}

    for contribution in contributions:
        key = key_resolver(contribution)
        if key not in totals:
            order.append(key)
            totals[key] = Decimal("0")
            accounts_by_key[key] = []
            contributions_by_key[key] = []
        totals[key] += contribution.presented_amount
        accounts_by_key[key].append(contribution.account)
        contributions_by_key[key].append(contribution)

    return [
        ClubbingGroup(
            group_key=key,
            total=totals[key],
            accounts=tuple(accounts_by_key[key]),
            contributions=tuple(contributions_by_key[key]),
        )
        for key in order
    ]
