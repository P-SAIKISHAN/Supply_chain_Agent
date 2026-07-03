(function (window, document) {
  "use strict";

  const API = window.EnergyAPI;
  const UI = window.EnergyUI;

  const state = {
    plans: [],
    selectedPlanId: null,
    selectedPlan: null,
    selectedAllocation: [],
    selectedStrategy: null,
    selectedRiskNotes: [],
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

  function formatBbl(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) {
      return "--";
    }
    if (number >= 1_000_000) {
      return `${formatNumber(number / 1_000_000, 2)}M bbl`;
    }
    if (number >= 1_000) {
      return `${formatNumber(number / 1_000, 1)}K bbl`;
    }
    return `${formatNumber(number, 0)} bbl`;
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

  function getFormPayload() {
    const targetScope = qs("#spr-scope").value;
    const scenarioId = qs("#spr-scenario-id").value ? Number(qs("#spr-scenario-id").value) : null;
    const refineryId = qs("#spr-refinery-id").value ? Number(qs("#spr-refinery-id").value) : null;
    const scenarioSupplyLossPct = qs("#spr-supply-loss").value ? Number(qs("#spr-supply-loss").value) : null;

    return {
      target_scope: targetScope,
      scenario_id: scenarioId,
      refinery_id: refineryId,
      current_reserve_days_cover: Number(qs("#spr-reserve-cover").value || 0),
      scenario_supply_loss_pct: scenarioSupplyLossPct,
      duration_days: Number(qs("#spr-duration").value || 0),
      import_recovery_days: Number(qs("#spr-recovery").value || 21),
      replenishment_window_days: Number(qs("#spr-replenishment-window").value || 45),
      reserve_usage_allowed: Boolean(qs("#spr-reserve-allowed").checked),
    };
  }

  function normalizePlanEntry(item) {
    if (item && item.plan) {
      return item.plan;
    }
    return item;
  }

  function getScheduleRows(plan) {
    const schedule = plan?.daily_release_schedule || {};
    return Array.isArray(schedule.days) ? schedule.days : [];
  }

  function renderReleaseChart(plan) {
    const canvas = qs("#spr-release-chart");
    if (!canvas) {
      return;
    }
    const ctx = canvas.getContext("2d");
    const dpr = window.devicePixelRatio || 1;
    const width = canvas.parentElement ? canvas.parentElement.clientWidth : 600;
    const height = 300;
    canvas.width = Math.max(1, Math.floor(width * dpr));
    canvas.height = Math.max(1, Math.floor(height * dpr));
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, width, height);

    const rows = getScheduleRows(plan);
    const values = rows.map((row) => Number(row.release_bbl || 0));
    if (!values.length) {
      ctx.fillStyle = "rgba(230,240,255,0.7)";
      ctx.font = "14px Segoe UI, sans-serif";
      ctx.fillText("No daily release schedule available", 20, 40);
      return;
    }

    const maxValue = Math.max(...values, 1);
    const padding = { left: 40, right: 18, top: 20, bottom: 34 };
    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;
    const barGap = 8;
    const barWidth = Math.max(10, (chartWidth - barGap * (rows.length - 1)) / rows.length);

    ctx.fillStyle = "rgba(230,240,255,0.85)";
    ctx.font = "11px Segoe UI, sans-serif";
    rows.forEach((row, index) => {
      const value = Number(row.release_bbl || 0);
      const barHeight = (value / maxValue) * chartHeight;
      const x = padding.left + index * (barWidth + barGap);
      const y = padding.top + chartHeight - barHeight;

      const gradient = ctx.createLinearGradient(0, y, 0, y + barHeight);
      gradient.addColorStop(0, "#5fb6ff");
      gradient.addColorStop(1, "#17d2c8");
      ctx.fillStyle = gradient;
      ctx.fillRect(x, y, barWidth, barHeight);

      ctx.fillStyle = "rgba(230,240,255,0.85)";
      ctx.save();
      ctx.translate(x + barWidth / 2, height - 12);
      ctx.rotate(-Math.PI / 6);
      ctx.textAlign = "right";
      ctx.fillText(`D${row.day}`, 0, 0);
      ctx.restore();
    });
  }

  function renderScheduleTable(plan) {
    const element = qs("#spr-schedule-table");
    if (!element) {
      return;
    }
    const rows = getScheduleRows(plan);
    if (!rows.length) {
      element.innerHTML = UI.renderErrorState("No daily release schedule available.", "Retry");
      return;
    }
    element.innerHTML = `
      <div class="spr-table">
        <div class="spr-table__head">
          <span>Day</span>
          <span>Release</span>
          <span>Cumulative</span>
          <span>Allocation notes</span>
        </div>
        ${rows
          .map((row) => `
            <div class="spr-table__row">
              <strong>D${row.day}</strong>
              <span>${formatBbl(row.release_bbl)}</span>
              <span>${formatBbl(row.cumulative_bbl)}</span>
              <span>${row.allocation?.length ? `${row.allocation.length} refinery buckets` : "Standard release"}</span>
            </div>
          `)
          .join("")}
      </div>
    `;
  }

  function renderAllocationList(plan, allocationSuggestion = []) {
    const element = qs("#spr-allocation-list");
    if (!element) {
      return;
    }
    const list = allocationSuggestion.length
      ? allocationSuggestion
      : Array.isArray(plan?.replenishment_strategy?.refinery_allocation)
        ? plan.replenishment_strategy.refinery_allocation
        : [];

    if (!list.length) {
      element.innerHTML = UI.renderErrorState("No refinery allocation suggestion available.", "Retry");
      return;
    }

    element.innerHTML = list
      .map((item) => `
        <article class="stress-card">
          <div class="stress-card__head">
            <div>
              <strong>${UI.escapeHtml(item.name)}</strong>
              <p>${UI.escapeHtml(item.state)} - Priority ${formatNumber(item.strategic_priority_score, 2)}</p>
            </div>
            <span class="pill ${riskClass(item.stress_score >= 80 ? "critical" : item.stress_score >= 60 ? "high" : "moderate")}">
              ${UI.escapeHtml(formatNumber(item.stress_score, 1))}
            </span>
          </div>
          <div class="stress-card__stats">
            <span>Allocated ${formatBbl(item.allocated_bbl)}</span>
            <span>${formatNumber(item.allocated_share_pct, 1)}%</span>
          </div>
          <div class="stress-card__meta">
            <span>${UI.escapeHtml(item.rationale || "")}</span>
          </div>
        </article>
      `)
      .join("");
  }

  function renderRiskNotes(notes) {
    const element = qs("#spr-risk-notes");
    if (!element) {
      return;
    }
    if (!notes.length) {
      element.innerHTML = "";
      return;
    }
    element.innerHTML = `
      <div class="note-list__header">
        <strong>Risk notes</strong>
      </div>
      ${notes
        .map((note) => `<div class="note-item">${UI.escapeHtml(note)}</div>`)
        .join("")}
    `;
  }

  function renderSelectedPlan() {
    const plan = state.selectedPlan;
    if (!plan) {
      setText("#spr-plan-badge", "No plan selected");
      setText("#spr-total-drawdown", "--");
      setText("#spr-drawdown-days", "--");
      setText("#spr-daily-release", "--");
      setText("#spr-replenishment", "--");
      setText("#spr-policy-notes", "--");
      renderReleaseChart({});
      renderScheduleTable({});
      renderAllocationList({}, []);
      renderRiskNotes([]);
      return;
    }

    setText("#spr-plan-badge", `Plan #${plan.id}`);
    setText("#spr-total-drawdown", formatBbl(plan.total_drawdown_bbl));
    setText("#spr-drawdown-days", formatNumber(plan.drawdown_days, 0));

    const rows = getScheduleRows(plan);
    const firstDay = rows[0]?.release_bbl || plan.total_drawdown_bbl || 0;
    setText("#spr-daily-release", formatBbl(firstDay));

    const strategy = state.selectedStrategy || plan.replenishment_strategy || {};
    setText("#spr-replenishment", strategy.execution_rule || "Phased replenishment");
    setText("#spr-policy-notes", plan.policy_notes || "Policy notes unavailable");

    renderReleaseChart(plan);
    renderScheduleTable(plan);
    renderAllocationList(plan, state.selectedAllocation);
    renderRiskNotes(state.selectedRiskNotes);
  }

  function renderPlanList() {
    const element = qs("#spr-plan-list");
    const badge = qs("#spr-plan-count");
    const plans = state.plans || [];
    if (badge) {
      badge.textContent = `${plans.length} saved`;
    }
    if (!element) {
      return;
    }
    if (!plans.length) {
      element.innerHTML = UI.renderErrorState("No SPR plans yet. Optimize one to get started.", "Retry");
      return;
    }

    element.innerHTML = plans
      .map((item) => {
        const plan = normalizePlanEntry(item);
        const isActive = Number(plan.id) === Number(state.selectedPlanId);
        return `
          <article class="scenario-card ${isActive ? "scenario-card--active" : ""}" data-spr-plan-id="${plan.id}">
            <div class="scenario-card__head">
              <div>
                <strong>Plan #${plan.id}</strong>
                <p>Scenario ID: ${plan.scenario_id ?? "n/a"}</p>
              </div>
              <span class="pill ${riskClass(plan.drawdown_days >= 20 ? "high" : plan.drawdown_days >= 10 ? "moderate" : "low")}">
                ${formatNumber(plan.drawdown_days, 0)} days
              </span>
            </div>
            <div class="scenario-card__meta">
              <span>Drawdown ${formatBbl(plan.total_drawdown_bbl)}</span>
              <span>${new Date(plan.generated_at).toLocaleDateString()}</span>
            </div>
            <div class="scenario-card__actions">
              <button class="btn btn-secondary" type="button" data-spr-select="${plan.id}">View</button>
              <button class="btn btn-primary" type="button" data-spr-load="${plan.id}">Load</button>
            </div>
          </article>
        `;
      })
      .join("");

    qsa("[data-spr-select]", element).forEach((button) => {
      button.addEventListener("click", () => loadPlan(Number(button.dataset.sprSelect)));
    });
    qsa("[data-spr-load]", element).forEach((button) => {
      button.addEventListener("click", () => loadPlan(Number(button.dataset.sprLoad)));
    });
  }

  async function optimizePlan(event) {
    if (event) {
      event.preventDefault();
    }
    const payload = getFormPayload();
    try {
      setLoading("#spr-allocation-list", "Optimizing reserve plan...");
      const response = await API.postJson("/spr/optimize", payload);
      state.selectedPlan = response.plan;
      state.selectedPlanId = response.plan?.id || null;
      state.selectedAllocation = response.refinery_allocation_suggestion || [];
      state.selectedStrategy = response.replenishment_strategy || response.plan?.replenishment_strategy || null;
      state.selectedRiskNotes = response.risk_notes || [];
      renderSelectedPlan();
      await loadPlans(true);
    } catch (error) {
      console.error("Failed to optimize SPR plan", error);
      setError("#spr-allocation-list", error.message || "Unable to optimize SPR plan.");
    }
  }

  async function loadPlans(preserveSelection = true) {
    setLoading("#spr-plan-list", "Loading SPR plans...");
    try {
      const response = await API.getJson("/spr/plans");
      const items = Array.isArray(response) ? response : response.items || [];
      state.plans = items;
      if (!preserveSelection || !state.selectedPlanId) {
        state.selectedPlanId = items[0]?.id || null;
      }
      renderPlanList();
      if (state.selectedPlanId) {
        await loadPlan(state.selectedPlanId, { skipListRefresh: true });
      } else {
        state.selectedPlan = null;
        state.selectedAllocation = [];
        state.selectedStrategy = null;
        state.selectedRiskNotes = [];
        renderSelectedPlan();
      }
    } catch (error) {
      console.error("Failed to load plans", error);
      setError("#spr-plan-list", error.message || "Unable to load SPR plans.");
    }
  }

  async function loadPlan(planId, options = {}) {
    try {
      const plan = await API.getJson(`/spr/plans/${planId}`);
      state.selectedPlanId = planId;
      state.selectedPlan = plan;
      state.selectedStrategy = plan.replenishment_strategy || null;
      state.selectedAllocation = plan.replenishment_strategy?.refinery_allocation || state.selectedAllocation;
      state.selectedRiskNotes = state.selectedRiskNotes || [];
      if (!options.skipListRefresh) {
        renderPlanList();
      }
      renderSelectedPlan();
    } catch (error) {
      console.error("Failed to load plan", error);
      setError("#spr-allocation-list", error.message || "Unable to load plan.");
    }
  }

  function bindActions() {
    const optimizeButton = qs("[data-spr-optimize]");
    const refreshButton = qs("[data-spr-refresh]");
    const form = qs("#spr-form");

    const handleOptimize = async (event) => {
      if (event) event.preventDefault();
      await optimizePlan();
    };

    if (optimizeButton) {
      optimizeButton.addEventListener("click", handleOptimize);
    }
    if (refreshButton) {
      refreshButton.addEventListener("click", () => loadPlans(false));
    }
    if (form) {
      form.addEventListener("submit", handleOptimize);
    }
  }

  function bindFieldHints() {
    const scope = qs("#spr-scope");
    const scenarioId = qs("#spr-scenario-id");
    const refineryId = qs("#spr-refinery-id");

    function updateHints() {
      const currentScope = scope.value;
      scenarioId.disabled = currentScope !== "scenario";
      refineryId.disabled = currentScope !== "refinery";
    }

    scope.addEventListener("change", updateHints);
    updateHints();
  }

  document.addEventListener("DOMContentLoaded", () => {
    bindActions();
    bindFieldHints();
    loadPlans(false);
  });
})(window, document);
