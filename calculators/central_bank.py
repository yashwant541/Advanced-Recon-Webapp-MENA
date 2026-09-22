"""Central Bank balances calculator.

Purpose
-------
Reconcile "Balances with Central Bank" (spec section 10.A): current/free
balance, statutory reserve, and any other approved Central Bank component,
each mapped via its own approved account -- never a hardcoded account list.

Formula (from approved mappings): ``A-CBI + A-CRR (+ other approved
Central Bank components)``.

Public contents: ``CentralBankCalculator``.
Dependencies: ``calculators.base``.
"""

from __future__ import annotations

from iraq_recon.calculators.base import BucketCalculator

DEFAULT_LINE_CODE = "BALANCES_WITH_CENTRAL_BANK"
DEFAULT_BUCKET = "BALANCES_WITH_CENTRAL_BANK"
ALLOWED_CATEGORIES = frozenset({"A-CBI", "A-CRR"})


class CentralBankCalculator(BucketCalculator):
    """Sums approved Central Bank asset accounts (A-CBI, A-CRR)."""

    def __init__(self, line_code: str = DEFAULT_LINE_CODE, iraq_reporting_bucket: str = DEFAULT_BUCKET) -> None:
        super().__init__(
            line_code=line_code,
            iraq_reporting_bucket=iraq_reporting_bucket,
            allowed_ayra_categories=ALLOWED_CATEGORIES,
            accounting_explanation=(
                "Balances with Central Bank = current/free balance (A-CBI) + "
                "statutory reserve (A-CRR), plus any other approved Central "
                "Bank component, each contributing its own approved "
                "presentation sign. Ties to Schedule 3."
            ),
        )
