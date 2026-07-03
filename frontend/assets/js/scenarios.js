(function (window, document) {
  "use strict";

  const API = window.EnergyAPI;
  const UI = window.EnergyUI;

  const state = {
    scenarios: [],
    selectedScenarioId: null,
    selectedScenario: null,
    selectedResult: null,
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

  function percent(value, digits = 1) {
    return `${formatNumber(value, digits)}%`;
  }

  function splitList(value) {
    if (!value) return [];
    return String(value)
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
  }

  function riskClass(level) {
    const normalized = String(level || "").toLowerCase();
    if (normalized === "critical") return "pill--critical";
    if (normalized === "high") return "pill--high";
    if (normalized === "medium" || normalized === "moderate") return "pill--moderate";
    return "pill--low";
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

  function getFormPayload() {
    return {
      name: qs("#scenario-name").value.trim(),
      scenario_type: qs("#scenario-type").value,
      trigger_description: qs("#scenario-trigger").value.trim(),
      impacted_corridors: splitList(qs("#scenario-corridors").value),
      impacted_suppliers: splitList(qs("#scenario-suppliers").value),
      duration_days: Number(qs("#scenario-duration").value || 0),
      disruption_severity_pct: Number(qs("#scenario-severity").value || 0),
      price_shock_pct: Number(qs("#scenario-price-shock").value || 0),
      tanker_delay_days: Number(qs("#scenario-delay").value || 0),
      reserve_usage_allowed: Boolean(qs("#scenario-reserve").checked),
      status: "ready",
    };
  }

  function normalizeScenarioEntry(entry) {
    if (entry && entry.scenario) {
      return {
        ...entry.scenario,
        result: entry.result || null,
        mitigation_urgency_level: entry.mitigation_urgency_level || null,
        most_affected_refineries: entry.most_affected_refineries || [],
      };
    }
    return {
      ...entry,
      result: entry?.result || null,
      mitigation_urgency_level: entry?.mitigation_urgency_level || null,
      most_affected_refineries: entry?.most_affected_refineries || [],
    };
  }

  function renderScenarioList() {
    const element = qs("#scenario-list");
    const countBadge = qs("#scenario-count-badge");
    if (!element) {
      return;
    }
    if (!state.scenarios.length) {
      element.innerHTML = UI.renderErrorState("No scenarios yet. Create one on the left.", "Reload");
      if (countBadge) countBadge.textContent = "0";
      return;
    }
    if (countBadge) countBadge.textContent = `${state.scenarios.length} saved`;
    element.innerHTML = state.scenarios
      .map((item) => {
        const scenario = normalizeScenarioEntry(item);
        const isActive = Number(scenario.id) === Number(state.selectedScenarioId);
        const result = scenario.result || {};
        return `
          <article class="scenario-card ${isActive ? "scenario-card--active" : ""}" data-scenario-id="${scenario.id}">
            <div class="scenario-card__head">
              <div>
                <strong>${UI.escapeHtml(scenario.name)}</strong>
                <p>${UI.escapeHtml(scenario.scenario_type)}</p>
              </div>
              <span class="pill ${riskClass(scenario.mitigation_urgency_level || result.mitigation_urgency_level)}">
                ${UI.escapeHtml(scenario.mitigation_urgency_level || result.mitigation_urgency_level || scenario.status || "ready")}
              </span>
            </div>
            <div class="scenario-card__meta">
              <span>Duration: ${UI.escapeHtml(formatNumber(scenario.duration_days, 0))} days</span>
              <span>Reserve: ${scenario.assumptions?.reserve_usage_allowed ? "Allowed" : "Blocked"}</span>
            </div>
            <div class="scenario-card__actions">
              <button class="btn btn-secondary" type="button" data-scenario-select="${scenario.id}">View</button>
              <button class="btn btn-primary" type="button" data-scenario-run="${scenario.id}">Run</button>
            </div>
          </article>
        `;
      })
      .join("");

    qsa("[data-scenario-select]", element).forEach((button) => {
      button.addEventListener("click", () => loadScenario(Number(button.dataset.scenarioSelect)));
    });
    qsa("[data-scenario-run]", element).forEach((button) => {
      button.addEventListener("click", () => runScenario(Number(button.dataset.scenarioRun)));
    });
  }

  function renderScenarioResult() {
    const details = qs("#scenario-result-details");
    if (!details) {
      return;
    }
    const result = state.selectedResult;
    if (!result) {
      details.innerHTML = UI.renderLoadingState("Select a scenario to see outputs.");
      setText("#scenario-supply-loss", "--");
      setText("#scenario-fuel-price", "--");
      setText("#scenario-urgency", "--");
      return;
    }

    setText("#scenario-supply-loss", percent(result.estimated_supply_loss_pct, 1));
    setText("#scenario-fuel-price", percent(result.fuel_price_impact_pct, 1));
    setText("#scenario-urgency", state.selectedScenario?.mitigation_urgency_level || result.mitigation_urgency_level || "--");

    const impactedRefineries = state.selectedResult?.most_affected_refineries || [];
    details.innerHTML = `
      <div class="scenario-result-summary">
        <div class="mini-table">
          <div class="mini-table__row"><span>Refinery utilization impact</span><strong>${percent(result.refinery_utilization_impact, 1)}</strong></div>
          <div class="mini-table__row"><span>Logistics cost impact</span><strong>${percent(result.logistics_cost_impact_pct, 1)}</strong></div>
          <div class="mini-table__row"><span>GDP stress estimate</span><strong>${percent(result.gdp_impact_estimate, 1)}</strong></div>
        </div>
        <div class="panel__divider"></div>
        <div class="scenario-result-summary__list">
          ${impactedRefineries.length
            ? impactedRefineries.map((item) => `
                <div class="data-row">
                  <div class="data-row__head">
                    <strong>${UI.escapeHtml(item.name)}</strong>
                    <span class="pill ${riskClass(item.risk_level)}">${UI.escapeHtml(item.risk_level)}</span>
                  </div>
                  <div class="data-row__meta">
                    <span>Stress ${UI.escapeHtml(formatNumber(item.stress_score, 1))}</span>
                    <span>${UI.escapeHtml(item.linked_port_name || "No linked port")}</span>
                  </div>
                </div>
              `).join("")
            : UI.renderErrorState("No refinery impacts available.", "Retry")}
        </div>
      </div>
    `;
  }

  function setText(selector, value) {
    const element = qs(selector);
    if (element) {
      element.textContent = value;
    }
  }

  function setButtonBusy(button, busy, label) {
    if (!button) {
      return;
    }
    button.disabled = busy;
    if (label) {
      button.textContent = label;
    }
  }

  function activeScenarioId() {
    return state.selectedScenarioId || state.scenarios[0]?.scenario?.id || state.scenarios[0]?.id || null;
  }

  async function fetchScenarioReport(scenarioId) {
    return API.postJson(`/reports/scenario-summary/${scenarioId}`, null);
  }

  function reportFileName(report, scenarioId) {
    const datePart = report?.generated_at ? new Date(report.generated_at).toISOString().slice(0, 10) : new Date().toISOString().slice(0, 10);
    const titlePart = window.EnergyReports ? window.EnergyReports.sanitizeFileName(report?.title || `scenario-${scenarioId}`) : `scenario-${scenarioId}`;
    return `${titlePart}-${datePart}.json`;
  }

  async function downloadScenarioReport() {
    const scenarioId = activeScenarioId();
    if (!scenarioId) {
      window.alert("Select or save a scenario first.");
      return;
    }
    const button = qs("[data-scenario-report-download]");
    const originalLabel = button ? button.textContent : "";
    try {
      setButtonBusy(button, true, "Downloading...");
      const report = await fetchScenarioReport(scenarioId);
      if (window.EnergyReports) {
        window.EnergyReports.downloadJsonReport(reportFileName(report, scenarioId), report);
      }
    } catch (error) {
      console.error("Failed to download scenario report", error);
      window.alert(error.message || "Unable to download scenario report.");
    } finally {
      setButtonBusy(button, false, originalLabel || "Download JSON");
    }
  }

  async function printScenarioReport() {
    const scenarioId = activeScenarioId();
    if (!scenarioId) {
      window.alert("Select or save a scenario first.");
      return;
    }
    const button = qs("[data-scenario-report-print]");
    const originalLabel = button ? button.textContent : "";
    let printWindow = null;
    try {
      setButtonBusy(button, true, "Preparing...");
      printWindow = window.EnergyReports
        ? window.EnergyReports.openPrintWindow({
            title: "Scenario Summary",
            loadingMessage: "Loading scenario summary...",
          })
        : window.open("", "_blank", "noopener,noreferrer");
      if (!printWindow) {
        throw new Error("Popup blocked. Please allow popups for printable reports.");
      }
      const report = await fetchScenarioReport(scenarioId);
      if (window.EnergyReports) {
        window.EnergyReports.renderPrintWindow(printWindow, report, {
          title: report.title || "Scenario Summary",
          subtitle: "Printable disruption simulation summary",
        });
      }
      window.setTimeout(() => {
        try {
          printWindow.focus();
          printWindow.print();
        } catch (error) {
          console.warn("Print dialog unavailable", error);
        }
      }, 250);
    } catch (error) {
      console.error("Failed to print scenario report", error);
      if (printWindow && !printWindow.closed) {
        printWindow.close();
      }
      window.alert(error.message || "Unable to open printable scenario report.");
    } finally {
      setButtonBusy(button, false, originalLabel || "Print summary");
    }
  }

  async function loadScenarios(preserveSelection = true) {
    setLoading("#scenario-list", "Loading scenarios...");
    try {
      const response = await API.getJson("/scenarios");
      state.scenarios = Array.isArray(response) ? response : [];
      if (!preserveSelection || !state.selectedScenarioId) {
        state.selectedScenarioId = state.scenarios[0]?.scenario?.id || state.scenarios[0]?.id || null;
      }
      renderScenarioList();
      if (state.selectedScenarioId) {
        await loadScenario(state.selectedScenarioId, { skipListRefresh: true });
      } else {
        state.selectedScenario = null;
        state.selectedResult = null;
        renderScenarioResult();
      }
    } catch (error) {
      console.error("Failed to load scenarios", error);
      setError("#scenario-list", error.message || "Unable to load scenarios.");
    }
  }

  async function loadScenario(scenarioId, options = {}) {
    try {
      const payload = await API.getJson(`/scenarios/${scenarioId}`);
      state.selectedScenarioId = scenarioId;
      state.selectedScenario = payload.scenario || payload;
      state.selectedResult = payload.result || null;
      if (!options.skipListRefresh) {
        renderScenarioList();
      }
      renderScenarioResult();
    } catch (error) {
      console.error("Failed to load scenario", error);
      setError("#scenario-result-details", error.message || "Unable to load scenario.");
    }
  }

  async function createScenario(event) {
    if (event) {
      event.preventDefault();
    }
    const payload = getFormPayload();
    try {
      const created = await API.postJson("/scenarios", payload);
      state.scenarios.unshift(created);
      state.selectedScenarioId = created.id || created.scenario?.id || null;
      renderScenarioList();
      if (state.selectedScenarioId) {
        await loadScenario(state.selectedScenarioId, { skipListRefresh: true });
      }
    } catch (error) {
      console.error("Failed to create scenario", error);
      window.alert(error.message || "Unable to create scenario.");
    }
  }

  async function runScenario(scenarioId) {
    try {
      setLoading("#scenario-result-details", "Running simulation...");
      const result = await API.postJson(`/scenarios/${scenarioId}/run`, {});
      if (state.selectedScenarioId === scenarioId) {
        state.selectedScenario = result.scenario || state.selectedScenario;
        state.selectedResult = result.result || null;
        renderScenarioResult();
      }
      await loadScenarios(true);
    } catch (error) {
      console.error("Failed to run scenario", error);
      setError("#scenario-result-details", error.message || "Unable to run scenario.");
    }
  }

  function bindActions() {
    const createButton = qs("[data-scenario-create]");
    const refreshButton = qs("[data-scenario-refresh]");
    const downloadButton = qs("[data-scenario-report-download]");
    const printButton = qs("[data-scenario-report-print]");
    const form = qs("#scenario-form");
    if (createButton) {
      createButton.addEventListener("click", createScenario);
    }
    if (refreshButton) {
      refreshButton.addEventListener("click", () => loadScenarios(false));
    }
    if (downloadButton) {
      downloadButton.addEventListener("click", downloadScenarioReport);
    }
    if (printButton) {
      printButton.addEventListener("click", printScenarioReport);
    }
    if (form) {
      form.addEventListener("submit", createScenario);
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    bindActions();
    loadScenarios(false);
  });
})(window, document);
