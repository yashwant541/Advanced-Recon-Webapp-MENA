"""Run-repository interface: persist and fetch whole reconciliation runs.

Purpose
-------
Give services one interface for storing/fetching
:class:`iraq_recon.models.reconciliation.ReconciliationRun` objects,
implemented identically whether the deployment target is a plain Python
process (``repositories.in_memory_repository.InMemoryRunRepository``) or a
Dataiku project (``repositories.dataiku_repository.DataikuRunRepository``).
Callers never need to know which one they hold.

Public contents: ``RunRepository`` (abstract interface).
Dependencies: ``iraq_recon.models.reconciliation``, standard library only.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from iraq_recon.models.reconciliation import ReconciliationRun


class RunRepository(ABC):
    """Interface for storing and retrieving whole reconciliation runs."""

    @abstractmethod
    def save(self, run: ReconciliationRun) -> None:
        """Persist (or overwrite) a run by its ``run_id``."""
        raise NotImplementedError

    @abstractmethod
    def get(self, run_id: str) -> ReconciliationRun:
        """Fetch a run by id.

        Raises:
            iraq_recon.exceptions.NotFoundError: if no run with this id has
                been saved.
        """
        raise NotImplementedError

    @abstractmethod
    def list_run_ids(self) -> list[str]:
        """Return every stored run id, most recently saved first."""
        raise NotImplementedError

    @abstractmethod
    def delete(self, run_id: str) -> None:
        """Remove a stored run, if present (no-op if absent)."""
        raise NotImplementedError
