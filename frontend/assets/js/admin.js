(function (window, document) {
  "use strict";

  const API = window.EnergyAPI;
  const UI = window.EnergyUI;

  const state = {
    summary: null,
    auditLogs: [],
    scheduler: null,
  };

  function qs(selector, root = document) {
    return root.querySelector(selector);
  }

  function qsa(selector, root = document) {
    return Array.from(root.querySelectorAll(selector));
  }

  function formatNumber(value, digits = 0) {
    const number = Number(value);
    if (!Number.isFinite(number)) {
      return "--";
    }
    return number.toLocaleString(undefined, {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    });
  }

  function formatDateTime(value) {
    if (!value) {
      return "--";
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return String(value);
    }
    return date.toLocaleString();
  }

  function setText(selector, value) {
    const element = qs(selector);
    if (element) {
      element.textContent = value;
    }
  }

  function setLoading(selector, message) {
    const element = qs(selector);
    if (element) {
      element.innerHTML = UI.renderLoadingState(message);
    }
  }

  function setError(selector, message) {
    const element = qs(selector);
    if (element) {
      element.innerHTML = UI.renderErrorState(message, "Retry");
    }
  }

  function getSelectedSources() {
    return qsa('input[name="ingestion-source"]:checked').map((input) => input.value);
  }

  function getDemoMode() {
    const checkbox = qs("#admin-demo-mode");
    return Boolean(checkbox && checkbox.checked);
  }

  function refreshActionNote(message) {
    const element = qs("#admin-action-note");
    if (element && message) {
      element.textContent = message;
    }
  }

  function schedulerStatusLabel(scheduler) {
    if (!scheduler) {
      return "Unknown";
    }
    if (scheduler.running) {
      return "Running";
    }
    if (scheduler.enabled) {
      return "Enabled";
    }
    return "Disabled";
  }

  function schedulerBadgeClass(scheduler) {
    if (!scheduler) {
      return "badge";
    }
    if (scheduler.running) {
      return "badge badge--success";
    }
    if (scheduler.enabled) {
      return "badge badge--warning";
    }
    return "badge";
  }

  function flattenSummary(summary) {
    const counts = summary?.counts || {};
    const latestActivity = summary?.latest_activity || {};
    return {
      counts,
      latestActivity,
      generatedAt: summary?.generated_at || null,
    };
  }

  function renderSummary(summary) {
    const flat = flattenSummary(summary);
    const counts = flat.counts;
    const latestActivity = flat.latestActivity;
    const scheduler = summary?.scheduler || state.scheduler || null;

    setText("#admin-system-badge", schedulerStatusLabel(scheduler));

    const summaryElement = qs("#admin-system-summary");
    if (summaryElement) {
      const rows = [
        ["Users", counts.users],
        ["Audit logs", counts.audit_logs],
        ["Suppliers", counts.supplier_countries ?? counts.suppliers],
        ["Corridors", counts.corridors],
        ["Ports", counts.ports],
        ["Refineries", counts.refineries],
        ["Shipments", counts.shipments],
        ["Events", counts.events],
        ["Sanctions", counts.sanctions],
        ["Risk scores", counts.risk_scores],
        ["Scenarios", counts.scenarios],
        ["Recommendations", counts.recommendations],
        ["SPR plans", counts.spr_plans],
      ].filter(([, value]) => value !== undefined && value !== null);

      const latestRows = [
        ["Latest login", latestActivity.latest_login],
        ["Latest ingestion", latestActivity.latest_ingestion],
        ["Latest risk run", latestActivity.latest_risk_recompute],
        ["Latest scenario", latestActivity.latest_scenario],
        ["Latest recommendation", latestActivity.latest_recommendation],
        ["Latest SPR plan", latestActivity.latest_spr],
      ].filter(([, value]) => value !== undefined && value !== null);

      summaryElement.innerHTML = `
        ${rows
          .map(
            ([label, value]) => `
              <div class="mini-table__row">
                <span>${UI.escapeHtml(label)}</span>
                <strong>${UI.escapeHtml(formatNumber(value, 0))}</strong>
              </div>
            `,
          )
          .join("")}
        ${latestRows
          .map(
            ([label, value]) => `
              <div class="mini-table__row">
                <span>${UI.escapeHtml(label)}</span>
                <strong>${UI.escapeHtml(formatDateTime(value))}</strong>
              </div>
            `,
          )
          .join("")}
        <div class="mini-table__row">
          <span>Scheduler status</span>
          <strong>${UI.escapeHtml(schedulerStatusLabel(scheduler))}</strong>
        </div>
      `;
    }

    setText("#admin-metric-users", formatNumber(counts.users, 0));
    setText("#admin-metric-audit_logs", formatNumber(counts.audit_logs, 0));
    setText("#admin-metric-scheduler", schedulerStatusLabel(scheduler));
    setText("#admin-metric-latest_activity", formatDateTime(latestActivity.latest_login || flat.generatedAt));
  }

  function renderAuditLogs(response) {
    const items = Array.isArray(response?.items) ? response.items : [];
    state.auditLogs = items;

    const badge = qs("#admin-audit-count");
    if (badge) {
      badge.textContent = `${formatNumber(response?.total_count ?? items.length, 0)} total`;
    }

    const element = qs("#admin-audit-list");
    if (!element) {
      return;
    }

    if (!items.length) {
      element.innerHTML = `
        <div class="panel state-card state-card--loading">
          <strong>No audit logs</strong>
          <p>The system has not recorded any auditable activity yet.</p>
        </div>
      `;
      return;
    }

    element.innerHTML = items
      .map((item) => {
        const meta = item.metadata_json || {};
        const metaSummary = Object.entries(meta)
          .slice(0, 3)
          .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(", ") : typeof value === "object" ? JSON.stringify(value) : value}`)
          .join(" | ");

        return `
          <div class="audit-row">
            <div>
              <strong>${UI.escapeHtml(item.action)}</strong>
              <div>${UI.escapeHtml(item.entity_type)} / ${UI.escapeHtml(item.entity_id)}</div>
            </div>
            <div>
              <strong>${UI.escapeHtml(item.user_email || `User #${item.user_id ?? "n/a"}`)}</strong>
              <div>${UI.escapeHtml(formatDateTime(item.created_at))}</div>
            </div>
            <div>
              <span>${UI.escapeHtml(metaSummary || "No metadata")}</span>
            </div>
          </div>
        `;
      })
      .join("");
  }

  async function loadSummary() {
    setLoading("#admin-system-summary", "Loading system summary...");
    try {
      const summary = await API.getJson("/admin/system-summary");
      state.summary = summary;
      renderSummary(summary);
      setText("#admin-system-badge", schedulerStatusLabel(summary.scheduler || state.scheduler));
    } catch (error) {
      console.error("Failed to load system summary", error);
      setError("#admin-system-summary", error.message || "Unable to load system summary.");
      setText("#admin-system-badge", "Unavailable");
    }
  }

  async function loadAuditLogs() {
    setLoading("#admin-audit-list", "Loading audit logs...");
    try {
      const response = await API.getJson("/admin/audit-logs?limit=12&offset=0");
      renderAuditLogs(response);
    } catch (error) {
      console.error("Failed to load audit logs", error);
      setError("#admin-audit-list", error.message || "Unable to load audit logs.");
      setText("#admin-audit-count", "Unavailable");
    }
  }

  async function loadJobStatus() {
    try {
      const status = await API.getJson("/admin/jobs/status");
      state.scheduler = status;
      if (state.summary) {
        renderSummary(state.summary);
      } else {
        setText("#admin-metric-scheduler", schedulerStatusLabel(status));
        setText("#admin-system-badge", schedulerStatusLabel(status));
      }
    } catch (error) {
      console.warn("Failed to load scheduler status", error);
    }
  }

  async function runIngestion() {
    const sources = getSelectedSources();
    const demoMode = getDemoMode();
    const button = qs("[data-admin-run-ingestion]");
    const previousLabel = button ? button.textContent : "";
    if (button) {
      button.disabled = true;
      button.textContent = "Running...";
    }
    setText("#admin-ingestion-status", "Running");
    refreshActionNote(`Running ingestion for ${sources.length ? sources.join(", ") : "all sources"}${demoMode ? " in demo mode" : ""}.`);

    try {
      const response = await API.postJson("/admin/run-ingestion", {
        sources,
        demo_mode: demoMode,
      });
      const successCount = Number(response.success_count || 0);
      const failureCount = Number(response.failure_count || 0);
      setText("#admin-ingestion-status", `${successCount} success / ${failureCount} failed`);
      refreshActionNote(`Ingestion finished with ${successCount} successful source runs and ${failureCount} failures.`);
      await Promise.all([loadSummary(), loadAuditLogs(), loadJobStatus()]);
    } catch (error) {
      console.error("Failed to run ingestion", error);
      setText("#admin-ingestion-status", "Failed");
      refreshActionNote(error.message || "Ingestion failed.");
    } finally {
      if (button) {
        button.disabled = false;
        button.textContent = previousLabel || "Run ingestion";
      }
    }
  }

  async function recomputeRisk() {
    const button = qs("[data-admin-recompute-risk]");
    const previousLabel = button ? button.textContent : "";
    if (button) {
      button.disabled = true;
      button.textContent = "Recomputing...";
    }
    setText("#admin-risk-status", "Running");
    refreshActionNote("Recomputing risk scores across corridors, suppliers, shipments, and refineries.");

    try {
      const response = await API.postJson("/admin/jobs/recompute-risk", null);
      setText("#admin-risk-status", response.status || "success");
      refreshActionNote(`Risk recomputation completed at ${formatDateTime(response.finished_at)}.`);
      await Promise.all([loadSummary(), loadAuditLogs(), loadJobStatus()]);
    } catch (error) {
      console.error("Failed to recompute risk", error);
      setText("#admin-risk-status", "Failed");
      refreshActionNote(error.message || "Risk recomputation failed.");
    } finally {
      if (button) {
        button.disabled = false;
        button.textContent = previousLabel || "Recompute risk";
      }
    }
  }

  async function seedDemo() {
    const button = qs("[data-admin-seed]");
    const previousLabel = button ? button.textContent : "";
    if (button) {
      button.disabled = true;
      button.textContent = "Seeding...";
    }
    setText("#admin-seed-status", "Running");
    refreshActionNote("Seeding demo data and refreshing summary panels.");

    try {
      const response = await API.postJson("/admin/seed-demo", null);
      setText("#admin-seed-status", "Completed");
      refreshActionNote(response.message || "Demo data seeded.");
      await Promise.all([loadSummary(), loadAuditLogs(), loadJobStatus()]);
    } catch (error) {
      console.error("Failed to seed demo data", error);
      setText("#admin-seed-status", "Failed");
      refreshActionNote(error.message || "Demo seed failed.");
    } finally {
      if (button) {
        button.disabled = false;
        button.textContent = previousLabel || "Seed demo";
      }
    }
  }

  function bindActions() {
    const refreshButton = qs("[data-admin-refresh]");
    const runIngestionButton = qs("[data-admin-run-ingestion]");
    const recomputeButton = qs("[data-admin-recompute-risk]");
    const seedButton = qs("[data-admin-seed]");
    const refreshJobsButton = qs("[data-admin-refresh-jobs]");

    if (refreshButton) {
      refreshButton.addEventListener("click", async () => {
        await Promise.all([loadSummary(), loadAuditLogs(), loadJobStatus()]);
      });
    }
    if (runIngestionButton) {
      runIngestionButton.addEventListener("click", runIngestion);
    }
    if (recomputeButton) {
      recomputeButton.addEventListener("click", recomputeRisk);
    }
    if (seedButton) {
      seedButton.addEventListener("click", seedDemo);
    }
    if (refreshJobsButton) {
      refreshJobsButton.addEventListener("click", loadJobStatus);
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    bindActions();
    Promise.all([loadSummary(), loadAuditLogs(), loadJobStatus()]);
  });
})(window, document);
