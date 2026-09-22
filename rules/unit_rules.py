"""Combine file-level and account-level unit conversion into one factor.

Purpose
-------
Guarantee that a unit conversion is applied exactly once per account (spec
success criterion #4) by making the *single* effective factor an explicit,
pure computation: the file-level conversion factor (from
:class:`iraq_recon.models.configuration.UnitConfiguration`) multiplied by
the account-level ``unit_factor`` on its :class:`MappingRecord`, which the
model docstring defines as independent of the file-level conversion.

Public contents
----------------
``compute_effective_unit_factor(file_conversion_factor, account_unit_factor)``
``convert_balance(original_balance, effective_unit_factor)``

Dependencies: ``decimal`` (standard library only).
"""

from __future__ import annotations

from decimal import Decimal


def compute_effective_unit_factor(
    file_conversion_factor: Decimal,
    account_unit_factor: Decimal,
) -> Decimal:
    """Combine the file-level and account-level conversion factors.

    Args:
        file_conversion_factor: From
            ``ReconciliationConfiguration.units.conversion_factor``.
        account_unit_factor: From ``MappingRecord.unit_factor``.

    Returns:
        The single factor to multiply an original balance by, exactly once.
    """
    return file_conversion_factor * account_unit_factor


def convert_balance(original_balance: Decimal, effective_unit_factor: Decimal) -> Decimal:
    """Apply the effective unit factor to an original balance.

    Args:
        original_balance: Balance in the source unit.
        effective_unit_factor: Result of :func:`compute_effective_unit_factor`.

    Returns:
        The converted balance.
    """
    return original_balance * effective_unit_factor
