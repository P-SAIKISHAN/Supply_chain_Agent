(function (window, document) {
  "use strict";

  const API = window.EnergyAPI;
  const UI = window.EnergyUI;

  const COLORS = {
    corridor: ["#5fb6ff", "#17d2c8", "#ffbd59", "#ff6b7a"],
    supplier: ["#5fb6ff", "#7c6cff", "#17d2c8", "#ffbd59"],
    price: ["#5fb6ff", "#17d2c8", "#ffbd59", "#ff6b7a"],
  };

  const dashboardState = {
    summary: null,
    corridorRisk: [],
    supplierRisk: [],
    alerts: [],
    refineryStress: [],
    recommendations: [],
    priceTrends: [],
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

  function formatPercent(value, digits = 0) {
    return `${formatNumber(value, digits)}%`;
  }

  function formatDate(value) {
    if (!value) {
      return "--";
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return "--";
    }
    return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  }

  function formatDateTime(value) {
    if (!value) {
      return "--";
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return "--";
    }
    return date.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function riskLevelClass(level) {
    const normalized = String(level || "").toLowerCase();
    if (normalized === "critical") return "pill--critical";
    if (normalized === "high") return "pill--high";
    if (normalized === "medium" || normalized === "moderate") return "pill--moderate";
    return "pill--low";
  }

  function severityBadgeClass(score) {
    if (score >= 0.8) return "badge--critical";
    if (score >= 0.6) return "badge--warning";
    return "badge--success";
  }

  function setSectionLoading(selector, message) {
    const element = qs(selector);
    if (element) {
      element.innerHTML = UI.renderLoadingState(message);
    }
  }

  function setSectionError(selector, message) {
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

  function createBarRow(label, value, maxValue, extraClass = "") {
    const width = maxValue > 0 ? Math.max(4, (value / maxValue) * 100) : 4;
    return `
      <div class="bar-row ${extraClass}">
        <div class="bar-row__meta">
          <span>${UI.escapeHtml(label)}</span>
          <strong>${UI.escapeHtml(formatNumber(value, 1))}</strong>
        </div>
        <div class="bar-row__track">
          <div class="bar-row__fill" style="width:${width.toFixed(2)}%"></div>
        </div>
      </div>
    `;
  }

  function drawChart(canvas, datasets, options = {}) {
    if (!canvas) {
      return;
    }
    const ctx = canvas.getContext("2d");
    const dpr = window.devicePixelRatio || 1;
    const width = canvas.clientWidth;
    const height = canvas.height || 240;
    canvas.width = Math.max(1, Math.floor(width * dpr));
    canvas.height = Math.max(1, Math.floor(height * dpr));
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, width, height);

    const padding = { top: 18, right: 20, bottom: 28, left: 44 };
    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;

    const allValues = datasets.flatMap((dataset) => dataset.points.map((point) => point.value));
    if (!allValues.length) {
      ctx.fillStyle = "rgba(230,240,255,0.7)";
      ctx.font = "14px Segoe UI, sans-serif";
      ctx.fillText("No data", padding.left, padding.top + 20);
      return;
    }

    const minValue = Math.min(...allValues);
    const maxValue = Math.max(...allValues);
    const valueRange = Math.max(1, maxValue - minValue);
    const pointCount = Math.max(...datasets.map((dataset) => dataset.points.length));
    const stepX = pointCount > 1 ? chartWidth / (pointCount - 1) : chartWidth;

    ctx.strokeStyle = "rgba(141,180,226,0.16)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(padding.left, padding.top + chartHeight);
    ctx.lineTo(padding.left + chartWidth, padding.top + chartHeight);
    ctx.stroke();

    datasets.forEach((dataset, datasetIndex) => {
      const color = dataset.color || COLORS.price[datasetIndex % COLORS.price.length];
      ctx.strokeStyle = color;
      ctx.fillStyle = color;
      ctx.lineWidth = 2.4;
      ctx.beginPath();
      dataset.points.forEach((point, index) => {
        const normalized = (point.value - minValue) / valueRange;
        const x = padding.left + (stepX * index);
        const y = padding.top + chartHeight - (normalized * (chartHeight - 20));
        if (index === 0) {
          ctx.moveTo(x, y);
        } else {
          ctx.lineTo(x, y);
        }
      });
      ctx.stroke();

      dataset.points.forEach((point, index) => {
        const normalized = (point.value - minValue) / valueRange;
        const x = padding.left + (stepX * index);
        const y = padding.top + chartHeight - (normalized * (chartHeight - 20));
        ctx.beginPath();
        ctx.arc(x, y, 3.5, 0, Math.PI * 2);
        ctx.fill();
      });
    });

    ctx.fillStyle = "rgba(230,240,255,0.55)";
    ctx.font = "11px Segoe UI, sans-serif";
    ctx.fillText(`${formatNumber(maxValue, 0)}`, 8, padding.top + 8);
    ctx.fillText(`${formatNumber(minValue, 0)}`, 8, padding.top + chartHeight);

    if (options.xLabels && options.xLabels.length) {
      ctx.fillStyle = "rgba(230,240,255,0.6)";
      options.xLabels.forEach((label, index) => {
        const x = padding.left + (stepX * index);
        ctx.fillText(label, x - 10, height - 8);
      });
    }
  }

  function buildTimeSeries(trends) {
    const groups = new Map();
    trends.forEach((point) => {
      if (!groups.has(point.benchmark_name)) {
        groups.set(point.benchmark_name, []);
      }
      groups.get(point.benchmark_name).push({
        label: formatDate(point.timestamp),
        value: Number(point.price_usd) || 0,
        timestamp: point.timestamp,
      });
    });
    return Array.from(groups.entries()).map(([name, points], index) => ({
      name,
      color: COLORS.price[index % COLORS.price.length],
      points: points.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp)),
    }));
  }

  function renderLegend(selector, datasets) {
    const element = qs(selector);
    if (!element) {
      return;
    }
    if (!datasets.length) {
      element.innerHTML = "";
      return;
    }
    element.innerHTML = datasets
      .map(
        (dataset) => `
          <span class="chart-legend__item">
            <span class="chart-legend__swatch" style="background:${dataset.color}"></span>
            ${UI.escapeHtml(dataset.name)}
          </span>
        `,
      )
      .join("");
  }

  function renderKpis(payload) {
    const kpis = payload?.kpis || {};
    setText("#kpi-national-risk", formatNumber(kpis.average_national_risk_score, 1));
    setText("#kpi-active-disruptions", formatNumber(kpis.active_disruptions_count, 0));
    setText("#kpi-shipments-at-risk", formatNumber(kpis.shipments_at_risk_count, 0));
    setText("#kpi-spr-days", `${formatNumber(kpis.strategic_reserve_days_cover, 0)} days`);
    setText("#kpi-import-dependency", formatPercent(kpis.estimated_import_dependency_pct, 0));

    setText("#kpi-national-risk-detail", "Composite national risk from the latest signals");
    setText("#kpi-active-disruptions-detail", "Geopolitical and sanctions events");
    setText("#kpi-shipments-at-risk-detail", "Shipments flagged by the risk engine");
    setText("#kpi-spr-days-detail", "Latest reserve cover estimate");
    setText("#kpi-import-dependency-detail", "Estimated from current import exposure");
  }

  function renderCorridorRisk(rows, options = {}) {
    const sorted = [...rows].sort((a, b) => Number(b.risk_score) - Number(a.risk_score));
    const maxValue = Math.max(1, ...sorted.map((row) => Number(row.risk_score) || 0));
    const table = qs("#corridor-risk-table");
    if (table && !options.skipTable) {
      table.innerHTML = sorted.length
        ? sorted
            .map((row) => `
              <div class="data-row">
                <div class="data-row__head">
                  <strong>${UI.escapeHtml(row.name)}</strong>
                  <span class="pill ${riskLevelClass(row.risk_level)}">${UI.escapeHtml(row.risk_level)}</span>
                </div>
                ${createBarRow("Risk score", Number(row.risk_score), maxValue)}
                <div class="data-row__meta">
                  <span>Status: ${UI.escapeHtml(row.status || "unknown")}</span>
                  <span>Shipments: ${UI.escapeHtml(formatNumber(row.shipment_count, 0))}</span>
                </div>
              </div>
            `)
            .join("")
        : UI.renderErrorState("No corridor risk data available.", "Retry");
    }

    const canvas = qs("#corridor-risk-chart");
    const dataset = {
      name: "Corridor risk",
      color: COLORS.corridor[0],
      points: sorted.map((row) => ({
        label: row.name,
        value: Number(row.risk_score) || 0,
      })),
    };
    drawChart(canvas, [dataset], { xLabels: sorted.map((row) => row.name.slice(0, 8)) });
  }

  function renderSupplierRisk(rows, options = {}) {
    const sorted = [...rows].sort((a, b) => Number(b.risk_score) - Number(a.risk_score));
    const maxValue = Math.max(1, ...sorted.map((row) => Number(row.risk_score) || 0));
    const table = qs("#supplier-risk-table");
    if (table && !options.skipTable) {
      table.innerHTML = sorted.length
        ? sorted
            .map((row) => `
              <div class="data-row">
                <div class="data-row__head">
                  <strong>${UI.escapeHtml(row.name)}</strong>
                  <span class="pill ${riskLevelClass(row.risk_level)}">${UI.escapeHtml(row.region)}</span>
                </div>
                ${createBarRow("Risk score", Number(row.risk_score), maxValue)}
                <div class="data-row__meta">
                  <span>Reliability: ${UI.escapeHtml(formatNumber(row.reliability_score * 100, 0))}%</span>
                  <span>Shipments: ${UI.escapeHtml(formatNumber(row.shipment_count, 0))}</span>
                </div>
              </div>
            `)
            .join("")
        : UI.renderErrorState("No supplier risk data available.", "Retry");
    }

    const canvas = qs("#supplier-risk-chart");
    const dataset = {
      name: "Supplier risk",
      color: COLORS.supplier[1],
      points: sorted.map((row) => ({
        label: row.name,
        value: Number(row.risk_score) || 0,
      })),
    };
    drawChart(canvas, [dataset], { xLabels: sorted.map((row) => row.name.slice(0, 8)) });
  }

  function renderAlerts(rows) {
    const element = qs("#alerts-panel");
    const badge = qs("#alerts-count-badge");
    if (badge) {
      badge.textContent = `${rows.length} alerts`;
    }
    if (!element) {
      return;
    }
    if (!rows.length) {
      element.innerHTML = UI.renderErrorState("No alerts available.", "Retry");
      return;
    }
    element.innerHTML = rows
      .map((row) => `
        <article class="alert-card ${severityBadgeClass(Number(row.severity_score) || 0)}">
          <div class="alert-card__head">
            <span class="pill ${riskLevelClass(row.event_type?.includes("sanctions") ? "high" : "moderate")}">
              ${UI.escapeHtml(row.region || "Global")}
            </span>
            <span class="alert-card__time">${UI.escapeHtml(formatDateTime(row.event_time))}</span>
          </div>
          <h3>${UI.escapeHtml(row.title)}</h3>
          <p>${UI.escapeHtml(row.summary || "")}</p>
          <div class="chip-row">
            ${(row.impact_tags || []).slice(0, 3).map((tag) => `<span class="chip">${UI.escapeHtml(tag)}</span>`).join("")}
          </div>
        </article>
      `)
      .join("");
  }

  function renderRefineryStress(rows) {
    const element = qs("#refinery-stress-panel");
    if (!element) {
      return;
    }
    if (!rows.length) {
      element.innerHTML = UI.renderErrorState("No refinery stress data available.", "Retry");
      return;
    }
    element.innerHTML = rows
      .map((row) => `
        <article class="stress-card">
          <div class="stress-card__head">
            <div>
              <strong>${UI.escapeHtml(row.name)}</strong>
              <p>${UI.escapeHtml(row.company)} | ${UI.escapeHtml(row.state)}</p>
            </div>
            <span class="pill ${riskLevelClass(row.risk_level)}">${UI.escapeHtml(row.risk_level)}</span>
          </div>
          <div class="stress-card__stats">
            <span>Risk score ${UI.escapeHtml(formatNumber(row.risk_score, 1))}</span>
            <span>Capacity ${UI.escapeHtml(formatNumber(row.capacity_bpd, 0))} bpd</span>
          </div>
          <div class="stress-card__meta">
            <span>Linked port: ${UI.escapeHtml(row.linked_port_name || "n/a")}</span>
            <span>Priority ${UI.escapeHtml(formatNumber(row.strategic_priority_score * 100, 0))}</span>
          </div>
        </article>
      `)
      .join("");
  }

  function renderRecommendations(rows) {
    const element = qs("#recommendations-panel");
    if (!element) {
      return;
    }
    if (!rows.length) {
      element.innerHTML = UI.renderErrorState("No procurement recommendations yet.", "Retry");
      return;
    }
    element.innerHTML = rows
      .map((row, index) => `
        <article class="recommendation-card">
          <span class="recommendation-card__rank">${String(index + 1).padStart(2, "0")}</span>
          <div>
            <strong>${UI.escapeHtml(row.title)}</strong>
            <p>${UI.escapeHtml(row.recommended_supplier)} | ${UI.escapeHtml(row.recommended_route)}</p>
            <div class="recommendation-card__facts">
              <span>Cost delta ${UI.escapeHtml(formatPercent(row.expected_cost_delta, 1))}</span>
              <span>Risk reduction ${UI.escapeHtml(formatNumber(row.risk_reduction_score, 2))}</span>
              <span>Compatibility ${UI.escapeHtml(formatNumber(row.compatibility_score, 2))}</span>
            </div>
          </div>
        </article>
      `)
      .join("");
  }

  function renderPriceTrends(rows, options = {}) {
    const grouped = buildTimeSeries(rows);
    const canvas = qs("#price-trend-chart");
    if (!options.skipLegend) {
      renderLegend("#price-trend-legend", grouped);
    }
    drawChart(canvas, grouped.map((dataset) => ({ ...dataset })), {
      xLabels: grouped[0]?.points.map((point) => point.label).slice(-6) || [],
    });
  }

  function attachRetryHandlers(loader) {
    qsa(".state-card .btn").forEach((button) => {
      button.addEventListener("click", loader);
    });
  }

  async function loadDashboard() {
    setSectionLoading("#corridor-risk-table", "Loading corridor risk...");
    setSectionLoading("#supplier-risk-table", "Loading supplier risk...");
    setSectionLoading("#alerts-panel", "Loading alerts...");
    setSectionLoading("#refinery-stress-panel", "Loading refinery stress...");
    setSectionLoading("#recommendations-panel", "Loading recommendations...");
    setSectionLoading("#price-trend-legend", "Loading price trends...");
    setText("#alerts-count-badge", "Loading");

    try {
      const [summary, corridorRisk, supplierRisk, alerts, refineryStress, recommendations, priceTrends] =
        await Promise.all([
          API.getJson("/dashboard/summary"),
          API.getJson("/dashboard/corridor-risk"),
          API.getJson("/dashboard/supplier-risk"),
          API.getJson("/dashboard/alerts"),
          API.getJson("/dashboard/refinery-stress"),
          API.getJson("/dashboard/recommendations"),
          API.getJson("/dashboard/price-trends"),
        ]);
      dashboardState.summary = summary;
      dashboardState.corridorRisk = corridorRisk;
      dashboardState.supplierRisk = supplierRisk;
      dashboardState.alerts = alerts;
      dashboardState.refineryStress = refineryStress;
      dashboardState.recommendations = recommendations;
      dashboardState.priceTrends = priceTrends;
      renderDashboard();
    } catch (error) {
      console.error("Failed to load dashboard", error);
      const message = error && error.message ? error.message : "Unable to load dashboard data.";
      setSectionError("#corridor-risk-table", message);
      setSectionError("#supplier-risk-table", message);
      setSectionError("#alerts-panel", message);
      setSectionError("#refinery-stress-panel", message);
      setSectionError("#recommendations-panel", message);
      setSectionError("#price-trend-legend", message);
    } finally {
      attachRetryHandlers(loadDashboard);
    }
  }

  function renderDashboard() {
    renderKpis(dashboardState.summary || {});
    renderCorridorRisk(dashboardState.corridorRisk || []);
    renderSupplierRisk(dashboardState.supplierRisk || []);
    renderAlerts(dashboardState.alerts || []);
    renderRefineryStress(dashboardState.refineryStress || []);
    renderRecommendations(dashboardState.recommendations || []);
    renderPriceTrends(dashboardState.priceTrends || []);
  }

  function bindActions() {
    const refreshButton = qs("[data-dashboard-refresh]");
    if (refreshButton) {
      refreshButton.addEventListener("click", loadDashboard);
    }
    const exportButton = qs("[data-dashboard-export]");
    if (exportButton) {
      exportButton.addEventListener("click", () => {
        window.alert("Export brief will be wired to backend report endpoints.");
      });
    }
  }

  function resizeCanvases() {
    if (!dashboardState.summary) {
      return;
    }
    renderCorridorRisk(dashboardState.corridorRisk || [], { skipTable: true });
    renderSupplierRisk(dashboardState.supplierRisk || [], { skipTable: true });
    renderPriceTrends(dashboardState.priceTrends || [], { skipLegend: true });
  }

  document.addEventListener("DOMContentLoaded", () => {
    bindActions();
    resizeCanvases();
    window.addEventListener("resize", () => {
      window.clearTimeout(window.__energyDashboardResizeTimer);
      window.__energyDashboardResizeTimer = window.setTimeout(resizeCanvases, 150);
    });
    loadDashboard();
  });
})(window, document);
