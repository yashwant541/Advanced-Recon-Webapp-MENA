"""Capital and reserves calculator.

Purpose
-------
Reconcile "Capital and Reserves" (spec section 10.F) by calculating share
capital, statutory reserves, and retained earnings as separate categories
(exposed via ``formula_component``) before they are summed into the
financial-statement subtotal -- never combined blindly.

Formula: share capital (EQ-SC) + statutory reserves (EQ-SR) + retained
earnings (EQ-RE).

Public contents: ``CapitalReservesCalculator``.
Dependencies: ``calculators.base``.
"""

from __future__ import annotations

from iraq_recon.calculators.base import BucketCalculator

DEFAULT_LINE_CODE = "CAPITAL_AND_RESERVES"
DEFAULT_BUCKET = "CAPITAL_AND_RESERVES"
ALLOWED_CATEGORIES = frozenset({"EQ-SC", "EQ-SR", "EQ-RE"})


class CapitalReservesCalculator(BucketCalculator):
    """Sums approved equity categories, keeping each category distinct."""

    def __init__(self, line_code: str = DEFAULT_LINE_CODE, iraq_reporting_bucket: str = DEFAULT_BUCKET) -> None:
        super().__init__(
            line_code=line_code,
            iraq_reporting_bucket=iraq_reporting_bucket,
            allowed_ayra_categories=ALLOWED_CATEGORIES,
            accounting_explanation=(
                "Capital and Reserves = share capital (EQ-SC) + statutory "
                "reserves (EQ-SR) + retained earnings (EQ-RE), each category "
                "calculated and exposed separately before summing."
            ),
        )
