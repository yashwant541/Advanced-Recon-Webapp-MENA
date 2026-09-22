"""Review service: reviewer decisions that are not the engine's to make.

Purpose
-------
Hold the small set of decisions the spec explicitly reserves for a human
reviewer rather than the engine: overriding the recommended TB snapshot,
and approving (or rejecting) a provisional combination match. Neither
action mutates engine output in place -- the engine's own results stay
exactly as calculated; a review decision is a separate record the caller
(the WebApp) is responsible for storing wherever review decisions live.

Public contents
----------------
``override_snapshot_selection(evidence, override_snapshot_id)``
``review_combination_match(match, *, decision, reviewed_by, notes="")``

Dependencies: ``iraq_recon.engine.snapshot_selector``,
``iraq_recon.engine.combination_matcher``, ``iraq_recon.exceptions``.
"""

from __future__ import annotations

from typing import Any, Literal

from iraq_recon.engine.combination_matcher import CombinationMatch
from iraq_recon.engine.snapshot_selector import SnapshotEvidence
from iraq_recon.exceptions import SnapshotError

ReviewDecision = Literal["APPROVED", "REJECTED"]


def override_snapshot_selection(evidence: list[SnapshotEvidence], override_snapshot_id: str) -> str:
    """Validate and accept a reviewer's manual TB snapshot override.

    Args:
        evidence: The scored candidates from
            ``engine.snapshot_selector.compare_tb_snapshots``.
        override_snapshot_id: The snapshot id the reviewer chose.

    Returns:
        ``override_snapshot_id``, once confirmed to be one of the evaluated
        candidates.

    Raises:
        SnapshotError: if ``override_snapshot_id`` was not among the
            candidates that were actually compared.
    """
    known_ids = {e.snapshot_id for e in evidence}
    if override_snapshot_id not in known_ids:
        raise SnapshotError(
            f"'{override_snapshot_id}' is not one of the compared snapshot candidates.",
            details={"override_snapshot_id": override_snapshot_id, "known_snapshot_ids": sorted(known_ids)},
        )
    return override_snapshot_id


def review_combination_match(
    match: CombinationMatch,
    *,
    decision: ReviewDecision,
    reviewed_by: str,
    notes: str = "",
) -> dict[str, Any]:
    """Record a reviewer's decision on a provisional combination match.

    A combination match is never auto-approved by the engine (spec section
    14); this function turns a reviewer's explicit decision into a plain
    record the caller persists. It never mutates ``match`` itself -- the
    engine's provisional finding remains the audit record of what was
    proposed, and this decision is the audit record of what happened to it.

    Args:
        match: The provisional match being reviewed.
        decision: ``"APPROVED"`` or ``"REJECTED"``.
        reviewed_by: Identifier of the reviewer.
        notes: Optional free-text justification.

    Returns:
        A plain dict combining the match's data with the review decision.
    """
    return {
        **match.to_dict(),
        "review_decision": decision,
        "reviewed_by": reviewed_by,
        "notes": notes,
    }
