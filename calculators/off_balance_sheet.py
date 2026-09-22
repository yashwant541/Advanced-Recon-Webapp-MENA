"""Off-balance-sheet calculator.

Purpose
-------
Reconcile off-balance-sheet exposure (guarantees, letters of credit, FX
forwards, contingent/memorandum accounts -- spec section 10.J) as its own
total. Unlike every other calculator, this one does NOT apply the
primary-BS inclusion filter to itself (an OFF_BALANCE_SHEET account would
otherwise be excluded from every total, including its own); it is instead
the reason that filter excludes these accounts from every *other*
calculator's primary BS/P&L totals.

Formula: ``OBS-Gtee + OBS-Contra``, excluded from primary BS totals.

Public contents: ``OffBalanceSheetCalculator``.
Dependencies: ``calculators.base``.
"""

from __future__ import annotations

from iraq_recon.calculators.base import BucketCalculator

DEFAULT_LINE_CODE = "OFF_BALANCE_SHEET"
DEFAULT_BUCKET = "OFF_BALANCE_SHEET"
ALLOWED_CATEGORIES = frozenset({"OBS-Gtee", "OBS-Contra"})


class OffBalanceSheetCalculator(BucketCalculator):
    """Sums approved OBS accounts as their own total, excluded elsewhere."""

    def __init__(self, line_code: str = DEFAULT_LINE_CODE, iraq_reporting_bucket: str = DEFAULT_BUCKET) -> None:
        super().__init__(
            line_code=line_code,
            iraq_reporting_bucket=iraq_reporting_bucket,
            allowed_ayra_categories=ALLOWED_CATEGORIES,
            apply_primary_inclusion_filter=False,
            accounting_explanation=(
                "Off Balance Sheet = guarantees (OBS-Gtee) + contingent/"
                "contra accounts (OBS-Contra). This total is reported "
                "separately and is excluded from every primary balance-sheet "
                "calculator's totals."
            ),
        )
