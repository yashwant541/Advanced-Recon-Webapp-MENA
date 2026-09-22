"""Economic-role classification helpers and expected-sign cross-checks.

Purpose
-------
Give calculators a single place to ask "is this a contra account?" / "is
this off-balance-sheet?" instead of re-deriving it from raw strings, and
provide a soft cross-check between an account's economic role and its
mapped presentation sign (spec section 9's example sign table), surfaced as
a warning -- never auto-corrected, since the mapping's sign is authoritative.

Public contents
----------------
``is_contra_role(role)``, ``is_off_balance_sheet_role(role)``,
``is_depreciation_or_impairment_role(role)``, ``is_asset_role(role)``,
``is_liability_role(role)``, ``expected_sign_for_role(role)``,
``check_role_sign_consistency(mapping_record)``.

Dependencies: ``iraq_recon.constants.EconomicRole``, ``iraq_recon.models.mapping``.
"""

from __future__ import annotations

from iraq_recon.constants import EconomicRole
from iraq_recon.models.mapping import MappingRecord

_CONTRA_ROLES = (
    EconomicRole.CONTRA_ASSET,
    EconomicRole.CONTRA_LIABILITY,
    EconomicRole.ACCUMULATED_DEPRECIATION,
    EconomicRole.ASSET_IMPAIRMENT,
)

_OFF_BS_ROLES = (EconomicRole.OFF_BALANCE_SHEET_DEBIT, EconomicRole.OFF_BALANCE_SHEET_CREDIT)

_ASSET_ROLES = (
    EconomicRole.ASSET_COST,
    EconomicRole.ASSET_WIP,
    EconomicRole.ASSET_CLEARING,
    EconomicRole.ORDINARY_ASSET,
)

_LIABILITY_ROLES = (EconomicRole.ORDINARY_LIABILITY,)

#: Expected presentation sign per economic role, from spec section 9's
#: worked examples. ``None`` means "no single expected sign" (e.g.
#: ``ASSET_CLEARING`` may legitimately be +1 or -1 depending on mapping).
_EXPECTED_SIGN_BY_ROLE: dict[EconomicRole, int | None] = {
    EconomicRole.ASSET_COST: 1,
    EconomicRole.ASSET_WIP: 1,
    EconomicRole.ASSET_CLEARING: None,
    EconomicRole.ACCUMULATED_DEPRECIATION: -1,
    EconomicRole.ASSET_IMPAIRMENT: -1,
    EconomicRole.ORDINARY_ASSET: 1,
    EconomicRole.ORDINARY_LIABILITY: 1,
    EconomicRole.CONTRA_ASSET: -1,
    EconomicRole.CONTRA_LIABILITY: -1,
    EconomicRole.EQUITY: 1,
    EconomicRole.INCOME: 1,
    EconomicRole.EXPENSE: 1,
    EconomicRole.OFF_BALANCE_SHEET_DEBIT: None,
    EconomicRole.OFF_BALANCE_SHEET_CREDIT: None,
    EconomicRole.INFORMATIONAL_ONLY: None,
}


def is_contra_role(role: EconomicRole) -> bool:
    return role in _CONTRA_ROLES


def is_off_balance_sheet_role(role: EconomicRole) -> bool:
    return role in _OFF_BS_ROLES


def is_depreciation_or_impairment_role(role: EconomicRole) -> bool:
    return role in (EconomicRole.ACCUMULATED_DEPRECIATION, EconomicRole.ASSET_IMPAIRMENT)


def is_asset_role(role: EconomicRole) -> bool:
    return role in _ASSET_ROLES


def is_liability_role(role: EconomicRole) -> bool:
    return role in _LIABILITY_ROLES


def expected_sign_for_role(role: EconomicRole) -> int | None:
    """Return the conventionally expected presentation sign for ``role``,
    or ``None`` if the role has no single expected sign."""
    return _EXPECTED_SIGN_BY_ROLE.get(role)


def check_role_sign_consistency(mapping_record: MappingRecord) -> str | None:
    """Return a warning if the mapping's sign contradicts its role's convention.

    This is advisory only: the mapping's ``presentation_sign`` remains
    authoritative and is never overridden by this check.

    Args:
        mapping_record: The account's approved mapping.

    Returns:
        A human-readable warning string, or ``None`` if consistent (or the
        role has no fixed expectation).
    """
    expected = expected_sign_for_role(mapping_record.economic_role)
    if expected is None:
        return None
    if mapping_record.presentation_sign != expected:
        return (
            f"Account '{mapping_record.local_account}' has economic role "
            f"'{mapping_record.economic_role}' (conventionally sign {expected:+d}) "
            f"but is mapped with presentation sign {mapping_record.presentation_sign:+d}."
        )
    return None
