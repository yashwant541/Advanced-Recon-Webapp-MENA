/* Iraq Reconciliation Engine -- Dataiku Standard WebApp frontend.
 *
 * Vanilla JS, no build step (matches how a Dataiku Standard WebApp's
 * body.html/style.css/app.js are served). Every call goes through the thin
 * backend.py, which in turn calls exactly one iraq_recon.api function per
 * route -- this file only renders responses and manages the in-browser
 * workflow state (which files are uploaded, which run is active). Nothing
 * is persisted here beyond the current page load; a refresh starts over.
 */

(function () {
  "use strict";

  // ---------------------------------------------------------------------
  // Backend URL helper -- Dataiku Standard WebApps expose
  // window.getWebAppBackendUrl(path) to build a correctly-prefixed URL to
  // this webapp's own backend. Fall back to a plain relative path so this
  // file also works when served standalone (e.g. local testing).
  // ---------------------------------------------------------------------

  function apiUrl(path) {
    if (typeof window.getWebAppBackendUrl === "function") {
      return window.getWebAppBackendUrl(path);
    }
    return path;
  }

  async function apiRequest(method, path, { json, formData } = {}) {
    const options = { method, headers: {} };
    if (formData) {
      options.body = formData;
    } else if (json !== undefined) {
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(json);
    }
    const response = await fetch(apiUrl(path), options);
    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      const body = await response.json();
      if (!response.ok) {
        const message = body.message || "Request failed.";
        throw new Error(message);
      }
      return body;
    }
    if (!response.ok) {
      throw new Error(`Request to ${path} failed with status ${response.status}.`);
    }
    return response; // caller handles binary/file responses itself
  }

  async function downloadFile(method, path, json, fallbackFilename) {
    const options = { method, headers: {} };
    if (json !== undefined) {
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(json);
    }
    const response = await fetch(apiUrl(path), options);
    if (!response.ok) {
      let message = `Download failed with status ${response.status}.`;
      try {
        const body = await response.json();
        message = body.message || message;
      } catch (e) { /* response wasn't JSON -- keep default message */ }
      throw new Error(message);
    }
    const blob = await response.blob();
    const disposition = response.headers.get("content-disposition") || "";
    const match = disposition.match(/filename=([^;]+)/);
    const filename = match ? match[1].trim() : fallbackFilename;
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  }

  // ---------------------------------------------------------------------
  // Application state (in-memory, this page load only)
  // ---------------------------------------------------------------------

  function generateSessionId() {
    if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
    // Fallback for browsers without crypto.randomUUID -- good enough for a
    // client-generated, per-page-load session key, not a security token.
    return "sess-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2);
  }

  // Assigned once, synchronously, at script load -- so every upload (even
  // several fired in quick succession before any response has returned)
  // shares the same session from the very first request. Assigning this
  // only after the first upload's response returned would let concurrent
  // uploads race into separate sessions.
  const state = {
    sessionId: generateSessionId(),
    uploads: { TRIAL_BALANCE: [], FINANCIAL_STATEMENT: [], MAPPING_LOCAL: [] },
    snapshotEvidence: [],
    selectedSnapshotId: null,
    runId: null,
  };

  const ANCHORS = [
    ["CENTRAL_BANK_CURRENT", "Central Bank current account"],
    ["STATUTORY_RESERVE", "Statutory reserve"],
    ["BANK_DEBIT_BALANCES", "Bank debit balances"],
    ["BANK_CREDIT_BALANCES", "Bank credit balances"],
    ["INVESTMENTS", "Investments"],
    ["HEAD_OFFICE_AND_BRANCHES", "Head Office & Branches"],
    ["FIXED_ASSET_COST", "Fixed asset cost"],
    ["ACCUMULATED_DEPRECIATION", "Accumulated depreciation"],
    ["OTHER_ASSETS", "Other assets"],
    ["CUSTOMER_DEPOSITS", "Customer deposits"],
    ["CAPITAL_AND_RESERVES", "Capital & reserves"],
  ];

  function el(id) { return document.getElementById(id); }

  function showError(message) {
    let banner = document.querySelector(".error-banner");
    if (!banner) {
      banner = document.createElement("div");
      banner.className = "error-banner";
      el("recon-app").insertBefore(banner, el("recon-app").firstChild.nextSibling);
    }
    banner.textContent = message;
    banner.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  function clearError() {
    const banner = document.querySelector(".error-banner");
    if (banner) banner.remove();
  }

  function statusBadge(status) {
    const cls = "status-" + String(status).toLowerCase();
    return `<span class="status-badge ${cls}">${status}</span>`;
  }

  function fmtAmount(value) {
    if (value === null || value === undefined || value === "") return "";
    const num = Number(value);
    if (Number.isNaN(num)) return String(value);
    return num.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function updateSessionIndicator() {
    el("session-indicator").textContent = state.sessionId
      ? `Session: ${state.sessionId} (in-memory, not persisted)`
      : "No session yet -- upload a file to start one";
  }

  // ---------------------------------------------------------------------
  // Step 1: upload
  // ---------------------------------------------------------------------

  function renderFileList(role) {
    const list = document.querySelector(`.file-list[data-list="${role}"]`);
    list.innerHTML = "";
    state.uploads[role].forEach((file) => {
      const li = document.createElement("li");
      const nameSpan = document.createElement("span");
      nameSpan.className = "file-name";
      nameSpan.textContent = file.filename;
      li.appendChild(nameSpan);

      const actions = document.createElement("span");
      actions.className = "file-actions";

      if (role === "TRIAL_BALANCE" || role === "FINANCIAL_STATEMENT") {
        const dlBtn = document.createElement("button");
        dlBtn.className = "btn btn-secondary btn-tiny";
        dlBtn.textContent = "Standardized";
        dlBtn.onclick = () => downloadStandardized(role, file);
        actions.appendChild(dlBtn);
      }
      li.appendChild(actions);
      list.appendChild(li);
    });
  }

  async function downloadStandardized(role, file) {
    clearError();
    const path = role === "TRIAL_BALANCE"
      ? "/api/standardize/trial-balance"
      : "/api/standardize/financial-statement";
    try {
      await downloadFile("POST", path, { session_id: state.sessionId, source_id: file.source_id },
        `standardized_${file.filename}.xlsx`);
    } catch (err) {
      showError(err.message);
    }
  }

  async function uploadFiles(role, fileListInput) {
    clearError();
    const files = Array.from(fileListInput.files || []);
    for (const file of files) {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("source_role", role);
      formData.append("session_id", state.sessionId);
      try {
        const result = await apiRequest("POST", "/api/files", { formData });
        state.uploads[role].push({ source_id: result.source_id, filename: result.filename });
        renderFileList(role);
        updateSessionIndicator();
      } catch (err) {
        showError(`Upload failed for '${file.name}': ${err.message}`);
      }
    }
    fileListInput.value = "";
  }

  function wireUploadSlots() {
    document.querySelectorAll(".upload-slot").forEach((slot) => {
      const role = slot.dataset.role;
      const input = slot.querySelector(".file-input");
      const button = slot.querySelector(".upload-btn");
      button.addEventListener("click", () => uploadFiles(role, input));
    });
  }

  // ---------------------------------------------------------------------
  // Step 2: mapping validation
  // ---------------------------------------------------------------------

  async function validateMapping() {
    clearError();
    if (!state.sessionId) { showError("Upload files first."); return; }
    try {
      const result = await apiRequest("POST", "/api/mapping/validate", { json: { session_id: state.sessionId } });
      el("mapping-summary").textContent =
        `${result.mapping_count} mapping record(s) loaded. Valid: ${result.is_valid ? "yes" : "no"}. `
        + `${result.issues.length} issue(s) found.`;

      const tbody = el("mapping-issues-table").querySelector("tbody");
      tbody.innerHTML = "";
      result.issues.forEach((issue) => {
        const tr = document.createElement("tr");
        tr.innerHTML = `<td>${statusBadge(issue.severity)}</td><td>${issue.issue_code}</td>`
          + `<td>${issue.local_account || ""}</td><td>${issue.description}</td>`;
        tbody.appendChild(tr);
      });
      el("mapping-issues-wrap").classList.toggle("hidden", result.issues.length === 0);
    } catch (err) {
      showError(err.message);
    }
  }

  // ---------------------------------------------------------------------
  // Step 3: snapshot comparison
  // ---------------------------------------------------------------------

  function renderAnchorInputs() {
    const grid = el("anchor-inputs");
    grid.innerHTML = "";
    ANCHORS.forEach(([code, label]) => {
      const wrapper = document.createElement("label");
      wrapper.innerHTML = `${label} <input type="text" data-anchor="${code}" placeholder="optional" />`;
      grid.appendChild(wrapper);
    });
  }

  function collectAnchorAmounts() {
    const amounts = {};
    document.querySelectorAll("#anchor-inputs input[data-anchor]").forEach((input) => {
      if (input.value.trim() !== "") {
        amounts[input.dataset.anchor] = input.value.trim();
      }
    });
    return amounts;
  }

  function buildConfiguration() {
    const schedulesRaw = el("cfg-schedules").value.trim();
    const scheduleCodes = schedulesRaw ? schedulesRaw.split(/[\s,]+/).filter(Boolean) : [];
    return {
      mapping: { effective_date: el("cfg-effective-date").value || null },
      tolerances: {
        precision: el("cfg-precision").value || "0.01",
        rounding: el("cfg-rounding").value || "1",
        materiality: el("cfg-materiality").value || "1000",
      },
      execution: { schedule_codes: scheduleCodes },
    };
  }

  async function compareSnapshots() {
    clearError();
    if (!state.sessionId) { showError("Upload files first."); return; }
    try {
      const result = await apiRequest("POST", "/api/snapshots/compare", {
        json: {
          session_id: state.sessionId,
          configuration: buildConfiguration(),
          anchor_reported_amounts: collectAnchorAmounts(),
        },
      });
      state.snapshotEvidence = result.candidates;
      state.selectedSnapshotId = result.recommended_snapshot_id;
      renderSnapshotTable();
    } catch (err) {
      showError(err.message);
    }
  }

  function renderSnapshotTable() {
    const tbody = el("snapshot-table").querySelector("tbody");
    tbody.innerHTML = "";
    state.snapshotEvidence.forEach((candidate) => {
      const filename = findUploadFilename(candidate.snapshot_id) || candidate.snapshot_id;
      const tr = document.createElement("tr");
      const checked = candidate.snapshot_id === state.selectedSnapshotId ? "checked" : "";
      tr.innerHTML = `
        <td><input type="radio" name="snapshot-choice" value="${candidate.snapshot_id}" ${checked} /></td>
        <td>${filename}${candidate.snapshot_id === state.snapshotEvidence[0].snapshot_id ? " (recommended)" : ""}</td>
        <td>${candidate.exact_match_count}</td>
        <td>${candidate.precision_match_count}</td>
        <td>${fmtAmount(candidate.total_absolute_variance)}</td>
        <td>${(Number(candidate.mapping_value_coverage) * 100).toFixed(1)}%</td>
      `;
      tbody.appendChild(tr);
    });
    tbody.querySelectorAll('input[name="snapshot-choice"]').forEach((radio) => {
      radio.addEventListener("change", (e) => { state.selectedSnapshotId = e.target.value; });
    });
    el("snapshot-results").classList.remove("hidden");
  }

  function findUploadFilename(sourceId) {
    for (const file of state.uploads.TRIAL_BALANCE) {
      if (file.source_id === sourceId) return file.filename;
    }
    return null;
  }

  // ---------------------------------------------------------------------
  // Step 4: run reconciliation
  // ---------------------------------------------------------------------

  async function runReconciliation() {
    clearError();
    if (!state.selectedSnapshotId) {
      if (state.uploads.TRIAL_BALANCE.length === 1) {
        state.selectedSnapshotId = state.uploads.TRIAL_BALANCE[0].source_id;
      } else {
        showError("Compare and select a trial-balance snapshot first.");
        return;
      }
    }
    el("run-status").textContent = "Running reconciliation...";
    try {
      const result = await apiRequest("POST", "/api/reconcile", {
        json: {
          session_id: state.sessionId,
          selected_tb_snapshot: state.selectedSnapshotId,
          configuration: buildConfiguration(),
        },
      });
      state.runId = result.run_id;
      el("run-status").textContent = `Run '${result.run_id}' completed.`;
      await loadResults();
    } catch (err) {
      el("run-status").textContent = "";
      showError(err.message);
    }
  }

  // ---------------------------------------------------------------------
  // Step 5: results
  // ---------------------------------------------------------------------

  async function loadResults() {
    el("section-results").classList.remove("hidden");
    const [summary, lineResultsResponse, schedulesAvailable] = await Promise.all([
      apiRequest("GET", `/api/runs/${state.runId}/summary`),
      apiRequest("GET", `/api/runs/${state.runId}/line-results`),
      Promise.resolve(true),
    ]);

    renderSummaryTiles(summary);
    renderLineResults(lineResultsResponse.lines);

    const controlsResponse = await apiRequest("POST", `/api/runs/${state.runId}/controls`, { json: {} });
    renderControls(controlsResponse.controls);

    const exceptionsResponse = await apiRequest("POST", `/api/runs/${state.runId}/exceptions`, { json: { limit: 200 } });
    renderExceptions(exceptionsResponse.exceptions);

    await renderSchedules(lineResultsResponse.lines);

    el("section-results").scrollIntoView({ behavior: "smooth" });
  }

  function renderSummaryTiles(summary) {
    const tiles = [
      ["Lines calculated", summary.line_count],
      ["Overall control status", summary.overall_control_status],
      ["Exceptions", summary.exception_count],
      ["Warnings", summary.warning_count],
      ["Selected snapshot", summary.selected_tb_snapshot],
    ];
    el("summary-tiles").innerHTML = tiles.map(([label, value]) => `
      <div class="tile"><div class="tile-value">${value}</div><div class="tile-label">${label}</div></div>
    `).join("");
  }

  function renderLineResults(lines) {
    const tbody = el("line-results-table").querySelector("tbody");
    tbody.innerHTML = "";
    lines.forEach((line) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><button class="btn btn-secondary btn-tiny" data-line="${line.line_code}">Details</button></td>
        <td>${line.line_description || line.line_code}</td>
        <td>${fmtAmount(line.reported_amount)}</td>
        <td>${fmtAmount(line.calculated_amount)}</td>
        <td>${fmtAmount(line.variance)}</td>
        <td>${statusBadge(line.status)}</td>
      `;
      tbody.appendChild(tr);
    });
    tbody.querySelectorAll("button[data-line]").forEach((button) => {
      button.addEventListener("click", () => showLineDetail(button.dataset.line));
    });
  }

  async function showLineDetail(lineCode) {
    clearError();
    const panel = el("line-detail-panel");
    panel.classList.remove("hidden");
    panel.innerHTML = "Loading...";
    try {
      const [lineDetail, calcDetail, traceResponse] = await Promise.all([
        apiRequest("POST", `/api/runs/${state.runId}/line-detail`, { json: { line_code: lineCode } }),
        apiRequest("POST", `/api/runs/${state.runId}/calculation-detail`, { json: { line_code: lineCode } }),
        apiRequest("POST", `/api/runs/${state.runId}/account-trace`, { json: { line_code: lineCode, limit: 500 } }),
      ]);

      const excludedList = calcDetail.excluded_accounts.map(
        (e) => `<li>${e.account}: ${e.reason}</li>`
      ).join("") || "<li>None</li>";
      const warningsList = calcDetail.warnings.map(
        (w) => `<li class="warning-item">${w}</li>`
      ).join("") || "<li>None</li>";
      const traceRows = traceResponse.entries.map((entry) => `
        <tr>
          <td>${entry.account}</td><td>${entry.description}</td>
          <td>${fmtAmount(entry.original_balance)}</td><td>${fmtAmount(entry.presented_amount)}</td>
          <td>${entry.mapping_method}</td><td>${entry.source_file} / ${entry.source_sheet} / row ${entry.source_row}</td>
        </tr>
      `).join("");

      panel.innerHTML = `
        <h4>${lineDetail.line_description || lineDetail.line_code} -- ${statusBadge(lineDetail.status)}</h4>
        <div class="detail-section">
          <strong>Formula:</strong> <span class="formula">${lineDetail.formula || "n/a"}</span><br/>
          Reported: ${fmtAmount(lineDetail.reported_amount)} &nbsp;|&nbsp;
          Calculated: ${fmtAmount(lineDetail.calculated_amount)} &nbsp;|&nbsp;
          Variance: ${fmtAmount(lineDetail.variance)}
          ${lineDetail.variance_percentage !== null ? " (" + (Number(lineDetail.variance_percentage) * 100).toFixed(2) + "%)" : ""}
        </div>
        <div class="detail-section">
          <strong>Included accounts:</strong> ${calcDetail.included_accounts.join(", ") || "None"}<br/>
          <strong>Deducted accounts:</strong> ${calcDetail.deducted_accounts.join(", ") || "None"}
        </div>
        <div class="detail-section">
          <strong>Excluded accounts (why):</strong>
          <ul>${excludedList}</ul>
        </div>
        <div class="detail-section">
          <strong>Warnings:</strong>
          <ul>${warningsList}</ul>
        </div>
        <div class="detail-section">
          <strong>Account trace (${traceResponse.total} account(s)):</strong>
          <table class="data-table">
            <thead><tr><th>Account</th><th>Description</th><th>Original</th><th>Presented</th><th>Mapping method</th><th>Source</th></tr></thead>
            <tbody>${traceRows}</tbody>
          </table>
        </div>
      `;
    } catch (err) {
      panel.innerHTML = "";
      showError(err.message);
    }
  }

  function renderControls(controls) {
    const tbody = el("controls-table").querySelector("tbody");
    tbody.innerHTML = controls.map((c) => `
      <tr>
        <td>${c.control_code}</td><td>${c.control_description}</td>
        <td>${statusBadge(c.status)}</td><td>${c.severity}</td>
      </tr>
    `).join("");
  }

  function renderExceptions(exceptions) {
    const tbody = el("exceptions-table").querySelector("tbody");
    tbody.innerHTML = exceptions.map((e) => `
      <tr>
        <td>${statusBadge(e.severity)}</td><td>${e.root_cause_code}</td>
        <td>${e.affected_account || e.affected_line || ""}</td>
        <td>${e.likely_cause}</td><td>${e.suggested_review_action}</td>
      </tr>
    `).join("");
  }

  async function renderSchedules(lines) {
    // Schedule codes aren't listed directly on the summary; re-derive from
    // the configuration's requested schedule codes, defaulting to the
    // common set the standard registry ships with.
    const scheduleCodesInput = el("cfg-schedules").value.trim();
    const codes = scheduleCodesInput
      ? scheduleCodesInput.split(/[\s,]+/).filter(Boolean)
      : ["SCHEDULE_3", "SCHEDULE_4_DEBIT", "SCHEDULE_4_CREDIT", "SCHEDULE_5"];

    const tbody = el("schedule-results-table").querySelector("tbody");
    tbody.innerHTML = "";
    for (const code of codes) {
      try {
        const schedule = await apiRequest("POST", `/api/runs/${state.runId}/schedule-detail`, {
          json: { schedule_code: code },
        });
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td>${schedule.schedule_description}</td>
          <td>${fmtAmount(schedule.schedule_total)}</td>
          <td>${fmtAmount(schedule.tb_total)}</td>
          <td>${fmtAmount(schedule.statement_total)}</td>
          <td>${statusBadge(schedule.status)}</td>
        `;
        tbody.appendChild(tr);
      } catch (err) {
        // Schedule not built for this run (e.g. not requested) -- skip silently.
      }
    }
  }

  function wireDownloadButtons() {
    document.querySelectorAll("[data-download]").forEach((button) => {
      button.addEventListener("click", async () => {
        clearError();
        const format = button.dataset.download;
        const extension = format === "json" ? "json" : "xlsx";
        try {
          await downloadFile(
            "POST", `/api/runs/${state.runId}/export`, { export_format: format },
            `reconciliation_${format}_${state.runId}.${extension}`
          );
        } catch (err) {
          showError(err.message);
        }
      });
    });
  }

  // ---------------------------------------------------------------------
  // Wire everything up
  // ---------------------------------------------------------------------

  document.addEventListener("DOMContentLoaded", () => {
    wireUploadSlots();
    renderAnchorInputs();
    wireDownloadButtons();
    updateSessionIndicator();

    el("btn-validate-mapping").addEventListener("click", validateMapping);
    el("btn-compare-snapshots").addEventListener("click", compareSnapshots);
    el("btn-run-reconciliation").addEventListener("click", runReconciliation);
  });
})();
