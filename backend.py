"""Thin Dataiku WebApp backend for the Iraq Category Formula reconciliation engine.

This file is the Python backend of a Dataiku Standard WebApp. It contains
NO accounting logic, NO Excel parsing, NO mapping rules, and NO Dataiku
dataset/folder-id knowledge beyond what a request payload supplies. Every
route:

    1. validates the request payload's required fields;
    2. calls exactly one ``iraq_recon.api`` function;
    3. returns a compact JSON response, or a file download for export routes;
    4. lets ``iraq_recon.exceptions.ReconError`` subclasses fall through to
       the error handler below, which is the only place HTTP status codes
       are decided.

Everything is transient -- NO Dataiku managed folder or dataset is read or
written by this backend. A file the user uploads lives only in this
process's memory for the lifetime of their browser session (the small
``_SESSIONS`` store below, keyed by a caller-issued ``session_id``); every
output (the reconciliation result, the standardized trial balance/
submission, and the "middle process" trace) is generated on demand and
streamed straight back as a file download. Nothing is left behind on disk
or in a managed folder after the response is sent. Completed reconciliation
runs are held the same way, in ``iraq_recon.api``'s in-memory run
repository -- they do not survive a WebApp backend restart, by design.

Dataiku supplies the Flask ``app`` object for a Standard WebApp backend;
this file never constructs one itself except when imported standalone
(e.g. under pytest) for testing.
"""

from __future__ import annotations

import sys
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any

# Dataiku adds a project's lib/python to sys.path automatically; this only
# matters when the file is imported standalone (outside a Dataiku kernel),
# e.g. by this project's own tests.
_LIB_PYTHON = Path(__file__).resolve().parent.parent / "lib" / "python"
if str(_LIB_PYTHON) not in sys.path and (_LIB_PYTHON / "iraq_recon").exists():
    sys.path.insert(0, str(_LIB_PYTHON))

from flask import jsonify, request  # noqa: E402

from iraq_recon import api  # noqa: E402
from iraq_recon.exceptions import ReconError, ValidationError  # noqa: E402
from iraq_recon.models.configuration import ReconciliationConfiguration  # noqa: E402
from iraq_recon.models.source import SourceFile  # noqa: E402

try:
    app  # type: ignore[used-before-def]  # noqa: B018 -- supplied by the Dataiku webapp kernel
except NameError:  # pragma: no cover - only true outside a Dataiku kernel
    from flask import Flask

    app = Flask(__name__)


# ---------------------------------------------------------------------------
# Request-scoped session store (uploaded files + loaded mappings/TBs).
# Not a replacement for the run repository -- see module docstring.
# ---------------------------------------------------------------------------

_SESSIONS: dict[str, dict[str, Any]] = {}


def _get_session(session_id: str) -> dict[str, Any]:
    if session_id not in _SESSIONS:
        raise ValidationError(
            f"Unknown session_id '{session_id}'. Upload files via /api/files first.",
            details={"session_id": session_id},
        )
    return _SESSIONS[session_id]


def _require_fields(payload: dict[str, Any], *fields: str) -> None:
    missing = [field for field in fields if field not in payload or payload[field] in (None, "")]
    if missing:
        raise ValidationError(
            f"Missing required field(s): {', '.join(missing)}.",
            details={"missing_fields": missing},
        )


_XLSX_MIMETYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_JSON_MIMETYPE = "application/json"


def _file_response(content: bytes, *, filename: str, mimetype: str):
    """Stream a generated file straight back as a download -- never written
    to disk or a managed folder."""
    from flask import Response

    return Response(
        content,
        mimetype=mimetype,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.errorhandler(ReconError)
def handle_reconciliation_error(error: ReconError):
    return jsonify(error.to_dict()), error.http_status


# ---------------------------------------------------------------------------
# File upload and inspection
# ---------------------------------------------------------------------------


@app.route("/api/files", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        raise ValidationError("No file was uploaded under the 'file' field.")

    uploaded = request.files["file"]
    source_role = request.form.get("source_role", "")
    source_unit = request.form.get("source_unit", "IQD")
    session_id = request.form.get("session_id") or str(uuid.uuid4())

    if not source_role:
        raise ValidationError("Missing required field: source_role.")

    content = uploaded.read()
    source_id = str(uuid.uuid4())
    source_file = SourceFile(
        source_id=source_id,
        filename=uploaded.filename or "upload.xlsx",
        file_type=(uploaded.filename or "").rsplit(".", 1)[-1].lower(),
        source_role=source_role,
        content=content,
        source_unit=source_unit,
    )

    session = _SESSIONS.setdefault(session_id, {"source_files": {}})
    session["source_files"][source_id] = source_file

    return jsonify(
        {
            "session_id": session_id,
            "source_id": source_id,
            "filename": source_file.filename,
            "source_role": source_role,
            "size_bytes": len(content),
        }
    )


@app.route("/api/inspect", methods=["POST"])
def inspect():
    payload = request.get_json(silent=True) or {}
    _require_fields(payload, "session_id", "source_id")

    session = _get_session(payload["session_id"])
    source_file = session["source_files"].get(payload["source_id"])
    if source_file is None:
        raise ValidationError(f"Unknown source_id '{payload['source_id']}' for this session.")

    inspection = api.inspect_workbook(source_file.filename, source_file.content, payload.get("sheet_names"))
    return jsonify(inspection.to_dict())


# ---------------------------------------------------------------------------
# Standardization -- download the normalized data before committing to a
# full reconciliation run, so a reviewer can sanity-check how the engine
# parsed their upload.
# ---------------------------------------------------------------------------


def _source_file_or_error(session: dict[str, Any], source_id: str):
    source_file = session["source_files"].get(source_id)
    if source_file is None:
        raise ValidationError(f"Unknown source_id '{source_id}' for this session.")
    return source_file


@app.route("/api/standardize/trial-balance", methods=["POST"])
def standardize_trial_balance():
    payload = request.get_json(silent=True) or {}
    _require_fields(payload, "session_id", "source_id")

    session = _get_session(payload["session_id"])
    source_file = _source_file_or_error(session, payload["source_id"])

    candidates, warnings = api.load_trial_balances([source_file])
    records = candidates[source_file.source_id]
    workbook_bytes = api.export_standardized_trial_balance(records)

    return _file_response(
        workbook_bytes,
        filename=f"standardized_trial_balance_{source_file.filename}.xlsx",
        mimetype=_XLSX_MIMETYPE,
    )


@app.route("/api/standardize/financial-statement", methods=["POST"])
def standardize_financial_statement():
    payload = request.get_json(silent=True) or {}
    _require_fields(payload, "session_id", "source_id")

    session = _get_session(payload["session_id"])
    source_file = _source_file_or_error(session, payload["source_id"])

    reported_lines, warnings = api.load_financial_statement(source_file)
    workbook_bytes = api.export_standardized_financial_statement(list(reported_lines.values()))

    return _file_response(
        workbook_bytes,
        filename=f"standardized_submission_{source_file.filename}.xlsx",
        mimetype=_XLSX_MIMETYPE,
    )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


@app.route("/api/validate", methods=["POST"])
def validate():
    payload = request.get_json(silent=True) or {}
    session_id = payload.get("session_id")
    source_files = list(_get_session(session_id)["source_files"].values()) if session_id else None

    validation = api.validate_inputs(payload.get("configuration"), source_files)
    return jsonify(validation.to_dict())


@app.route("/api/mapping/validate", methods=["POST"])
def validate_mapping():
    payload = request.get_json(silent=True) or {}
    _require_fields(payload, "session_id")

    session = _get_session(payload["session_id"])
    mapping_files = [
        sf for sf in session["source_files"].values() if sf.source_role.startswith("MAPPING")
    ]
    if not mapping_files:
        raise ValidationError("No uploaded mapping source files found for this session.")

    mapping_records, load_issues = api.load_mapping_files(mapping_files)
    validation = api.validate_mappings(mapping_records)

    session["mappings"] = mapping_records
    session["mapping_load_issues"] = load_issues

    response = validation.to_dict()
    response["load_issues"] = load_issues
    response["mapping_count"] = len(mapping_records)
    return jsonify(response)


# ---------------------------------------------------------------------------
# Snapshot comparison
# ---------------------------------------------------------------------------


@app.route("/api/snapshots/compare", methods=["POST"])
def compare_snapshots():
    payload = request.get_json(silent=True) or {}
    _require_fields(payload, "session_id", "configuration")

    session = _get_session(payload["session_id"])
    mappings = session.get("mappings")
    if not mappings:
        raise ValidationError("Load and validate mappings via /api/mapping/validate first.")

    tb_files = [sf for sf in session["source_files"].values() if sf.source_role == "TRIAL_BALANCE"]
    if not tb_files:
        raise ValidationError("No uploaded trial-balance source files found for this session.")

    configuration = ReconciliationConfiguration.from_dict(payload["configuration"])
    candidates, warnings = api.load_trial_balances(tb_files)
    session["tb_candidates"] = candidates
    session["configuration"] = configuration

    anchor_reported_amounts = {
        anchor_code: Decimal(str(amount))
        for anchor_code, amount in (payload.get("anchor_reported_amounts") or {}).items()
    }
    evidence = api.compare_tb_snapshots(
        candidates, mappings, configuration,
        anchor_reported_amounts=anchor_reported_amounts,
    )
    recommended = api.select_best_snapshot(evidence)

    return jsonify(
        {
            "recommended_snapshot_id": recommended,
            "candidates": [e.to_dict() for e in evidence],
            "warnings": {source_id: w for source_id, w in warnings.items() if w},
        }
    )


# ---------------------------------------------------------------------------
# Reconciliation
# ---------------------------------------------------------------------------


@app.route("/api/reconcile", methods=["POST"])
def reconcile():
    payload = request.get_json(silent=True) or {}
    _require_fields(payload, "session_id", "selected_tb_snapshot")

    session = _get_session(payload["session_id"])
    mappings = session.get("mappings")
    tb_candidates = session.get("tb_candidates")
    if not mappings or not tb_candidates:
        raise ValidationError(
            "Run /api/mapping/validate and /api/snapshots/compare before /api/reconcile."
        )

    selected_tb_snapshot = payload["selected_tb_snapshot"]
    trial_balance = tb_candidates.get(selected_tb_snapshot)
    if trial_balance is None:
        raise ValidationError(f"Unknown selected_tb_snapshot '{selected_tb_snapshot}'.")

    fs_files = [sf for sf in session["source_files"].values() if sf.source_role == "FINANCIAL_STATEMENT"]
    if not fs_files:
        raise ValidationError("No uploaded financial-statement source file found for this session.")
    financial_statement, fs_warnings = api.load_financial_statement(fs_files[0])

    configuration = session.get("configuration") or ReconciliationConfiguration.from_dict(
        payload.get("configuration")
    )

    run = api.run_reconciliation(
        trial_balance=trial_balance,
        financial_statement=financial_statement,
        mappings=mappings,
        configuration=configuration,
        run_id=payload.get("run_id"),
        selected_tb_snapshot=selected_tb_snapshot,
        line_descriptions=payload.get("line_descriptions"),
        warnings=tuple(fs_warnings),
    )
    return jsonify(run.summary_dict())


@app.route("/api/runs/<run_id>/summary", methods=["GET"])
def get_run_summary(run_id: str):
    return jsonify(api.get_run_summary(run_id))


@app.route("/api/runs/<run_id>/line-results", methods=["GET"])
def list_line_results(run_id: str):
    """Every line's summary numbers (small, fixed-size list) -- the initial
    results table. Full per-line/per-account detail is loaded on demand via
    /line-detail, /calculation-detail, and /account-trace."""
    lines = api.list_line_results(run_id)
    return jsonify({"lines": [line.to_dict() for line in lines]})


@app.route("/api/runs/<run_id>/line-detail", methods=["POST"])
def get_line_detail(run_id: str):
    payload = request.get_json(silent=True) or {}
    _require_fields(payload, "line_code")
    line = api.get_line_breakdown(run_id, payload["line_code"])
    return jsonify(line.to_dict())


@app.route("/api/runs/<run_id>/schedule-detail", methods=["POST"])
def get_schedule_detail(run_id: str):
    payload = request.get_json(silent=True) or {}
    _require_fields(payload, "schedule_code")
    schedule = api.get_schedule_reconciliation(run_id, payload["schedule_code"])
    return jsonify(schedule.to_dict())


@app.route("/api/runs/<run_id>/account-trace", methods=["POST"])
def get_account_trace(run_id: str):
    payload = request.get_json(silent=True) or {}
    entries, total = api.get_account_trace(
        run_id,
        line_code=payload.get("line_code"),
        account=payload.get("account"),
        offset=int(payload.get("offset", 0)),
        limit=int(payload.get("limit", 100)),
    )
    return jsonify({"entries": [e.to_dict() for e in entries], "total": total})


@app.route("/api/runs/<run_id>/exceptions", methods=["POST"])
def get_exceptions(run_id: str):
    payload = request.get_json(silent=True) or {}
    exceptions, total = api.get_exceptions(
        run_id,
        severity=payload.get("severity"),
        offset=int(payload.get("offset", 0)),
        limit=int(payload.get("limit", 100)),
    )
    return jsonify({"exceptions": [e.to_dict() for e in exceptions], "total": total})


@app.route("/api/runs/<run_id>/controls", methods=["POST"])
def get_controls(run_id: str):
    controls = api.get_control_results(run_id)
    return jsonify({"controls": [c.to_dict() for c in controls]})


@app.route("/api/runs/<run_id>/calculation-detail", methods=["POST"])
def get_calculation_detail(run_id: str):
    """Return the raw calculator output behind one line: formula, included/
    deducted/excluded accounts with reasons, and warnings -- the "show how
    the reconciliation is working" detail behind a line's summary numbers."""
    payload = request.get_json(silent=True) or {}
    _require_fields(payload, "line_code")
    calculation = api.get_calculation_detail(run_id, payload["line_code"])
    return jsonify(calculation.to_dict())


@app.route("/api/runs/<run_id>/export", methods=["POST"])
def export_run(run_id: str):
    payload = request.get_json(silent=True) or {}
    export_format = payload.get("export_format", "xlsx")

    run = api.get_full_run(run_id)
    export_bytes = api.export_reconciliation(run, export_format)
    extension = "json" if export_format == "json" else "xlsx"
    mimetype = _JSON_MIMETYPE if export_format == "json" else _XLSX_MIMETYPE

    return _file_response(
        export_bytes, filename=f"reconciliation_{export_format}_{run_id}.{extension}", mimetype=mimetype
    )
