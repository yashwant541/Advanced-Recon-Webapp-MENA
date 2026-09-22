"""Customer deposits calculator.

Purpose
-------
Reconcile "Customer Deposits" (spec section 10.G) while retaining product
classification (current/savings/term/customer/bank/group/other) via each
account's ``metadata["deposit_product"]``, so the breakdown a reviewer sees
is never flattened into a single undifferentiated total.

Formula: sum of approved L-CASA and other approved customer-deposit
categories, retaining product classification.

Public contents: ``CustomerDepositsCalculator``.
Dependencies: ``calculators.base``.
"""

from __future__ import annotations

from iraq_recon.calculators.base import BucketCalculator
from iraq_recon.models.mapping import MappingRecord

DEFAULT_LINE_CODE = "CUSTOMER_DEPOSITS"
DEFAULT_BUCKET = "CUSTOMER_DEPOSITS"
ALLOWED_CATEGORIES = frozenset({"L-CASA"})


def _deposit_product(mapping_record: MappingRecord) -> str:
    return str(mapping_record.metadata.get("deposit_product", "other"))


class CustomerDepositsCalculator(BucketCalculator):
    """Sums approved customer-deposit accounts, retaining product classification."""

    def __init__(self, line_code: str = DEFAULT_LINE_CODE, iraq_reporting_bucket: str = DEFAULT_BUCKET) -> None:
        super().__init__(
            line_code=line_code,
            iraq_reporting_bucket=iraq_reporting_bucket,
            allowed_ayra_categories=ALLOWED_CATEGORIES,
            formula_component_resolver=_deposit_product,
            accounting_explanation=(
                "Customer Deposits = sum of approved current/savings/term/"
                "customer/bank/group/other deposit categories, each product "
                "classification retained via mapping metadata rather than "
                "collapsed into a single figure."
            ),
        )
