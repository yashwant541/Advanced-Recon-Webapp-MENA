"""Schedule registry and selective-execution orchestrator.

Purpose
-------
Give the reconciliation engine one call to build "all schedules" or a
selected subset by code (spec section 15: "Support selective execution ...
selected schedules"), without the engine needing to know about each
schedule class individually.

Public contents
----------------
``DEFAULT_SCHEDULE_REGISTRY`` -- code -> :class:`ScheduleBuilder` instance.
``build_schedules(schedule_codes, records, reported_lines, context, registry=None)``.

Dependencies: ``schedules.schedule_03``, ``schedules.schedule_04``,
``schedules.schedule_05``.
"""

from __future__ import annotations

from iraq_recon.calculators.base import CalculatorContext
from iraq_recon.exceptions import ScheduleError
from iraq_recon.models.reconciliation import ScheduleReconciliationResult
from iraq_recon.models.source import StatementLineRecord, TrialBalanceRecord
from iraq_recon.schedules.base import ScheduleBuilder
from iraq_recon.schedules.schedule_03 import Schedule3Builder
from iraq_recon.schedules.schedule_04 import Schedule4CreditBuilder, Schedule4DebitBuilder
from iraq_recon.schedules.schedule_05 import Schedule5Builder


def _build_default_registry() -> dict[str, ScheduleBuilder]:
    return {
        Schedule3Builder().schedule_code: Schedule3Builder(),
        Schedule4DebitBuilder().schedule_code: Schedule4DebitBuilder(),
        Schedule4CreditBuilder().schedule_code: Schedule4CreditBuilder(),
        Schedule5Builder().schedule_code: Schedule5Builder(),
    }


DEFAULT_SCHEDULE_REGISTRY: dict[str, ScheduleBuilder] = _build_default_registry()


def build_schedules(
    schedule_codes: tuple[str, ...] | list[str] | None,
    records: list[TrialBalanceRecord],
    reported_lines: dict[str, StatementLineRecord],
    context: CalculatorContext,
    registry: dict[str, ScheduleBuilder] | None = None,
) -> list[ScheduleReconciliationResult]:
    """Build all registered schedules, or a selected subset by code.

    Args:
        schedule_codes: Specific schedule codes to build; an empty tuple or
            ``None`` builds every schedule in ``registry``.
        records: Trial-balance records for the selected snapshot.
        reported_lines: Reported financial-statement lines, keyed by line
            code.
        context: Shared per-run dependencies.
        registry: Schedule code -> builder map; defaults to
            :data:`DEFAULT_SCHEDULE_REGISTRY`.

    Returns:
        A list of :class:`ScheduleReconciliationResult`, in registry/request
        order.

    Raises:
        ScheduleError: if an explicitly requested schedule code is not in
            the registry.
    """
    active_registry = registry if registry is not None else DEFAULT_SCHEDULE_REGISTRY

    if not schedule_codes:
        selected_codes = list(active_registry.keys())
    else:
        unknown = [code for code in schedule_codes if code not in active_registry]
        if unknown:
            raise ScheduleError(
                f"Unknown schedule code(s): {unknown}. Known schedules: {sorted(active_registry)}.",
                details={"unknown_codes": unknown},
            )
        selected_codes = list(schedule_codes)

    return [active_registry[code].build(records, reported_lines, context) for code in selected_codes]
