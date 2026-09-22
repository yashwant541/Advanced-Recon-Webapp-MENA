"""Natural-side / balance-sign consistency checks.

Purpose
-------
Detect when a trial-balance account's actual balance sign contradicts its
mapped natural side (e.g. a debit-natural account carrying a large credit
balance), which is the raw material for the
``DiagnosticCode.SIGN_MISMATCH`` finding. This module only detects and
reports; it never silently flips a sign.

Public contents
----------------
``detect_sign_mismatch(balance, natural_side)`` -- ``True`` if the balance's
sign contradicts the natural side.

Dependencies: ``decimal``, ``iraq_recon.constants.NaturalSide``.
"""

from __future__ import annotations

from decimal import Decimal

from iraq_recon.constants import NaturalSide


def detect_sign_mismatch(balance: Decimal, natural_side: NaturalSide) -> bool:
    """Return whether ``balance``'s sign contradicts ``natural_side``.

    Convention: a debit-natural balance is expected to be non-negative, and
    a credit-natural balance is expected to be non-positive (the standard
    trial-balance sign convention). A balance of exactly zero never
    mismatches, and an ``UNKNOWN`` natural side can never mismatch since
    there is nothing to compare against.

    Args:
        balance: The account's normalized balance.
        natural_side: The account's mapped natural side.

    Returns:
        ``True`` if the sign contradicts the natural side, else ``False``.
    """
    if balance == Decimal("0") or natural_side == NaturalSide.UNKNOWN:
        return False
    if natural_side == NaturalSide.DEBIT:
        return balance < Decimal("0")
    if natural_side == NaturalSide.CREDIT:
        return balance > Decimal("0")
    return False
