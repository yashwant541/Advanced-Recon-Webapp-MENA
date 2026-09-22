"""Central registry of human-readable formula descriptions per reporting line.

Purpose
-------
Give every calculator and export sheet the same formula description for a
given Iraq reporting bucket, preferring a description derived from the
*actual* loaded mapping data (so it stays accurate as mappings change) and
falling back to the static seed formulas from spec section 25 only when no
mapping data is available yet (e.g. for documentation/preview purposes).

Public contents
----------------
``STATIC_SEED_FORMULAS`` -- bucket -> spec-documented formula description.
``get_formula_description(bucket, records=None)`` -- resolve a description.

Dependencies: ``iraq_recon.mapping.reporting_mapper``.
"""

from __future__ import annotations

from iraq_recon.mapping.reporting_mapper import derive_bucket_formula
from iraq_recon.models.mapping import MappingRecord

STATIC_SEED_FORMULAS: dict[str, str] = {
    "BALANCES_WITH_CENTRAL_BANK": "A-CBI + A-CRR",
    "DEBIT_BALANCES_WITH_BANKS": "approved asset-side A-IGA + A-IBA",
    "INVESTMENTS_IN_SECURITIES": "approved A-TB carrying-value components",
    "FIXED_ASSETS": "cost + WIP +/- approved clearing - accumulated depreciation - impairment",
    "OTHER_ASSETS": "approved A-OA accounts only",
    "HEAD_OFFICE_AND_BRANCHES": "approved Head Office and Branch reciprocal balances",
    "BANK_GROUP_CURRENT_LIABILITIES": "L-IGL-C + L-IBL (current)",
    "BANK_GROUP_TERM_LIABILITIES": "L-IGL-F + L-MM-F (term)",
    "CUSTOMER_DEPOSITS": "L-CASA + term + other approved customer deposit categories",
    "CAPITAL_AND_RESERVES": "share capital + statutory reserves + retained earnings",
    "PROVISIONS": "sum of approved provision categories, retained separately",
    "SPOT_POSITION": "approved SPOT accounts, processed separately",
    "OFF_BALANCE_SHEET": "OBS-Gtee + OBS-Contra, excluded from primary BS totals",
}


def get_formula_description(bucket: str, records: list[MappingRecord] | None = None) -> str:
    """Resolve the formula description for a reporting bucket.

    Args:
        bucket: The Iraq reporting bucket code.
        records: If supplied, the description is derived from these actual
            mapping records (see
            ``iraq_recon.mapping.reporting_mapper.derive_bucket_formula``);
            this always takes precedence since it reflects the mappings a
            reviewer approved, not a generic seed description.

    Returns:
        The formula description, falling back to
        :data:`STATIC_SEED_FORMULAS`, or an empty string if neither source
        has anything for ``bucket``.
    """
    if records is not None:
        derived = derive_bucket_formula(records, bucket)
        if derived:
            return derived
    return STATIC_SEED_FORMULAS.get(bucket, "")
