"""Header row detection for raw sheet grids.

Purpose
-------
Locate which physical row (if any) is the column-header row of a table, and
which column indexes hold the account number, description, and balance /
debit / credit values -- without assuming headers sit on row 1.

Public contents
----------------
``HeaderCandidate`` -- one scored candidate header row.
``HeaderDetectionResult`` -- selected candidate plus all alternatives.
``detect_header(grid, max_scan_rows=30)`` -- run detection over a grid.

Inputs/Outputs
--------------
Input: a rectangular grid (``list[list[Any]]``) as produced by
``ingestion.excel_reader``.
Output: :class:`HeaderDetectionResult`.

Dependencies: standard library only.

Error handling
--------------
Never raises for "no header found" -- returns a result with
``selected is None`` and a diagnostic-friendly candidate list instead, so
callers can decide whether to fail, warn, or ask a reviewer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

_ACCOUNT_KEYWORDS = (
    "account",
    "acct",
    "gl code",
    "coa",
    "account no",
    "account number",
    "line code",
    "line item",
    "line ref",
)
_DESCRIPTION_KEYWORDS = ("description", "particulars", "name", "narrative", "account name")
_BALANCE_KEYWORDS = ("balance", "amount", "closing balance", "net balance", "total")
_DEBIT_KEYWORDS = ("debit", "dr")
_CREDIT_KEYWORDS = ("credit", "cr")
_CURRENCY_KEYWORDS = ("currency", "ccy")
_RESIDENCY_KEYWORDS = ("residency", "resident", "non-resident")
_SCHEDULE_KEYWORDS = ("schedule", "note", "note ref", "note reference")

_ROLE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "account": _ACCOUNT_KEYWORDS,
    "description": _DESCRIPTION_KEYWORDS,
    "balance": _BALANCE_KEYWORDS,
    "debit": _DEBIT_KEYWORDS,
    "credit": _CREDIT_KEYWORDS,
    "currency": _CURRENCY_KEYWORDS,
    "residency": _RESIDENCY_KEYWORDS,
    "schedule": _SCHEDULE_KEYWORDS,
}

_WHITESPACE_RE = re.compile(r"\s+")


def _clean_header_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    return _WHITESPACE_RE.sub(" ", text)


@dataclass(frozen=True)
class HeaderCandidate:
    """One candidate header row and the column roles it appears to define.

    Attributes:
        row_index: 0-based row index within the grid.
        column_roles: ``{role: column_index}`` for roles this row matched
            (roles are keys of ``_ROLE_KEYWORDS``: account/description/
            balance/debit/credit).
        confidence: 0.0-1.0 score.
        evidence: Human-readable reasons contributing to the score.
    """

    row_index: int
    column_roles: dict[str, int]
    confidence: float
    evidence: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "row_index": self.row_index,
            "column_roles": dict(self.column_roles),
            "confidence": self.confidence,
            "evidence": list(self.evidence),
        }


@dataclass(frozen=True)
class HeaderDetectionResult:
    """Outcome of scanning a grid for its header row.

    Attributes:
        selected: Best candidate, or ``None`` if nothing scored above zero.
        candidates: Every candidate considered, best first.
    """

    selected: HeaderCandidate | None
    candidates: tuple[HeaderCandidate, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected": self.selected.to_dict() if self.selected else None,
            "candidates": [c.to_dict() for c in self.candidates],
        }


def _score_row(grid: list[list[Any]], row_index: int) -> HeaderCandidate:
    row = grid[row_index]
    column_roles: dict[str, int] = {}
    evidence: list[str] = []

    for col_index, raw_value in enumerate(row):
        text = _clean_header_text(raw_value)
        if not text:
            continue
        for role, keywords in _ROLE_KEYWORDS.items():
            if role in column_roles:
                continue
            for keyword in keywords:
                if keyword in text:
                    column_roles[role] = col_index
                    evidence.append(f"col {col_index} matched '{keyword}' for role '{role}'")
                    break

    score = 0.0
    if "account" in column_roles:
        score += 0.35
    if "description" in column_roles:
        score += 0.25
    if "balance" in column_roles:
        score += 0.25
    if "debit" in column_roles or "credit" in column_roles:
        score += 0.15

    # A row that is mostly non-empty text (not numbers) looks more like a
    # header than a data row.
    non_empty = [v for v in row if v not in (None, "")]
    if non_empty:
        text_like = sum(1 for v in non_empty if isinstance(v, str))
        text_ratio = text_like / len(non_empty)
        if text_ratio >= 0.6:
            score += 0.1
            evidence.append(f"row is {text_ratio:.0%} text-like")
        else:
            score -= 0.1

    # A following row that looks numeric where the header claims a balance
    # column boosts confidence further; checked by the caller since it needs
    # the next row too.
    return HeaderCandidate(
        row_index=row_index,
        column_roles=column_roles,
        confidence=max(0.0, min(1.0, score)),
        evidence=tuple(evidence),
    )


def _row_below_looks_like_data(grid: list[list[Any]], row_index: int, column_roles: dict[str, int]) -> bool:
    if row_index + 1 >= len(grid):
        return False
    next_row = grid[row_index + 1]
    balance_col = column_roles.get("balance")
    if balance_col is None or balance_col >= len(next_row):
        return False
    value = next_row[balance_col]
    return isinstance(value, (int, float)) or (
        isinstance(value, str) and any(ch.isdigit() for ch in value)
    )


def detect_header(grid: list[list[Any]], max_scan_rows: int = 30) -> HeaderDetectionResult:
    """Scan candidate rows and pick the most likely header row.

    Args:
        grid: Rectangular sheet grid.
        max_scan_rows: How many leading rows to consider as header candidates.

    Returns:
        A :class:`HeaderDetectionResult` with the best-scoring candidate
        selected only if it has at least an account or a balance column and
        a positive confidence.
    """
    candidates: list[HeaderCandidate] = []
    scan_limit = min(max_scan_rows, len(grid))

    for row_index in range(scan_limit):
        candidate = _score_row(grid, row_index)
        if not candidate.column_roles:
            continue
        if _row_below_looks_like_data(grid, row_index, candidate.column_roles):
            candidate = HeaderCandidate(
                row_index=candidate.row_index,
                column_roles=candidate.column_roles,
                confidence=min(1.0, candidate.confidence + 0.15),
                evidence=candidate.evidence + ("row below contains data-like values",),
            )
        candidates.append(candidate)

    candidates.sort(key=lambda c: c.confidence, reverse=True)

    selected: HeaderCandidate | None = None
    for candidate in candidates:
        has_anchor = "account" in candidate.column_roles or "balance" in candidate.column_roles
        if has_anchor and candidate.confidence > 0.0:
            selected = candidate
            break

    return HeaderDetectionResult(selected=selected, candidates=tuple(candidates))
