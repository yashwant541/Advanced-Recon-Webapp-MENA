"""Level-1 mapping: local account -> approved local accounting meaning.

Purpose
-------
Resolve a local account number to the single :class:`MappingRecord` that
should govern it on a given date, following the deterministic-matching
order's first rule (approved account-number mapping beats everything else).
Surfaces conflicts (more than one mapping active for the same account on
the same date) rather than silently picking one.

Public contents
----------------
``LocalAccountBridge`` -- resolved lookup plus detected conflicts.
``build_local_account_bridge(records, as_of=None)`` -- build the bridge.

Dependencies: ``iraq_recon.models.mapping``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from iraq_recon.models.mapping import MappingRecord


@dataclass(frozen=True)
class LocalAccountBridge:
    """Resolved local-account -> mapping lookup for a given effective date.

    Attributes:
        as_of: The effective date the bridge was built for.
        resolved: ``{local_account: MappingRecord}`` for accounts with
            exactly one active mapping.
        conflicts: ``{local_account: [MappingRecord, ...]}`` for accounts
            with more than one mapping active on ``as_of`` -- these are
            never auto-resolved.
    """

    as_of: date
    resolved: dict[str, MappingRecord] = field(default_factory=dict)
    conflicts: dict[str, tuple[MappingRecord, ...]] = field(default_factory=dict)

    def get(self, local_account: str) -> MappingRecord | None:
        """Return the resolved mapping for ``local_account``, if unambiguous."""
        return self.resolved.get(local_account)

    def has_conflict(self, local_account: str) -> bool:
        return local_account in self.conflicts

    def to_dict(self) -> dict[str, Any]:
        return {
            "as_of": self.as_of.isoformat(),
            "resolved_count": len(self.resolved),
            "conflict_accounts": sorted(self.conflicts.keys()),
        }


def build_local_account_bridge(
    records: list[MappingRecord],
    as_of: date | None = None,
) -> LocalAccountBridge:
    """Build a local-account bridge from a flat list of mapping records.

    Args:
        records: All loaded mapping records (any effective window).
        as_of: The date to resolve mappings for; defaults to today.

    Returns:
        A :class:`LocalAccountBridge`. Accounts with zero active mappings
        simply do not appear in ``resolved`` -- see
        ``mapping.mapping_coverage`` for turning that into an "unmapped
        account" finding against actual trial-balance data.
    """
    effective_date = as_of or date.today()

    by_account: dict[str, list[MappingRecord]] = {}
    for record in records:
        if record.is_active_on(effective_date):
            by_account.setdefault(record.local_account, []).append(record)

    resolved: dict[str, MappingRecord] = {}
    conflicts: dict[str, tuple[MappingRecord, ...]] = {}
    for account, active_records in by_account.items():
        if len(active_records) == 1:
            resolved[account] = active_records[0]
        else:
            conflicts[account] = tuple(active_records)

    return LocalAccountBridge(as_of=effective_date, resolved=resolved, conflicts=conflicts)
