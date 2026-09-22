"""Presentation-sign application.

Purpose
-------
Apply a mapped account's approved presentation sign to a converted balance.
The sign always comes from the account's :class:`MappingRecord` -- never
from which sheet or section the account happened to be listed under (spec
section 9: "Do not reverse an account merely because it appears on a
Liability sheet.").

Public contents
----------------
``apply_presentation_sign(converted_amount, mapping_record)`` -- return the
signed, presented amount.

Dependencies: ``decimal``, ``iraq_recon.models.mapping``.
"""

from __future__ import annotations

from decimal import Decimal

from iraq_recon.models.mapping import MappingRecord


def apply_presentation_sign(converted_amount: Decimal, mapping_record: MappingRecord) -> Decimal:
    """Return ``converted_amount`` signed according to the account's mapping.

    Args:
        converted_amount: The account's balance after unit conversion,
            unsigned (i.e. exactly as carried in the trial balance).
        mapping_record: The account's approved mapping, whose
            ``presentation_sign`` (``+1`` or ``-1``) is authoritative.

    Returns:
        ``converted_amount * mapping_record.presentation_sign``.
    """
    return converted_amount * mapping_record.presentation_sign
