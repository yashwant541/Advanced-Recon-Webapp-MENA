"""Decimal-safe variance classification against configured tolerances.

Purpose
-------
Turn a raw variance into a :class:`ReconciliationStatus` using the
configured precision/rounding/materiality thresholds (spec section 16),
without ever replacing the raw variance value itself -- classification is a
label attached alongside the exact variance, never a substitute for it
(spec success criterion #10: "Raw variances are never overwritten.").

Public contents
----------------
``classify_variance_by_tolerance(variance, tolerances)`` -- magnitude-only
classification (``EXACT_MATCH``/``PRECISION_MATCH``/``ROUNDING_MATCH``/
``PARTIAL_MATCH``/``MATERIAL_BREAK``).
``calculate_variance_percentage(variance, reported_amount)`` -- Decimal-safe
percentage, or ``None`` when the reported amount is zero.

Dependencies: ``decimal``, ``iraq_recon.constants.ReconciliationStatus``,
``iraq_recon.models.configuration.ToleranceConfiguration``.
"""

from __future__ import annotations

from decimal import Decimal

from iraq_recon.constants import ReconciliationStatus
from iraq_recon.models.configuration import ToleranceConfiguration


def classify_variance_by_tolerance(
    variance: Decimal,
    tolerances: ToleranceConfiguration,
) -> ReconciliationStatus:
    """Classify a variance by magnitude alone against configured tolerances.

    This does not consider *why* a variance exists (mapping, unit, sign,
    schedule causes are layered on top by the variance/diagnostics engines);
    it only answers "how big is this variance relative to tolerance".

    Args:
        variance: ``calculated_amount - reported_amount``, exact.
        tolerances: Configured precision/rounding/materiality thresholds.

    Returns:
        One of ``EXACT_MATCH``, ``PRECISION_MATCH``, ``ROUNDING_MATCH``,
        ``PARTIAL_MATCH``, or ``MATERIAL_BREAK``.
    """
    absolute_variance = abs(variance)

    if absolute_variance == Decimal("0"):
        return ReconciliationStatus.EXACT_MATCH
    if absolute_variance <= tolerances.precision:
        return ReconciliationStatus.PRECISION_MATCH
    if absolute_variance <= tolerances.rounding:
        return ReconciliationStatus.ROUNDING_MATCH
    if absolute_variance <= tolerances.materiality:
        return ReconciliationStatus.PARTIAL_MATCH
    return ReconciliationStatus.MATERIAL_BREAK


def calculate_variance_percentage(variance: Decimal, reported_amount: Decimal) -> Decimal | None:
    """Compute ``abs(variance) / abs(reported_amount)``, Decimal-safe.

    Args:
        variance: The exact variance.
        reported_amount: The reported amount being varied against.

    Returns:
        The percentage as a ``Decimal`` (e.g. ``Decimal("0.0250")`` for
        2.5%), or ``None`` if ``reported_amount`` is zero (not applicable,
        per spec section 16).
    """
    if reported_amount == Decimal("0"):
        return None
    return abs(variance) / abs(reported_amount)
