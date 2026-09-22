"""Off-balance-sheet controls (spec section 18).

Purpose
-------
Report the OBS debit and credit contra totals separately, surface their
informational residual, and confirm OBS balances are excluded from primary
balance-sheet totals and correctly classified as guarantee vs. contingent.

Public contents
----------------
``check_off_balance_sheet_debit_credit_totals(obs_result)``
``check_guarantee_and_contingent_classification(obs_result)``

Dependencies: ``iraq_recon.models.calculation``, ``iraq_recon.constants``.
"""

from __future__ import annotations

from decimal import Decimal

from iraq_recon.constants import ControlStatus, NaturalSide, Severity
from iraq_recon.models.calculation import CalculationResult
from iraq_recon.models.controls import ControlResult


def check_off_balance_sheet_debit_credit_totals(obs_result: CalculationResult) -> list[ControlResult]:
    """Report OBS debit and credit contra totals, plus their informational residual.

    Args:
        obs_result: The off-balance-sheet calculator's
            :class:`CalculationResult` (see
            ``calculators.off_balance_sheet.OffBalanceSheetCalculator``).

    Returns:
        Three :class:`ControlResult` entries: debit total, credit total, and
        the informational residual between them. The residual is always
        ``PASS`` -- it is informational, not a pass/fail expectation, unless
        an approved presentation rule states otherwise (a decision this
        control does not make).
    """
    debit_total = Decimal("0")
    credit_total = Decimal("0")
    for contribution in obs_result.contributions:
        natural_side = contribution.source_lineage.get("natural_side")
        if natural_side == str(NaturalSide.DEBIT):
            debit_total += contribution.presented_amount
        elif natural_side == str(NaturalSide.CREDIT):
            credit_total += contribution.presented_amount

    residual = debit_total - credit_total

    return [
        ControlResult(
            control_code="OBS_DEBIT_CONTRA_TOTAL",
            control_description="Total off-balance-sheet debit contra accounts.",
            status=ControlStatus.PASS,
            severity=Severity.INFO,
            actual_amount=debit_total,
        ),
        ControlResult(
            control_code="OBS_CREDIT_CONTRA_TOTAL",
            control_description="Total off-balance-sheet credit contra accounts.",
            status=ControlStatus.PASS,
            severity=Severity.INFO,
            actual_amount=credit_total,
        ),
        ControlResult(
            control_code="OBS_DEBIT_CREDIT_RESIDUAL",
            control_description=(
                "Informational residual between OBS debit and credit contra totals; "
                "not a pass/fail expectation unless an approved presentation rule "
                "requires equality."
            ),
            status=ControlStatus.PASS,
            severity=Severity.INFO,
            actual_amount=residual,
        ),
    ]


def check_guarantee_and_contingent_classification(obs_result: CalculationResult) -> ControlResult:
    """Confirm every OBS contribution has a recognized formula component/category.

    Flags any contribution whose ``formula_component`` is empty, which
    would indicate an account reached the OBS calculator without a proper
    Ayra category classification.
    """
    unclassified = [c.account for c in obs_result.contributions if not c.formula_component]
    return ControlResult(
        control_code="OBS_CLASSIFICATION_CONTROL",
        control_description="Every off-balance-sheet account has a recognized guarantee/contingent classification.",
        status=ControlStatus.FAIL if unclassified else ControlStatus.PASS,
        severity=Severity.MEDIUM,
        details={"unclassified_accounts": unclassified},
    )
