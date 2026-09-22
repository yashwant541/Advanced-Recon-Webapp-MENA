"""Level-2 mapping: Ayra semantic category registry and lookups.

Purpose
-------
Hold the human-readable meaning of each Ayra semantic category (spec
section 8, Level 2) and provide the lookup calculators use to select which
mapped accounts belong to them. Contains no per-account logic -- accounts
are already tagged with an ``ayra_category`` on their :class:`MappingRecord`
by the mapping loader; this module only interprets that tag.

Public contents
----------------
``AYRA_CATEGORY_DESCRIPTIONS`` -- category -> human-readable meaning.
``describe_ayra_category(category)`` -- look up a description.
``accounts_in_category(records, category)`` -- filter mapping records.
``group_by_ayra_category(records)`` -- partition records by category.

Dependencies: ``iraq_recon.constants.AYRA_CATEGORIES``.
"""

from __future__ import annotations

from iraq_recon.constants import AYRA_CATEGORIES
from iraq_recon.models.mapping import MappingRecord

AYRA_CATEGORY_DESCRIPTIONS: dict[str, str] = {
    "A-CBI": "Central Bank asset (current/free balance and eligible term deposits).",
    "A-CRR": "Statutory regulatory reserve held with the Central Bank.",
    "A-IGA": "Intergroup asset (debit balance with a related/group entity).",
    "A-IBA": "Interbank asset (debit balance with an unrelated correspondent bank).",
    "A-TB": "Treasury bills and other eligible investment components.",
    "A-FA": "Fixed asset cost, work-in-progress, and approved clearing accounts.",
    "A-FA-CONTRA": "Contra-asset against fixed assets (accumulated depreciation, impairment).",
    "A-OA": "Approved other asset.",
    "A-HOB": "Head Office and Branches reciprocal asset balance.",
    "L-CASA": "Customer current and savings account deposit liability.",
    "L-IGL-C": "Intergroup current liability.",
    "L-IGL-F": "Intergroup fixed/term liability.",
    "L-IBL": "Interbank liability.",
    "L-MM-F": "Money-market term liability.",
    "L-PR": "Provision liability.",
    "SPOT": "Spot and FX-position account.",
    "OBS-Gtee": "Off-balance-sheet guarantee or letter of credit.",
    "OBS-Contra": "Off-balance-sheet contra/contingent account.",
}


def describe_ayra_category(category: str) -> str:
    """Return the human-readable meaning of an Ayra semantic category.

    Args:
        category: An Ayra category code, e.g. ``"A-CBI"``.

    Returns:
        The description, or a generic placeholder if the category is not in
        the registry (never raises, since new categories may legitimately
        be introduced via mapping/configuration before this registry is
        updated).
    """
    return AYRA_CATEGORY_DESCRIPTIONS.get(category, f"Unregistered Ayra category '{category}'.")


def is_known_ayra_category(category: str) -> bool:
    """Return whether ``category`` is one of the recognized Ayra categories."""
    return category in AYRA_CATEGORIES


def accounts_in_category(records: list[MappingRecord], category: str) -> list[MappingRecord]:
    """Return the subset of ``records`` tagged with ``category``."""
    return [record for record in records if record.ayra_category == category]


def group_by_ayra_category(records: list[MappingRecord]) -> dict[str, list[MappingRecord]]:
    """Partition mapping records by their Ayra semantic category."""
    grouped: dict[str, list[MappingRecord]] = {}
    for record in records:
        grouped.setdefault(record.ayra_category, []).append(record)
    return grouped
