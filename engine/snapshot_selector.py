"""Trial-balance snapshot comparison and selection (spec section 12).

Purpose
-------
When multiple candidate trial balances (e.g. W1, W2, W3, W4) are supplied,
score each one against a set of high-confidence anchor amounts (Central
Bank balance, statutory reserve, fixed asset cost, etc.) and produce a
ranked recommendation with numerical evidence -- never inferring a date not
explicitly present in the files, and always leaving the final choice
overridable by the caller.

Public contents
----------------
``AnchorDefinition`` -- one anchor's targeting metadata.
``SnapshotEvidence`` -- one candidate's scored evidence.
``compare_tb_snapshots(candidates, anchors, anchor_reported_amounts, ...)``.
``select_best_snapshot(evidence)`` -- pick the top-ranked candidate.

Dependencies: ``iraq_recon.calculators.base`` (reused for anchor summation),
``iraq_recon.mapping.local_bridge``, ``iraq_recon.mapping.mapping_coverage``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from iraq_recon.calculators.base import BucketCalculator, CalculatorContext
from iraq_recon.mapping.local_bridge import build_local_account_bridge
from iraq_recon.mapping.mapping_coverage import calculate_mapping_coverage
from iraq_recon.models.configuration import ReconciliationConfiguration
from iraq_recon.models.mapping import MappingRecord
from iraq_recon.models.source import TrialBalanceRecord
from iraq_recon.rules.tolerance_rules import classify_variance_by_tolerance

@dataclass(frozen=True)
class AnchorDefinition:
    """One high-confidence anchor used to score a candidate snapshot.

    Attributes:
        anchor_code: Stable identifier, e.g. ``"CENTRAL_BANK_CURRENT"``.
        iraq_reporting_bucket: The bucket this anchor sums.
        ayra_categories: Ayra categories claimed by this anchor.
    """

    anchor_code: str
    iraq_reporting_bucket: str
    ayra_categories: frozenset[str]


#: Standard high-confidence anchor set from spec section 12. Callers may
#: supply a narrower or broader set to :func:`compare_tb_snapshots`.
DEFAULT_ANCHORS: tuple[AnchorDefinition, ...] = (
    AnchorDefinition("CENTRAL_BANK_CURRENT", "BALANCES_WITH_CENTRAL_BANK", frozenset({"A-CBI"})),
    AnchorDefinition("STATUTORY_RESERVE", "BALANCES_WITH_CENTRAL_BANK", frozenset({"A-CRR"})),
    AnchorDefinition("BANK_DEBIT_BALANCES", "DEBIT_BALANCES_WITH_BANKS", frozenset({"A-IGA", "A-IBA"})),
    AnchorDefinition("BANK_CREDIT_BALANCES", "BANK_GROUP_CURRENT_LIABILITIES", frozenset({"L-IGL-C", "L-IBL"})),
    AnchorDefinition("INVESTMENTS", "INVESTMENTS_IN_SECURITIES", frozenset({"A-TB"})),
    AnchorDefinition("HEAD_OFFICE_AND_BRANCHES", "HEAD_OFFICE_AND_BRANCHES", frozenset({"A-HOB"})),
    AnchorDefinition("FIXED_ASSET_COST", "FIXED_ASSETS", frozenset({"A-FA"})),
    AnchorDefinition("ACCUMULATED_DEPRECIATION", "FIXED_ASSETS", frozenset({"A-FA-CONTRA"})),
    AnchorDefinition("OTHER_ASSETS", "OTHER_ASSETS", frozenset({"A-OA"})),
    AnchorDefinition("CUSTOMER_DEPOSITS", "CUSTOMER_DEPOSITS", frozenset({"L-CASA"})),
    AnchorDefinition("CAPITAL_AND_RESERVES", "CAPITAL_AND_RESERVES", frozenset({"EQ-SC", "EQ-SR", "EQ-RE"})),
)


@dataclass(frozen=True)
class SnapshotEvidence:
    """Scored evidence for one candidate trial-balance snapshot.

    Attributes:
        snapshot_id: Candidate identifier (e.g. ``"W1"``).
        matched_anchor_count: Anchors with a non-``None`` reported amount to
            compare against.
        exact_match_count: Anchors matching the reported amount exactly.
        precision_match_count: Anchors matching within precision tolerance
            (exact matches also count here).
        total_absolute_variance: Sum of absolute variances across all
            matched anchors.
        mapping_account_coverage: Overall account-count coverage ratio.
        mapping_value_coverage: Overall value coverage ratio.
        control_failure_count: Placeholder for control failures detected
            elsewhere and attributed to this snapshot by the caller.
        anchor_details: Per-anchor breakdown for diagnostic display.
    """

    snapshot_id: str
    matched_anchor_count: int
    exact_match_count: int
    precision_match_count: int
    total_absolute_variance: Decimal
    mapping_account_coverage: Decimal
    mapping_value_coverage: Decimal
    control_failure_count: int = 0
    anchor_details: tuple[dict[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "matched_anchor_count": self.matched_anchor_count,
            "exact_match_count": self.exact_match_count,
            "precision_match_count": self.precision_match_count,
            "total_absolute_variance": str(self.total_absolute_variance),
            "mapping_account_coverage": str(self.mapping_account_coverage),
            "mapping_value_coverage": str(self.mapping_value_coverage),
            "control_failure_count": self.control_failure_count,
            "anchor_details": [dict(d) for d in self.anchor_details],
        }


def compare_tb_snapshots(
    candidates: dict[str, list[TrialBalanceRecord]],
    anchors: list[AnchorDefinition],
    anchor_reported_amounts: dict[str, Decimal],
    mapping_records: list[MappingRecord],
    configuration: ReconciliationConfiguration,
    *,
    as_of: date | None = None,
) -> list[SnapshotEvidence]:
    """Score every candidate snapshot against the anchor set.

    Args:
        candidates: ``{snapshot_id: trial_balance_records}``.
        anchors: Anchors to evaluate (see :class:`AnchorDefinition`).
        anchor_reported_amounts: ``{anchor_code: reported_amount}`` sourced
            from the main financial statement or supporting schedules;
            anchors with no entry here are skipped, never inferred.
        mapping_records: All loaded mapping records.
        configuration: The run configuration (units and tolerances).
        as_of: Effective date for mapping resolution.

    Returns:
        A list of :class:`SnapshotEvidence`, ranked best-first: most exact
        matches, then most precision matches, then lowest total absolute
        variance, then highest value coverage.
    """
    bridge = build_local_account_bridge(mapping_records, as_of=as_of or configuration.mapping.effective_date)
    context = CalculatorContext(
        bridge=bridge,
        unit_config=configuration.units,
        tolerances=configuration.tolerances,
        run_date=as_of,
        mapping_records=tuple(mapping_records),
    )

    evidence: list[SnapshotEvidence] = []
    for snapshot_id, records in candidates.items():
        matched_anchor_count = 0
        exact_match_count = 0
        precision_match_count = 0
        total_absolute_variance = Decimal("0")
        anchor_details: list[dict[str, Any]] = []

        for anchor in anchors:
            reported_amount = anchor_reported_amounts.get(anchor.anchor_code)
            calculator = BucketCalculator(
                line_code=anchor.anchor_code,
                iraq_reporting_bucket=anchor.iraq_reporting_bucket,
                allowed_ayra_categories=anchor.ayra_categories,
            )
            calc_result = calculator.calculate(records, {}, context)

            if reported_amount is None:
                anchor_details.append(
                    {
                        "anchor_code": anchor.anchor_code,
                        "calculated_amount": str(calc_result.calculated_amount),
                        "reported_amount": None,
                        "variance": None,
                        "status": "NOT_APPLICABLE",
                    }
                )
                continue

            matched_anchor_count += 1
            variance = calc_result.calculated_amount - reported_amount
            total_absolute_variance += abs(variance)
            status = classify_variance_by_tolerance(variance, configuration.tolerances)
            if status.value == "EXACT_MATCH":
                exact_match_count += 1
                precision_match_count += 1
            elif status.value == "PRECISION_MATCH":
                precision_match_count += 1

            anchor_details.append(
                {
                    "anchor_code": anchor.anchor_code,
                    "calculated_amount": str(calc_result.calculated_amount),
                    "reported_amount": str(reported_amount),
                    "variance": str(variance),
                    "status": status.value,
                }
            )

        coverage = calculate_mapping_coverage(records, bridge)

        evidence.append(
            SnapshotEvidence(
                snapshot_id=snapshot_id,
                matched_anchor_count=matched_anchor_count,
                exact_match_count=exact_match_count,
                precision_match_count=precision_match_count,
                total_absolute_variance=total_absolute_variance,
                mapping_account_coverage=coverage.account_coverage_ratio,
                mapping_value_coverage=coverage.value_coverage_ratio,
                anchor_details=tuple(anchor_details),
            )
        )

    evidence.sort(
        key=lambda e: (
            -e.exact_match_count,
            -e.precision_match_count,
            e.total_absolute_variance,
            -e.mapping_value_coverage,
        )
    )
    return evidence


def select_best_snapshot(evidence: list[SnapshotEvidence]) -> str | None:
    """Return the top-ranked snapshot id, or ``None`` if ``evidence`` is empty.

    This is a recommendation only -- the caller (typically a reviewer via
    the WebApp) may override it with any other candidate's id.
    """
    if not evidence:
        return None
    return evidence[0].snapshot_id
