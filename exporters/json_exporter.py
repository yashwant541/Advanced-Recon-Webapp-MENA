"""JSON export of a completed reconciliation run.

Purpose
-------
Serialize a completed :class:`ReconciliationRun` to JSON bytes for
downloads or API responses that need the full detail (as opposed to the
compact ``summary_dict()`` used for the WebApp's initial response). Never
reruns the reconciliation -- it only serializes an already-completed result.

Public contents
----------------
``export_to_json(run, *, indent=None)``.

Dependencies: standard library ``json`` only.
"""

from __future__ import annotations

import json

from iraq_recon.models.reconciliation import ReconciliationRun


def export_to_json(run: ReconciliationRun, *, indent: int | None = 2) -> bytes:
    """Serialize a completed run to JSON bytes.

    Args:
        run: A completed :class:`ReconciliationRun`.
        indent: Passed through to ``json.dumps``; ``None`` for compact output.

    Returns:
        UTF-8 encoded JSON bytes.
    """
    return json.dumps(run.to_dict(), indent=indent).encode("utf-8")
