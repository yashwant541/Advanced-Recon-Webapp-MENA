"""Level-3 mapping: Iraq reporting bucket registry and roll-up description.

Purpose
-------
Hold the human-readable meaning of each Iraq reporting bucket (spec section
8, Level 3) and derive the formula description (which Ayra categories roll
up into it) directly from the loaded mapping records, rather than
hardcoding formulas per country -- so a new country's buckets need only new
mapping/seed data, not new code (spec success criterion #16).

Public contents
----------------
``IRAQ_BUCKET_DESCRIPTIONS`` -- bucket -> human-readable meaning.
``describe_iraq_reporting_bucket(bucket)`` -- look up a description.
``accounts_in_bucket(records, bucket)`` -- filter mapping records.
``group_by_reporting_bucket(records)`` -- partition records by bucket.
``derive_bucket_formula(records, bucket)`` -- e.g. ``"A-CBI + A-CRR"``.

Dependencies: ``iraq_recon.constants.IRAQ_REPORTING_BUCKETS``.
"""

from __future__ import annotations

from iraq_recon.constants import IRAQ_REPORTING_BUCKETS
from iraq_recon.models.mapping import MappingRecord

IRAQ_BUCKET_DESCRIPTIONS: dict[str, str] = {
    "BALANCES_WITH_CENTRAL_BANK": "Central Bank current/free balance plus statutory reserve.",
    "DEBIT_BALANCES_WITH_BANKS": "Debit balances with group and correspondent banks.",
    "INVESTMENTS_IN_SECURITIES": "Treasury bills and other eligible investment carrying values.",
    "FIXED_ASSETS": "Net fixed assets: cost, WIP, and approved clearing less depreciation and impairment.",
    "OTHER_ASSETS": "Approved other-asset accounts only, never a residual plug.",
    "HEAD_OFFICE_AND_BRANCHES": "Reciprocal Head Office and Branches balances, reported separately.",
    "BANK_GROUP_CURRENT_LIABILITIES": "Current liabilities to group/correspondent banks.",
    "BANK_GROUP_TERM_LIABILITIES": "Term liabilities to group/correspondent banks.",
    "CUSTOMER_DEPOSITS": "Customer current, savings, term, and other deposit products.",
    "CAPITAL_AND_RESERVES": "Share capital, statutory reserves, and retained earnings.",
    "PROVISIONS": "Tax, employee, ECL, impairment, and other provisions.",
    "SPOT_POSITION": "Spot and FX-position accounts, reported separately.",
    "OFF_BALANCE_SHEET": "Guarantees, letters of credit, and other contingent/memorandum accounts.",
}


def describe_iraq_reporting_bucket(bucket: str) -> str:
    """Return the human-readable meaning of an Iraq reporting bucket."""
    return IRAQ_BUCKET_DESCRIPTIONS.get(bucket, f"Unregistered Iraq reporting bucket '{bucket}'.")


def is_known_reporting_bucket(bucket: str) -> bool:
    """Return whether ``bucket`` is one of the recognized reporting buckets."""
    return bucket in IRAQ_REPORTING_BUCKETS


def accounts_in_bucket(records: list[MappingRecord], bucket: str) -> list[MappingRecord]:
    """Return the subset of ``records`` tagged with ``bucket``."""
    return [record for record in records if record.iraq_reporting_bucket == bucket]


def group_by_reporting_bucket(records: list[MappingRecord]) -> dict[str, list[MappingRecord]]:
    """Partition mapping records by their Iraq reporting bucket."""
    grouped: dict[str, list[MappingRecord]] = {}
    for record in records:
        grouped.setdefault(record.iraq_reporting_bucket, []).append(record)
    return grouped


def derive_bucket_formula(records: list[MappingRecord], bucket: str) -> str:
    """Build a human-readable roll-up formula string for a reporting bucket.

    Args:
        records: All loaded mapping records.
        bucket: The Iraq reporting bucket to describe.

    Returns:
        e.g. ``"A-CBI + A-CRR"`` for accounts with presentation sign ``+1``,
        or ``"A-FA - A-FA-CONTRA"`` when a category is uniformly deducted.
        Categories are ordered by first appearance for determinism.
    """
    bucket_records = accounts_in_bucket(records, bucket)
    if not bucket_records:
        return ""

    seen_categories: list[str] = []
    sign_by_category: dict[str, int] = {}
    for record in bucket_records:
        category = record.ayra_category
        if category not in sign_by_category:
            seen_categories.append(category)
            sign_by_category[category] = record.presentation_sign

    terms: list[str] = []
    for index, category in enumerate(seen_categories):
        sign = sign_by_category[category]
        if index == 0:
            terms.append(category if sign == 1 else f"-{category}")
        else:
            terms.append(f"+ {category}" if sign == 1 else f"- {category}")
    return " ".join(terms)
