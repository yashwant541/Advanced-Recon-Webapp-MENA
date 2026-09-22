"""Typed configuration objects for a reconciliation run.

Purpose
-------
Replace scattered hardcoded folder IDs, dataset names, and tolerances with a
single typed configuration tree that is built once (typically by
``iraq_recon.adapters.dataiku_io.resolve_project_configuration``) and passed
through the engine by value.

Public contents
----------------
``SourceConfiguration``, ``UnitConfiguration``, ``ToleranceConfiguration``,
``ExecutionConfiguration``, ``MappingConfiguration``, ``OutputConfiguration``,
``ReconciliationConfiguration`` (the aggregate root), each with
``from_dict``/``to_dict``.

Dependencies: ``decimal`` (standard library only).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from iraq_recon.exceptions import ConfigurationError


def _dec(value: Any, default: str) -> Decimal:
    if value is None:
        return Decimal(default)
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


@dataclass(frozen=True)
class SourceConfiguration:
    """Locations of the source workbooks for a run."""

    financial_statement_folder_id: str = ""
    trial_balance_folder_id: str = ""
    mapping_folder_id: str = ""
    schedule_folder_id: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "SourceConfiguration":
        data = data or {}
        return cls(
            financial_statement_folder_id=str(data.get("financial_statement_folder_id", "")),
            trial_balance_folder_id=str(data.get("trial_balance_folder_id", "")),
            mapping_folder_id=str(data.get("mapping_folder_id", "")),
            schedule_folder_id=str(data.get("schedule_folder_id", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "financial_statement_folder_id": self.financial_statement_folder_id,
            "trial_balance_folder_id": self.trial_balance_folder_id,
            "mapping_folder_id": self.mapping_folder_id,
            "schedule_folder_id": self.schedule_folder_id,
        }


@dataclass(frozen=True)
class UnitConfiguration:
    """Declared units and the conversion factor between them."""

    tb_unit: str = "IQD"
    financial_statement_unit: str = "IQD"
    conversion_factor: Decimal = Decimal("1")

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "UnitConfiguration":
        data = data or {}
        return cls(
            tb_unit=str(data.get("tb_unit", "IQD")),
            financial_statement_unit=str(data.get("financial_statement_unit", "IQD")),
            conversion_factor=_dec(data.get("conversion_factor"), "1"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "tb_unit": self.tb_unit,
            "financial_statement_unit": self.financial_statement_unit,
            "conversion_factor": str(self.conversion_factor),
        }


@dataclass(frozen=True)
class ToleranceConfiguration:
    """Decimal-safe tolerance thresholds used by the variance engine.

    Attributes:
        precision: Absolute variance at or below this is an exact/precision
            match (e.g. rounding to the cent).
        rounding: Absolute variance at or below this is a rounding match.
        materiality: Absolute variance above this is a material break,
            regardless of percentage.
    """

    precision: Decimal = Decimal("0.01")
    rounding: Decimal = Decimal("1")
    materiality: Decimal = Decimal("1000")

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ToleranceConfiguration":
        data = data or {}
        return cls(
            precision=_dec(data.get("precision"), "0.01"),
            rounding=_dec(data.get("rounding"), "1"),
            materiality=_dec(data.get("materiality"), "1000"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "precision": str(self.precision),
            "rounding": str(self.rounding),
            "materiality": str(self.materiality),
        }


@dataclass(frozen=True)
class ExecutionConfiguration:
    """Controls which parts of the reconciliation actually run."""

    statement_sections: tuple[str, ...] = ()
    schedule_codes: tuple[str, ...] = ()
    run_combination_matching: bool = True
    maximum_combination_size: int = 3

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ExecutionConfiguration":
        data = data or {}
        return cls(
            statement_sections=tuple(data.get("statement_sections", []) or []),
            schedule_codes=tuple(data.get("schedule_codes", []) or []),
            run_combination_matching=bool(data.get("run_combination_matching", True)),
            maximum_combination_size=int(data.get("maximum_combination_size", 3)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "statement_sections": list(self.statement_sections),
            "schedule_codes": list(self.schedule_codes),
            "run_combination_matching": self.run_combination_matching,
            "maximum_combination_size": self.maximum_combination_size,
        }

    def runs_all_sections(self) -> bool:
        return len(self.statement_sections) == 0

    def runs_all_schedules(self) -> bool:
        return len(self.schedule_codes) == 0


@dataclass(frozen=True)
class MappingConfiguration:
    """Controls mapping resolution behavior."""

    effective_date: date | None = None
    allow_description_suggestions: bool = False
    require_approved_mapping: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "MappingConfiguration":
        data = data or {}
        raw_date = data.get("effective_date")
        effective_date = date.fromisoformat(raw_date) if raw_date else None
        return cls(
            effective_date=effective_date,
            allow_description_suggestions=bool(data.get("allow_description_suggestions", False)),
            require_approved_mapping=bool(data.get("require_approved_mapping", True)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "effective_date": self.effective_date.isoformat() if self.effective_date else None,
            "allow_description_suggestions": self.allow_description_suggestions,
            "require_approved_mapping": self.require_approved_mapping,
        }


@dataclass(frozen=True)
class OutputConfiguration:
    """Controls where results and exports are written."""

    result_dataset_names: dict[str, str] = field(default_factory=dict)
    export_folder_id: str = ""
    export_filename_pattern: str = "reconciliation_{run_id}.xlsx"

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "OutputConfiguration":
        data = data or {}
        return cls(
            result_dataset_names=dict(data.get("result_dataset_names", {}) or {}),
            export_folder_id=str(data.get("export_folder_id", "")),
            export_filename_pattern=str(
                data.get("export_filename_pattern", "reconciliation_{run_id}.xlsx")
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_dataset_names": dict(self.result_dataset_names),
            "export_folder_id": self.export_folder_id,
            "export_filename_pattern": self.export_filename_pattern,
        }


@dataclass(frozen=True)
class ReconciliationConfiguration:
    """Aggregate root configuration object passed through the whole engine."""

    source: SourceConfiguration = field(default_factory=SourceConfiguration)
    units: UnitConfiguration = field(default_factory=UnitConfiguration)
    tolerances: ToleranceConfiguration = field(default_factory=ToleranceConfiguration)
    execution: ExecutionConfiguration = field(default_factory=ExecutionConfiguration)
    mapping: MappingConfiguration = field(default_factory=MappingConfiguration)
    output: OutputConfiguration = field(default_factory=OutputConfiguration)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ReconciliationConfiguration":
        """Build a configuration tree from a plain JSON-compatible dict.

        Raises:
            ConfigurationError: if ``data`` is not a mapping.
        """
        if data is not None and not isinstance(data, dict):
            raise ConfigurationError(
                "Configuration payload must be a JSON object.",
                details={"received_type": type(data).__name__},
            )
        data = data or {}
        return cls(
            source=SourceConfiguration.from_dict(data.get("source")),
            units=UnitConfiguration.from_dict(data.get("units")),
            tolerances=ToleranceConfiguration.from_dict(data.get("tolerances")),
            execution=ExecutionConfiguration.from_dict(data.get("execution")),
            mapping=MappingConfiguration.from_dict(data.get("mapping")),
            output=OutputConfiguration.from_dict(data.get("output")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source.to_dict(),
            "units": self.units.to_dict(),
            "tolerances": self.tolerances.to_dict(),
            "execution": self.execution.to_dict(),
            "mapping": self.mapping.to_dict(),
            "output": self.output.to_dict(),
        }
