"""Typed data models shared across the reconciliation engine.

Every model here is a plain ``@dataclass`` (frozen where the object is a
value produced once and never mutated in place). No model imports pandas,
Dataiku, or any calculator/service module -- models are pure data.
"""

from __future__ import annotations

from iraq_recon.models.calculation import CalculationContribution, CalculationResult
from iraq_recon.models.configuration import (
    ExecutionConfiguration,
    MappingConfiguration,
    OutputConfiguration,
    ReconciliationConfiguration,
    SourceConfiguration,
    ToleranceConfiguration,
    UnitConfiguration,
)
from iraq_recon.models.controls import ControlResult
from iraq_recon.models.mapping import MappingRecord
from iraq_recon.models.reconciliation import (
    AccountTraceEntry,
    LineReconciliationResult,
    ReconciliationException,
    ReconciliationRun,
    ScheduleReconciliationResult,
)
from iraq_recon.models.source import (
    SourceFile,
    SourceRow,
    StatementLineRecord,
    TrialBalanceRecord,
)
from iraq_recon.models.validation import MappingValidationIssue, ValidationResult

__all__ = [
    "AccountTraceEntry",
    "CalculationContribution",
    "CalculationResult",
    "ControlResult",
    "ExecutionConfiguration",
    "LineReconciliationResult",
    "MappingConfiguration",
    "MappingRecord",
    "MappingValidationIssue",
    "OutputConfiguration",
    "ReconciliationConfiguration",
    "ReconciliationException",
    "ReconciliationRun",
    "ScheduleReconciliationResult",
    "SourceConfiguration",
    "SourceFile",
    "SourceRow",
    "StatementLineRecord",
    "ToleranceConfiguration",
    "TrialBalanceRecord",
    "UnitConfiguration",
    "ValidationResult",
]
