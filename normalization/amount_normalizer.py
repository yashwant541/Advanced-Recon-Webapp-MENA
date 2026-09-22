"""Decimal-safe amount parsing for financial cell values.

Purpose
-------
Convert raw Excel cell values (numbers, comma-formatted strings, parenthetical
negatives, blank cells) into ``decimal.Decimal`` without ever silently
producing zero for genuinely invalid text, and without ever using binary
floating point for the final value.

Public contents
----------------
``ParsedAmount`` -- parsed value plus flags distinguishing zero from missing
and negative-from-parentheses from negative-from-sign.
``normalize_amount(raw_value)`` -- parse one cell value.

Dependencies: ``decimal`` (standard library only). Never raises: invalid
text is reported via ``ParsedAmount.warning`` with ``value=None`` so callers
can decide how to react (skip the row, raise, flag for review).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

_THOUSANDS_RE = re.compile(r"[,\s ]")
_PARENTHETICAL_RE = re.compile(r"^\((.*)\)$")
_NUMERIC_RE = re.compile(r"^-?\d+(\.\d+)?$")


@dataclass(frozen=True)
class ParsedAmount:
    """Result of parsing one raw cell value into a Decimal amount.

    Attributes:
        value: Parsed amount, or ``None`` if the cell was invalid text.
            A genuinely blank cell parses to ``value=None`` as well, but
            with ``is_blank=True`` and no warning, distinguishing "missing"
            from "invalid".
        original_text: The raw value's string form, preserved for audit.
        is_blank: ``True`` if the cell was empty/whitespace-only (missing,
            not zero).
        is_negative_parenthetical: ``True`` if negativity was expressed via
            surrounding parentheses rather than a leading minus sign.
        warning: Set when the text could not be parsed as a number at all.
    """

    value: Decimal | None
    original_text: str
    is_blank: bool = False
    is_negative_parenthetical: bool = False
    warning: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": str(self.value) if self.value is not None else None,
            "original_text": self.original_text,
            "is_blank": self.is_blank,
            "is_negative_parenthetical": self.is_negative_parenthetical,
            "warning": self.warning,
        }


def normalize_amount(raw_value: Any) -> ParsedAmount:
    """Parse a raw Excel cell value into a Decimal-backed :class:`ParsedAmount`.

    Handles:
        - native ``int``/``float`` cell values (openpyxl gives these for
          numeric cells);
        - comma/space thousands separators;
        - parenthetical negatives, e.g. ``"(1,234.56)"`` -> ``-1234.56``;
        - explicit leading ``+``/``-`` signs;
        - blank/``None`` cells (returned as blank, not zero);
        - invalid text (returned as a warning, never silently zero).

    Args:
        raw_value: The raw cell value as read by openpyxl (``int``, ``float``,
            ``str``, or ``None``).

    Returns:
        A :class:`ParsedAmount`. Never raises.
    """
    if raw_value is None:
        return ParsedAmount(value=None, original_text="", is_blank=True)

    if isinstance(raw_value, bool):
        # bool is a subclass of int; a checkbox-like cell is not an amount.
        text = str(raw_value)
        return ParsedAmount(
            value=None,
            original_text=text,
            warning=f"Boolean value '{text}' is not a valid amount.",
        )

    if isinstance(raw_value, (int, float)):
        text = str(raw_value)
        try:
            return ParsedAmount(value=Decimal(str(raw_value)), original_text=text)
        except InvalidOperation:
            return ParsedAmount(value=None, original_text=text, warning=f"Could not parse numeric value '{text}'.")

    text = str(raw_value).strip()
    if text == "":
        return ParsedAmount(value=None, original_text="", is_blank=True)

    # Treat lone dash/placeholder markers as blank, not invalid.
    if text in ("-", "--", "n/a", "N/A", "na", "NA"):
        return ParsedAmount(value=None, original_text=text, is_blank=True)

    is_parenthetical = False
    working = text
    paren_match = _PARENTHETICAL_RE.match(working)
    if paren_match:
        is_parenthetical = True
        working = paren_match.group(1).strip()

    working = _THOUSANDS_RE.sub("", working)

    # Trailing minus sign, e.g. "1234.56-".
    if working.endswith("-"):
        working = "-" + working[:-1]

    if working.startswith("+"):
        working = working[1:]

    if not _NUMERIC_RE.match(working):
        return ParsedAmount(
            value=None,
            original_text=text,
            warning=f"'{text}' could not be parsed as a numeric amount.",
        )

    try:
        value = Decimal(working)
    except InvalidOperation:
        return ParsedAmount(
            value=None,
            original_text=text,
            warning=f"'{text}' could not be parsed as a numeric amount.",
        )

    if is_parenthetical:
        value = -abs(value)

    return ParsedAmount(
        value=value,
        original_text=text,
        is_negative_parenthetical=is_parenthetical,
    )
