"""Sheet-level classification: what kind of content a sheet holds.

Purpose
-------
Decide whether a sheet is a balance-sheet asset/liability/equity section, a
P&L, an off-balance-sheet section, the main financial statement, a
supporting schedule, a mapping table, or unknown -- using sheet name and
content keywords. This drives which reader (``financial_statement_reader``
vs. ``trial_balance_reader`` vs. ``mapping_reader``) should process the
sheet, and is never a source of accounting truth by itself.

Public contents
----------------
``SheetClassification`` -- selected class, confidence, evidence, review flag.
``classify_sheet(sheet_name, grid)`` -- classify one sheet.

Dependencies: ``iraq_recon.constants.SheetClass``, standard library.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from iraq_recon.constants import SheetClass

_WHITESPACE_RE = re.compile(r"\s+")

_NAME_KEYWORDS: dict[SheetClass, tuple[str, ...]] = {
    SheetClass.ASSETS: ("asset",),
    SheetClass.LIABILITIES: ("liabilit",),
    SheetClass.EQUITY: ("equity", "capital", "reserve"),
    SheetClass.P_AND_L: ("profit", "loss", "p&l", "p and l", "income statement"),
    SheetClass.OFF_BALANCE_SHEET: ("off balance", "off-balance", "obs", "contingent", "memorandum"),
    SheetClass.FINANCIAL_STATEMENT: ("financial statement", "balance sheet", "statement of financial position"),
    SheetClass.SUPPORTING_SCHEDULE: ("schedule", "note", "annex"),
    SheetClass.MAPPING: ("mapping", "bridge", "coa map", "chart of account"),
}

_CONTENT_KEYWORDS: dict[SheetClass, tuple[str, ...]] = {
    SheetClass.ASSETS: ("cash", "central bank", "investment", "fixed asset", "receivable"),
    SheetClass.LIABILITIES: ("deposit", "payable", "borrowing", "provision"),
    SheetClass.EQUITY: ("share capital", "retained earning", "statutory reserve"),
    SheetClass.P_AND_L: ("interest income", "interest expense", "net profit", "operating expense"),
    SheetClass.OFF_BALANCE_SHEET: ("guarantee", "letter of credit", "forward", "contra"),
    SheetClass.MAPPING: ("ayra", "local account", "iraq bucket", "semantic category"),
}


def _normalize(text: Any) -> str:
    if text is None:
        return ""
    return _WHITESPACE_RE.sub(" ", str(text).strip().lower())


@dataclass(frozen=True)
class SheetClassification:
    """Outcome of classifying one sheet.

    Attributes:
        sheet_class: Best-guess classification.
        confidence: 0.0-1.0 score.
        evidence: Human-readable reasons for the classification.
        review_flag: ``True`` when confidence is too low to trust
            automatically and a human should confirm.
    """

    sheet_class: SheetClass
    confidence: float
    evidence: tuple[str, ...] = ()
    review_flag: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "sheet_class": str(self.sheet_class),
            "confidence": self.confidence,
            "evidence": list(self.evidence),
            "review_flag": self.review_flag,
        }


def classify_sheet(
    sheet_name: str,
    grid: list[list[Any]],
    *,
    review_threshold: float = 0.4,
) -> SheetClassification:
    """Classify a sheet using its name and a sample of its cell content.

    Args:
        sheet_name: The sheet's name.
        grid: The sheet's raw grid (only the first ~100 rows are scanned for
            content keywords, for performance).
        review_threshold: Confidence below this triggers ``review_flag``.

    Returns:
        A :class:`SheetClassification`. Never raises; unknown/ambiguous
        sheets are returned as ``SheetClass.UNKNOWN`` with ``review_flag=True``.
    """
    normalized_name = _normalize(sheet_name)
    evidence: list[str] = []
    scores: dict[SheetClass, float] = {}

    for sheet_class, keywords in _NAME_KEYWORDS.items():
        for keyword in keywords:
            if keyword in normalized_name:
                scores[sheet_class] = scores.get(sheet_class, 0.0) + 0.6
                evidence.append(f"sheet name matched '{keyword}' -> {sheet_class}")

    sample_rows = grid[:100]
    flat_text = " ".join(
        _normalize(cell)
        for row in sample_rows
        for cell in row
        if isinstance(cell, str)
    )
    for sheet_class, keywords in _CONTENT_KEYWORDS.items():
        for keyword in keywords:
            if keyword in flat_text:
                scores[sheet_class] = scores.get(sheet_class, 0.0) + 0.2
                evidence.append(f"content matched '{keyword}' -> {sheet_class}")

    if not scores:
        return SheetClassification(
            sheet_class=SheetClass.UNKNOWN,
            confidence=0.0,
            evidence=("no name or content keywords matched",),
            review_flag=True,
        )

    best_class = max(scores, key=lambda cls: scores[cls])
    best_score = min(1.0, scores[best_class])

    return SheetClassification(
        sheet_class=best_class,
        confidence=best_score,
        evidence=tuple(evidence),
        review_flag=best_score < review_threshold,
    )
