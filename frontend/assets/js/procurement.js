(function (window, document) {
  "use strict";

  const API = window.EnergyAPI;
  const UI = window.EnergyUI;

  const state = {
    recommendations: [],
    selectedId: null,
    selectedRecommendation: null,
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

  function activeRecommendationId() {
    return state.selectedId || state.recommendations[0]?.id || null;
  }

  async function fetchRecommendationReport(recommendationId) {
    return API.postJson(`/reports/procurement-summary/${recommendationId}`, null);
  }

  function reportFileName(report, recommendationId) {
    const datePart = report?.generated_at ? new Date(report.generated_at).toISOString().slice(0, 10) : new Date().toISOString().slice(0, 10);
    const titlePart = window.EnergyReports ? window.EnergyReports.sanitizeFileName(report?.title || `recommendation-${recommendationId}`) : `recommendation-${recommendationId}`;
    return `${titlePart}-${datePart}.json`;
  }

  async function downloadRecommendationReport() {
    const recommendationId = activeRecommendationId();
    if (!recommendationId) {
      window.alert("Select or generate a recommendation first.");
      return;
    }
    const button = qs("[data-procurement-report-download]");
    const originalLabel = button ? button.textContent : "";
    try {
      setButtonBusy(button, true, "Downloading...");
      const report = await fetchRecommendationReport(recommendationId);
      if (window.EnergyReports) {
        window.EnergyReports.downloadJsonReport(reportFileName(report, recommendationId), report);
      }
    } catch (error) {
      console.error("Failed to download procurement report", error);
      window.alert(error.message || "Unable to download procurement report.");
    } finally {
      setButtonBusy(button, false, originalLabel || "Download JSON");
    }
  }

  async function printRecommendationReport() {
    const recommendationId = activeRecommendationId();
    if (!recommendationId) {
      window.alert("Select or generate a recommendation first.");
      return;
    }
    const button = qs("[data-procurement-report-print]");
    const originalLabel = button ? button.textContent : "";
    let printWindow = null;
    try {
      setButtonBusy(button, true, "Preparing...");
      printWindow = window.EnergyReports
        ? window.EnergyReports.openPrintWindow({
            title: "Procurement Summary",
            loadingMessage: "Loading procurement summary...",
          })
        : window.open("", "_blank", "noopener,noreferrer");
      if (!printWindow) {
        throw new Error("Popup blocked. Please allow popups for printable reports.");
      }
      const report = await fetchRecommendationReport(recommendationId);
      if (window.EnergyReports) {
        window.EnergyReports.renderPrintWindow(printWindow, report, {
          title: report.title || "Procurement Summary",
          subtitle: "Printable procurement recommendation summary",
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
      console.error("Failed to print procurement report", error);
      if (printWindow && !printWindow.closed) {
        printWindow.close();
      }
      window.alert(error.message || "Unable to open printable procurement report.");
    } finally {
      setButtonBusy(button, false, originalLabel || "Print summary");
    }
  }

  function getFilters() {
    return {
      target_scope: qs("#procurement-scope").value,
      scenario_id: qs("#procurement-scenario-id").value ? Number(qs("#procurement-scenario-id").value) : null,
      refinery_id: qs("#procurement-refinery-id").value ? Number(qs("#procurement-refinery-id").value) : null,
      top_n: Number(qs("#procurement-top-n").value || 5),
      candidate_suppliers_limit: Number(qs("#procurement-supplier-limit").value || 8),
      candidate_corridors_limit: Number(qs("#procurement-corridor-limit").value || 3),
      risk_level: qs("#procurement-risk-filter").value,
      supplier_region: qs("#procurement-region-filter").value.trim(),
    };
  }

  function filterByUserSelections(recommendations) {
    const filters = getFilters();
    return recommendations.filter((item) => {
      const payload = item.recommendation_payload || {};
      const region = String(payload.supplier_region || payload.scenario_context?.region || payload.sanctions_context?.region || "");
      const riskLevel = String(item.action_priority || payload.action_priority || "").toLowerCase();
      const refineryId = Number(item.refinery_id || payload.refinery_id || 0);
      const scenarioId = Number(item.scenario_id || payload.scenario_id || 0);

      if (filters.risk_level && riskLevel !== filters.risk_level) {
        return false;
      }
      if (filters.supplier_region && region && !region.toLowerCase().includes(filters.supplier_region.toLowerCase())) {
        return false;
      }
      if (filters.supplier_region && !region) {
        return false;
      }
      if (filters.target_scope === "refinery" && filters.refinery_id && refineryId !== filters.refinery_id) {
        return false;
      }
      if (filters.target_scope === "scenario" && filters.scenario_id && scenarioId !== filters.scenario_id) {
        return false;
      }
      return true;
    }).slice(0, filters.top_n);
  }

  function renderRecommendationList() {
    const element = qs("#procurement-list");
    const badge = qs("#procurement-count-badge");
    const list = filterByUserSelections(state.recommendations || []);

    if (badge) {
      badge.textContent = `${list.length} ranked`;
    }
    if (!element) {
      return;
    }
    if (!list.length) {
      element.innerHTML = UI.renderErrorState("No recommendations match the current filters.", "Reset");
      return;
    }

    element.innerHTML = list
      .map((item, index) => {
        const payload = item.recommendation_payload || {};
        const isActive = Number(item.id) === Number(state.selectedId);
        const score = Number(payload.overall_score || item.overall_score || 0);
        const delivery = Number(payload.delivery_delay_days || 0);
        const routeRisk = Number(payload.score_breakdown?.route_risk || 0);
        const routeRiskInverse = Math.max(0, 100 - routeRisk);
        const rationale = payload.route_rationale || payload.rationale || "No rationale provided.";
        return `
          <article class="ranking-card ${isActive ? "ranking-card--active" : ""}" data-procurement-id="${item.id}">
            <div class="ranking-card__head">
              <strong>${String(index + 1).padStart(2, "0")}. ${UI.escapeHtml(item.title)}</strong>
              <span class="pill ${riskClass(item.action_priority)}">${UI.escapeHtml(item.action_priority || "low")}</span>
            </div>
            <p>${UI.escapeHtml(item.recommended_supplier)} | ${UI.escapeHtml(item.recommended_route)}</p>
            <div class="ranking-metrics">
              <div class="ranking-metric"><span>Score</span><strong>${formatNumber(score, 1)}</strong></div>
              <div class="ranking-metric"><span>Cost delta</span><strong>${percent(item.expected_cost_delta, 1)}</strong></div>
              <div class="ranking-metric"><span>Risk reduction</span><strong>${formatNumber(item.risk_reduction_score, 2)}</strong></div>
              <div class="ranking-metric"><span>Compat.</span><strong>${formatNumber(item.compatibility_score, 2)}</strong></div>
            </div>
            <div class="ranking-card__meta">
              <span>Route risk inverse: ${formatNumber(routeRiskInverse, 1)}</span>
              <span>Delivery days: ${formatNumber(delivery, 1)}</span>
            </div>
            <p class="ranking-card__rationale">${UI.escapeHtml(rationale)}</p>
            <div class="ranking-card__actions">
              <button class="btn btn-secondary" type="button" data-procurement-select="${item.id}">View</button>
              <button class="btn btn-primary" type="button" data-procurement-focus="${item.id}">Focus</button>
            </div>
          </article>
        `;
      })
      .join("");

    qsa("[data-procurement-select]", element).forEach((button) => {
      button.addEventListener("click", () => loadRecommendation(Number(button.dataset.procurementSelect)));
    });
    qsa("[data-procurement-focus]", element).forEach((button) => {
      button.addEventListener("click", () => loadRecommendation(Number(button.dataset.procurementFocus)));
    });
  }

  function renderRecommendationDetails() {
    const element = qs("#procurement-details");
    const rec = state.selectedRecommendation;
    if (!element) {
      return;
    }
    if (!rec) {
      element.innerHTML = `
        <div class="chart-placeholder chart-placeholder--tall">
          <div class="chart-placeholder__label">Select a recommendation to view rationale</div>
        </div>
      `;
      setText("#procurement-cost-delta", "--");
      setText("#procurement-risk-reduction", "--");
      setText("#procurement-delivery-feasibility", "--");
      return;
    }

    const payload = rec.recommendation_payload || {};
    const scoreBreakdown = payload.score_breakdown || {};
    const rationale = payload.route_rationale || "No rationale provided.";
    const routeContext = payload.scoring_components?.route_context || {};
    const scenarioContext = payload.scenario_context || {};
    const sanctionsContext = payload.sanctions_context || {};
    const delivery = Number(payload.delivery_delay_days || 0);
    const costDelta = Number(rec.expected_cost_delta || 0);
    const riskReduction = Number(rec.risk_reduction_score || 0);
    const compatibility = Number(rec.compatibility_score || 0);

    setText("#procurement-cost-delta", percent(costDelta, 1));
    setText("#procurement-risk-reduction", formatNumber(riskReduction, 2));
    setText("#procurement-delivery-feasibility", `${Math.max(0, 100 - delivery * 5).toFixed(1)}%`);

    element.innerHTML = `
      <article class="recommendation-detail">
        <div class="recommendation-detail__head">
          <div>
            <p class="eyebrow">Selected recommendation</p>
            <h3>${UI.escapeHtml(rec.title)}</h3>
            <p>${UI.escapeHtml(rec.recommended_supplier)} | ${UI.escapeHtml(rec.recommended_route)}</p>
          </div>
          <span class="pill ${riskClass(rec.action_priority)}">${UI.escapeHtml(rec.action_priority || "low")}</span>
        </div>

        <div class="mini-table">
          <div class="mini-table__row"><span>Expected cost delta</span><strong>${percent(costDelta, 1)}</strong></div>
          <div class="mini-table__row"><span>Risk reduction score</span><strong>${formatNumber(riskReduction, 2)}</strong></div>
          <div class="mini-table__row"><span>Compatibility score</span><strong>${formatNumber(compatibility, 2)}</strong></div>
          <div class="mini-table__row"><span>Delivery delay</span><strong>${formatNumber(delivery, 1)} days</strong></div>
        </div>

        <div class="panel__divider"></div>

        <div class="recommendation-detail__grid">
          <div class="data-row">
            <div class="data-row__head">
              <strong>Route logic</strong>
              <span class="pill ${riskClass(routeContext.scenario_penalty >= 18 ? "high" : "moderate")}">Route context</span>
            </div>
            <div class="data-row__meta">
              <span>Supplier risk: ${formatNumber(routeContext.supplier_risk || 0, 1)}</span>
              <span>Corridor risk: ${formatNumber(routeContext.corridor_risk || 0, 1)}</span>
            </div>
            <div class="data-row__meta">
              <span>Source congestion: ${formatNumber(routeContext.source_congestion || 0, 1)}</span>
              <span>Destination congestion: ${formatNumber(routeContext.destination_congestion || 0, 1)}</span>
            </div>
          </div>

          <div class="data-row">
            <div class="data-row__head">
              <strong>Scoring breakdown</strong>
              <span class="pill ${riskClass(scenarioContext.scenario_urgency || "moderate")}">${UI.escapeHtml(scenarioContext.scenario_urgency || "context")}</span>
            </div>
            <div class="data-row__meta">
              <span>Route risk inverse: ${formatNumber(scoreBreakdown.route_risk_inverse || 0, 1)}</span>
              <span>Crude compatibility: ${formatNumber(scoreBreakdown.crude_compatibility || compatibility, 1)}</span>
            </div>
            <div class="data-row__meta">
              <span>Cost efficiency: ${formatNumber(scoreBreakdown.cost_efficiency || 0, 1)}</span>
              <span>Delivery feasibility: ${formatNumber(scoreBreakdown.delivery_feasibility || Math.max(0, 100 - delivery * 5), 1)}</span>
            </div>
            <div class="data-row__meta">
              <span>Sanctions safety: ${formatNumber(scoreBreakdown.sanctions_safety || 0, 1)}</span>
            </div>
          </div>
        </div>

        <div class="panel__divider"></div>

        <div class="recommendation-detail__notes">
          <p><strong>Rationale:</strong> ${UI.escapeHtml(rationale)}</p>
          <p><strong>Sanctions note:</strong> ${UI.escapeHtml(sanctionsContext.event_penalty ? `${formatNumber(sanctionsContext.event_penalty, 1)} penalty from active sanctions events.` : "No additional sanctions penalty identified.")}</p>
        </div>
      </article>
    `;
  }

  function bindFormActions() {
    const form = qs("#procurement-form");
    const refreshButton = qs("[data-procurement-refresh]");
    const generateButton = qs("[data-procurement-generate]");
    const downloadButton = qs("[data-procurement-report-download]");
    const printButton = qs("[data-procurement-report-print]");

    const handleGenerate = async (event) => {
      if (event) event.preventDefault();
      await generateRecommendations();
    };

    if (form) {
      form.addEventListener("submit", handleGenerate);
    }
    if (refreshButton) {
      refreshButton.addEventListener("click", () => loadRecommendations());
    }
    if (downloadButton) {
      downloadButton.addEventListener("click", downloadRecommendationReport);
    }
    if (printButton) {
      printButton.addEventListener("click", printRecommendationReport);
    }
    if (generateButton) {
      generateButton.addEventListener("click", handleGenerate);
    }
  }

  async function generateRecommendations() {
    const filters = getFilters();
    const payload = {
      target_scope: filters.target_scope,
      scenario_id: filters.scenario_id,
      refinery_id: filters.refinery_id,
      top_n: filters.top_n,
      candidate_suppliers_limit: filters.candidate_suppliers_limit,
      candidate_corridors_limit: filters.candidate_corridors_limit,
    };

    try {
      setLoading("#procurement-list", "Generating recommendations...");
      const response = await API.postJson("/procurement/recommend", payload);
      const recommendations = response.recommendations || [];
      state.recommendations = recommendations;
      state.selectedId = recommendations[0]?.id || null;
      state.selectedRecommendation = recommendations[0] || null;
      renderRecommendationList();
      renderRecommendationDetails();
    } catch (error) {
      console.error("Failed to generate recommendations", error);
      setError("#procurement-list", error.message || "Unable to generate recommendations.");
    }
  }

  async function loadRecommendations() {
    setLoading("#procurement-list", "Loading recommendations...");
    try {
      const response = await API.getJson("/procurement/recommendations");
      const items = Array.isArray(response) ? response : response.items || [];
      state.recommendations = items;
      state.selectedId = items[0]?.id || null;
      state.selectedRecommendation = items[0] || null;
      renderRecommendationList();
      renderRecommendationDetails();
    } catch (error) {
      console.error("Failed to load recommendations", error);
      setError("#procurement-list", error.message || "Unable to load recommendations.");
    }
  }

  async function loadRecommendation(id) {
    try {
      const recommendation = await API.getJson(`/procurement/recommendations/${id}`);
      state.selectedId = id;
      state.selectedRecommendation = recommendation;
      renderRecommendationList();
      renderRecommendationDetails();
    } catch (error) {
      console.error("Failed to load recommendation", error);
      setError("#procurement-details", error.message || "Unable to load recommendation.");
    }
  }

  function bindFilterSync() {
    qsa("#procurement-form input, #procurement-form select").forEach((input) => {
      input.addEventListener("change", renderRecommendationList);
      input.addEventListener("input", () => {
        if (input.id === "procurement-region-filter") {
          renderRecommendationList();
        }
      });
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    bindFormActions();
    bindFilterSync();
    loadRecommendations();
  });
})(window, document);
