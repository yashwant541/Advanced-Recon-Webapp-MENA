"""Fixed assets calculator: gross cost to net carrying value.

Purpose
-------
Reconcile "Net Fixed Assets" (spec section 10.D and 25) as cost + eligible
WIP +/- approved clearing - accumulated depreciation - impairment, with
each component exposed separately via ``formula_component`` on every
contribution (driven by the account's ``economic_role``, since cost, WIP,
clearing, accumulated depreciation, and impairment share the same Ayra
categories (``A-FA`` / ``A-FA-CONTRA``) but different roles).

Formula: ``cost + WIP +/- approved clearing - accumulated depreciation -
impairment``.

Public contents: ``FixedAssetsCalculator``.
Dependencies: ``calculators.base``.
"""

from __future__ import annotations

from iraq_recon.calculators.base import BucketCalculator
from iraq_recon.models.mapping import MappingRecord

DEFAULT_LINE_CODE = "FIXED_ASSETS"
DEFAULT_BUCKET = "FIXED_ASSETS"
ALLOWED_CATEGORIES = frozenset({"A-FA", "A-FA-CONTRA"})


def _fixed_asset_component(mapping_record: MappingRecord) -> str:
    return str(mapping_record.economic_role).lower()


class FixedAssetsCalculator(BucketCalculator):
    """Sums approved fixed-asset accounts, exposing cost/WIP/clearing/
    depreciation/impairment as separate formula components."""

    def __init__(self, line_code: str = DEFAULT_LINE_CODE, iraq_reporting_bucket: str = DEFAULT_BUCKET) -> None:
        super().__init__(
            line_code=line_code,
            iraq_reporting_bucket=iraq_reporting_bucket,
            allowed_ayra_categories=ALLOWED_CATEGORIES,
            formula_component_resolver=_fixed_asset_component,
            accounting_explanation=(
                "Net Fixed Assets = asset cost + eligible WIP +/- approved "
                "clearing - accumulated depreciation - asset impairment. Each "
                "component's presentation sign comes from its own approved "
                "mapping, not a hardcoded formula."
            ),
        )
