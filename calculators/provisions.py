"""Provisions calculator.

Purpose
-------
Reconcile "Provisions" (spec section 10.H) while distinguishing tax,
employee, bonus, holiday, gratuity, ECL, investment impairment, and other
provisions via each account's ``metadata["provision_type"]`` -- provisions
are never collapsed into one undifferentiated ordinary-liability figure.

Formula: sum of approved L-PR accounts, retained separately by provision type.

Public contents: ``ProvisionsCalculator``.
Dependencies: ``calculators.base``.
"""

from __future__ import annotations

from iraq_recon.calculators.base import BucketCalculator
from iraq_recon.models.mapping import MappingRecord

DEFAULT_LINE_CODE = "PROVISIONS"
DEFAULT_BUCKET = "PROVISIONS"
ALLOWED_CATEGORIES = frozenset({"L-PR"})


def _provision_type(mapping_record: MappingRecord) -> str:
    return str(mapping_record.metadata.get("provision_type", "other"))


class ProvisionsCalculator(BucketCalculator):
    """Sums approved provision accounts, retaining provision type."""

    def __init__(self, line_code: str = DEFAULT_LINE_CODE, iraq_reporting_bucket: str = DEFAULT_BUCKET) -> None:
        super().__init__(
            line_code=line_code,
            iraq_reporting_bucket=iraq_reporting_bucket,
            allowed_ayra_categories=ALLOWED_CATEGORIES,
            formula_component_resolver=_provision_type,
            accounting_explanation=(
                "Provisions = sum of approved tax/employee/bonus/holiday/"
                "gratuity/ECL/investment-impairment/other provision accounts, "
                "each type retained separately rather than treated as one "
                "ordinary liability."
            ),
        )
