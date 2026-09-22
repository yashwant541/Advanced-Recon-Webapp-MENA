"""Account-number normalization.

Purpose
-------
Turn whatever Excel hands back for an account-number cell (a float like
``183110.0``, an ``int``, a zero-padded string, or stray whitespace) into a
single stable string form, while never silently discarding a leading zero
and always preserving the original raw value for audit.

Public contents
----------------
``NormalizedAccount`` -- normalized value plus the original text and any
warning.
``normalize_account(raw_value, *, preserve_leading_zeros=True)`` -- parse
one cell value.

Dependencies: standard library only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class NormalizedAccount:
    """Result of normalizing one raw account-number cell value.

    Attributes:
        value: Normalized account string, or ``None`` if the cell was blank
            or could not be normalized at all.
        original_text: The raw value's string form, preserved for audit.
        warning: Set when the raw value looked malformed (e.g. contains
            letters mixed unexpectedly, or is blank where an account was
            expected).
    """

    value: str | None
    original_text: str
    warning: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "original_text": self.original_text,
            "warning": self.warning,
        }


def normalize_account(raw_value: Any, *, preserve_leading_zeros: bool = True) -> NormalizedAccount:
    """Normalize a raw account-number cell value to a stable string.

    Args:
        raw_value: Raw cell value (``int``, ``float``, ``str``, or ``None``).
        preserve_leading_zeros: When ``True`` (default), a string form that
            already carries leading zeros (e.g. ``"018311"``) keeps them;
            a numeric Excel cell can never carry leading zeros by
            construction, so this only affects string inputs.

    Returns:
        A :class:`NormalizedAccount`. Never raises.
    """
    if raw_value is None:
        return NormalizedAccount(value=None, original_text="", warning="Account value is blank.")

    original_text = str(raw_value)

    if isinstance(raw_value, bool):
        return NormalizedAccount(
            value=None,
            original_text=original_text,
            warning=f"Boolean value '{original_text}' is not a valid account number.",
        )

    if isinstance(raw_value, int):
        return NormalizedAccount(value=str(raw_value), original_text=original_text)

    if isinstance(raw_value, float):
        if raw_value.is_integer():
            return NormalizedAccount(value=str(int(raw_value)), original_text=original_text)
        # A non-integer float account number is malformed, but we still
        # surface a best-effort value rather than dropping it silently.
        return NormalizedAccount(
            value=original_text,
            original_text=original_text,
            warning=f"Account value '{original_text}' is a non-integer number.",
        )

    text = str(raw_value).strip()
    if text == "":
        return NormalizedAccount(value=None, original_text="", warning="Account value is blank.")

    # Excel sometimes stores a numeric-looking account as text with a
    # trailing ".0" (copy/paste from a float column).
    if text.endswith(".0") and text[:-2].lstrip("-").isdigit():
        text = text[:-2]

    if not preserve_leading_zeros and text.isdigit():
        stripped = text.lstrip("0") or "0"
        return NormalizedAccount(value=stripped, original_text=original_text)

    return NormalizedAccount(value=text, original_text=original_text)
