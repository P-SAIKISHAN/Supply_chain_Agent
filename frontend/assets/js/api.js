(function (window) {
  "use strict";

  const STORAGE_KEYS = {
    apiBaseUrl: "energy.apiBaseUrl",
  };

  const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000/api/v1";

  function normalizeBaseUrl(value) {
    if (!value) {
      return DEFAULT_API_BASE_URL;
    }
    return String(value).replace(/\/+$/, "");
  }

  function getConfigBaseUrl() {
    if (window.ENERGY_APP_CONFIG && window.ENERGY_APP_CONFIG.apiBaseUrl) {
      return normalizeBaseUrl(window.ENERGY_APP_CONFIG.apiBaseUrl);
    }
    return normalizeBaseUrl(localStorage.getItem(STORAGE_KEYS.apiBaseUrl));
  }

  function setApiBaseUrl(url) {
    localStorage.setItem(STORAGE_KEYS.apiBaseUrl, normalizeBaseUrl(url));
  }

  function getAuthToken() {
    return window.EnergyAuth && typeof window.EnergyAuth.getAuthToken === "function"
      ? window.EnergyAuth.getAuthToken()
      : localStorage.getItem("energy.authToken");
  }

  async function apiRequest(path, options) {
    const config = options || {};
    const method = config.method || "GET";
    const headers = new Headers(config.headers || {});
    const body = config.body;
    const includeAuth = config.includeAuth !== false;
    const baseUrl = normalizeBaseUrl(config.baseUrl || getConfigBaseUrl());
    const url = `${baseUrl}${path.startsWith("/") ? path : `/${path}`}`;

    headers.set("Accept", "application/json");
    if (body && !headers.has("Content-Type") && !(body instanceof FormData)) {
      headers.set("Content-Type", "application/json");
    }
    if (includeAuth) {
      const token = getAuthToken();
      if (token) {
        headers.set("Authorization", `Bearer ${token}`);
      }
    }

    const response = await fetch(url, {
      method,
      headers,
      body: body && !(body instanceof FormData) && typeof body !== "string" ? JSON.stringify(body) : body,
    });

    const contentType = response.headers.get("content-type") || "";
    const payload = contentType.includes("application/json")
      ? await response.json()
      : await response.text();

    if (!response.ok) {
      const message = payload && typeof payload === "object"
        ? payload.detail || payload.message || response.statusText
        : response.statusText || "Request failed";
      const error = new Error(message);
      error.status = response.status;
      error.payload = payload;
      throw error;
    }

    return payload;
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function renderLoadingState(message) {
    return `
      <div class="panel state-card state-card--loading">
        <strong>Loading</strong>
        <p>${escapeHtml(message || "Fetching data...")}</p>
      </div>
    `;
  }

  function renderErrorState(message, actionLabel) {
    return `
      <div class="panel state-card state-card--error">
        <strong>Unable to load data</strong>
        <p>${escapeHtml(message || "Something went wrong.")}</p>
        ${actionLabel ? `<button class="btn btn-secondary" type="button">${escapeHtml(actionLabel)}</button>` : ""}
      </div>
    `;
  }

  async function getJson(path, options) {
    return apiRequest(path, { ...(options || {}), method: "GET" });
  }

  async function postJson(path, body, options) {
    return apiRequest(path, { ...(options || {}), method: "POST", body });
  }

  async function putJson(path, body, options) {
    return apiRequest(path, { ...(options || {}), method: "PUT", body });
  }

  async function deleteJson(path, options) {
    return apiRequest(path, { ...(options || {}), method: "DELETE" });
  }

  window.ENERGY_APP_CONFIG = window.ENERGY_APP_CONFIG || {};
  window.EnergyAPI = {
    getConfigBaseUrl,
    setApiBaseUrl,
    apiRequest,
    getJson,
    postJson,
    putJson,
    deleteJson,
  };
  window.EnergyUI = {
    escapeHtml,
    renderLoadingState,
    renderErrorState,
  };
})(window);

