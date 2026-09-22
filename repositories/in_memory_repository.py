"""In-memory run repository, for local use and unit tests.

Purpose
-------
Give services a place to store and fetch reconciliation runs that works
identically whether or not Dataiku is installed, so the engine and
services layers never need to special-case "am I running inside Dataiku".
A real deployment swaps this for
``repositories.dataiku_repository.DataikuRunRepository``, which implements
the same :class:`RunRepository` interface.

Public contents
----------------
``InMemoryRunRepository`` -- process-local :class:`RunRepository`.

For the paired :class:`ResultRepository`, use
``repositories.result_repository.GenericResultRepository`` wrapped around
an ``InMemoryRunRepository`` -- the filtering/pagination logic is written
once and shared by every backend.

Dependencies: ``iraq_recon.repositories.run_repository``.
"""

from __future__ import annotations

from iraq_recon.exceptions import NotFoundError
from iraq_recon.models.reconciliation import ReconciliationRun
from iraq_recon.repositories.run_repository import RunRepository


class InMemoryRunRepository(RunRepository):
    """Process-local run repository backed by a plain dict.

    Suitable for local development and unit/integration tests where no
    Dataiku project is available. State does not survive process restarts.
    """

    def __init__(self) -> None:
        self._runs: dict[str, ReconciliationRun] = {}
        self._order: list[str] = []

    def save(self, run: ReconciliationRun) -> None:
        if run.run_id in self._runs:
            self._order.remove(run.run_id)
        self._order.insert(0, run.run_id)
        self._runs[run.run_id] = run

    def get(self, run_id: str) -> ReconciliationRun:
        try:
            return self._runs[run_id]
        except KeyError as exc:
            raise NotFoundError(
                f"No reconciliation run found with id '{run_id}'.",
                details={"run_id": run_id},
            ) from exc

    def list_run_ids(self) -> list[str]:
        return list(self._order)

    def delete(self, run_id: str) -> None:
        self._runs.pop(run_id, None)
        if run_id in self._order:
            self._order.remove(run_id)
