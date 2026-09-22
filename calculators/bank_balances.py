"""Bank and group balances calculator: asset and liability sides.

Purpose
-------
Reconcile debit balances with banks (asset side) and bank/group liabilities
(liability side) as two independent totals (spec section 10.B). The two
sides are never netted against each other here or anywhere upstream --
each is a separate :class:`BucketCalculator` instance targeting a
different reporting bucket, so there is no code path that could combine
them without an explicit approved presentation rule doing so deliberately.

Formulas (from approved mappings):
    Asset side: ``A-IGA + A-IBA`` -> Debit Balances with Banks.
    Liability side: ``L-IGL-C + L-IGL-F + L-IBL + L-MM-F`` -> Bank and
    Group Liabilities (current and term reported as separate lines).

Public contents
----------------
``BankDebitBalancesCalculator`` -- asset-side total.
``BankCurrentLiabilitiesCalculator`` -- liability-side current total.
``BankTermLiabilitiesCalculator`` -- liability-side term total.

Dependencies: ``calculators.base``.
"""

from __future__ import annotations

from iraq_recon.calculators.base import BucketCalculator

ASSET_LINE_CODE = "DEBIT_BALANCES_WITH_BANKS"
ASSET_BUCKET = "DEBIT_BALANCES_WITH_BANKS"
ASSET_CATEGORIES = frozenset({"A-IGA", "A-IBA"})

CURRENT_LIABILITY_LINE_CODE = "BANK_GROUP_CURRENT_LIABILITIES"
CURRENT_LIABILITY_BUCKET = "BANK_GROUP_CURRENT_LIABILITIES"
CURRENT_LIABILITY_CATEGORIES = frozenset({"L-IGL-C", "L-IBL"})

TERM_LIABILITY_LINE_CODE = "BANK_GROUP_TERM_LIABILITIES"
TERM_LIABILITY_BUCKET = "BANK_GROUP_TERM_LIABILITIES"
TERM_LIABILITY_CATEGORIES = frozenset({"L-IGL-F", "L-MM-F"})


class BankDebitBalancesCalculator(BucketCalculator):
    """Sums approved intergroup/interbank debit (asset) balances."""

    def __init__(self, line_code: str = ASSET_LINE_CODE, iraq_reporting_bucket: str = ASSET_BUCKET) -> None:
        super().__init__(
            line_code=line_code,
            iraq_reporting_bucket=iraq_reporting_bucket,
            allowed_ayra_categories=ASSET_CATEGORIES,
            accounting_explanation=(
                "Debit Balances with Banks = approved asset-side intergroup "
                "(A-IGA) + interbank (A-IBA) balances. Never offset against "
                "bank credit balances."
            ),
        )


class BankCurrentLiabilitiesCalculator(BucketCalculator):
    """Sums approved current intergroup/interbank liability balances."""

    def __init__(
        self,
        line_code: str = CURRENT_LIABILITY_LINE_CODE,
        iraq_reporting_bucket: str = CURRENT_LIABILITY_BUCKET,
    ) -> None:
        super().__init__(
            line_code=line_code,
            iraq_reporting_bucket=iraq_reporting_bucket,
            allowed_ayra_categories=CURRENT_LIABILITY_CATEGORIES,
            accounting_explanation=(
                "Bank/Group Current Liabilities = approved current intergroup "
                "(L-IGL-C) + interbank (L-IBL) liabilities. Never offset "
                "against bank debit balances."
            ),
        )


class BankTermLiabilitiesCalculator(BucketCalculator):
    """Sums approved term intergroup/money-market liability balances."""

    def __init__(
        self,
        line_code: str = TERM_LIABILITY_LINE_CODE,
        iraq_reporting_bucket: str = TERM_LIABILITY_BUCKET,
    ) -> None:
        super().__init__(
            line_code=line_code,
            iraq_reporting_bucket=iraq_reporting_bucket,
            allowed_ayra_categories=TERM_LIABILITY_CATEGORIES,
            accounting_explanation=(
                "Bank/Group Term Liabilities = approved term intergroup "
                "(L-IGL-F) + money-market (L-MM-F) liabilities. Never offset "
                "against bank debit balances."
            ),
        )
