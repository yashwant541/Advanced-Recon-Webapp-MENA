"""Enumerations and fixed vocabularies shared across the engine.

Purpose
-------
Centralize every controlled vocabulary (statement types, economic roles,
reconciliation statuses, diagnostic codes, etc.) so that no other module
hardcodes magic strings. Country-specific *values* (e.g. which account maps
to which Ayra category) belong in mapping/seed configuration, not here --
this module only defines the closed sets of labels the engine understands.

Public contents
----------------
StatementType, NaturalSide, EconomicRole, RowType, SheetClass, MappingMethod,
InclusionStatus, ReconciliationStatus, DiagnosticCode, Severity,
ControlSeverity, ControlStatus, ExportFormat -- all ``str`` enums so they
serialize cleanly to JSON and compare equal to plain strings.

Dependencies: standard library only (``enum``).
"""

from __future__ import annotations

from enum import Enum


class _StrEnum(str, Enum):
    """Base class giving ``str``-compatible, JSON-friendly enums."""

    def __str__(self) -> str:  # pragma: no cover - trivial
        return str(self.value)


class StatementType(_StrEnum):
    ASSET = "ASSET"
    LIABILITY = "LIABILITY"
    EQUITY = "EQUITY"
    INCOME = "INCOME"
    EXPENSE = "EXPENSE"
    OFF_BALANCE_SHEET = "OFF_BALANCE_SHEET"
    UNKNOWN = "UNKNOWN"


class NaturalSide(_StrEnum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"
    UNKNOWN = "UNKNOWN"


class EconomicRole(_StrEnum):
    ASSET_COST = "ASSET_COST"
    ASSET_WIP = "ASSET_WIP"
    ASSET_CLEARING = "ASSET_CLEARING"
    ACCUMULATED_DEPRECIATION = "ACCUMULATED_DEPRECIATION"
    ASSET_IMPAIRMENT = "ASSET_IMPAIRMENT"
    ORDINARY_ASSET = "ORDINARY_ASSET"
    ORDINARY_LIABILITY = "ORDINARY_LIABILITY"
    CONTRA_ASSET = "CONTRA_ASSET"
    CONTRA_LIABILITY = "CONTRA_LIABILITY"
    EQUITY = "EQUITY"
    INCOME = "INCOME"
    EXPENSE = "EXPENSE"
    OFF_BALANCE_SHEET_DEBIT = "OFF_BALANCE_SHEET_DEBIT"
    OFF_BALANCE_SHEET_CREDIT = "OFF_BALANCE_SHEET_CREDIT"
    INFORMATIONAL_ONLY = "INFORMATIONAL_ONLY"


class RowType(_StrEnum):
    POSTING = "POSTING"
    PARENT = "PARENT"
    SUBTOTAL = "SUBTOTAL"
    TOTAL = "TOTAL"
    GRAND_TOTAL = "GRAND_TOTAL"
    HEADER = "HEADER"
    BLANK = "BLANK"
    TEMPLATE = "TEMPLATE"
    UNKNOWN = "UNKNOWN"


class SheetClass(_StrEnum):
    ASSETS = "ASSETS"
    LIABILITIES = "LIABILITIES"
    EQUITY = "EQUITY"
    P_AND_L = "P_AND_L"
    OFF_BALANCE_SHEET = "OFF_BALANCE_SHEET"
    FINANCIAL_STATEMENT = "FINANCIAL_STATEMENT"
    SUPPORTING_SCHEDULE = "SUPPORTING_SCHEDULE"
    MAPPING = "MAPPING"
    UNKNOWN = "UNKNOWN"


class MappingMethod(_StrEnum):
    APPROVED_ACCOUNT = "APPROVED_ACCOUNT"
    APPROVED_LOCAL_GROUP = "APPROVED_LOCAL_GROUP"
    AYRA_SEMANTIC_CATEGORY = "AYRA_SEMANTIC_CATEGORY"
    IRAQ_REPORTING_BUCKET = "IRAQ_REPORTING_BUCKET"
    SUPPORTING_SCHEDULE = "SUPPORTING_SCHEDULE"
    DESCRIPTION_MATCH = "DESCRIPTION_MATCH"
    COMBINATION_MATCH = "COMBINATION_MATCH"
    RESIDUAL_INVESTIGATION = "RESIDUAL_INVESTIGATION"
    UNMAPPED = "UNMAPPED"


class InclusionStatus(_StrEnum):
    INCLUDE = "INCLUDE"
    EXCLUDE = "EXCLUDE"
    CONDITIONAL = "CONDITIONAL"


class ReconciliationStatus(_StrEnum):
    EXACT_MATCH = "EXACT_MATCH"
    PRECISION_MATCH = "PRECISION_MATCH"
    ROUNDING_MATCH = "ROUNDING_MATCH"
    PARTIAL_MATCH = "PARTIAL_MATCH"
    MATERIAL_BREAK = "MATERIAL_BREAK"
    MAPPING_DIFFERENCE = "MAPPING_DIFFERENCE"
    PRESENTATION_DIFFERENCE = "PRESENTATION_DIFFERENCE"
    UNIT_DIFFERENCE = "UNIT_DIFFERENCE"
    SIGN_DIFFERENCE = "SIGN_DIFFERENCE"
    SCHEDULE_DIFFERENCE = "SCHEDULE_DIFFERENCE"
    SOURCE_DATA_DIFFERENCE = "SOURCE_DATA_DIFFERENCE"
    UNMAPPED_ACCOUNT = "UNMAPPED_ACCOUNT"
    DUPLICATE_MAPPING = "DUPLICATE_MAPPING"
    OFF_BS_EXCLUSION = "OFF_BS_EXCLUSION"
    UNRESOLVED = "UNRESOLVED"


class DiagnosticCode(_StrEnum):
    HEADER_NOT_FOUND = "HEADER_NOT_FOUND"
    AMOUNT_PARSE_FAILED = "AMOUNT_PARSE_FAILED"
    ACCOUNT_NORMALIZATION_FAILED = "ACCOUNT_NORMALIZATION_FAILED"
    NON_POSTING_ROW_INCLUDED = "NON_POSTING_ROW_INCLUDED"
    PARENT_CHILD_DOUBLE_COUNT = "PARENT_CHILD_DOUBLE_COUNT"
    DUPLICATE_SOURCE_ROW = "DUPLICATE_SOURCE_ROW"
    DUPLICATE_MAPPING = "DUPLICATE_MAPPING"
    CONFLICTING_MAPPING = "CONFLICTING_MAPPING"
    UNMAPPED_ACCOUNT = "UNMAPPED_ACCOUNT"
    MISSING_PRESENTATION_SIGN = "MISSING_PRESENTATION_SIGN"
    UNIT_MISMATCH = "UNIT_MISMATCH"
    SIGN_MISMATCH = "SIGN_MISMATCH"
    MISSING_CONTRA_ACCOUNT = "MISSING_CONTRA_ACCOUNT"
    OFF_BS_MISCLASSIFICATION = "OFF_BS_MISCLASSIFICATION"
    SCHEDULE_BREAK = "SCHEDULE_BREAK"
    CURRENCY_BREAK = "CURRENCY_BREAK"
    MATURITY_BREAK = "MATURITY_BREAK"
    ROUNDING_DIFFERENCE = "ROUNDING_DIFFERENCE"
    PRECISION_DIFFERENCE = "PRECISION_DIFFERENCE"
    SNAPSHOT_MISMATCH = "SNAPSHOT_MISMATCH"
    SOURCE_DATA_DIFFERENCE = "SOURCE_DATA_DIFFERENCE"
    PROVISIONAL_COMBINATION_MATCH = "PROVISIONAL_COMBINATION_MATCH"


class Severity(_StrEnum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ControlStatus(_StrEnum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ExportFormat(_StrEnum):
    XLSX = "xlsx"
    JSON = "json"
    PROCESS_TRACE = "process_trace"


#: Ayra semantic categories (Level 2 of the three-level mapping design).
AYRA_CATEGORIES = frozenset(
    {
        "A-CBI",
        "A-CRR",
        "A-IGA",
        "A-IBA",
        "A-TB",
        "A-FA",
        "A-FA-CONTRA",
        "A-OA",
        "A-HOB",
        "L-CASA",
        "L-IGL-C",
        "L-IGL-F",
        "L-IBL",
        "L-MM-F",
        "L-PR",
        "SPOT",
        "OBS-Gtee",
        "OBS-Contra",
        "EQ-SC",
        "EQ-SR",
        "EQ-RE",
    }
)

#: Iraq reporting roll-up buckets (Level 3 of the three-level mapping design).
IRAQ_REPORTING_BUCKETS = frozenset(
    {
        "BALANCES_WITH_CENTRAL_BANK",
        "DEBIT_BALANCES_WITH_BANKS",
        "INVESTMENTS_IN_SECURITIES",
        "FIXED_ASSETS",
        "OTHER_ASSETS",
        "HEAD_OFFICE_AND_BRANCHES",
        "BANK_GROUP_CURRENT_LIABILITIES",
        "BANK_GROUP_TERM_LIABILITIES",
        "CUSTOMER_DEPOSITS",
        "CAPITAL_AND_RESERVES",
        "PROVISIONS",
        "SPOT_POSITION",
        "OFF_BALANCE_SHEET",
    }
)

#: Default Decimal quantum for currency amounts (2 decimal places).
DEFAULT_AMOUNT_QUANTUM = "0.01"

#: Default Decimal quantum for percentages (4 decimal places, i.e. bps).
DEFAULT_PERCENT_QUANTUM = "0.0001"
