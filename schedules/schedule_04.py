"""Schedule 4: bank and group balances (debit and credit sides).

Purpose
-------
Build and validate the gross debit and gross credit sides of bank/group
balances separately (spec section 11): debit, credit, current, term,
interbank, intergroup -- gross presentation, with the informational net
balance available from ``bucket_results`` but never substituted for the
gross totals or used to offset one side against the other.

Public contents
----------------
``Schedule4DebitBuilder`` -- gross debit-side schedule.
``Schedule4CreditBuilder`` -- gross credit-side schedule (current + term).
``informational_net_balance(debit_result, credit_result)`` -- memo-only net.

Dependencies: ``schedules.base``.
"""

from __future__ import annotations

from decimal import Decimal

from iraq_recon.models.reconciliation import ScheduleReconciliationResult
from iraq_recon.schedules.base import BucketScheduleBuilder

DEBIT_SCHEDULE_CODE = "SCHEDULE_4_DEBIT"
CREDIT_SCHEDULE_CODE = "SCHEDULE_4_CREDIT"

DEBIT_BUCKETS = frozenset({"DEBIT_BALANCES_WITH_BANKS"})
CREDIT_BUCKETS = frozenset({"BANK_GROUP_CURRENT_LIABILITIES", "BANK_GROUP_TERM_LIABILITIES"})


class Schedule4DebitBuilder(BucketScheduleBuilder):
    """Gross debit-side bank/group balances schedule."""

    def __init__(self, statement_line_code: str = "DEBIT_BALANCES_WITH_BANKS") -> None:
        super().__init__(
            schedule_code=DEBIT_SCHEDULE_CODE,
            schedule_description="Bank/group balances schedule -- debit side",
            target_iraq_reporting_buckets=DEBIT_BUCKETS,
            statement_line_code=statement_line_code,
        )


class Schedule4CreditBuilder(BucketScheduleBuilder):
    """Gross credit-side (current + term) bank/group balances schedule."""

    def __init__(self, statement_line_code: str = "BANK_GROUP_CURRENT_LIABILITIES") -> None:
        super().__init__(
            schedule_code=CREDIT_SCHEDULE_CODE,
            schedule_description="Bank/group balances schedule -- credit side",
            target_iraq_reporting_buckets=CREDIT_BUCKETS,
            statement_line_code=statement_line_code,
        )


def informational_net_balance(
    debit_result: ScheduleReconciliationResult,
    credit_result: ScheduleReconciliationResult,
) -> Decimal:
    """Return the memo-only net of debit minus credit gross totals.

    This value is informational only (spec section 11: "informational net
    balance") and must never be substituted for either gross total or used
    to offset one side against the other in primary reporting.
    """
    return debit_result.schedule_total - credit_result.schedule_total
