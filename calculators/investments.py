"""Investments in securities calculator.

Purpose
-------
Reconcile "Investments in Securities" (spec section 10.C) as the sum of
approved carrying-value components (principal, premium, discount, approved
MTM, impairment, approved carrying-value adjustments), each identified by
its account's ``metadata["investment_component"]`` rather than a hardcoded
formula, so an equity reserve is only ever swept into the carrying amount
when an approved mapping explicitly says so via that same metadata field.

Formula: sum of approved ``A-TB`` carrying-value components.

Public contents: ``InvestmentsCalculator``.
Dependencies: ``calculators.base``.
"""

from __future__ import annotations

from iraq_recon.calculators.base import BucketCalculator
from iraq_recon.models.mapping import MappingRecord

DEFAULT_LINE_CODE = "INVESTMENTS_IN_SECURITIES"
DEFAULT_BUCKET = "INVESTMENTS_IN_SECURITIES"
ALLOWED_CATEGORIES = frozenset({"A-TB"})


def _investment_component(mapping_record: MappingRecord) -> str:
    return str(mapping_record.metadata.get("investment_component", "carrying_value"))


class InvestmentsCalculator(BucketCalculator):
    """Sums approved A-TB carrying-value components."""

    def __init__(self, line_code: str = DEFAULT_LINE_CODE, iraq_reporting_bucket: str = DEFAULT_BUCKET) -> None:
        super().__init__(
            line_code=line_code,
            iraq_reporting_bucket=iraq_reporting_bucket,
            allowed_ayra_categories=ALLOWED_CATEGORIES,
            formula_component_resolver=_investment_component,
            accounting_explanation=(
                "Investments in Securities = sum of approved A-TB carrying-value "
                "components (principal, premium, discount, approved MTM, "
                "impairment, approved carrying-value adjustments). An equity "
                "reserve is included only when an approved mapping's "
                "'investment_component' metadata says so explicitly."
            ),
        )
