"""Account/line description normalization.

Purpose
-------
Produce a clean, whitespace-collapsed description plus an uppercase
"matching form" used by controlled description matching
(``engine.combination_matcher`` and ``mapping.mapping_validator``), while
always preserving the original text unchanged for audit and display.

Public contents
----------------
``NormalizedDescription`` -- cleaned text, matching form, original text.
``normalize_description(raw_value)`` -- normalize one description value.

Dependencies: standard library only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_WHITESPACE_RE = re.compile(r"\s+")

#: Common punctuation variants collapsed to a single canonical form so that
#: "A/C", "A / C" and "AC" compare consistently in the uppercase matching
#: form. Applied only to the matching form, never to the displayed text.
_PUNCTUATION_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("&", " AND "),
    ("/", " "),
    ("-", " "),
    ("_", " "),
    (".", ""),
    (",", ""),
    ("'", ""),
)


@dataclass(frozen=True)
class NormalizedDescription:
    """Result of normalizing one description value.

    Attributes:
        cleaned_text: Original text with whitespace trimmed/collapsed only;
            case and punctuation are preserved for display.
        matching_form: Uppercase, punctuation-normalized form used for
            controlled description matching.
        original_text: The raw value exactly as received.
    """

    cleaned_text: str
    matching_form: str
    original_text: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "cleaned_text": self.cleaned_text,
            "matching_form": self.matching_form,
            "original_text": self.original_text,
        }


def normalize_description(raw_value: Any) -> NormalizedDescription:
    """Normalize a raw description cell value.

    Args:
        raw_value: Raw cell value; non-string values are stringified.

    Returns:
        A :class:`NormalizedDescription`. Never raises.
    """
    original_text = "" if raw_value is None else str(raw_value)
    cleaned_text = _WHITESPACE_RE.sub(" ", original_text.strip())

    matching_source = cleaned_text.upper()
    for old, new in _PUNCTUATION_REPLACEMENTS:
        matching_source = matching_source.replace(old, new)
    matching_form = _WHITESPACE_RE.sub(" ", matching_source).strip()

    return NormalizedDescription(
        cleaned_text=cleaned_text,
        matching_form=matching_form,
        original_text=original_text,
    )
