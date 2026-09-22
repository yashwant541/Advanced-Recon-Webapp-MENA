"""Mapping coverage: how much of the trial balance is actually mapped.

Purpose
-------
Measure account-count and value coverage of a resolved
:class:`iraq_recon.mapping.local_bridge.LocalAccountBridge` against actual
posting trial-balance records, and surface non-zero unmapped accounts as
first-class findings (spec section 8: "non-zero unmapped accounts" is a
required validator/coverage check).

Public contents
----------------
``UnmappedAccount`` -- one non-zero account with no active mapping.
``MappingCoverageResult`` -- aggregate coverage metrics.
``calculate_mapping_coverage(records, bridge)`` -- compute coverage.

Dependencies: ``iraq_recon.models.source.TrialBalanceRecord``,
``iraq_recon.mapping.local_bridge.LocalAccountBridge``,
``iraq_recon.normalization.row_classifier.is_summable``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from iraq_recon.mapping.local_bridge import LocalAccountBridge
from iraq_recon.models.source import TrialBalanceRecord
from iraq_recon.normalization.row_classifier import is_summable


@dataclass(frozen=True)
class UnmappedAccount:
    """A posting account with a non-zero balance and no active mapping."""

    account_number: str
    account_description: str
    balance: Decimal
    source_file: str
    source_sheet: str
    source_row: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_number": self.account_number,
            "account_description": self.account_description,
            "balance": str(self.balance),
            "source_file": self.source_file,
            "source_sheet": self.source_sheet,
            "source_row": self.source_row,
        }


@dataclass(frozen=True)
class MappingCoverageResult:
    """Aggregate coverage metrics for one trial balance against one bridge.

    Attributes:
        total_accounts: Count of distinct posting accounts.
        mapped_accounts: Count of distinct posting accounts with an active,
            unambiguous mapping.
        account_coverage_ratio: ``mapped_accounts / total_accounts``.
        total_value: Sum of absolute posting balances.
        mapped_value: Sum of absolute posting balances for mapped accounts.
        value_coverage_ratio: ``mapped_value / total_value``.
        unmapped_accounts: Non-zero accounts with no active mapping.
        conflicted_accounts: Accounts whose mapping is ambiguous (more than
            one mapping active on the bridge's date).
    """

    total_accounts: int
    mapped_accounts: int
    account_coverage_ratio: Decimal
    total_value: Decimal
    mapped_value: Decimal
    value_coverage_ratio: Decimal
    unmapped_accounts: tuple[UnmappedAccount, ...] = field(default_factory=tuple)
    conflicted_accounts: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_accounts": self.total_accounts,
            "mapped_accounts": self.mapped_accounts,
            "account_coverage_ratio": str(self.account_coverage_ratio),
            "total_value": str(self.total_value),
            "mapped_value": str(self.mapped_value),
            "value_coverage_ratio": str(self.value_coverage_ratio),
            "unmapped_accounts": [u.to_dict() for u in self.unmapped_accounts],
            "conflicted_accounts": list(self.conflicted_accounts),
        }

    def summary_dict(self) -> dict[str, Any]:
        return {
            "total_accounts": self.total_accounts,
            "mapped_accounts": self.mapped_accounts,
            "account_coverage_ratio": str(self.account_coverage_ratio),
            "value_coverage_ratio": str(self.value_coverage_ratio),
            "unmapped_account_count": len(self.unmapped_accounts),
            "conflicted_account_count": len(self.conflicted_accounts),
        }


def calculate_mapping_coverage(
    records: list[TrialBalanceRecord],
    bridge: LocalAccountBridge,
) -> MappingCoverageResult:
    """Compute account-count and value coverage of ``bridge`` over ``records``.

    Args:
        records: Trial-balance records for one selected snapshot (posting
            and non-posting rows may both be present; only posting rows
            are counted).
        bridge: A resolved :class:`LocalAccountBridge`.

    Returns:
        A :class:`MappingCoverageResult`.
    """
    posting_records = [r for r in records if is_summable(r.row_type)]

    distinct_accounts = {r.account_number for r in posting_records}
    total_accounts = len(distinct_accounts)
    mapped_account_set = {a for a in distinct_accounts if bridge.get(a) is not None}
    mapped_accounts = len(mapped_account_set)

    total_value = Decimal("0")
    mapped_value = Decimal("0")
    unmapped_accounts: list[UnmappedAccount] = []
    conflicted_accounts: set[str] = set()

    for record in posting_records:
        absolute_balance = abs(record.normalized_balance)
        total_value += absolute_balance
        if record.account_number in mapped_account_set:
            mapped_value += absolute_balance
        else:
            if bridge.has_conflict(record.account_number):
                conflicted_accounts.add(record.account_number)
            if absolute_balance != Decimal("0"):
                unmapped_accounts.append(
                    UnmappedAccount(
                        account_number=record.account_number,
                        account_description=record.account_description,
                        balance=record.normalized_balance,
                        source_file=record.source_file,
                        source_sheet=record.source_sheet,
                        source_row=record.source_row,
                    )
                )

    account_coverage_ratio = (
        Decimal(mapped_accounts) / Decimal(total_accounts) if total_accounts else Decimal("1")
    )
    value_coverage_ratio = (
        mapped_value / total_value if total_value != Decimal("0") else Decimal("1")
    )

    return MappingCoverageResult(
        total_accounts=total_accounts,
        mapped_accounts=mapped_accounts,
        account_coverage_ratio=account_coverage_ratio,
        total_value=total_value,
        mapped_value=mapped_value,
        value_coverage_ratio=value_coverage_ratio,
        unmapped_accounts=tuple(unmapped_accounts),
        conflicted_accounts=tuple(sorted(conflicted_accounts)),
    )
