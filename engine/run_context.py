"""Per-run context: bundles configuration, mappings, and the resolved bridge.

Purpose
-------
Build the single object a reconciliation run threads through every stage
(calculators, schedules, controls) exactly once, so the local-account
bridge is resolved a single time per run rather than rebuilt per calculator.

Public contents
----------------
``RunContext`` -- run-scoped state.
``build_run_context(run_id, configuration, mapping_records, as_of=None)``.

Dependencies: ``iraq_recon.mapping.local_bridge``, ``iraq_recon.calculators.base``.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from iraq_recon.calculators.base import CalculatorContext
from iraq_recon.mapping.local_bridge import LocalAccountBridge, build_local_account_bridge
from iraq_recon.models.configuration import ReconciliationConfiguration
from iraq_recon.models.mapping import MappingRecord


@dataclass(frozen=True)
class RunContext:
    """Run-scoped state shared by every stage of one reconciliation run.

    Attributes:
        run_id: Stable identifier for this run.
        configuration: The full run configuration.
        mapping_records: All loaded mapping records (any effective window).
        bridge: Local-account bridge resolved at the configuration's
            effective date.
        extra: Free-form additional context passed through to calculators.
    """

    run_id: str
    configuration: ReconciliationConfiguration
    mapping_records: tuple[MappingRecord, ...]
    bridge: LocalAccountBridge
    extra: dict[str, Any] = field(default_factory=dict)

    def to_calculator_context(self) -> CalculatorContext:
        """Build the :class:`CalculatorContext` calculators/schedules consume."""
        return CalculatorContext(
            bridge=self.bridge,
            unit_config=self.configuration.units,
            tolerances=self.configuration.tolerances,
            run_date=self.bridge.as_of,
            mapping_records=self.mapping_records,
            extra=dict(self.extra),
        )


def build_run_context(
    configuration: ReconciliationConfiguration,
    mapping_records: list[MappingRecord],
    *,
    run_id: str | None = None,
    as_of: date | None = None,
    extra: dict[str, Any] | None = None,
) -> RunContext:
    """Build a :class:`RunContext` for one reconciliation run.

    Args:
        configuration: The run configuration.
        mapping_records: All loaded mapping records.
        run_id: Stable run identifier; a UUID4 is generated if omitted.
        as_of: Effective date for mapping resolution; defaults to
            ``configuration.mapping.effective_date`` or today.
        extra: Additional context passed through to calculators.

    Returns:
        A :class:`RunContext`.
    """
    effective_date = as_of or configuration.mapping.effective_date
    bridge = build_local_account_bridge(mapping_records, as_of=effective_date)
    return RunContext(
        run_id=run_id or str(uuid.uuid4()),
        configuration=configuration,
        mapping_records=tuple(mapping_records),
        bridge=bridge,
        extra=extra or {},
    )
