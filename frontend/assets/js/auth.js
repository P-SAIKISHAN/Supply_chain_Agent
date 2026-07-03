(function (window) {
  "use strict";

  const TOKEN_KEY = "energy.authToken";
  const USER_KEY = "energy.currentUser";

  function getAuthToken() {
    return localStorage.getItem(TOKEN_KEY);
  }

  function setAuthToken(token) {
    if (token) {
      localStorage.setItem(TOKEN_KEY, token);
    } else {
      localStorage.removeItem(TOKEN_KEY);
    }
    window.dispatchEvent(new Event("energy:auth-changed"));
  }

  function getCurrentUser() {
    const raw = localStorage.getItem(USER_KEY);
    if (!raw) {
      return null;
    }
    try {
      return JSON.parse(raw);
    } catch (_error) {
      return null;
    }
  }

  function setCurrentUser(user) {
    if (user) {
      localStorage.setItem(USER_KEY, JSON.stringify(user));
    } else {
      localStorage.removeItem(USER_KEY);
    }
    window.dispatchEvent(new Event("energy:auth-changed"));
  }

  function clearAuthToken() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    window.dispatchEvent(new Event("energy:auth-changed"));
  }

  function isAuthenticated() {
    return Boolean(getAuthToken());
  }

  function hydrateSessionUI() {
    const user = getCurrentUser();
    const name = user?.full_name || user?.name || "Demo analyst";
    const role = user?.role || "guest";

    document.querySelectorAll("[data-auth-name]").forEach((element) => {
      element.textContent = name;
    });
    document.querySelectorAll("[data-auth-role]").forEach((element) => {
      element.textContent = role;
    });
    document.querySelectorAll("[data-auth-status]").forEach((element) => {
      element.dataset.authenticated = isAuthenticated() ? "true" : "false";
    });
  }

  function bindLogoutButtons() {
    document.querySelectorAll("[data-action='logout']").forEach((button) => {
      button.addEventListener("click", () => {
        clearAuthToken();
        window.location.href = "../index.html";
      });
    });
  }

  async function login(email, password, options) {
    const payload = await window.EnergyAPI.postJson(
      "/auth/login",
      { email: email, password: password },
      options || {},
    );
    setAuthToken(payload.access_token);
    setCurrentUser(payload.user);
    hydrateSessionUI();
    return payload;
  }

  async function register(userData, options) {
    const payload = await window.EnergyAPI.postJson("/auth/register", userData, options || {});
    setAuthToken(payload.access_token);
    setCurrentUser(payload.user);
    hydrateSessionUI();
    return payload;
  }

  async function fetchCurrentUser(options) {
    const payload = await window.EnergyAPI.getJson("/auth/me", options || {});
    setCurrentUser(payload);
    hydrateSessionUI();
    return payload;
  }

  function requireAuth(redirectUrl) {
    if (isAuthenticated()) {
      return true;
    }
    if (redirectUrl) {
      window.location.href = redirectUrl;
    }
    return false;
  }

  function setApiBaseUrl(url) {
    window.EnergyAPI.setApiBaseUrl(url);
  }

  window.EnergyAuth = {
    getAuthToken,
    setAuthToken,
    getCurrentUser,
    setCurrentUser,
    clearAuthToken,
    isAuthenticated,
    hydrateSessionUI,
    bindLogoutButtons,
    login,
    register,
    fetchCurrentUser,
    requireAuth,
    setApiBaseUrl,
  };

  document.addEventListener("DOMContentLoaded", function () {
    hydrateSessionUI();
    bindLogoutButtons();
  });
})(window);

