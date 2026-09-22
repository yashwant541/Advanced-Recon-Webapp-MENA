"""Spot / FX-position calculator.

Purpose
-------
Reconcile the SPOT position (spec section 10.I) as its own separate total.
SPOT accounts are never absorbed into Other Assets or Other Liabilities
here -- that only happens if an approved final presentation rule explicitly
maps a SPOT account's ``iraq_reporting_bucket`` elsewhere, which is a
mapping-table decision, not something this calculator does implicitly.

Formula: sum of approved SPOT accounts.

Public contents: ``SpotPositionCalculator``.
Dependencies: ``calculators.base``.
"""

from __future__ import annotations

from iraq_recon.calculators.base import BucketCalculator

DEFAULT_LINE_CODE = "SPOT_POSITION"
DEFAULT_BUCKET = "SPOT_POSITION"
ALLOWED_CATEGORIES = frozenset({"SPOT"})


class SpotPositionCalculator(BucketCalculator):
    """Sums approved SPOT accounts as an independent total."""

    def __init__(self, line_code: str = DEFAULT_LINE_CODE, iraq_reporting_bucket: str = DEFAULT_BUCKET) -> None:
        super().__init__(
            line_code=line_code,
            iraq_reporting_bucket=iraq_reporting_bucket,
            allowed_ayra_categories=ALLOWED_CATEGORIES,
            accounting_explanation=(
                "Spot Position = sum of approved SPOT accounts, processed as "
                "its own total rather than absorbed into Other Assets or "
                "Other Liabilities."
            ),
        )
