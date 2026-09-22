"""Standard accounting-calculator interface and the generic bucket calculator.

Purpose
-------
Give every calculator in ``iraq_recon.calculators`` the same shape
(``calculate(records, reported_lines, context) -> CalculationResult``) and
provide one metadata-driven implementation, :class:`BucketCalculator`, that
every concrete calculator (Central Bank, fixed assets, deposits, ...)
configures rather than reimplements -- so account eligibility, unit
conversion, presentation-sign application, and lineage assembly are written
exactly once (spec section 7: "Avoid ... repeated parsing").

Public contents
----------------
``CalculatorContext`` -- per-run dependencies every calculator needs.
``AccountingCalculator`` -- abstract base defining the standard interface.
``BucketCalculator`` -- generic, metadata-driven implementation most
concrete calculators subclass or instantiate directly.

Dependencies: ``iraq_recon.mapping.local_bridge``, ``iraq_recon.rules.*``,
``iraq_recon.models.*``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Callable

from iraq_recon.mapping.local_bridge import LocalAccountBridge
from iraq_recon.models.calculation import CalculationContribution, CalculationResult
from iraq_recon.models.configuration import ToleranceConfiguration, UnitConfiguration
from iraq_recon.models.mapping import MappingRecord
from iraq_recon.models.source import StatementLineRecord, TrialBalanceRecord
from iraq_recon.normalization.row_classifier import is_summable
from iraq_recon.rules.account_role_rules import check_role_sign_consistency
from iraq_recon.rules.exclusion_rules import should_include_in_primary_totals
from iraq_recon.rules.formula_registry import get_formula_description
from iraq_recon.rules.presentation_rules import apply_presentation_sign
from iraq_recon.rules.sign_rules import detect_sign_mismatch
from iraq_recon.rules.tolerance_rules import classify_variance_by_tolerance
from iraq_recon.rules.unit_rules import compute_effective_unit_factor, convert_balance


@dataclass(frozen=True)
class CalculatorContext:
    """Per-run dependencies shared by every calculator invocation.

    Attributes:
        bridge: Resolved local-account-to-mapping lookup for the run's
            effective date.
        unit_config: File-level unit configuration (TB unit, FS unit,
            conversion factor).
        tolerances: Configured variance tolerances, used to attach a status
            to the calculator's own reported-vs-calculated comparison.
        run_date: The reconciliation run's effective date.
        mapping_records: All loaded mapping records, made available so a
            calculator can derive an accurate formula description from the
            actual approved mappings (see
            ``rules.formula_registry.get_formula_description``).
        extra: Free-form additional context (e.g. ``eligible_accounts`` for
            conditional inclusion -- see ``rules.exclusion_rules``).
    """

    bridge: LocalAccountBridge
    unit_config: UnitConfiguration
    tolerances: ToleranceConfiguration
    run_date: date | None = None
    mapping_records: tuple[MappingRecord, ...] = ()
    extra: dict[str, Any] = field(default_factory=dict)


class AccountingCalculator(ABC):
    """Standard interface every accounting calculator must implement.

    Attributes:
        line_code: The financial-statement line this calculator produces.
        iraq_reporting_bucket: The Level-3 reporting bucket this calculator
            reconciles.
    """

    line_code: str
    iraq_reporting_bucket: str

    @abstractmethod
    def calculate(
        self,
        records: list[TrialBalanceRecord],
        reported_lines: dict[str, StatementLineRecord],
        context: CalculatorContext,
    ) -> CalculationResult:
        """Calculate this calculator's line from trial-balance records.

        Args:
            records: Trial-balance records for the selected snapshot (any
                row type; only posting rows are summed).
            reported_lines: ``{line_code: StatementLineRecord}`` from the
                main financial statement, keyed as produced by
                ``ingestion.financial_statement_reader``.
            context: Shared per-run dependencies.

        Returns:
            A :class:`CalculationResult`.
        """
        raise NotImplementedError


def _default_formula_component(mapping_record: MappingRecord) -> str:
    return mapping_record.ayra_category


class BucketCalculator(AccountingCalculator):
    """Generic, metadata-driven calculator for one Iraq reporting bucket.

    Sums every posting trial-balance account whose approved mapping targets
    ``iraq_reporting_bucket`` and whose Ayra category is in
    ``allowed_ayra_categories``, applying each account's own unit factor and
    presentation sign from its mapping -- never a hardcoded sign or a
    residual/plug calculation.
    """

    def __init__(
        self,
        line_code: str,
        iraq_reporting_bucket: str,
        allowed_ayra_categories: frozenset[str] | set[str],
        *,
        accounting_explanation: str = "",
        formula_component_resolver: Callable[[MappingRecord], str] = _default_formula_component,
        apply_primary_inclusion_filter: bool = True,
    ) -> None:
        """Configure a generic bucket calculator.

        Args:
            line_code: Target financial-statement line code.
            iraq_reporting_bucket: Target Level-3 reporting bucket.
            allowed_ayra_categories: Ayra categories this calculator claims;
                an account mapped to the right bucket but a category outside
                this set is reported in ``excluded_accounts``, not summed.
            accounting_explanation: Plain-language explanation attached to
                the result.
            formula_component_resolver: Maps a mapping record to the
                ``formula_component`` label on its contribution (defaults to
                the Ayra category; fixed assets uses the economic role
                instead so cost/WIP/depreciation/impairment stay distinct).
            apply_primary_inclusion_filter: When ``True`` (default), accounts
                whose mapping excludes them from primary BS/P&L totals (see
                ``rules.exclusion_rules``) are excluded here too. Set
                ``False`` for the off-balance-sheet calculator itself, since
                OBS totals are a real total, just excluded from *other*
                calculators' primary totals.
        """
        self.line_code = line_code
        self.iraq_reporting_bucket = iraq_reporting_bucket
        self.allowed_ayra_categories = frozenset(allowed_ayra_categories)
        self.accounting_explanation = accounting_explanation
        self.formula_component_resolver = formula_component_resolver
        self.apply_primary_inclusion_filter = apply_primary_inclusion_filter

    def calculate(
        self,
        records: list[TrialBalanceRecord],
        reported_lines: dict[str, StatementLineRecord],
        context: CalculatorContext,
    ) -> CalculationResult:
        contributions: list[CalculationContribution] = []
        included_accounts: list[str] = []
        deducted_accounts: list[str] = []
        excluded_accounts: list[dict[str, Any]] = []
        warnings: list[str] = []

        for tb_record in records:
            if not is_summable(tb_record.row_type):
                continue

            mapping_record = context.bridge.get(tb_record.account_number)
            if mapping_record is None:
                continue

            if mapping_record.iraq_reporting_bucket != self.iraq_reporting_bucket:
                continue

            if mapping_record.ayra_category not in self.allowed_ayra_categories:
                excluded_accounts.append(
                    {
                        "account": tb_record.account_number,
                        "reason": (
                            f"ayra_category '{mapping_record.ayra_category}' not claimed by "
                            f"this calculator ({sorted(self.allowed_ayra_categories)})."
                        ),
                    }
                )
                continue

            if self.apply_primary_inclusion_filter and not should_include_in_primary_totals(
                mapping_record, context.extra
            ):
                excluded_accounts.append(
                    {
                        "account": tb_record.account_number,
                        "reason": "excluded by inclusion_status or off-balance-sheet classification.",
                    }
                )
                continue

            sign_warning = check_role_sign_consistency(mapping_record)
            if sign_warning:
                warnings.append(sign_warning)
            if detect_sign_mismatch(tb_record.normalized_balance, mapping_record.natural_side):
                warnings.append(
                    f"Account '{tb_record.account_number}' balance sign contradicts its "
                    f"mapped natural side ('{mapping_record.natural_side}')."
                )

            effective_factor = compute_effective_unit_factor(
                context.unit_config.conversion_factor, mapping_record.unit_factor
            )
            converted_amount = convert_balance(tb_record.normalized_balance, effective_factor)
            presented_amount = apply_presentation_sign(converted_amount, mapping_record)

            lineage = {
                "source_file": tb_record.source_file,
                "source_sheet": tb_record.source_sheet,
                "source_row": tb_record.source_row,
                "original_balance": str(tb_record.original_balance),
                "source_unit": tb_record.source_unit,
                "conversion_factor": str(effective_factor),
                "statement_type": str(mapping_record.statement_type),
                "natural_side": str(mapping_record.natural_side),
                "economic_role": str(mapping_record.economic_role),
                "ayra_category": mapping_record.ayra_category,
                "iraq_reporting_bucket": mapping_record.iraq_reporting_bucket,
                "schedule_code": mapping_record.schedule_code,
                "mapping_method": str(mapping_record.mapping_method),
                "mapping_confidence": mapping_record.mapping_confidence,
                "mapping_rationale": mapping_record.mapping_rationale,
            }

            contribution = CalculationContribution(
                line_code=self.line_code,
                account=tb_record.account_number,
                description=tb_record.account_description,
                converted_amount=converted_amount,
                presentation_sign=mapping_record.presentation_sign,
                presented_amount=presented_amount,
                formula_component=self.formula_component_resolver(mapping_record),
                source_lineage=lineage,
            )
            contributions.append(contribution)
            if mapping_record.presentation_sign == -1:
                deducted_accounts.append(tb_record.account_number)
            else:
                included_accounts.append(tb_record.account_number)

        calculated_amount = sum((c.presented_amount for c in contributions), Decimal("0"))

        formula = get_formula_description(self.iraq_reporting_bucket, list(context.mapping_records))

        reported_line = reported_lines.get(self.line_code)
        reported_amount = reported_line.reported_amount if reported_line else None

        variance: Decimal | None = None
        status: str | None = None
        if reported_amount is not None:
            variance = calculated_amount - reported_amount
            status = classify_variance_by_tolerance(variance, context.tolerances).value

        return CalculationResult(
            line_code=self.line_code,
            calculated_amount=calculated_amount,
            contributions=tuple(contributions),
            formula=formula,
            included_accounts=tuple(included_accounts),
            deducted_accounts=tuple(deducted_accounts),
            excluded_accounts=tuple(excluded_accounts),
            reported_amount=reported_amount,
            variance=variance,
            status=status,
            accounting_explanation=self.accounting_explanation,
            warnings=tuple(warnings),
        )
