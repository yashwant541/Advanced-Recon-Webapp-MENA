"""Unit conversion for source amounts.

Purpose
-------
Apply a unit conversion exactly once between a source amount's declared unit
and the reporting unit, using ``Decimal`` throughout (spec success criterion
#4: "Units are converted exactly once"). Callers are responsible for calling
this at a single, well-defined point in the pipeline (normalization of the
trial balance) -- this module only supplies the pure conversion function and
a small named-unit registry; it does not track whether conversion has
already happened.

Public contents
----------------
``KNOWN_UNIT_FACTORS`` -- named unit -> multiplier-to-``"IQD"`` registry.
``resolve_unit_factor(unit)`` -- look up a named unit's factor.
``convert_amount(amount, conversion_factor)`` -- multiply by an explicit factor.
``convert_between_units(amount, source_unit, target_unit)`` -- convert via
the named-unit registry.

Dependencies: ``decimal`` (standard library only).
"""

from __future__ import annotations

from decimal import Decimal

from iraq_recon.exceptions import ConfigurationError

#: Multiplier to convert FROM the named unit TO plain ``"IQD"``.
KNOWN_UNIT_FACTORS: dict[str, Decimal] = {
    "IQD": Decimal("1"),
    "IQD_THOUSAND": Decimal("1000"),
    "IQD_MILLION": Decimal("1000000"),
}


def resolve_unit_factor(unit: str) -> Decimal:
    """Return the multiplier to convert an amount in ``unit`` to plain ``"IQD"``.

    Args:
        unit: A key of :data:`KNOWN_UNIT_FACTORS`.

    Returns:
        The Decimal multiplier.

    Raises:
        ConfigurationError: if ``unit`` is not a recognized unit.
    """
    normalized_unit = unit.strip().upper()
    if normalized_unit not in KNOWN_UNIT_FACTORS:
        raise ConfigurationError(
            f"Unknown unit '{unit}'. Known units: {sorted(KNOWN_UNIT_FACTORS)}.",
            details={"unit": unit},
        )
    return KNOWN_UNIT_FACTORS[normalized_unit]


def convert_amount(amount: Decimal, conversion_factor: Decimal) -> Decimal:
    """Apply an explicit conversion factor to a Decimal amount.

    Args:
        amount: Amount in the source unit.
        conversion_factor: Multiplier to reach the target unit.

    Returns:
        ``amount * conversion_factor``, as a ``Decimal``.
    """
    return amount * conversion_factor


def convert_between_units(amount: Decimal, source_unit: str, target_unit: str) -> Decimal:
    """Convert an amount between two named units via the ``"IQD"`` base unit.

    Args:
        amount: Amount expressed in ``source_unit``.
        source_unit: Source unit name (a key of :data:`KNOWN_UNIT_FACTORS`).
        target_unit: Target unit name (a key of :data:`KNOWN_UNIT_FACTORS`).

    Returns:
        The equivalent amount in ``target_unit``.

    Raises:
        ConfigurationError: if either unit is unrecognized.
    """
    source_factor = resolve_unit_factor(source_unit)
    target_factor = resolve_unit_factor(target_unit)
    amount_in_base_unit = amount * source_factor
    return amount_in_base_unit / target_factor
