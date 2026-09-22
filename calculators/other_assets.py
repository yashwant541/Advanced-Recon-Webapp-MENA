"""Other assets calculator.

Purpose
-------
Reconcile "Other Assets" (spec section 10.E and 25) as the sum of approved
A-OA accounts only. This calculator has no residual/plug behavior: an
account that fails to match any other calculator's bucket is surfaced by
``mapping.mapping_coverage`` as unmapped, never swept in here.

Formula: sum of approved A-OA accounts.

Public contents: ``OtherAssetsCalculator``.
Dependencies: ``calculators.base``.
"""

from __future__ import annotations

from iraq_recon.calculators.base import BucketCalculator

DEFAULT_LINE_CODE = "OTHER_ASSETS"
DEFAULT_BUCKET = "OTHER_ASSETS"
ALLOWED_CATEGORIES = frozenset({"A-OA"})


class OtherAssetsCalculator(BucketCalculator):
    """Sums approved A-OA accounts only -- never a residual plug."""

    def __init__(self, line_code: str = DEFAULT_LINE_CODE, iraq_reporting_bucket: str = DEFAULT_BUCKET) -> None:
        super().__init__(
            line_code=line_code,
            iraq_reporting_bucket=iraq_reporting_bucket,
            allowed_ayra_categories=ALLOWED_CATEGORIES,
            accounting_explanation=(
                "Other Assets = sum of approved A-OA accounts only. This is "
                "never used as a residual plug to absorb unexplained variance; "
                "accounts with no approved mapping remain unmapped and are "
                "reported separately."
            ),
        )
