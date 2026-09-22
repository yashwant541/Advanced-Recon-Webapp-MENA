"""Result-repository interface: on-demand, filtered/paginated drill-down.

Purpose
-------
Give the WebApp's drill-down endpoints (line detail, schedule detail,
exceptions, account trace) a way to fetch a slice of a run's results
without loading or re-transmitting the whole
:class:`iraq_recon.models.reconciliation.ReconciliationRun` (spec section
19: "Detailed results must be loaded on demand." / section 22: "Paginate
long results. Filter details server-side."). Implementations wrap a
:class:`iraq_recon.repositories.run_repository.RunRepository` and slice its
stored runs; they never re-run the reconciliation.

Public contents: ``ResultRepository`` (abstract interface).
Dependencies: ``iraq_recon.models.reconciliation``, standard library only.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from iraq_recon.exceptions import NotFoundError
from iraq_recon.models.calculation import CalculationResult
from iraq_recon.models.controls import ControlResult
from iraq_recon.models.reconciliation import (
    AccountTraceEntry,
    LineReconciliationResult,
    ReconciliationException,
    ScheduleReconciliationResult,
)
from iraq_recon.repositories.run_repository import RunRepository


class ResultRepository(ABC):
    """Interface for on-demand, filtered/paginated access to run results."""

    @abstractmethod
    def get_line_result(self, run_id: str, line_code: str) -> LineReconciliationResult:
        """Fetch one line's reconciliation result.

        Raises:
            iraq_recon.exceptions.NotFoundError: if the run or line is not found.
        """
        raise NotImplementedError

    @abstractmethod
    def list_line_results(self, run_id: str) -> list[LineReconciliationResult]:
        """Fetch every line result for a run.

        Line counts are small (one per calculator that ran, at most a
        couple dozen), so returning the full list -- rather than a
        paginated slice -- stays well within "compact JSON response"; only
        account-level detail (``get_account_trace``) needs pagination.
        """
        raise NotImplementedError

    @abstractmethod
    def get_account_trace(
        self,
        run_id: str,
        *,
        line_code: str | None = None,
        account: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[list[AccountTraceEntry], int]:
        """Fetch a filtered, paginated page of account-trace entries.

        Args:
            run_id: The run to query.
            line_code: If given, only entries for this financial-statement line.
            account: If given, only entries for this account number.
            offset: Number of matching entries to skip.
            limit: Maximum number of entries to return.

        Returns:
            ``(page, total_matching)`` -- ``page`` has at most ``limit``
            entries; ``total_matching`` is the count before pagination.
        """
        raise NotImplementedError

    @abstractmethod
    def get_schedule_result(self, run_id: str, schedule_code: str) -> ScheduleReconciliationResult:
        """Fetch one schedule's reconciliation result."""
        raise NotImplementedError

    @abstractmethod
    def get_calculation_result(self, run_id: str, line_code: str) -> CalculationResult:
        """Fetch one line's raw calculator output ("how did we get this number"):
        formula, included/deducted/excluded accounts with reasons, and warnings.

        Raises:
            iraq_recon.exceptions.NotFoundError: if the run or line is not found.
        """
        raise NotImplementedError

    @abstractmethod
    def get_control_results(self, run_id: str) -> list[ControlResult]:
        """Fetch every control result for a run."""
        raise NotImplementedError

    @abstractmethod
    def get_exceptions(
        self,
        run_id: str,
        *,
        severity: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[list[ReconciliationException], int]:
        """Fetch a filtered, paginated page of diagnosed exceptions."""
        raise NotImplementedError


class GenericResultRepository(ResultRepository):
    """:class:`ResultRepository` implemented generically over any :class:`RunRepository`.

    Slices whatever :class:`iraq_recon.models.reconciliation.ReconciliationRun`
    the wrapped run repository returns; used as-is by both the in-memory and
    Dataiku deployments (see ``repositories.in_memory_repository`` and
    ``repositories.dataiku_repository``), so filtering/pagination logic is
    written exactly once.
    """

    def __init__(self, run_repository: RunRepository) -> None:
        self._run_repository = run_repository

    def get_line_result(self, run_id: str, line_code: str) -> LineReconciliationResult:
        run = self._run_repository.get(run_id)
        for line in run.line_results:
            if line.line_code == line_code:
                return line
        raise NotFoundError(
            f"No line result '{line_code}' found on run '{run_id}'.",
            details={"run_id": run_id, "line_code": line_code},
        )

    def list_line_results(self, run_id: str) -> list[LineReconciliationResult]:
        return list(self._run_repository.get(run_id).line_results)

    def get_account_trace(
        self,
        run_id: str,
        *,
        line_code: str | None = None,
        account: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[list[AccountTraceEntry], int]:
        run = self._run_repository.get(run_id)
        matching = [
            entry
            for entry in run.account_trace
            if (line_code is None or entry.financial_statement_line == line_code)
            and (account is None or entry.account == account)
        ]
        return matching[offset : offset + limit], len(matching)

    def get_schedule_result(self, run_id: str, schedule_code: str) -> ScheduleReconciliationResult:
        run = self._run_repository.get(run_id)
        for schedule in run.schedule_results:
            if schedule.schedule_code == schedule_code:
                return schedule
        raise NotFoundError(
            f"No schedule result '{schedule_code}' found on run '{run_id}'.",
            details={"run_id": run_id, "schedule_code": schedule_code},
        )

    def get_calculation_result(self, run_id: str, line_code: str) -> CalculationResult:
        run = self._run_repository.get(run_id)
        for calc_result in run.calculation_results:
            if calc_result.line_code == line_code:
                return calc_result
        raise NotFoundError(
            f"No calculation result '{line_code}' found on run '{run_id}'.",
            details={"run_id": run_id, "line_code": line_code},
        )

    def get_control_results(self, run_id: str) -> list[ControlResult]:
        return list(self._run_repository.get(run_id).control_results)

    def get_exceptions(
        self,
        run_id: str,
        *,
        severity: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[list[ReconciliationException], int]:
        run = self._run_repository.get(run_id)
        matching = [exc for exc in run.exceptions if severity is None or str(exc.severity) == severity]
        return matching[offset : offset + limit], len(matching)
