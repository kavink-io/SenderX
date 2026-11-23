/**
 * SenderX Frontend Application
 */

const DASHBOARD_NAVIGATION = [
  {
    id: "menu-overview",
    name: "Overview",
    tabId: "tab-org-overview",
    tab_id: "tab-org-overview",
    requiredPermission: null,
    required_permission: null,
    allowedActions: ["view_dashboard"],
    icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="7" height="9" x="3" y="3" rx="1"/><rect width="7" height="5" x="14" y="3" rx="1"/><rect width="7" height="9" x="14" y="12" rx="1"/><rect width="7" height="5" x="3" y="16" rx="1"/></svg>`
  },
  {
    id: "menu-applications",
    name: "Connected Applications",
    tabId: "tab-org-applications",
    tab_id: "tab-org-applications",
    requiredPermission: "organization:configuration:manage",
    required_permission: "organization:configuration:manage",
    allowedActions: ["register_app", "activate_app", "deactivate_app"],
    icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="14" height="20" x="5" y="2" rx="2" ry="2"/><path d="M12 18h.01"/></svg>`
  },
  {
    id: "menu-credentials",
    name: "API Credentials",
    tabId: "tab-org-credentials",
    tab_id: "tab-org-credentials",
    requiredPermission: "organization:configuration:manage",
    required_permission: "organization:configuration:manage",
    allowedActions: ["create_key", "rotate_key", "revoke_key"],
    icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="7.5" cy="15.5" r="5.5"/><path d="m21 2-9.6 9.6"/><path d="m15.5 7.5 3 3L22 7l-3-3"/></svg>`
  },
  {
    id: "menu-messages",
    name: "Messages",
    tabId: "tab-org-messages",
    tab_id: "tab-org-messages",
    requiredPermission: "organization:messages:read",
    required_permission: "organization:messages:read",
    allowedActions: ["view_messages", "send_message", "queue_message"],
    icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/></svg>`
  },
  {
    id: "menu-templates",
    name: "Email Templates",
    tabId: "tab-org-templates",
    tab_id: "tab-org-templates",
    requiredPermission: "organization:templates:read",
    required_permission: "organization:templates:read",
    allowedActions: ["view_templates", "create_template", "publish_template"],
    icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>`
  },
  {
    id: "menu-json-requests",
    name: "JSON Requests",
    tabId: "tab-org-json-requests",
    tab_id: "tab-org-json-requests",
    requiredPermission: "organization:payloads:read",
    required_permission: "organization:payloads:read",
    allowedActions: ["view_payload", "edit_payload", "validate_payload", "retry_payload"],
    icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>`
  },
  {
    id: "menu-dlq",
    name: "Dead Letter Queue",
    tabId: "tab-org-dlq",
    tab_id: "tab-org-dlq",
    requiredPermission: "organization:dead_letters:read",
    required_permission: "organization:dead_letters:read",
    allowedActions: ["view_dlq", "retry_dlq", "delete_dlq"],
    icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="7.86 2 16.14 2 22 7.86 22 16.14 16.14 22 7.86 22 2 16.14 2 7.86 7.86 2"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`
  },
  {
    id: "menu-analytics",
    name: "Analytics",
    tabId: "tab-org-analytics",
    tab_id: "tab-org-analytics",
    requiredPermission: "organization:analytics:read",
    required_permission: "organization:analytics:read",
    allowedActions: ["view_analytics"],
    icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>`
  },
  {
    id: "menu-users",
    name: "Employees & Roles",
    tabId: "tab-org-users",
    tab_id: "tab-org-users",
    requiredPermission: "organization:users:manage",
    required_permission: "organization:users:manage",
    allowedActions: ["add_employee", "assign_roles", "manage_roles", "deactivate_employee"],
    icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>`
  },
  {
    id: "menu-settings",
    name: "Settings",
    tabId: "tab-org-settings",
    tab_id: "tab-org-settings",
    requiredPermission: "organization:providers:read",
    required_permission: "organization:providers:read",
    allowedActions: ["view_settings", "configure_providers"],
    icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>`
  }
];

const ALL_ORG_PERMISSIONS = [
  "organization:messages:read", "organization:messages:create", "organization:messages:manage",
  "organization:templates:read", "organization:templates:create", "organization:templates:manage",
  "organization:payloads:read", "organization:payloads:edit", "organization:payloads:validate",
  "organization:dead_letters:read", "organization:dead_letters:manage", "organization:dlq:read", "organization:dlq:retry",
  "organization:media:read", "organization:media:upload", "organization:media:delete", "organization:media:manage",
  "organization:analytics:read", "organization:users:manage", "organization:roles:manage",
  "organization:configuration:manage", "organization:providers:read", "organization:providers:manage"
];

let currentUserDashboardContext = null;
let currentUserAllowedTabs = new Set(["tab-org-overview"]);
let currentUserAllowedWidgets = new Set();
let currentUserPermissions = new Set();
let currentOrgProfile = null;
let cachedApplicationsList = [];
let hasCopiedSecretKey = false;

// ==========================================
// Theme Management (Phase 5: Responsive White Theme)
// ==========================================
function initTheme() {
  try {
    const currentTheme = localStorage.getItem("senderx_theme") || "light";
    document.documentElement.setAttribute("data-theme", currentTheme);
    updateThemeIcons(currentTheme);
  } catch (e) {
    console.error("Theme init error", e);
  }
}

function toggleTheme() {
  try {
    const current = document.documentElement.getAttribute("data-theme") || "light";
    const nextTheme = current === "light" ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", nextTheme);
    localStorage.setItem("senderx_theme", nextTheme);
    updateThemeIcons(nextTheme);
  } catch (e) {
    console.error("Theme toggle error", e);
  }
}

function updateThemeIcons(theme) {
  const isDark = theme === "dark";
  document.querySelectorAll("#theme-icon-sun, .theme-icon-sun-alt").forEach(el => {
    el.style.display = isDark ? "block" : "none";
  });
  document.querySelectorAll("#theme-icon-moon, .theme-icon-moon-alt").forEach(el => {
    el.style.display = isDark ? "none" : "block";
  });
}

document.addEventListener("DOMContentLoaded", () => {
  initTheme();
  initApp();
});

function showToast(msg, type = "info") {
  const container = document.getElementById("toast-container");
  if (!container) return;
  const el = document.createElement("div");
  el.className = `toast toast-${type}`;
  el.textContent = msg;
  container.appendChild(el);
  setTimeout(() => el.remove(), 4000);
}

function openModal(id) {
  const m = document.getElementById(id);
  if (m) {
    m.classList.add("active");
    document.body.style.overflow = "hidden";
  }
}

function closeModal(id) {
  const m = document.getElementById(id);
  if (m) {
    m.classList.remove("active");
    const anyActive = document.querySelector(".modal.active");
    if (!anyActive) {
      document.body.style.overflow = "";
    }
  }
}

async function initApp() {
  const storedAccount = ApiClient.getStoredAccount();
  const token = ApiClient.getAccessToken();

  if (token && storedAccount) {
    showDashboard(storedAccount);
    // Refresh authoritative user profile details from backend /api/v1/auth/me
    try {
      const res = await ApiClient.getCurrentAccount();
      if (res && res.success && res.data) {
        ApiClient.setStoredAccount(res.data);
        if (res.data.account_type === "PLATFORM_ADMIN") {
          updatePlatformAdminProfileDisplay(res.data);
        } else {
          await initOrganizationDashboard(res.data);
        }
      }
    } catch (e) {
      console.warn("Could not refresh account from /auth/me on init:", e);
    }
  } else {
    showAuth();
  }

  // Login form handler
  const loginForm = document.getElementById("login-form");
  if (loginForm) {
    loginForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const email = document.getElementById("login-email").value.trim();
      const password = document.getElementById("login-password").value;
      const errBox = document.getElementById("login-error");
      errBox.textContent = "";

      try {
        const res = await ApiClient.login(email, password);
        if (res.success && res.data) {
          showToast("Signed in successfully!", "success");
          showDashboard(res.data.account);
        } else {
          errBox.textContent = res.message || "Invalid credentials.";
        }
      } catch (err) {
        errBox.textContent = err.message || "Could not connect to API server.";
      }
    });
  }

  // Global Logout handlers
  const handleLogout = () => {
    ApiClient.clearTokens();
    currentUserPermissions.clear();
    currentUserAllowedTabs.clear();
    currentUserAllowedWidgets.clear();
    currentUserDashboardContext = null;
    currentOrgProfile = null;
    showAuth();
  };
  document.getElementById("btn-logout")?.addEventListener("click", handleLogout);
  document.getElementById("btn-header-logout")?.addEventListener("click", handleLogout);

  window.addEventListener("sx_logout", () => {
    handleLogout();
  });

  window.addEventListener("sx_permission_denied", async (e) => {
    console.warn("Protected action returned 401/403. Re-fetching dashboard context & re-rendering navigation...", e.detail);
    if (ApiClient.getAccessToken()) {
      try {
        await loadDashboardContext();
        if (typeof applyPermissionVisibility === "function") {
          applyPermissionVisibility();
        }
        if (typeof updateNavScopeIndicators === "function") {
          updateNavScopeIndicators();
        }
      } catch (err) {
        console.error("Error refreshing context after permission denial:", err);
      }
    }
  });

  // Sidebar Tab Navigation Setup
  setupNavItemListeners();

  // Setup Top Navigation
  setupTopNav();

  // Setup Forms
  setupCreateOrgForm();
  setupSendMessageForm();
  setupCreateUserForm();
  setupAuthOtpFlow();
  setupProviderConfigForm();
  setupTemplateEditorForm();
  setupRegisterAppForm();
  setupGenerateCredentialForm();
  setupCreateRoleForm();
}

function setupNavItemListeners() {
  document.querySelectorAll(".sidebar .nav-item").forEach((btn) => {
    btn.addEventListener("click", () => {
      const tabId = btn.getAttribute("data-tab");
      if (tabId && tabId !== "undefined") {
        switchTab(tabId);
      }
    });
  });
}

function showAuth() {
  resetAuthOtpFlow();
  document.getElementById("auth-view").classList.add("active");
  document.getElementById("app-shell").classList.remove("active");
}

let authOtpPurpose = null;
let authOtpEmail = "";
let authOtpResetToken = "";
let authOtpExpiryAt = 0;
let authOtpResendAt = 0;
let authOtpCountdownTimer = null;

function resetAuthOtpFlow() {
  if (authOtpCountdownTimer) {
    clearInterval(authOtpCountdownTimer);
    authOtpCountdownTimer = null;
  }
  authOtpPurpose = null;
  authOtpEmail = "";
  authOtpResetToken = "";
  authOtpExpiryAt = 0;
  authOtpResendAt = 0;

  const flow = document.getElementById("auth-otp-flow");
  if (flow) flow.hidden = true;
  const loginForm = document.getElementById("login-form");
  if (loginForm) loginForm.hidden = false;
  const loginLinks = document.getElementById("auth-login-links");
  if (loginLinks) loginLinks.hidden = false;
  const cancelButton = document.getElementById("btn-cancel-otp-flow");
  if (cancelButton) cancelButton.hidden = false;

  ["otp-email-form", "otp-code-form", "otp-password-form", "otp-success"].forEach((id) => {
    const element = document.getElementById(id);
    if (element) element.hidden = id !== "otp-email-form";
  });
  ["otp-email-error", "otp-code-error", "otp-password-error"].forEach((id) => {
    const element = document.getElementById(id);
    if (element) element.textContent = "";
  });
  document.querySelectorAll(".otp-digit").forEach((input) => { input.value = ""; });
  const passwordInput = document.getElementById("otp-new-password");
  if (passwordInput) passwordInput.value = "";
}

function startAuthOtpFlow(purpose) {
  resetAuthOtpFlow();
  authOtpPurpose = purpose;
  const loginEmail = document.getElementById("login-email");
  const emailInput = document.getElementById("otp-email");
  if (emailInput && loginEmail) emailInput.value = loginEmail.value.trim();

  document.getElementById("login-form").hidden = true;
  document.getElementById("auth-login-links").hidden = true;
  document.getElementById("login-error").textContent = "";
  document.getElementById("auth-otp-flow").hidden = false;
  document.getElementById("otp-flow-title").textContent =
    purpose === "ACTIVATION" ? "Activate your account" : "Reset your password";
  document.getElementById("otp-flow-description").textContent =
    purpose === "ACTIVATION"
      ? "Enter your work email to receive a one-time activation code."
      : "Enter your account email. If it is eligible, we will send a one-time reset code.";
  document.getElementById("otp-email-form").hidden = false;
  document.getElementById("otp-code-form").hidden = true;
  document.getElementById("otp-password-form").hidden = true;
  document.getElementById("otp-success").hidden = true;
}

function authOtpPasswordRules(password) {
  return {
    length: password.length >= 8,
    upper: /[A-Z]/.test(password),
    lower: /[a-z]/.test(password),
    digit: /\d/.test(password),
    special: /[^A-Za-z0-9]/.test(password)
  };
}

function updateAuthOtpPasswordRules() {
  const password = document.getElementById("otp-new-password")?.value || "";
  const rules = authOtpPasswordRules(password);
  document.querySelectorAll("#otp-password-rules [data-rule]").forEach((item) => {
    item.classList.toggle("is-met", Boolean(rules[item.dataset.rule]));
  });
}

function updateAuthOtpCountdown() {
  const now = Date.now();
  const expirySeconds = Math.max(0, Math.ceil((authOtpExpiryAt - now) / 1000));
  const resendSeconds = Math.max(0, Math.ceil((authOtpResendAt - now) / 1000));
  const format = (seconds) => `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
  const expiryLabel = document.getElementById("otp-expiry-countdown");
  const resendButton = document.getElementById("btn-resend-otp");
  const resendLabel = document.getElementById("otp-resend-countdown");
  const verifyButton = document.querySelector("#otp-code-form button[type='submit']");

  if (expiryLabel) {
    expiryLabel.textContent = expirySeconds
      ? `Code expires in ${format(expirySeconds)}`
      : "This code has expired. Request a new one.";
  }
  if (verifyButton) verifyButton.disabled = expirySeconds === 0;
  if (resendButton) {
    resendButton.disabled = resendSeconds > 0;
    resendButton.textContent = resendSeconds ? "Resend code" : "Didn't get it? Resend";
  }
  if (resendLabel) {
    resendLabel.textContent = resendSeconds ? `Available in ${format(resendSeconds)}` : "";
  }

  if (expirySeconds === 0 && authOtpCountdownTimer) {
    clearInterval(authOtpCountdownTimer);
    authOtpCountdownTimer = null;
  }
}

function startAuthOtpCountdown() {
  if (authOtpCountdownTimer) clearInterval(authOtpCountdownTimer);
  authOtpExpiryAt = Date.now() + 10 * 60 * 1000;
  authOtpResendAt = Date.now() + 60 * 1000;
  updateAuthOtpCountdown();
  authOtpCountdownTimer = setInterval(updateAuthOtpCountdown, 1000);
}

function clearAuthOtpDigits() {
  document.querySelectorAll(".otp-digit").forEach((input) => { input.value = ""; });
  document.querySelector(".otp-digit")?.focus();
}

function setupAuthOtpFlow() {
  document.getElementById("link-forgot-password")?.addEventListener("click", () => {
    startAuthOtpFlow("PASSWORD_RESET");
  });
  document.getElementById("link-activate-account")?.addEventListener("click", () => {
    startAuthOtpFlow("ACTIVATION");
  });
  document.getElementById("btn-cancel-otp-flow")?.addEventListener("click", () => {
    const email = document.getElementById("otp-email")?.value.trim();
    resetAuthOtpFlow();
    if (email) document.getElementById("login-email").value = email;
  });
  document.getElementById("btn-otp-back-to-login")?.addEventListener("click", () => {
    const email = authOtpEmail;
    resetAuthOtpFlow();
    if (email) document.getElementById("login-email").value = email;
  });

  const requestEmailForm = document.getElementById("otp-email-form");
  const codeForm = document.getElementById("otp-code-form");
  const passwordForm = document.getElementById("otp-password-form");

  const requestCode = async (resend) => {
    const errorBox = document.getElementById(resend ? "otp-code-error" : "otp-email-error");
    errorBox.textContent = "";
    const button = document.getElementById(resend ? "btn-resend-otp" : "btn-request-otp");
    button.disabled = true;
    try {
      const result = authOtpPurpose === "ACTIVATION"
        ? await ApiClient.requestActivationOtp(authOtpEmail)
        : await ApiClient.requestPasswordResetOtp(authOtpEmail);
      if (!result.success) {
        errorBox.textContent = result.message || "Could not send a code. Please try again.";
        if (resend && Number(result.retry_after) > 0) {
          authOtpResendAt = Date.now() + Number(result.retry_after) * 1000;
          if (!authOtpCountdownTimer) {
            authOtpCountdownTimer = setInterval(updateAuthOtpCountdown, 1000);
          }
          updateAuthOtpCountdown();
        } else {
          button.disabled = false;
        }
        return false;
      }

      document.getElementById("otp-email-caption").textContent = authOtpEmail;
      requestEmailForm.hidden = true;
      codeForm.hidden = false;
      document.getElementById("otp-password-form").hidden = true;
      document.getElementById("otp-success").hidden = true;
      document.getElementById("btn-cancel-otp-flow").hidden = false;
      document.getElementById("otp-code-error").textContent = "";
      clearAuthOtpDigits();
      startAuthOtpCountdown();
      return true;
    } catch (error) {
      errorBox.textContent = error.message || "Could not connect to the service. Please try again.";
      button.disabled = false;
      return false;
    }
  };

  requestEmailForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    authOtpEmail = document.getElementById("otp-email").value.trim().toLowerCase();
    await requestCode(false);
  });

  document.getElementById("btn-resend-otp")?.addEventListener("click", async () => {
    if (Date.now() < authOtpResendAt) return;
    await requestCode(true);
  });

  const digitInputs = Array.from(document.querySelectorAll(".otp-digit"));
  digitInputs.forEach((input, index) => {
    input.addEventListener("input", () => {
      const digits = input.value.replace(/\D/g, "");
      if (digits.length > 1) {
        digits.slice(0, 6).split("").forEach((digit, position) => {
          if (digitInputs[position]) digitInputs[position].value = digit;
        });
        digitInputs[Math.min(digits.length, 6) - 1]?.focus();
      } else {
        input.value = digits.slice(0, 1);
        if (input.value) digitInputs[index + 1]?.focus();
      }
      document.getElementById("otp-code-error").textContent = "";
    });
    input.addEventListener("keydown", (event) => {
      if (event.key === "Backspace" && !input.value) digitInputs[index - 1]?.focus();
    });
    input.addEventListener("paste", (event) => {
      event.preventDefault();
      const digits = event.clipboardData.getData("text").replace(/\D/g, "").slice(0, 6);
      digits.split("").forEach((digit, position) => {
        if (digitInputs[position]) digitInputs[position].value = digit;
      });
      digitInputs[Math.max(0, digits.length - 1)]?.focus();
    });
  });

  codeForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const code = digitInputs.map((input) => input.value).join("");
    const errorBox = document.getElementById("otp-code-error");
    errorBox.textContent = "";
    if (!/^\d{6}$/.test(code)) {
      errorBox.textContent = "Enter all six digits from the email.";
      return;
    }

    const submitButton = codeForm.querySelector("button[type='submit']");
    submitButton.disabled = true;
    try {
      const result = await ApiClient.verifyOtp(authOtpEmail, authOtpPurpose, code);
      if (!result.success || !result.data?.reset_token) {
        errorBox.textContent = result.message || "That code could not be verified.";
        return;
      }
      authOtpResetToken = result.data.reset_token;
      codeForm.hidden = true;
      passwordForm.hidden = false;
      document.getElementById("otp-password-error").textContent = "";
      document.getElementById("otp-new-password").focus();
    } catch (error) {
      errorBox.textContent = error.message || "Could not verify the code. Please try again.";
    } finally {
      submitButton.disabled = false;
    }
  });

  const passwordInput = document.getElementById("otp-new-password");
  passwordInput?.addEventListener("input", updateAuthOtpPasswordRules);
  document.getElementById("btn-toggle-otp-password")?.addEventListener("click", (event) => {
    const button = event.currentTarget;
    const isHidden = passwordInput.type === "password";
    passwordInput.type = isHidden ? "text" : "password";
    button.textContent = isHidden ? "Hide" : "Show";
    button.setAttribute("aria-label", isHidden ? "Hide password" : "Show password");
  });

  passwordForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const password = passwordInput.value;
    const rules = authOtpPasswordRules(password);
    const errorBox = document.getElementById("otp-password-error");
    errorBox.textContent = "";
    if (!Object.values(rules).every(Boolean)) {
      errorBox.textContent = "Choose a password that meets all the requirements.";
      return;
    }

    const button = document.getElementById("btn-set-otp-password");
    button.disabled = true;
    try {
      const result = await ApiClient.setPasswordWithOtp(
        authOtpPurpose,
        authOtpResetToken,
        password
      );
      if (!result.success) {
        errorBox.textContent = result.message || "Could not set the password. Request a new code.";
        return;
      }
      if (authOtpCountdownTimer) clearInterval(authOtpCountdownTimer);
      authOtpCountdownTimer = null;
      authOtpResetToken = "";
      passwordForm.hidden = true;
      document.getElementById("otp-success-message").textContent = result.message;
      document.getElementById("otp-success").hidden = false;
      document.getElementById("btn-cancel-otp-flow").hidden = true;
    } catch (error) {
      errorBox.textContent = error.message || "Could not set the password. Please try again.";
    } finally {
      button.disabled = false;
    }
  });
}

function updatePlatformAdminProfileDisplay(account) {
  const emailEl = document.getElementById("header-user-email");
  const roleEl = document.getElementById("header-user-role");
  const scopeBadgeEl = document.getElementById("header-user-scope-badge");
  const empCodeEl = document.getElementById("header-user-emp-code");
  const avatarEl = document.getElementById("user-avatar-initial");
  const bottomRoleEl = document.getElementById("current-account-type");
  const bottomNameEl = document.getElementById("current-account-name");
  const envTextEl = document.getElementById("header-env-text");

  const displayName = account?.name || account?.email || "Platform Admin";
  if (emailEl) emailEl.textContent = account?.email || "admin@senderx.io";
  if (bottomNameEl) bottomNameEl.textContent = displayName;
  if (bottomRoleEl) bottomRoleEl.textContent = "SUPER_ADMIN";
  if (avatarEl) avatarEl.textContent = (displayName.charAt(0) || "A").toUpperCase();
  if (roleEl) {
    roleEl.textContent = account?.role || "SUPER_ADMIN";
    roleEl.className = "user-role badge-primary";
  }
  if (scopeBadgeEl) {
    scopeBadgeEl.textContent = "Platform Root";
    scopeBadgeEl.className = "badge badge-scope";
    scopeBadgeEl.style.display = "inline-block";
  }
  if (empCodeEl) empCodeEl.style.display = "none";
  if (envTextEl) envTextEl.textContent = "Platform Console";
}

async function showDashboard(account) {
  document.getElementById("auth-view").classList.remove("active");
  document.getElementById("app-shell").classList.add("active");

  const accountType = account.account_type;
  const isOrgAdmin = account.is_org_admin === true;
  const roles = account.roles || [];

  const bottomRoleEl = document.getElementById("current-account-type");
  const bottomNameEl = document.getElementById("current-account-name");
  if (bottomNameEl) bottomNameEl.textContent = account.name || account.email;
  if (bottomRoleEl) {
    if (accountType === "PLATFORM_ADMIN") {
      bottomRoleEl.textContent = "PLATFORM_ADMIN";
    } else if (isOrgAdmin) {
      bottomRoleEl.textContent = "ORG_ADMIN";
    } else if (roles.length > 0) {
      bottomRoleEl.textContent = roles[0].name || roles[0].role_id;
    } else {
      bottomRoleEl.textContent = "EMPLOYEE";
    }
  }

  const navPlatform = document.getElementById("nav-platform");
  const navOrg = document.getElementById("nav-organization");

  if (accountType === "PLATFORM_ADMIN") {
    if (navPlatform) navPlatform.style.display = "block";
    if (navOrg) navOrg.style.display = "none";
    updatePlatformAdminProfileDisplay(account);
    switchTab("tab-platform-overview");
  } else {
    if (navPlatform) navPlatform.style.display = "none";
    if (navOrg) navOrg.style.display = "block";
    await initOrganizationDashboard(account);
  }
}

function setupTopNav() {
  const notifBtn = document.getElementById("btn-notifications");
  const notifMenu = document.getElementById("notification-menu");

  notifBtn?.addEventListener("click", (e) => {
    e.stopPropagation();
    notifMenu?.classList.toggle("open");
  });

  document.addEventListener("click", (e) => {
    if (notifMenu && !notifMenu.contains(e.target) && e.target !== notifBtn) {
      notifMenu.classList.remove("open");
    }
  });

  // Mobile sidebar drawer toggle & backdrop
  const mobileNavBtn = document.getElementById("btn-mobile-nav");
  const mobileBackdrop = document.getElementById("mobile-backdrop");
  const sidebar = document.querySelector(".sidebar");

  const closeMobileSidebar = () => {
    sidebar?.classList.remove("mobile-open");
    mobileBackdrop?.classList.remove("active");
  };

  mobileNavBtn?.addEventListener("click", (e) => {
    e.stopPropagation();
    sidebar?.classList.toggle("mobile-open");
    mobileBackdrop?.classList.toggle("active");
  });

  mobileBackdrop?.addEventListener("click", () => {
    closeMobileSidebar();
  });

  // Also close mobile sidebar on nav-item click on smaller screens
  document.querySelectorAll(".nav-item").forEach((item) => {
    item.addEventListener("click", () => {
      if (window.innerWidth <= 900) {
        closeMobileSidebar();
      }
    });
  });

  // Global modal dismissal: backdrop click and Escape key
  document.querySelectorAll(".modal").forEach((m) => {
    m.addEventListener("click", (e) => {
      if (e.target === m) {
        m.classList.remove("active");
      }
    });
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      const activeModal = document.querySelector(".modal.active");
      if (activeModal) {
        activeModal.classList.remove("active");
      }
    }
  });
}

function updateBreadcrumb(tabId) {
  const orgNameEl = document.getElementById("breadcrumb-org-name");
  const tabNameEl = document.getElementById("breadcrumb-current-tab");
  const pageTitleEl = document.getElementById("page-title");
  const pageSubtitleEl = document.getElementById("page-subtitle");

  if (currentOrgProfile?.name && orgNameEl) {
    orgNameEl.textContent = currentOrgProfile.name;
  }

  const tabMeta = {
    "tab-org-overview": { title: "Overview", sub: "Organization performance, application telemetry, and delivery metrics" },
    "tab-org-applications": { title: "Connected Applications", sub: "Register and manage external web applications, e-commerce stores, and microservices" },
    "tab-org-credentials": { title: "API Credentials", sub: "Cryptographically hashed API keys for external payload ingestion" },
    "tab-org-json-requests": { title: "Received JSON Requests", sub: "Immutable audit log of inbound JSON payloads and routing states" },
    "tab-org-dlq": { title: "Dead Letter Queue", sub: "Unrouted or delivery-failed messages requiring inspection or manual retry" },
    "tab-org-analytics": { title: "Analytics", sub: "Comprehensive volume, delivery performance, and failure trends" },
    "tab-org-users": { title: "Employees & Roles", sub: "Manage organization members, assignments, and custom role permissions" },
    "tab-org-settings": { title: "Settings", sub: "Organization profile, environment policies, and security architecture parameters" },
    "tab-platform-overview": { title: "Platform Organizations", sub: "Platform-wide organization management" },
    "tab-platform-change-requests": { title: "Organization Change Requests", sub: "Review, approve, or reject tenant name and slug rebranding requests" },
    "tab-platform-analytics": { title: "Platform Analytics", sub: "Cross-organization telemetry and system throughput" },
    "tab-platform-monitoring": { title: "System Health", sub: "Real-time health status of infrastructure services" },
    "tab-org-messages": { title: "Messages", sub: "Direct message management" },
    "tab-org-templates": { title: "Email Templates", sub: "Multi-tenant sandboxed email templates" }
  };

  const meta = tabMeta[tabId] || { title: "Dashboard", sub: "Multi-tenant messaging platform" };
  if (tabNameEl) tabNameEl.textContent = meta.title;
  if (pageTitleEl) pageTitleEl.textContent = meta.title;
  if (pageSubtitleEl) pageSubtitleEl.textContent = meta.sub;
}

function hasPermission(perm) {
  if (!perm) return true;
  const currentAccount = ApiClient.getStoredAccount();
  if (currentAccount?.account_type === "PLATFORM_ADMIN") return true;
  if (currentUserDashboardContext?.is_org_admin) return true;
  if (currentUserPermissions.has(perm)) return true;
  // Handle dead letters aliases
  if (perm === "organization:dead_letters:read" && (currentUserPermissions.has("organization:dlq:read") || currentUserPermissions.has("organization:dead_letters:read"))) return true;
  if (perm === "organization:dead_letters:manage" && (currentUserPermissions.has("organization:dlq:manage") || currentUserPermissions.has("organization:dead_letters:manage"))) return true;
  return false;
}

function applyPermissionVisibility() {
  document.querySelectorAll("[data-perm]").forEach((el) => {
    const requiredPerm = el.getAttribute("data-perm");
    if (!requiredPerm || hasPermission(requiredPerm)) {
      el.style.display = "";
    } else {
      el.style.display = "none";
    }
  });
}

function renderDynamicSidebar(ctx) {
  const container = document.getElementById("nav-org-items");
  if (!container) return;

  const isOrgAdmin = ctx?.is_org_admin || false;
  let html = "";

  for (const item of DASHBOARD_NAVIGATION) {
    const tabId = item.tabId || item.tab_id;
    const reqPerm = item.requiredPermission || item.required_permission;

    // If not admin and not in allowed tabs, skip
    if (!isOrgAdmin && currentUserAllowedTabs.size > 0 && !currentUserAllowedTabs.has(tabId)) {
      continue;
    }
    // If requires permission and user doesn't have it, skip
    if (reqPerm && !hasPermission(reqPerm)) {
      continue;
    }
    html += `
      <button class="nav-item" data-tab="${tabId}" data-menu-id="${item.id}" data-perm="${reqPerm || ''}">
        <span class="nav-icon">${item.icon}</span>
        <span>${escapeHtml(item.name)}</span>
      </button>
    `;
  }

  container.innerHTML = html;

  container.querySelectorAll(".nav-item").forEach((btn) => {
    btn.addEventListener("click", () => {
      const tabId = btn.getAttribute("data-tab");
      if (tabId && tabId !== "undefined") switchTab(tabId);
    });
  });
}

function renderApplicationScopeSelector(ctx) {
  const box = document.getElementById("header-scope-box");
  const select = document.getElementById("header-scope-select");
  if (!box || !select) return;

  const isOrgAdmin = ctx?.is_org_admin || false;
  const assignedApps = ctx?.assigned_applications || [];

  if (isOrgAdmin) {
    box.style.display = "flex";
    let html = `<option value="">All Applications (Global Scope)</option>`;
    ApiClient.listApplications(1, 100).then((res) => {
      if (res.success && res.data) {
        res.data.forEach((app) => {
          html += `<option value="${escapeHtml(app.application_id)}">${escapeHtml(app.name)}</option>`;
        });
        select.innerHTML = html;
        select.value = ApiClient.getActiveApplicationId() || "";
      }
    }).catch(() => {
      select.innerHTML = `<option value="">All Applications (Global Scope)</option>`;
    });
  } else {
    // Employee: only assigned applications
    if (assignedApps.length === 0) {
      box.style.display = "none";
      ApiClient.setActiveApplicationId(null);
    } else {
      box.style.display = "flex";
      let html = "";
      if (assignedApps.length > 1) {
        html += `<option value="">Select Scoped Application (${assignedApps.length} assigned)</option>`;
      }
      assignedApps.forEach((app) => {
        html += `<option value="${escapeHtml(app.application_id)}">${escapeHtml(app.name)}</option>`;
      });
      select.innerHTML = html;

      const currentActive = ApiClient.getActiveApplicationId();
      const isAssigned = assignedApps.some((a) => a.application_id === currentActive);
      if (isAssigned) {
        select.value = currentActive;
      } else {
        select.value = assignedApps[0].application_id;
        ApiClient.setActiveApplicationId(assignedApps[0].application_id);
      }
    }
  }

  select.onchange = (e) => {
    const val = e.target.value;
    handleAppScopeChange(val);
  };
}

function handleAppScopeChange(val) {
  ApiClient.setActiveApplicationId(val || null);
  showToast(val ? "Application scope updated" : "Global application scope selected", "info");
  const activeTab = document.querySelector(".tab-pane.active");
  if (activeTab && activeTab.id) {
    handleTabActivation(activeTab.id);
  }
}

async function loadDashboardContext() {
  try {
    const res = await ApiClient.getDashboardContext();
    if (res && res.success && res.data) {
      currentUserDashboardContext = res.data;
      return res.data;
    }
  } catch (err) {
    console.warn("Could not load dashboard context from API:", err);
  }
  return null;
}

function updateUserProfileDisplay(ctx) {
  const emailEl = document.getElementById("header-user-email");
  const roleEl = document.getElementById("header-user-role") || document.getElementById("header-user-role-badge");
  const scopeBadgeEl = document.getElementById("header-user-scope-badge");
  const avatarEl = document.getElementById("user-avatar-initial");
  const profilePill = document.getElementById("user-profile-pill");
  const bottomRoleEl = document.getElementById("current-account-type");
  const bottomNameEl = document.getElementById("current-account-name");

  if (emailEl) emailEl.textContent = ctx?.email || "User";

  const displayName = ctx?.name || ctx?.email || "User";
  if (bottomNameEl) bottomNameEl.textContent = displayName;

  if (avatarEl) {
    avatarEl.textContent = (displayName.charAt(0) || "U").toUpperCase();
  }

  const isOrgAdmin = ctx?.is_org_admin === true;
  const roles = ctx?.roles || [];

  let roleLabel = "EMPLOYEE (No Role)";
  let roleClass = "user-role badge-secondary";

  if (isOrgAdmin) {
    roleLabel = "ORG_ADMIN";
    roleClass = "user-role badge-primary";
  } else if (roles.length > 0) {
    roleLabel = roles.map((r) => r.name || r.role_id).join(", ");
    roleClass = "user-role badge-info";
  }

  if (roleEl) {
    roleEl.textContent = roleLabel;
    roleEl.className = roleClass;
  }

  if (bottomRoleEl) {
    bottomRoleEl.textContent = isOrgAdmin ? "ORG_ADMIN" : (roles.length > 0 ? roles[0].name : "EMPLOYEE");
  }

  if (scopeBadgeEl) {
    if (isOrgAdmin) {
      scopeBadgeEl.textContent = "All Applications";
      scopeBadgeEl.className = "badge badge-scope";
      scopeBadgeEl.style.display = "inline-block";
    } else {
      const apps = ctx?.assigned_applications || [];
      if (apps.length === 0) {
        scopeBadgeEl.textContent = "No Apps";
        scopeBadgeEl.style.display = "inline-block";
      } else if (apps.length === 1) {
        scopeBadgeEl.textContent = apps[0].name || apps[0].application_id;
        scopeBadgeEl.style.display = "inline-block";
      } else {
        scopeBadgeEl.textContent = `${apps.length} Apps`;
        scopeBadgeEl.style.display = "inline-block";
      }
      scopeBadgeEl.className = "badge badge-scope";
    }
  }

  if (profilePill) {
    profilePill.onclick = () => showUserProfile();
  }

  // Employee Code in Header Pill
  const empCodeEl = document.getElementById("header-user-emp-code");
  if (empCodeEl) {
    if (ctx?.employee_code) {
      empCodeEl.textContent = ctx.employee_code;
      empCodeEl.style.display = "inline-block";
    } else {
      empCodeEl.style.display = "none";
    }
  }
}

async function showUserProfile() {
  const modal = document.getElementById("modal-user-profile");
  if (!modal) return;

  // 1. Fetch fresh authoritative account data from backend /api/v1/auth/me
  let account = ApiClient.getStoredAccount();
  try {
    const meRes = await ApiClient.getCurrentAccount();
    if (meRes && meRes.success && meRes.data) {
      account = meRes.data;
      ApiClient.setStoredAccount(account);
    }
  } catch (err) {
    console.warn("Could not fetch current account from /auth/me for profile modal:", err);
  }

  if (!account) return;

  const isPlatformAdmin = account.account_type === "PLATFORM_ADMIN";

  const titleEl = document.getElementById("profile-modal-title");
  const nameEl = document.getElementById("profile-modal-name");
  const emailEl = document.getElementById("profile-modal-email") || document.getElementById("modal-profile-email");
  const statusEl = document.getElementById("profile-modal-status");
  const roleBadgeEl = document.getElementById("profile-modal-role");
  const orgEl = document.getElementById("profile-modal-org") || document.getElementById("modal-profile-org");
  const createdEl = document.getElementById("profile-modal-created");
  const lastLoginEl = document.getElementById("profile-modal-last-login");
  const empIdEl = document.getElementById("profile-modal-emp-id");
  const rolesListEl = document.getElementById("profile-modal-roles") || document.getElementById("modal-profile-roles-list");
  const appsListEl = document.getElementById("profile-modal-apps") || document.getElementById("modal-profile-apps-list");
  const permsCountEl = document.getElementById("profile-modal-perm-count");
  const permsListEl = document.getElementById("profile-modal-perms") || document.getElementById("modal-profile-perms-list");

  if (isPlatformAdmin) {
    // ----------------------------------------------------
    // SUPER_ADMIN / PLATFORM_ADMIN PROFILE
    // ----------------------------------------------------
    if (titleEl) titleEl.textContent = "Platform Administrator Profile";
    const displayName = account.name || "Platform Super Administrator";
    if (nameEl) nameEl.textContent = displayName;
    if (emailEl) emailEl.textContent = account.email || "admin@senderx.io";
    if (statusEl) {
      const isAct = account.status === "ACTIVE" || account.is_active !== false;
      statusEl.textContent = isAct ? "ACTIVE" : "INACTIVE";
      statusEl.className = isAct ? "badge badge-success" : "badge badge-danger";
    }
    if (roleBadgeEl) {
      roleBadgeEl.textContent = account.role || "SUPER_ADMIN";
      roleBadgeEl.className = "badge badge-primary";
    }
    if (orgEl) orgEl.textContent = "Platform Root (Multi-Tenant System)";
    if (createdEl) {
      createdEl.textContent = account.created_at ? new Date(account.created_at).toLocaleString() : "System Inception";
    }
    if (lastLoginEl) {
      const loginTime = account.last_login || account.last_login_at;
      lastLoginEl.textContent = loginTime ? new Date(loginTime).toLocaleString() : "Active Session";
    }
    if (empIdEl) empIdEl.style.display = "none";

    if (rolesListEl) {
      rolesListEl.innerHTML = `
        <div style="background: rgba(99,102,241,0.15); border: 1px solid rgba(99,102,241,0.35); border-radius: 6px; padding: 10px 14px; display: flex; justify-content: space-between; align-items: center;">
          <div>
            <strong style="color: #818cf8;">${escapeHtml(account.role || "SUPER_ADMIN")} (Root Platform Administrator)</strong>
            <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 2px;">Full administrative authority across all platform tenants, organizations, and monitoring subsystems</div>
          </div>
          <span class="badge badge-primary" style="font-size: 0.75rem;">Platform-Wide Scope</span>
        </div>
      `;
    }

    if (appsListEl) {
      appsListEl.innerHTML = `
        <span class="badge badge-success" style="padding: 4px 10px; font-size: 0.8rem;">All Tenant Connected Applications (Global Scope)</span>
      `;
    }

    if (permsCountEl) permsCountEl.textContent = "5+ (Full Platform Access)";
    if (permsListEl) {
      const platformPerms = [
        "platform:organizations:read",
        "platform:organizations:manage",
        "platform:analytics:read",
        "platform:health:read",
        "platform:providers:manage"
      ];
      permsListEl.innerHTML = `<div style="width: 100%; color: var(--text-secondary); font-size: 0.8rem; margin-bottom: 6px;"><strong>Unrestricted Platform Privileges</strong></div>` +
        platformPerms.map((p) => `<span class="badge badge-secondary" style="margin: 2px 4px 2px 0; font-size: 0.72rem;">${escapeHtml(p)}</span>`).join("");
    }
  } else {
    // ----------------------------------------------------
    // ORGANIZATION USER / ORG_ADMIN / EMPLOYEE PROFILE
    // ----------------------------------------------------
    if (titleEl) titleEl.textContent = "User Profile & Access Scopes";

    const freshCtx = await loadDashboardContext();
    const ctx = freshCtx || currentUserDashboardContext || account;

    const displayName = ctx.name || ctx.email || "Organization User";
    if (nameEl) nameEl.textContent = displayName;
    if (emailEl) emailEl.textContent = ctx.email || account.email;

    if (statusEl) {
      const isAct = ctx.is_active !== false && ctx.status !== "INACTIVE";
      statusEl.textContent = isAct ? "ACTIVE" : "INACTIVE";
      statusEl.className = isAct ? "badge badge-success" : "badge badge-danger";
    }

    const isOrgAdmin = ctx.is_org_admin === true;
    const roles = ctx.roles || [];
    if (roleBadgeEl) {
      if (isOrgAdmin) {
        roleBadgeEl.textContent = "ORG_ADMIN";
        roleBadgeEl.className = "badge badge-primary";
      } else if (roles.length > 0) {
        roleBadgeEl.textContent = roles.map(r => r.name || r.role_id).join(", ");
        roleBadgeEl.className = "badge badge-info";
      } else {
        roleBadgeEl.textContent = "EMPLOYEE";
        roleBadgeEl.className = "badge badge-secondary";
      }
    }

    if (orgEl) {
      orgEl.textContent = ctx.organization_name || account.organization_name || "Organization Workspace";
    }

    if (createdEl) {
      const cDate = ctx.created_at || account.created_at;
      createdEl.textContent = cDate ? new Date(cDate).toLocaleString() : "-";
    }

    if (lastLoginEl) {
      const lDate = ctx.last_login || ctx.last_login_at || account.last_login || account.last_login_at;
      lastLoginEl.textContent = lDate ? new Date(lDate).toLocaleString() : "Active Session";
    }

    if (empIdEl) {
      const code = ctx.employee_code || account.employee_code;
      if (code) {
        empIdEl.textContent = code;
        empIdEl.style.display = "inline-block";
      } else {
        empIdEl.style.display = "none";
      }
    }

    if (rolesListEl) {
      const assignments = ctx.role_assignments || [];
      if (isOrgAdmin) {
        rolesListEl.innerHTML = `
          <div style="background: rgba(99,102,241,0.15); border: 1px solid rgba(99,102,241,0.35); border-radius: 6px; padding: 8px 12px; display: flex; justify-content: space-between; align-items: center;">
            <strong style="color: #818cf8;">ORG_ADMIN (Predefined Organization Admin)</strong>
            <span class="badge badge-primary" style="font-size: 0.75rem;">Organization-Wide</span>
          </div>
        `;
      } else if (assignments.length > 0) {
        rolesListEl.innerHTML = assignments.map((a) => `
          <div style="background: var(--bg-surface); border: 1px solid var(--border-color); border-radius: 6px; padding: 8px 12px; display: flex; justify-content: space-between; align-items: center;">
            <div>
              <strong style="color: var(--accent-cyan);">${escapeHtml(a.role_name || "Custom Role")}</strong>
              <span style="font-size: 0.75rem; color: var(--text-muted); margin-left: 6px;">(${a.permissions ? a.permissions.length : 0} perms)</span>
            </div>
            <span class="badge ${a.application_id ? 'badge-scope' : 'badge-primary'}" style="font-size: 0.75rem;">
              ${escapeHtml(a.application_name || (a.application_id ? 'App-scoped' : 'Org-wide'))}
            </span>
          </div>
        `).join("");
      } else if (roles.length > 0) {
        rolesListEl.innerHTML = roles.map((r) => `
          <div style="background: var(--bg-surface); border: 1px solid var(--border-color); border-radius: 6px; padding: 8px 12px; display: flex; justify-content: space-between; align-items: center;">
            <strong style="color: var(--accent-cyan);">${escapeHtml(r.name || r.role_id)}</strong>
            <span class="badge badge-scope" style="font-size: 0.75rem;">${r.application_id ? escapeHtml(r.application_id) : 'Org-wide'}</span>
          </div>
        `).join("");
      } else {
        rolesListEl.innerHTML = `<div style="color: var(--text-muted); font-size: 0.85rem; padding: 6px 0;">No roles assigned yet. Contact your administrator.</div>`;
      }
    }

    if (appsListEl) {
      const apps = ctx.assigned_applications || [];
      if (isOrgAdmin) {
        appsListEl.innerHTML = `<span class="badge badge-success" style="padding: 4px 10px;">All Connected Applications (Unrestricted Org Scope)</span>`;
      } else if (apps.length === 0) {
        appsListEl.innerHTML = `<span style="color: var(--text-muted); font-size: 0.85rem;">No application scopes assigned.</span>`;
      } else {
        appsListEl.innerHTML = apps.map((a) => `
          <span class="badge badge-scope" style="padding: 4px 10px; font-size: 0.8rem;">
            ${escapeHtml(a.name || a.application_id)}
          </span>
        `).join("");
      }
    }

    const perms = ctx.effective_permissions || [];
    if (permsCountEl) permsCountEl.textContent = perms.length;

    if (permsListEl) {
      if (isOrgAdmin) {
        permsListEl.innerHTML = `<div style="width: 100%; color: var(--text-secondary); font-size: 0.8rem; margin-bottom: 6px;"><strong>Full Organization Admin Privileges (${ALL_ORG_PERMISSIONS.length} Permissions)</strong></div>` +
          ALL_ORG_PERMISSIONS.map((p) => `<span class="badge badge-secondary" style="margin: 2px 4px 2px 0; font-size: 0.72rem;">${escapeHtml(p)}</span>`).join("");
      } else if (perms.length === 0) {
        permsListEl.innerHTML = `<span style="color: var(--text-muted); font-size: 0.85rem;">No active permissions. Module access is restricted.</span>`;
      } else {
        permsListEl.innerHTML = perms.map((p) => `
          <span class="badge badge-secondary" style="margin: 2px 4px 2px 0; font-size: 0.72rem;">${escapeHtml(p)}</span>
        `).join("");
      }
    }
  }

  modal.classList.add("active");
}

function openUserProfileModal() {
  showUserProfile();
}

function closeUserProfileModal() {
  const modal = document.getElementById("modal-user-profile");
  if (modal) modal.classList.remove("active");
}

function showAccessDenied(reason) {
  document.querySelectorAll(".tab-pane").forEach((p) => {
    p.classList.remove("active");
    p.style.display = "none";
  });
  document.querySelectorAll(".nav-item").forEach((n) => n.classList.remove("active"));

  const deniedPane = document.getElementById("tab-access-denied");
  if (deniedPane) {
    deniedPane.classList.add("active");
    deniedPane.style.display = "block";
    const reasonEl = document.getElementById("access-denied-reason");
    if (reasonEl && reason) {
      reasonEl.textContent = reason;
    }
  }
  showToast(reason || "Access denied: insufficient permissions", "error");
}

function switchTab(targetId) {
  if (!targetId || targetId === "undefined") {
    console.warn("switchTab called with invalid targetId:", targetId);
    return;
  }
  const currentAccount = ApiClient.getStoredAccount();
  const isPlatformAdmin = currentAccount?.account_type === "PLATFORM_ADMIN";
  const isOrgAdmin = currentUserDashboardContext?.is_org_admin || false;

  // Platform tabs check
  if (targetId.startsWith("tab-platform-")) {
    if (!isPlatformAdmin) {
      showAccessDenied("Only platform administrators can access platform management modules.");
      return;
    }
  }

  // Organization tabs check
  if (targetId.startsWith("tab-org-")) {
    if (isPlatformAdmin) {
      showAccessDenied("Platform administrators must access platform sections.");
      return;
    }

    if (!isOrgAdmin) {
      if (currentUserAllowedTabs.size > 0 && !currentUserAllowedTabs.has(targetId)) {
        showAccessDenied(`You do not have permission to access this module (${targetId.replace('tab-org-', '')}).`);
        return;
      }
    }
  }

  document.querySelectorAll(".tab-pane").forEach((p) => {
    p.classList.remove("active");
    p.style.display = "none";
  });
  document.querySelectorAll(".nav-item").forEach((n) => n.classList.remove("active"));

  const targetPane = document.getElementById(targetId);
  if (targetPane) {
    targetPane.classList.add("active");
    targetPane.style.display = "block";
  }

  const matchingBtn = document.querySelector(`.nav-item[data-tab="${targetId}"]`);
  if (matchingBtn) {
    matchingBtn.classList.add("active");
  }

  handleTabActivation(targetId);
}

function navigateToTab(tabId) {
  switchTab(tabId);
}

async function initOrganizationDashboard(account) {
  const orgNameEl = document.getElementById("breadcrumb-org-name");
  try {
    const res = await ApiClient.getCurrentOrganization();
    if (res.success && res.data) {
      currentOrgProfile = res.data;
      if (orgNameEl) orgNameEl.textContent = res.data.name;
      const envIndicator = document.getElementById("header-env-indicator");
      const envText = document.getElementById("header-env-text");
      if (envIndicator && envText) {
        if (res.data.status === "ACTIVE") {
          envIndicator.className = "env-indicator env-live";
          envText.textContent = "Production";
        } else {
          envIndicator.className = "env-indicator env-test";
          envText.textContent = res.data.status || "Test";
        }
      }
    }
  } catch (err) {
    if (orgNameEl) orgNameEl.textContent = "Organization Workspace";
  }

  currentUserPermissions.clear();
  currentUserAllowedTabs.clear();
  currentUserAllowedWidgets.clear();

  let ctx = await loadDashboardContext();
  if (!ctx && account) {
    ctx = {
      user_id: account.user_id || account.id,
      name: account.name || account.email,
      email: account.email,
      account_type: "ORGANIZATION_USER",
      organization_id: account.organization_id,
      organization_name: account.organization_name || "Organization Workspace",
      is_org_admin: account.is_org_admin === true,
      roles: account.roles || [],
      role_assignments: account.role_assignments || [],
      assigned_applications: account.assigned_applications || [],
      effective_permissions: account.effective_permissions || [],
      allowed_tabs: account.allowed_tabs || ["tab-org-overview"],
      allowed_widgets: account.allowed_widgets || []
    };
    currentUserDashboardContext = ctx;
  }

  if (ctx) {
    (ctx.allowed_tabs || []).forEach((t) => currentUserAllowedTabs.add(t));
    (ctx.allowed_widgets || []).forEach((w) => currentUserAllowedWidgets.add(w));

    if (ctx.is_org_admin) {
      ALL_ORG_PERMISSIONS.forEach((p) => currentUserPermissions.add(p));
    } else {
      (ctx.effective_permissions || []).forEach((p) => currentUserPermissions.add(p));
    }

    renderDynamicSidebar(ctx);
    renderApplicationScopeSelector(ctx);
    updateUserProfileDisplay(ctx);
  }

  applyPermissionVisibility();

  // If currently active tab is not allowed, switch to first allowed tab
  const currentActiveTab = document.querySelector(".tab-pane.active")?.id;
  if (!currentActiveTab || (currentUserAllowedTabs.size > 0 && !currentUserAllowedTabs.has(currentActiveTab))) {
    const defaultTab = currentUserAllowedTabs.has("tab-org-overview")
      ? "tab-org-overview"
      : (Array.from(currentUserAllowedTabs)[0] || "tab-org-overview");
    switchTab(defaultTab);
  }
}

async function handleTabActivation(tabId) {
  updateBreadcrumb(tabId);

  switch (tabId) {
    case "tab-platform-overview":
      await loadOrganizations();
      break;
    case "tab-platform-change-requests":
      await loadPlatformChangeRequests();
      break;
    case "tab-platform-analytics":
      await loadPlatformAnalytics();
      break;
    case "tab-platform-monitoring":
      await loadSystemHealth();
      break;
    case "tab-org-overview":
      await loadOrgOverview();
      break;
    case "tab-org-applications":
      await loadOrgApplications();
      break;
    case "tab-org-credentials":
      await loadOrgCredentials();
      break;
    case "tab-org-json-requests":
      await loadOrgJsonRequests();
      break;
    case "tab-org-dlq":
      await loadOrgDlq();
      break;
    case "tab-org-analytics":
      await loadOrgAnalytics();
      break;
    case "tab-org-users":
      await loadOrgUsers();
      break;
    case "tab-org-settings":
      await loadOrgSettings();
      break;
    case "tab-org-messages":
      await loadOrgMessages();
      break;
    case "tab-org-templates":
      await loadOrgTemplates();
      break;
  }
}

// ----------------------------------------------------
// PLATFORM OPERATIONS
// ----------------------------------------------------
let platformOrgsCurrentPage = 1;
let platformOrgsLimit = 50;
let platformOrgsSearch = "";
let platformOrgsStatus = "ALL";
let platformOrgsDebounceTimer = null;

async function loadOrganizations(page = platformOrgsCurrentPage, limit = platformOrgsLimit) {
  platformOrgsCurrentPage = page;
  platformOrgsLimit = limit;

  const tbody = document.getElementById("orgs-table-body");
  if (!tbody) return;
  tbody.innerHTML = '<tr><td colspan="5" class="loading-cell">Loading organizations...</td></tr>';

  try {
    const filters = {
      search: platformOrgsSearch,
      status: platformOrgsStatus
    };
    const res = await ApiClient.listOrganizations(page, limit, filters);
    if (res.success && res.data) {
      if (res.data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="loading-cell">No organizations found matching your criteria.</td></tr>';
      } else {
        tbody.innerHTML = res.data
          .map(
            (org) => `
          <tr>
            <td>
              <div style="font-weight: 600; color: var(--text-primary); cursor: pointer;" onclick="openOrgDetailsModal('${org.organization_id}')" title="View details">${escapeHtml(org.name)}</div>
            </td>
            <td><code>${escapeHtml(org.slug)}</code></td>
            <td><span class="badge badge-${(org.status || "active").toLowerCase()}">${org.status || "ACTIVE"}</span></td>
            <td>${new Date(org.created_at).toLocaleDateString()}</td>
            <td style="text-align: right;">
              <div style="display: inline-flex; gap: 8px; justify-content: flex-end;">
                <button class="btn btn-secondary btn-sm" onclick="openOrgDetailsModal('${org.organization_id}')">Details</button>
                ${
                  org.status === "ACTIVE"
                    ? `<button class="btn btn-secondary btn-sm" onclick="toggleOrgStatus('${org.organization_id}', 'INACTIVE')">Deactivate</button>`
                    : org.status === "INACTIVE"
                    ? `<button class="btn btn-primary btn-sm" onclick="toggleOrgStatus('${org.organization_id}', 'ACTIVE')">Activate</button>`
                    : ""
                }
                ${
                  org.status !== "DELETED"
                    ? `<button class="btn btn-danger btn-sm" onclick="openDeleteOrgModal('${org.organization_id}', '${escapeHtml(org.name)}', '${escapeHtml(org.slug)}')">Delete</button>`
                    : `<span class="badge badge-inactive">DELETED</span>`
                }
              </div>
            </td>
          </tr>
        `
          )
          .join("");
      }

      // Update Pagination Controls
      const pagination = res.pagination || { total: res.total_count || 0, page: 1, limit: 50, total_pages: 1 };
      const total = pagination.total || 0;
      const totalPages = pagination.total_pages || 1;
      const start = total === 0 ? 0 : (page - 1) * limit + 1;
      const end = Math.min(page * limit, total);

      const infoEl = document.getElementById("platform-org-pagination-info");
      const indicatorEl = document.getElementById("platform-org-page-indicator");
      const prevBtn = document.getElementById("platform-org-prev-btn");
      const nextBtn = document.getElementById("platform-org-next-btn");

      if (infoEl) infoEl.textContent = `Showing ${start} - ${end} of ${total} organizations`;
      if (indicatorEl) indicatorEl.textContent = `Page ${page} of ${totalPages}`;
      if (prevBtn) prevBtn.disabled = page <= 1;
      if (nextBtn) nextBtn.disabled = page >= totalPages;
    } else {
      tbody.innerHTML = `<tr><td colspan="5" class="loading-cell error">${res.message || "Failed to load organizations"}</td></tr>`;
    }
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="5" class="loading-cell error">${err.message || "Could not connect to API server"}</td></tr>`;
  }
}

function debounceFilterPlatformOrgs() {
  clearTimeout(platformOrgsDebounceTimer);
  platformOrgsDebounceTimer = setTimeout(() => {
    const input = document.getElementById("platform-org-search");
    platformOrgsSearch = input ? input.value.trim() : "";
    loadOrganizations(1);
  }, 250);
}

function handlePlatformOrgStatusChange(val) {
  platformOrgsStatus = val;
  loadOrganizations(1);
}

function handlePlatformOrgLimitChange(val) {
  platformOrgsLimit = parseInt(val, 10) || 50;
  loadOrganizations(1, platformOrgsLimit);
}

function resetPlatformOrgFilters() {
  platformOrgsSearch = "";
  platformOrgsStatus = "ALL";
  const searchInput = document.getElementById("platform-org-search");
  if (searchInput) searchInput.value = "";
  const statusSelect = document.getElementById("platform-org-status-filter");
  if (statusSelect) statusSelect.value = "ALL";
  const limitSelect = document.getElementById("platform-org-limit-select");
  if (limitSelect) limitSelect.value = "50";
  platformOrgsLimit = 50;
  loadOrganizations(1, 50);
}

function navigatePlatformOrgsPage(delta) {
  const newPage = platformOrgsCurrentPage + delta;
  if (newPage >= 1) {
    loadOrganizations(newPage);
  }
}

async function openOrgDetailsModal(orgId) {
  const modal = document.getElementById("modal-org-details");
  if (!modal) return;
  openModal("modal-org-details");

  // Loading placeholders
  document.getElementById("org-detail-name").textContent = "Loading...";
  document.getElementById("org-detail-slug").textContent = "-";
  if (document.getElementById("org-detail-id")) document.getElementById("org-detail-id").textContent = "";
  document.getElementById("org-detail-status-badge").textContent = "...";
  if (document.getElementById("org-detail-prefix")) document.getElementById("org-detail-prefix").textContent = "-";
  document.getElementById("org-detail-users-count").textContent = "-";
  document.getElementById("org-detail-apps-count").textContent = "-";
  document.getElementById("org-detail-admin").textContent = "-";
  document.getElementById("org-detail-created").textContent = "-";
  document.getElementById("org-detail-toggle-action").innerHTML = "";

  try {
    const res = await ApiClient.getOrganizationDetails(orgId);
    if (res.success && res.data) {
      const org = res.data;
      document.getElementById("org-detail-name").textContent = org.name;
      document.getElementById("org-detail-slug").textContent = org.slug;
      if (document.getElementById("org-detail-id")) document.getElementById("org-detail-id").textContent = "";
      
      const badge = document.getElementById("org-detail-status-badge");
      badge.textContent = org.status || "ACTIVE";
      badge.className = `badge badge-${(org.status || "active").toLowerCase()}`;

      if (document.getElementById("org-detail-prefix")) document.getElementById("org-detail-prefix").textContent = org.employee_id_prefix || "None (Default: EMP)";
      document.getElementById("org-detail-users-count").textContent = org.user_count !== undefined ? org.user_count : "-";
      document.getElementById("org-detail-apps-count").textContent = org.application_count !== undefined ? org.application_count : "-";
      
      if (org.admin) {
        document.getElementById("org-detail-admin").textContent = `${org.admin.name} (${org.admin.email}) [${org.admin.role || "ORG_ADMIN"}]`;
      } else {
        document.getElementById("org-detail-admin").textContent = "No administrator user linked";
      }

      document.getElementById("org-detail-created").textContent = org.created_at ? new Date(org.created_at).toLocaleString() : "-";

      const toggleActionBox = document.getElementById("org-detail-toggle-action");
      if (org.status === "ACTIVE") {
        toggleActionBox.innerHTML = `
          <button class="btn btn-secondary" onclick="toggleOrgStatusFromModal('${org.organization_id}', 'INACTIVE')">Deactivate Organization</button>
          <button class="btn btn-danger" style="margin-left: 8px;" onclick="closeModal('modal-org-details'); openDeleteOrgModal('${org.organization_id}', '${escapeHtml(org.name)}', '${escapeHtml(org.slug)}')">Delete Organization</button>
        `;
      } else if (org.status === "INACTIVE") {
        toggleActionBox.innerHTML = `
          <button class="btn btn-primary" onclick="toggleOrgStatusFromModal('${org.organization_id}', 'ACTIVE')">Activate Organization</button>
          <button class="btn btn-danger" style="margin-left: 8px;" onclick="closeModal('modal-org-details'); openDeleteOrgModal('${org.organization_id}', '${escapeHtml(org.name)}', '${escapeHtml(org.slug)}')">Delete Organization</button>
        `;
      } else {
        toggleActionBox.innerHTML = `<span class="badge badge-inactive">ORGANIZATION DELETED</span>`;
      }
    } else {
      showToast(res.message || "Could not load organization details", "danger");
      closeModal("modal-org-details");
    }
  } catch (err) {
    showToast(err.message || "Failed to fetch organization details", "danger");
    closeModal("modal-org-details");
  }
}

async function toggleOrgStatusFromModal(orgId, status) {
  closeModal("modal-org-details");
  await toggleOrgStatus(orgId, status);
}

async function toggleOrgStatus(orgId, status) {
  try {
    const res = await ApiClient.updateOrganizationStatus(orgId, status);
    if (res.success) {
      showToast(`Organization is now ${status}`, "success");
      loadOrganizations();
    } else {
      showToast(res.message || "Failed to update organization status", "danger");
    }
  } catch (err) {
    showToast(err.message, "danger");
  }
}

function setupCreateOrgForm() {
  document.getElementById("form-create-org")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = {
      name: document.getElementById("new-org-name").value.trim(),
      slug: document.getElementById("new-org-slug").value.trim().toLowerCase(),
      admin_name: document.getElementById("new-org-admin-name").value.trim(),
      admin_email: document.getElementById("new-org-admin-email").value.trim().toLowerCase(),
      admin_password: document.getElementById("new-org-admin-password").value
    };

    try {
      const res = await ApiClient.createOrganization(payload);
      if (res.success) {
        showToast("Organization created successfully!", "success");
        closeModal("modal-create-org");
        document.getElementById("form-create-org").reset();
        // Reset any search or status filter so newly created org appears at the top of page 1
        platformOrgsSearch = "";
        platformOrgsStatus = "ALL";
        const searchInput = document.getElementById("platform-org-search");
        if (searchInput) searchInput.value = "";
        const statusSelect = document.getElementById("platform-org-status-filter");
        if (statusSelect) statusSelect.value = "ALL";
        await loadOrganizations(1);
      } else {
        showToast(res.message || "Failed to create organization", "danger");
      }
    } catch (err) {
      showToast(err.message, "danger");
    }
  });
}

async function loadPlatformAnalytics() {
  try {
    const res = await ApiClient.getPlatformAnalytics();
    if (res.success && res.overview) {
      document.getElementById("plat-m-total").textContent = res.overview.total_messages;
      document.getElementById("plat-m-sent").textContent = res.overview.sent;
      document.getElementById("plat-m-failed").textContent = res.overview.failed;
      document.getElementById("plat-m-dead").textContent = res.overview.dead;
      document.getElementById("plat-m-rate").textContent = `${res.overview.delivery_rate_percent}%`;
    }
  } catch (err) {
    console.error(err);
  }
}

async function loadSystemHealth() {
  try {
    const res = await ApiClient.getDetailedHealth();
    if (res.data) {
      document.getElementById("h-flask").textContent = res.data.flask || "operational";
      document.getElementById("h-mongo").textContent = res.data.mongodb || "unknown";
      document.getElementById("h-redis").textContent = res.data.redis || "unknown";
      document.getElementById("h-rabbitmq").textContent = res.data.rabbitmq || "unknown";
      document.getElementById("h-celery").textContent = `${res.data.celery_workers || 0} worker(s)`;
    }
  } catch (err) {
    console.error(err);
  }
}

// ----------------------------------------------------
// ORGANIZATION OPERATIONS
// ----------------------------------------------------
// ----------------------------------------------------
// MESSAGE MANAGEMENT DASHBOARD STATE & CONTROLLER (Phase 5 Task 5.1)
// ----------------------------------------------------
let msgCurrentPage = 1;
let msgLimit = 50;
let msgSearch = "";
let msgStatus = "";
let msgChannel = "";
let msgAppId = "";
let msgStartDate = "";
let msgEndDate = "";
let msgDebounceTimer = null;
let msgActiveSubtab = "history";
let msgCurrentRetryingId = null;
let msgCurrentViewingMessage = null;
let msgComposerAttachments = [];
let msgCachedApps = [];
let msgCachedTemplates = [];

function getAuthorizedAppIds() {
  const account = ApiClient.getStoredAccount();
  if (account?.account_type === "PLATFORM_ADMIN" || currentUserDashboardContext?.is_org_admin) {
    return null; // Organization admin or platform admin has full org-wide scope
  }
  if (Array.isArray(currentUserDashboardContext?.authorized_applications)) {
    return currentUserDashboardContext.authorized_applications.map(a => typeof a === "object" ? a.application_id : a);
  }
  if (Array.isArray(account?.application_ids)) {
    return account.application_ids;
  }
  return null;
}

function switchMessageSubtab(subtab) {
  msgActiveSubtab = subtab;
  const pills = {
    history: document.getElementById("pill-msg-history"),
    composer: document.getElementById("pill-msg-composer"),
    scheduled: document.getElementById("pill-msg-scheduled"),
    analytics: document.getElementById("pill-msg-analytics")
  };
  const views = {
    history: document.getElementById("subview-msg-history"),
    composer: document.getElementById("subview-msg-composer"),
    scheduled: document.getElementById("subview-msg-scheduled"),
    analytics: document.getElementById("subview-msg-analytics")
  };

  Object.keys(pills).forEach((k) => {
    if (pills[k]) pills[k].classList.toggle("active", k === subtab);
  });
  Object.keys(views).forEach((k) => {
    if (views[k]) views[k].style.display = k === subtab ? "block" : "none";
  });

  if (subtab === "history") {
    loadOrgMessages(msgCurrentPage, msgLimit);
  } else if (subtab === "composer") {
    initMessageComposer();
  } else if (subtab === "analytics") {
    loadMessageAnalytics();
  }
}

async function populateMessageFilterApps() {
  try {
    const res = await ApiClient.listApplications(1, 100);
    if (res.success && res.data) {
      msgCachedApps = res.data;
      const select = document.getElementById("msg-filter-app");
      if (select) {
        const authorizedScopes = getAuthorizedAppIds();
        const availableApps = authorizedScopes 
          ? msgCachedApps.filter(a => authorizedScopes.includes(a.application_id))
          : msgCachedApps;

        select.innerHTML = '<option value="">All Applications</option>' +
          availableApps.map(a => `<option value="${escapeHtml(a.application_id)}">${escapeHtml(a.name)} (${escapeHtml(a.environment || "live")})</option>`).join("");
      }
    }
  } catch (err) {
    console.warn("Failed to load connected applications:", err);
  }
}

async function updateMessageSummaryMetrics() {
  try {
    const res = await ApiClient.getOrganizationAnalytics();
    if (res.success || res.overview) {
      const d = res.data || res;
      const total = d.overview?.total_messages ?? (d.total_messages || 0);
      const statusCounts = d.status_breakdown || {};
      const sent = d.overview?.sent ?? (statusCounts.SENT || 0);
      const delivered = statusCounts.DELIVERED || 0;
      const failed = d.overview?.failed ?? ((statusCounts.FAILED || 0) + (statusCounts.DEAD || 0));
      const queued = d.overview?.queued ?? ((statusCounts.QUEUED || 0) + (statusCounts.PROCESSING || 0));
      const dlqTotal = d.dead_letter_queue?.total_records ?? (d.dead_letters?.total || 0);
      const rate = d.overview?.delivery_rate_percent ?? (d.delivery_success_rate || 0);

      const setEl = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.textContent = val;
      };

      setEl("msg-stat-total", total.toLocaleString());
      setEl("msg-stat-sent", sent.toLocaleString());
      setEl("msg-stat-delivered", delivered.toLocaleString());
      setEl("msg-stat-rate", `${rate}%`);
      setEl("msg-stat-failed", failed.toLocaleString());
      setEl("msg-stat-queued", queued.toLocaleString());
      setEl("msg-stat-dlq", dlqTotal.toLocaleString());
    }
  } catch (err) {
    console.warn("Failed to update message summary metrics:", err);
  }
}

async function loadOrgMessages(page = 1, limit = 50) {
  msgCurrentPage = page;
  msgLimit = limit;
  const tbody = document.getElementById("messages-table-body");
  if (!tbody) return;

  tbody.innerHTML = '<tr><td colspan="8" class="loading-cell">Loading messages...</td></tr>';

  if (msgCachedApps.length === 0) {
    await populateMessageFilterApps();
  }

  const filters = {
    search: msgSearch,
    status: msgStatus,
    channel: msgChannel,
    application_id: msgAppId,
    start_date: msgStartDate,
    end_date: msgEndDate
  };

  try {
    const res = await ApiClient.listMessages(page, limit, filters);
    if (res.success && res.data) {
      updateMessageSummaryMetrics();

      if (res.data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="loading-cell" style="padding: 30px 10px; color: var(--text-muted);">No messages found matching your criteria.</td></tr>';
        updateMessagePaginationBar({ total: 0, page: 1, limit, total_pages: 1 });
        return;
      }

      tbody.innerHTML = res.data
        .map((m) => {
          const appObj = msgCachedApps.find((a) => a.application_id === m.application_id);
          const appLabel = appObj
            ? `<span class="app-scope-badge" title="${escapeHtml(appObj.application_id)}">${escapeHtml(appObj.name)}</span>`
            : m.application_id
            ? `<code style="font-size: 0.72rem;">${escapeHtml(m.application_id.substring(0, 10))}...</code>`
            : '<span style="color: var(--text-muted); font-size: 0.75rem;">Global</span>';

          const status = (m.status || "UNKNOWN").toUpperCase();
          let badgeClass = "badge-created";
          let statusDisplay = status;
          if (status === "DELIVERED") {
            badgeClass = "badge-delivered";
            statusDisplay = "DELIVERED &#10003;";
          } else if (status === "SENT") {
            badgeClass = "badge-sent";
            statusDisplay = "SENT (Accepted)";
          } else if (status === "QUEUED" || status === "RETRYING") {
            badgeClass = "badge-queued";
          } else if (status === "PROCESSING") {
            badgeClass = "badge-processing";
          } else if (status === "FAILED" || status === "DEAD") {
            badgeClass = "badge-failed";
          }

          const canRetry = status === "FAILED" || status === "DEAD";
          const formattedTime = m.created_at ? new Date(m.created_at).toLocaleString() : "-";

          return `
            <tr>
              <td><code>${escapeHtml((m.message_id || "").substring(0, 8))}...</code></td>
              <td>${appLabel}</td>
              <td><span class="badge" style="background: var(--bg-surface); border: 1px solid var(--border-color); color: var(--text-primary); font-family: var(--font-mono); font-size: 0.72rem;">${escapeHtml(m.channel || "")}</span></td>
              <td><span title="${escapeHtml(m.recipient || "")}" style="max-width: 170px; display: inline-block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 0.85rem;">${escapeHtml(m.recipient || "")}</span></td>
              <td><span class="badge ${badgeClass}">${statusDisplay}</span></td>
              <td><span style="font-family: var(--font-mono); font-size: 0.8rem;">${m.retry_count || 0}</span></td>
              <td style="font-size: 0.78rem; color: var(--text-secondary);">${formattedTime}</td>
              <td style="text-align: right; white-space: nowrap;">
                <button class="btn btn-secondary btn-sm" onclick="openMessageDetailsModal('${escapeHtml(m.message_id)}')">Details</button>
                ${canRetry ? `<button class="btn btn-secondary btn-sm" style="color: var(--accent-cyan); margin-left: 4px;" onclick="promptManualRetry('${escapeHtml(m.message_id)}')">Retry</button>` : ""}
              </td>
            </tr>
          `;
        })
        .join("");

      updateMessagePaginationBar(res.pagination || { total: res.data.length, page, limit, total_pages: 1 });
    } else {
      tbody.innerHTML = `<tr><td colspan="8" class="loading-cell error">${escapeHtml(res.message || "Failed to load messages")}</td></tr>`;
    }
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="8" class="loading-cell error">${escapeHtml(err.message)}</td></tr>`;
  }
}

function debounceFilterMessages() {
  clearTimeout(msgDebounceTimer);
  msgDebounceTimer = setTimeout(() => {
    msgSearch = (document.getElementById("msg-search")?.value || "").trim();
    loadOrgMessages(1, msgLimit);
  }, 300);
}

function handleMessageFilterChange() {
  msgAppId = document.getElementById("msg-filter-app")?.value || "";
  msgChannel = document.getElementById("msg-filter-channel")?.value || "";
  msgStatus = document.getElementById("msg-filter-status")?.value || "";
  msgStartDate = document.getElementById("msg-filter-start-date")?.value || "";
  msgEndDate = document.getElementById("msg-filter-end-date")?.value || "";
  loadOrgMessages(1, msgLimit);
}

function handleMessageLimitChange() {
  const select = document.getElementById("msg-limit-select");
  if (select) {
    msgLimit = parseInt(select.value, 10) || 50;
    loadOrgMessages(1, msgLimit);
  }
}

function resetMessageFilters() {
  msgSearch = "";
  msgStatus = "";
  msgChannel = "";
  msgAppId = "";
  msgStartDate = "";
  msgEndDate = "";

  const setVal = (id, v) => {
    const el = document.getElementById(id);
    if (el) el.value = v;
  };

  setVal("msg-search", "");
  setVal("msg-filter-app", "");
  setVal("msg-filter-channel", "");
  setVal("msg-filter-status", "");
  setVal("msg-filter-start-date", "");
  setVal("msg-filter-end-date", "");

  loadOrgMessages(1, msgLimit);
}

function navigateMessagePage(delta) {
  const target = msgCurrentPage + delta;
  if (target >= 1) {
    loadOrgMessages(target, msgLimit);
  }
}

function updateMessagePaginationBar(pagination) {
  const total = pagination.total || 0;
  const page = pagination.page || 1;
  const limit = pagination.limit || 50;
  const totalPages = pagination.total_pages || Math.ceil(total / limit) || 1;

  const start = total === 0 ? 0 : (page - 1) * limit + 1;
  const end = Math.min(page * limit, total);

  const infoEl = document.getElementById("msg-pagination-info");
  if (infoEl) infoEl.textContent = `Showing ${start} to ${end} of ${total.toLocaleString()} messages`;

  const indEl = document.getElementById("msg-page-indicator");
  if (indEl) indEl.textContent = `Page ${page} of ${totalPages}`;

  const prevBtn = document.getElementById("msg-prev-btn");
  if (prevBtn) prevBtn.disabled = page <= 1;

  const nextBtn = document.getElementById("msg-next-btn");
  if (nextBtn) nextBtn.disabled = page >= totalPages;
}

// ----------------------------------------------------
// MESSAGE DETAILS MODAL & DELIVERY TRACKING
// ----------------------------------------------------
async function openMessageDetailsModal(messageId) {
  try {
    const res = await ApiClient.getMessage(messageId);
    if (!res.success || !res.data) {
      showToast(res.message || "Failed to retrieve message details", "danger");
      return;
    }

    const m = res.data;
    msgCurrentViewingMessage = m;

    const setVal = (id, v) => {
      const el = document.getElementById(id);
      if (el) el.textContent = v;
    };

    setVal("modal-msg-id", m.message_id || "-");

    const appObj = msgCachedApps.find((a) => a.application_id === m.application_id);
    setVal("modal-msg-app", appObj ? `${appObj.name} (${appObj.environment || "live"})` : m.application_id || "Global / Unassigned");

    setVal("modal-msg-channel-provider", `${(m.channel || "").toUpperCase()} / ${(m.provider || "unassigned").toUpperCase()}`);
    setVal("modal-msg-recipient", m.recipient || "-");
    setVal("modal-msg-created", m.created_at ? new Date(m.created_at).toLocaleString() : "-");
    setVal("modal-msg-retries", `${m.retry_count || 0} auto / ${m.manual_retry_count || 0} manual`);

    // Status badge
    const status = (m.status || "UNKNOWN").toUpperCase();
    let badgeClass = "badge-created";
    let statusText = status;
    if (status === "DELIVERED") {
      badgeClass = "badge-delivered";
      statusText = "DELIVERED (Confirmed)";
    } else if (status === "SENT") {
      badgeClass = "badge-sent";
      statusText = "SENT (Provider Accepted)";
    } else if (status === "QUEUED" || status === "RETRYING") {
      badgeClass = "badge-queued";
    } else if (status === "PROCESSING") {
      badgeClass = "badge-processing";
    } else if (status === "FAILED" || status === "DEAD") {
      badgeClass = "badge-failed";
    }

    const badgeEl = document.getElementById("modal-msg-status-badge");
    if (badgeEl) {
      badgeEl.className = `badge ${badgeClass}`;
      badgeEl.innerHTML = statusText;
    }

    const markupBadge = document.getElementById("modal-msg-markup-badge");
    if (markupBadge) {
      const hasMarkup = m.contains_markup || (m.validation_notes && m.validation_notes.includes("contains_markup"));
      markupBadge.style.display = hasMarkup ? "inline-block" : "none";
    }

    // Provider info
    const provInfoBox = document.getElementById("modal-msg-provider-info");
    const provIdEl = document.getElementById("modal-msg-provider-id");
    if (m.provider_message_id) {
      if (provIdEl) provIdEl.textContent = m.provider_message_id;
      if (provInfoBox) provInfoBox.style.display = "block";
    } else {
      if (provInfoBox) provInfoBox.style.display = "none";
    }

    // Error details
    const errBox = document.getElementById("modal-msg-errors-box");
    const errText = document.getElementById("modal-msg-error-text");
    const failureMsg = m.last_error || m.delivery_error_message || (m.delivery_error_code ? `Code: ${m.delivery_error_code}` : null);
    if (failureMsg) {
      if (errText) errText.textContent = failureMsg;
      if (errBox) errBox.style.display = "block";
    } else {
      if (errBox) errBox.style.display = "none";
    }

    // Timeline rendering (Audit Trail)
    const timelineEl = document.getElementById("modal-msg-timeline");
    if (timelineEl) {
      const history = Array.isArray(m.status_history) && m.status_history.length > 0
        ? m.status_history
        : [{ to: m.status || "CREATED", timestamp: m.created_at, reason: "Initial ingestion" }];

      timelineEl.innerHTML = history.map((h, idx) => {
        const toStatus = (h.to || "").toUpperCase();
        let dotClass = "";
        if (toStatus === "DELIVERED") dotClass = "delivered";
        else if (toStatus === "FAILED" || toStatus === "DEAD") dotClass = "failed";
        else if (toStatus === "SENT") dotClass = "sent";

        const timeStr = h.timestamp ? new Date(h.timestamp).toLocaleTimeString() : "";
        const fromStr = h.from ? `<span style="color: var(--text-muted); font-size: 0.75rem;">(${escapeHtml(h.from)} &rarr;)</span> ` : "";
        const reasonStr = h.reason ? `<div class="timeline-step-body">${escapeHtml(h.reason)}</div>` : "";
        const sourceStr = h.source ? `<span style="font-size: 0.7rem; color: var(--accent-cyan); margin-left: 6px;">[${escapeHtml(h.source)}]</span>` : "";

        return `
          <div class="timeline-step">
            <div class="timeline-step-dot ${dotClass}"></div>
            <div class="timeline-step-header">
              <span>${fromStr}<strong>${escapeHtml(toStatus)}</strong>${sourceStr}</span>
              <span class="timeline-step-time">${timeStr}</span>
            </div>
            ${reasonStr}
          </div>
        `;
      }).join("");
    }

    // Payload display
    const payloadPre = document.getElementById("modal-msg-payload-json");
    if (payloadPre) {
      payloadPre.textContent = JSON.stringify(m.data || m, null, 2);
    }

    // Retry button visibility
    const retryBtn = document.getElementById("btn-modal-msg-retry");
    if (retryBtn) {
      retryBtn.style.display = (status === "FAILED" || status === "DEAD") ? "inline-flex" : "none";
    }

    openModal("modal-msg-details");
  } catch (err) {
    showToast(err.message, "danger");
  }
}

function copyMessagePayloadJson() {
  if (msgCurrentViewingMessage) {
    const text = JSON.stringify(msgCurrentViewingMessage.data || msgCurrentViewingMessage, null, 2);
    navigator.clipboard.writeText(text).then(() => {
      showToast("Payload JSON copied to clipboard", "success");
    });
  }
}

// ----------------------------------------------------
// MANUAL RETRY CONFIRMATION & EXECUTION
// ----------------------------------------------------
function promptManualRetry(messageId) {
  msgCurrentRetryingId = messageId;
  const idEl = document.getElementById("confirm-retry-msg-id");
  if (idEl) idEl.textContent = messageId;
  openModal("modal-confirm-retry");
}

function triggerManualRetryFromModal() {
  if (msgCurrentViewingMessage) {
    closeModal("modal-msg-details");
    promptManualRetry(msgCurrentViewingMessage.message_id);
  }
}

async function executeConfirmedRetry() {
  if (!msgCurrentRetryingId) return;
  const btn = document.getElementById("btn-confirm-retry-execute");
  if (btn) btn.disabled = true;

  try {
    const res = await ApiClient.retryMessage(msgCurrentRetryingId);
    closeModal("modal-confirm-retry");
    if (res.success) {
      showToast("Message successfully requeued for retry!", "success");
      loadOrgMessages(msgCurrentPage, msgLimit);
    } else {
      showToast(res.message || "Failed to retry message", "danger");
    }
  } catch (err) {
    closeModal("modal-confirm-retry");
    showToast(err.message, "danger");
  } finally {
    if (btn) btn.disabled = false;
    msgCurrentRetryingId = null;
  }
}

// ----------------------------------------------------
// MESSAGE COMPOSER LOGIC
// ----------------------------------------------------
async function initMessageComposer() {
  const appSelect = document.getElementById("composer-app");
  const tplSelect = document.getElementById("composer-template");

  // Load connected applications
  try {
    const res = await ApiClient.listApplications(1, 100);
    if (res.success && res.data) {
      msgCachedApps = res.data;
      const authorizedScopes = getAuthorizedAppIds();
      const availableApps = authorizedScopes 
        ? msgCachedApps.filter(a => authorizedScopes.includes(a.application_id))
        : msgCachedApps;

      if (appSelect) {
        appSelect.innerHTML = '<option value="" disabled selected>-- Select Connected Application --</option>' +
          availableApps.map(a => `<option value="${escapeHtml(a.application_id)}">${escapeHtml(a.name)} (${escapeHtml(a.environment || "live")})</option>`).join("");

        // If only 1 authorized app, auto-select it
        if (availableApps.length === 1) {
          appSelect.value = availableApps[0].application_id;
        }
      }
    }
  } catch (err) {
    console.warn("Failed to load applications for composer:", err);
  }

  // Load templates
  try {
    const res = await ApiClient.listTemplates(1, 100, { status: "ACTIVE" });
    if (res.success && res.data) {
      msgCachedTemplates = res.data;
      if (tplSelect) {
        tplSelect.innerHTML = '<option value="">-- None: Direct Plain Text / HTML Message --</option>' +
          msgCachedTemplates.map(t => `<option value="${escapeHtml(t.template_id)}">${escapeHtml(t.name)} (v${t.version || 1}) - ${escapeHtml(t.channel || "email")}</option>`).join("");
      }
    }
  } catch (err) {
    console.warn("Failed to load templates for composer:", err);
  }

  updateComposerPayloadPreview();
}

function handleComposerChannelChange() {
  const channel = document.getElementById("composer-channel")?.value || "";
  const recipInput = document.getElementById("composer-recipient");
  const recipHint = document.getElementById("composer-recipient-hint");
  const subjectGroup = document.getElementById("composer-subject-group");
  const subjectReq = document.getElementById("composer-subject-req");

  if (channel === "email") {
    if (recipInput) recipInput.placeholder = "e.g. user@company.com";
    if (recipHint) recipHint.textContent = "Valid recipient email address";
    if (subjectGroup) subjectGroup.style.display = "block";
    if (subjectReq) subjectReq.style.display = "inline";
  } else if (channel === "sms") {
    if (recipInput) recipInput.placeholder = "e.g. +14155552671";
    if (recipHint) recipHint.textContent = "E.164 formatted telephone number";
    if (subjectGroup) subjectGroup.style.display = "none";
    if (subjectReq) subjectReq.style.display = "none";
  } else if (channel === "whatsapp") {
    if (recipInput) recipInput.placeholder = "e.g. +14155552671";
    if (recipHint) recipHint.textContent = "E.164 formatted WhatsApp number";
    if (subjectGroup) subjectGroup.style.display = "none";
    if (subjectReq) subjectReq.style.display = "none";
  } else if (channel === "microsoft_teams") {
    if (recipInput) recipInput.placeholder = "e.g. https://outlook.office.com/webhook/... or user@org.com";
    if (recipHint) recipHint.textContent = "Incoming webhook URL, channel email, or user principal";
    if (subjectGroup) subjectGroup.style.display = "block";
    if (subjectReq) subjectReq.style.display = "none";
  } else {
    if (recipInput) recipInput.placeholder = "Select a channel first";
  }

  handleComposerInputChange();
}

async function handleComposerTemplateChange() {
  const tplId = document.getElementById("composer-template")?.value || "";
  const varsBox = document.getElementById("composer-template-vars-box");
  const previewOut = document.getElementById("composer-template-preview-output");

  if (!tplId) {
    if (varsBox) varsBox.style.display = "none";
    if (previewOut) previewOut.style.display = "none";
    updateComposerPayloadPreview();
    return;
  }

  const tpl = msgCachedTemplates.find(t => t.template_id === tplId);
  if (tpl) {
    // If template has a channel, set channel
    const channelSelect = document.getElementById("composer-channel");
    if (channelSelect && tpl.channel && ["email", "sms", "whatsapp", "microsoft_teams"].includes(tpl.channel)) {
      channelSelect.value = tpl.channel;
      handleComposerChannelChange();
    }

    if (tpl.subject && document.getElementById("composer-subject")) {
      document.getElementById("composer-subject").value = tpl.subject;
    }

    // Populate default variables sample if required_variables defined
    const varsTextarea = document.getElementById("composer-template-vars");
    if (varsTextarea && tpl.required_variables && Array.isArray(tpl.required_variables)) {
      const sample = {};
      tpl.required_variables.forEach(v => { sample[v] = `Sample ${v}`; });
      varsTextarea.value = JSON.stringify(sample, null, 2);
    }
  }

  if (varsBox) varsBox.style.display = "block";
  updateComposerPayloadPreview();
}

async function previewComposerTemplate() {
  const tplId = document.getElementById("composer-template")?.value;
  if (!tplId) return;

  const varsRaw = document.getElementById("composer-template-vars")?.value || "{}";
  let sampleData = {};
  try {
    sampleData = JSON.parse(varsRaw);
  } catch {
    showToast("Invalid JSON in template variables", "danger");
    return;
  }

  const outEl = document.getElementById("composer-template-preview-output");
  if (outEl) {
    outEl.style.display = "block";
    outEl.innerHTML = '<span style="color: var(--text-muted);">Rendering preview...</span>';
  }

  try {
    const res = await ApiClient.previewTemplate(tplId, sampleData);
    if (res.success && res.data) {
      if (outEl) {
        outEl.innerHTML = `
          <div style="background: var(--bg-surface); border: 1px solid var(--border-color); border-radius: 6px; padding: 10px;">
            <div style="font-weight: 600; color: var(--text-primary); margin-bottom: 4px;">Subject: ${escapeHtml(res.data.subject || "-")}</div>
            <div style="color: var(--text-secondary); font-size: 0.78rem; max-height: 120px; overflow-y: auto;">${escapeHtml(res.data.plain_text_body || "")}</div>
          </div>
        `;
      }
    } else {
      if (outEl) outEl.innerHTML = `<span style="color: var(--status-error);">${escapeHtml(res.message || "Preview failed")}</span>`;
    }
  } catch (err) {
    if (outEl) outEl.innerHTML = `<span style="color: var(--status-error);">${escapeHtml(err.message)}</span>`;
  }
}

async function handleComposerFileUpload(event) {
  const file = event.target.files?.[0];
  if (!file) return;

  const channel = document.getElementById("composer-channel")?.value || "email";
  const formData = new FormData();
  formData.append("file", file);
  formData.append("channel", channel);
  formData.append("purpose", `Message attachment: ${file.name}`);

  showToast(`Uploading ${file.name}...`, "info");

  try {
    const res = await ApiClient.uploadMedia(formData);
    if (res.success && res.data) {
      msgComposerAttachments.push({
        media_id: res.data.media_id,
        filename: res.data.filename || file.name,
        mime_type: res.data.mime_type || file.type,
        size_bytes: res.data.size_bytes || file.size
      });
      renderComposerAttachments();
      updateComposerPayloadPreview();
      showToast(`Attachment ${file.name} uploaded successfully!`, "success");
    } else {
      showToast(res.message || "Failed to upload file", "danger");
    }
  } catch (err) {
    showToast(err.message, "danger");
  } finally {
    event.target.value = "";
  }
}

async function openMediaSelectorModal() {
  const listEl = document.getElementById("media-selector-list");
  const loadingEl = document.getElementById("media-selector-loading");
  if (loadingEl) loadingEl.style.display = "block";
  if (listEl) listEl.innerHTML = "";

  openModal("modal-media-selector");

  try {
    const res = await ApiClient.listMedia(1, 50);
    if (loadingEl) loadingEl.style.display = "none";
    if (res.success && res.data) {
      if (res.data.length === 0) {
        if (listEl) listEl.innerHTML = '<div style="color: var(--text-muted); font-size: 0.85rem; text-align: center; padding: 20px;">No media files uploaded yet.</div>';
        return;
      }
      if (listEl) {
        listEl.innerHTML = res.data.map(m => `
          <div style="display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; background: var(--bg-surface); border: 1px solid var(--border-color); border-radius: 8px;">
            <div>
              <div style="font-size: 0.825rem; font-weight: 600; color: var(--text-primary);">${escapeHtml(m.filename)}</div>
              <div style="font-size: 0.72rem; color: var(--text-muted);">${escapeHtml(m.mime_type || "")} &bull; ${(m.size_bytes / 1024).toFixed(1)} KB</div>
            </div>
            <button type="button" class="btn btn-secondary btn-sm" onclick="attachMediaItem('${escapeHtml(m.media_id)}', '${escapeHtml(m.filename)}', '${escapeHtml(m.mime_type || "")}', ${m.size_bytes || 0})">Attach</button>
          </div>
        `).join("");
      }
    }
  } catch (err) {
    if (loadingEl) loadingEl.style.display = "none";
    if (listEl) listEl.innerHTML = `<div style="color: var(--status-error);">${escapeHtml(err.message)}</div>`;
  }
}

function attachMediaItem(mediaId, filename, mimeType, sizeBytes) {
  if (!msgComposerAttachments.some(a => a.media_id === mediaId)) {
    msgComposerAttachments.push({ media_id: mediaId, filename, mime_type: mimeType, size_bytes: sizeBytes });
    renderComposerAttachments();
    updateComposerPayloadPreview();
    showToast(`Attached ${filename}`, "success");
  }
  closeModal("modal-media-selector");
}

function removeComposerAttachment(idx) {
  msgComposerAttachments.splice(idx, 1);
  renderComposerAttachments();
  updateComposerPayloadPreview();
}

function renderComposerAttachments() {
  const container = document.getElementById("composer-attachments-list");
  if (!container) return;
  if (msgComposerAttachments.length === 0) {
    container.innerHTML = '<span style="color: var(--text-muted); font-size: 0.75rem;">No files attached</span>';
    return;
  }
  container.innerHTML = msgComposerAttachments.map((a, i) => `
    <span class="attachment-pill">
      <span>${escapeHtml(a.filename)}</span>
      <button type="button" onclick="removeComposerAttachment(${i})" title="Remove attachment">&times;</button>
    </span>
  `).join("");
}

function handleComposerInputChange() {
  updateComposerPayloadPreview();
}

function buildComposerPayload() {
  const appId = document.getElementById("composer-app")?.value || "";
  const channel = document.getElementById("composer-channel")?.value || "";
  const recipient = (document.getElementById("composer-recipient")?.value || "").trim();
  const templateId = document.getElementById("composer-template")?.value || "";
  const subject = (document.getElementById("composer-subject")?.value || "").trim();
  const body = (document.getElementById("composer-body")?.value || "").trim();

  let templateVars = {};
  if (templateId) {
    try {
      templateVars = JSON.parse(document.getElementById("composer-template-vars")?.value || "{}");
    } catch {
      templateVars = {};
    }
  }

  const dataBlock = {};
  if (subject) dataBlock.subject = subject;
  if (body) {
    dataBlock.body = body;
    dataBlock.message = body;
  }
  if (templateId) {
    dataBlock.template_id = templateId;
    dataBlock.template_variables = templateVars;
  }
  if (msgComposerAttachments.length > 0) {
    dataBlock.media_ids = msgComposerAttachments.map(a => a.media_id);
    dataBlock.attachments = msgComposerAttachments.map(a => ({
      media_id: a.media_id,
      filename: a.filename,
      mime_type: a.mime_type
    }));
  }

  const payload = {
    channel: channel,
    recipient: recipient,
    application_id: appId,
    data: dataBlock
  };

  return payload;
}

function updateComposerPayloadPreview() {
  const payload = buildComposerPayload();
  const previewBox = document.getElementById("composer-payload-preview");
  if (previewBox) {
    previewBox.textContent = JSON.stringify(payload, null, 2);
  }

  // Update Validation Checklist
  const updateVal = (id, isValid) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.classList.toggle("valid", isValid);
    el.classList.toggle("invalid", !isValid && el.dataset.touched === "true");
    el.innerHTML = isValid
      ? `&#10003; ${el.textContent.replace(/^[\u25CB\u2713\u2717]\s*/, "")}`
      : `&#9675; ${el.textContent.replace(/^[\u25CB\u2713\u2717]\s*/, "")}`;
  };

  updateVal("val-app", Boolean(payload.application_id));
  updateVal("val-channel", Boolean(payload.channel));
  updateVal("val-recipient", Boolean(payload.recipient && payload.recipient.length >= 3));

  const hasContent = Boolean(
    payload.data?.body || 
    payload.data?.message || 
    payload.data?.template_id || 
    (payload.data?.media_ids && payload.data.media_ids.length > 0)
  );
  updateVal("val-content", hasContent);
}

async function handleComposerSubmit(event) {
  event.preventDefault();
  const payload = buildComposerPayload();

  if (!payload.application_id) {
    showToast("Please select a connected application", "danger");
    return;
  }
  if (!payload.channel) {
    showToast("Please select an explicit communication channel", "danger");
    return;
  }
  if (!payload.recipient) {
    showToast("Recipient is required", "danger");
    return;
  }
  if (!payload.data?.body && !payload.data?.template_id && (!payload.data?.media_ids || payload.data.media_ids.length === 0)) {
    showToast("Please provide message content or select a template", "danger");
    return;
  }

  const sendBtn = document.getElementById("btn-composer-send");
  if (sendBtn) sendBtn.disabled = true;

  try {
    // 1. Create message
    const res = await ApiClient.createMessage(payload);
    if (res.success && res.data?.message?.message_id) {
      const msgId = res.data.message.message_id;
      // 2. Queue for immediate worker processing
      await ApiClient.queueMessage(msgId);
      showToast("Message created and queued for processing successfully!", "success");
      resetComposerForm();
      switchMessageSubtab("history");
    } else {
      showToast(res.message || "Failed to create message", "danger");
    }
  } catch (err) {
    showToast(err.message, "danger");
  } finally {
    if (sendBtn) sendBtn.disabled = false;
  }
}

async function handleComposerSaveDraft() {
  const payload = buildComposerPayload();

  if (!payload.application_id) {
    showToast("Please select a connected application", "danger");
    return;
  }
  if (!payload.channel) {
    showToast("Please select an explicit communication channel", "danger");
    return;
  }
  if (!payload.recipient) {
    showToast("Recipient is required", "danger");
    return;
  }

  try {
    const res = await ApiClient.createMessage(payload);
    if (res.success && res.data?.message?.message_id) {
      showToast("Message draft saved in CREATED status!", "success");
      resetComposerForm();
      switchMessageSubtab("history");
    } else {
      showToast(res.message || "Failed to save message draft", "danger");
    }
  } catch (err) {
    showToast(err.message, "danger");
  }
}

function resetComposerForm() {
  const form = document.getElementById("composer-form");
  if (form) form.reset();
  msgComposerAttachments = [];
  renderComposerAttachments();
  document.getElementById("composer-template-vars-box")?.style && (document.getElementById("composer-template-vars-box").style.display = "none");
  document.getElementById("composer-template-preview-output")?.style && (document.getElementById("composer-template-preview-output").style.display = "none");
  handleComposerChannelChange();
  updateComposerPayloadPreview();
}

// ----------------------------------------------------
// MESSAGE ANALYTICS TAB CONTROLLER
// ----------------------------------------------------
async function loadMessageAnalytics() {
  try {
    const res = await ApiClient.getOrganizationAnalytics();
    if (res.success || res.overview) {
      const d = res.data || res;
      const total = d.overview?.total_messages ?? (d.total_messages || 0);
      const statusCounts = d.status_breakdown || {};
      const rate = d.overview?.delivery_rate_percent ?? (d.delivery_success_rate || 0);
      const failed = d.overview?.failed ?? ((statusCounts.FAILED || 0) + (statusCounts.DEAD || 0));
      const queued = d.overview?.queued ?? ((statusCounts.QUEUED || 0) + (statusCounts.PROCESSING || 0));

      const setEl = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.textContent = val;
      };

      setEl("analytics-total", total.toLocaleString());
      setEl("analytics-rate", `${rate}%`);
      setEl("analytics-failed", failed.toLocaleString());
      setEl("analytics-queued", queued.toLocaleString());

      // Channel breakdown
      const chContainer = document.getElementById("analytics-channel-breakdown");
      if (chContainer) {
        const channels = d.channels || [];
        if (channels.length === 0) {
          chContainer.innerHTML = '<div style="color: var(--text-muted); font-size: 0.85rem;">No channel dispatch data recorded yet.</div>';
        } else {
          chContainer.innerHTML = channels.map(c => {
            const chName = c.channel || c._id || "unknown";
            const chCount = c.count || 0;
            const pct = total > 0 ? ((chCount / total) * 100).toFixed(1) : 0;
            return `
              <div>
                <div style="display: flex; justify-content: space-between; font-size: 0.825rem; margin-bottom: 4px;">
                  <span style="font-weight: 600; text-transform: uppercase;">${escapeHtml(chName)}</span>
                  <span style="color: var(--text-muted);">${chCount} messages (${pct}%)</span>
                </div>
                <div style="height: 6px; background: var(--border-color); border-radius: 3px; overflow: hidden;">
                  <div style="height: 100%; width: ${pct}%; background: var(--accent-cyan); border-radius: 3px;"></div>
                </div>
              </div>
            `;
          }).join("");
        }
      }

      // 14-day Daily Dispatch Volume
      const trendContainer = document.getElementById("analytics-trend-list");
      if (trendContainer) {
        const trends = d.daily_trends || d.trends_14d || [];
        if (trends.length === 0) {
          trendContainer.innerHTML = '<div style="color: var(--text-muted); font-size: 0.85rem;">No message volume in the last 14 days.</div>';
        } else {
          trendContainer.innerHTML = trends.map(t => {
            const dateStr = t.date || t._id || "";
            const count = t.total ?? t.count ?? 0;
            return `
              <div style="display: flex; justify-content: space-between; align-items: center; padding: 6px 10px; background: var(--bg-surface); border: 1px solid var(--border-color); border-radius: 6px; font-size: 0.8rem;">
                <span style="font-family: var(--font-mono); color: var(--text-secondary);">${escapeHtml(dateStr)}</span>
                <span style="font-weight: 600; color: var(--accent-cyan);">${count} dispatched</span>
              </div>
            `;
          }).join("");
        }
      }
    }
  } catch (err) {
    showToast(err.message, "danger");
  }
}

function setupSendMessageForm() {
  // Backward compatibility wrapper
  document.getElementById("send-message-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
  });
}

async function runJsonAnalyzer() {
  const raw = document.getElementById("analyzer-input").value;
  const outPre = document.getElementById("analyzer-output-pre");
  try {
    const payload = JSON.parse(raw);
    outPre.textContent = "Analyzing structure...";
    const res = await ApiClient.analyzeJson(payload);
    outPre.textContent = JSON.stringify(res, null, 2);
  } catch (err) {
    outPre.textContent = `Error: ${err.message}`;
  }
}

async function loadOrgDlq() {
  const tbody = document.getElementById("dlq-table-body");
  tbody.innerHTML = '<tr><td colspan="7" class="loading-cell">Loading DLQ records...</td></tr>';

  try {
    const res = await ApiClient.listDlq();
    if (res.success && res.data) {
      if (res.data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="loading-cell">DLQ is empty. No failed messages!</td></tr>';
        return;
      }
      tbody.innerHTML = res.data
        .map(
          (d) => `
        <tr>
          <td><code>${escapeHtml(d.message_id.substring(0, 8))}...</code></td>
          <td>${escapeHtml(d.recipient)}</td>
          <td><span class="badge badge-${(d.dead_letter_status || "").toLowerCase()}">${d.dead_letter_status}</span></td>
          <td>${d.manual_retry_dispatch_state || "NONE"}</td>
          <td>${d.failure_cycles ? d.failure_cycles.length : 0}</td>
          <td title="${escapeHtml(d.last_error || "")}">${escapeHtml((d.last_error || "").substring(0, 32))}...</td>
          <td>
            ${
              d.dead_letter_status === "PENDING_REVIEW"
                ? `<button class="btn btn-primary btn-sm" onclick="retryDlqMessage('${d.message_id}')">Retry</button>`
                : `<span class="badge badge-resolved">${d.dead_letter_status}</span>`
            }
          </td>
        </tr>
      `
        )
        .join("");
    }
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="7" class="loading-cell error">${err.message}</td></tr>`;
  }
}

async function retryDlqMessage(msgId) {
  try {
    const res = await ApiClient.retryDlq(msgId);
    if (res.success) {
      showToast("Manual retry requested and queued!", "success");
      loadOrgDlq();
    } else {
      showToast(res.message || "Manual retry failed", "danger");
    }
  } catch (err) {
    showToast(err.message, "danger");
  }
}

// ====================================================
// EMPLOYEE & ROLE MANAGEMENT (PHASE 5 TASK 2)
// ====================================================

let _usersFilterDebounceTimer = null;
let _cachedOrgRoles = [];
let _cachedOrgApps = [];
let _currentRoleAssignments = [];
let _activeViewingRoleId = null;

function debounceFilterUsers() {
  clearTimeout(_usersFilterDebounceTimer);
  _usersFilterDebounceTimer = setTimeout(() => {
    loadOrgUsers();
  }, 300);
}

function filterUsersList() {
  loadOrgUsers();
}

function resetUsersFilter() {
  const searchInput = document.getElementById("users-search-input");
  const statusSelect = document.getElementById("users-filter-status");
  const roleSelect = document.getElementById("users-filter-role");
  const appSelect = document.getElementById("users-filter-app");

  if (searchInput) searchInput.value = "";
  if (statusSelect) statusSelect.value = "";
  if (roleSelect) roleSelect.value = "";
  if (appSelect) appSelect.value = "";

  loadOrgUsers();
}

function switchUsersSubView(view) {
  const empView = document.getElementById("view-org-employees");
  const rolesView = document.getElementById("view-org-roles");
  const auditView = document.getElementById("view-org-audit");

  const empBtn = document.getElementById("subtab-employees-btn");
  const rolesBtn = document.getElementById("subtab-roles-btn");
  const auditBtn = document.getElementById("subtab-audit-btn");

  if (empView) empView.style.display = view === "employees" ? "block" : "none";
  if (rolesView) rolesView.style.display = view === "roles" ? "block" : "none";
  if (auditView) auditView.style.display = view === "audit" ? "block" : "none";

  if (empBtn) empBtn.classList.toggle("active", view === "employees");
  if (rolesBtn) rolesBtn.classList.toggle("active", view === "roles");
  if (auditBtn) auditBtn.classList.toggle("active", view === "audit");

  if (view === "employees") loadOrgUsers();
  else if (view === "roles") loadOrgRoles();
  else if (view === "audit") loadOrgAuditLogs();
}

async function populateUsersFilterDropdowns() {
  try {
    const resRoles = await ApiClient.listRoles();
    if (resRoles.success && resRoles.data) {
      _cachedOrgRoles = resRoles.data;
    }
    const resApps = await ApiClient.listApplications();
    if (resApps.success && resApps.data) {
      _cachedOrgApps = resApps.data;
    }

    const roleFilter = document.getElementById("users-filter-role");
    if (roleFilter) {
      const currentVal = roleFilter.value;
      roleFilter.innerHTML = '<option value="">All Roles</option>' + 
        _cachedOrgRoles.map(r => `<option value="${r.role_id}">${escapeHtml(r.name)}</option>`).join("");
      roleFilter.value = currentVal;
    }

    const appFilter = document.getElementById("users-filter-app");
    if (appFilter) {
      const currentVal = appFilter.value;
      appFilter.innerHTML = '<option value="">All App Scopes</option>' + 
        _cachedOrgApps.map(a => `<option value="${a.application_id}">${escapeHtml(a.name)}</option>`).join("");
      appFilter.value = currentVal;
    }
  } catch (err) {
    console.error("Error populating user filter dropdowns:", err);
  }
}

async function loadOrgUsers() {
  const tbody = document.getElementById("users-table-body");
  const emptyState = document.getElementById("users-empty-state");
  if (!tbody) return;

  tbody.innerHTML = '<tr><td colspan="6" class="loading-cell">Loading employees...</td></tr>';
  if (emptyState) emptyState.style.display = "none";

  await populateUsersFilterDropdowns();

  const search = document.getElementById("users-search-input")?.value?.trim() || "";
  const status = document.getElementById("users-filter-status")?.value || "";
  const role_id = document.getElementById("users-filter-role")?.value || "";
  const application_id = document.getElementById("users-filter-app")?.value || "";

  try {
    const res = await ApiClient.listUsers(1, 100, { search, status, role_id, application_id });
    if (res.success && res.data) {
      if (res.data.length === 0) {
        tbody.innerHTML = "";
        if (emptyState) emptyState.style.display = "block";
        return;
      }

      const currentAccount = ApiClient.getStoredAccount() || {};
      const currentUserId = currentAccount.user_id || currentAccount.id;

      // Count active admins in organization to enforce last active admin UI hint
      const activeAdmins = res.data.filter(u =>
        u.is_active && (
          (u.roles && u.roles.some(r => r.name === "ORG_ADMIN")) ||
          (u.role_ids && _cachedOrgRoles.some(r => r.name === "ORG_ADMIN" && u.role_ids.includes(r.role_id)))
        )
      );
      const isOnlyOneActiveAdmin = activeAdmins.length <= 1;

      tbody.innerHTML = res.data.map(u => {
        const isSelf = u.user_id === currentUserId;
        const isUserAdmin = u.is_active && (
          (u.roles && u.roles.some(r => r.name === "ORG_ADMIN")) ||
          (u.role_ids && _cachedOrgRoles.some(r => r.name === "ORG_ADMIN" && u.role_ids.includes(r.role_id)))
        );
        const isLastAdmin = isUserAdmin && isOnlyOneActiveAdmin;

        // Render role tags with application scopes
        let roleTagsHtml = '<span class="subtitle" style="font-size: 0.75rem;">No roles</span>';
        if (u.roles && u.roles.length > 0) {
          roleTagsHtml = u.roles.map(r => {
            const scopeLabel = r.application_name || (r.application_id ? "App-scoped" : "Org-wide");
            const isOrgWide = !r.application_id || r.application_id === "all";
            const badgeClass = isOrgWide ? "org-wide" : "app-scoped";
            return `
              <span class="role-assignment-pill" style="margin-right: 6px; margin-bottom: 4px;">
                <strong>${escapeHtml(r.name)}</strong>
                <span class="app-scope-badge ${badgeClass}">${escapeHtml(scopeLabel)}</span>
              </span>
            `;
          }).join("");
        } else if (u.role_ids && u.role_ids.length > 0) {
          roleTagsHtml = u.role_ids.map(rid => {
            const foundRole = _cachedOrgRoles.find(r => r.role_id === rid);
            const roleName = foundRole ? foundRole.name : rid;
            return `
              <span class="role-assignment-pill" style="margin-right: 6px; margin-bottom: 4px;">
                <strong>${escapeHtml(roleName)}</strong>
                <span class="app-scope-badge org-wide">Org-wide</span>
              </span>
            `;
          }).join("");
        }

        const isDeleted = u.status === "DELETED" || u.is_deleted === true;
        const isPendingActivation = u.status === "PENDING_ACTIVATION";

        // Action buttons
        let statusToggleBtn = "";
        let deleteBtn = "";

        const roleDisplayName = u.is_org_admin ? "ORG_ADMIN" : (u.roles && u.roles.length > 0 ? (u.roles[0].name || u.roles[0].role_name || "Employee") : "Employee");
        const empCodeVal = u.employee_code || "";
        const deptVal = u.department || "";
        const phoneVal = u.phone || "";

        if (isDeleted) {
          statusToggleBtn = "";
          deleteBtn = `<span class="badge badge-inactive" style="font-size: 0.7rem;">DELETED</span>`;
        } else if (isPendingActivation) {
          statusToggleBtn = `<button class="btn btn-outline btn-sm" data-perm="organization:users:manage" onclick="handleResendActivationOtp('${u.user_id}', '${escapeHtml(u.name)}')">Resend activation code</button>`;
          deleteBtn = `<button class="btn btn-danger btn-sm" data-perm="organization:users:manage" onclick="openDeleteEmployeeModal('${u.user_id}', '${escapeHtml(u.name)}', '${escapeHtml(u.email)}', '${escapeHtml(empCodeVal)}', '${escapeHtml(deptVal)}', '${escapeHtml(phoneVal)}', '${escapeHtml(roleDisplayName)}')">Delete</button>`;
        } else {
          if (isSelf) {
            statusToggleBtn = `<button class="btn btn-outline btn-sm" disabled style="opacity: 0.5; cursor: not-allowed;" title="You cannot deactivate your own account">Deactivate (You)</button>`;
            deleteBtn = `<button class="btn btn-outline btn-sm" disabled style="opacity: 0.4; cursor: not-allowed;" title="You cannot delete your own account">Delete</button>`;
          } else if (u.is_active) {
            if (isLastAdmin) {
              statusToggleBtn = `<button class="btn btn-outline btn-sm" disabled style="opacity: 0.5; cursor: not-allowed;" title="Cannot deactivate the last active organization administrator">Deactivate (Last Admin)</button>`;
              deleteBtn = `<button class="btn btn-outline btn-sm" disabled style="opacity: 0.4; cursor: not-allowed;" title="Cannot delete the last active organization administrator">Delete</button>`;
            } else {
              statusToggleBtn = `<button class="btn btn-outline btn-sm" data-perm="organization:users:manage" onclick="handleToggleUserStatus('${u.user_id}', '${escapeHtml(u.name)}', true)">Deactivate</button>`;
              deleteBtn = `<button class="btn btn-danger btn-sm" data-perm="organization:users:manage" onclick="openDeleteEmployeeModal('${u.user_id}', '${escapeHtml(u.name)}', '${escapeHtml(u.email)}', '${escapeHtml(empCodeVal)}', '${escapeHtml(deptVal)}', '${escapeHtml(phoneVal)}', '${escapeHtml(roleDisplayName)}')">Delete</button>`;
            }
          } else {
            statusToggleBtn = `<button class="btn btn-outline btn-sm" style="border-color: var(--status-success); color: var(--status-success);" data-perm="organization:users:manage" onclick="handleToggleUserStatus('${u.user_id}', '${escapeHtml(u.name)}', false)">Activate</button>`;
            deleteBtn = `<button class="btn btn-danger btn-sm" data-perm="organization:users:manage" onclick="openDeleteEmployeeModal('${u.user_id}', '${escapeHtml(u.name)}', '${escapeHtml(u.email)}', '${escapeHtml(empCodeVal)}', '${escapeHtml(deptVal)}', '${escapeHtml(phoneVal)}', '${escapeHtml(roleDisplayName)}')">Delete</button>`;
          }
        }

        const initials = (u.name || "U").split(" ").map(p => p[0]).join("").toUpperCase().slice(0, 2);
        const empCodeHtml = u.employee_code
          ? `<span class="badge-emp-code">${escapeHtml(u.employee_code)}</span>`
          : `<span style="color: var(--text-muted); font-size: 0.775rem;">-</span>`;

        const statusBadgeHtml = isDeleted
          ? `<span class="badge badge-inactive">DELETED</span>`
          : isPendingActivation
            ? `<span class="badge badge-pending-activation">Pending activation</span>`
            : `<span class="badge badge-${u.is_active ? "active" : "inactive"}">${u.is_active ? "ACTIVE" : "INACTIVE"}</span>`;

        return `
          <tr>
            <td>
              <div class="user-cell-wrapper">
                <div class="user-avatar-circle">${escapeHtml(initials)}</div>
                <div>
                  <strong style="color: var(--text-primary); display: block;">${escapeHtml(u.name)}</strong>
                </div>
              </div>
            </td>
            <td>${empCodeHtml}</td>
            <td><span style="color: var(--text-secondary);">${escapeHtml(u.email)}</span></td>
            <td>${statusBadgeHtml}</td>
            <td>
              <div style="display: flex; flex-wrap: wrap; max-width: 380px;">${roleTagsHtml}</div>
            </td>
            <td>
              <div style="display: flex; gap: 6px; align-items: center;">
                <button class="btn btn-secondary btn-sm" onclick="handleViewUserDetails('${u.user_id}')">Details</button>
                ${!isDeleted ? `<button class="btn btn-outline btn-sm" data-perm="organization:roles:manage" onclick="handleOpenAssignRoles('${u.user_id}')">Assign Roles</button>` : ""}
                ${statusToggleBtn}
                ${deleteBtn}
              </div>
            </td>
          </tr>
        `;
      }).join("");
    }
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" class="loading-cell error">${escapeHtml(err.message)}</td></tr>`;
  }
}

async function loadOrgRoles() {
  const tbody = document.getElementById("roles-table-body");
  const emptyState = document.getElementById("roles-empty-state");
  if (!tbody) return;

  tbody.innerHTML = '<tr><td colspan="6" class="loading-cell">Loading roles...</td></tr>';
  if (emptyState) emptyState.style.display = "none";

  try {
    const res = await ApiClient.listRoles();
    if (res.success && res.data) {
      _cachedOrgRoles = res.data;
      if (res.data.length === 0) {
        tbody.innerHTML = "";
        if (emptyState) emptyState.style.display = "block";
        return;
      }

      tbody.innerHTML = res.data.map(r => {
        const isSystem = r.is_system_role || r.name === "ORG_ADMIN";
        const membersCount = r.assigned_employees_count || 0;
        const permsCount = (r.permissions || []).length;
        const scopeLabel = r.application_name || (r.application_id ? "App-scoped" : "All Applications (Org-wide)");
        const isOrgWide = !r.application_id || r.application_id === "all";

        let deleteBtn = "";
        if (isSystem) {
          deleteBtn = `<button class="btn btn-outline btn-sm" disabled style="opacity: 0.4; cursor: not-allowed;" title="System roles cannot be deleted">System</button>`;
        } else if (membersCount > 0) {
          deleteBtn = `<button class="btn btn-outline btn-sm" disabled style="opacity: 0.4; cursor: not-allowed;" title="Cannot delete role assigned to ${membersCount} active member(s)">Delete</button>`;
        } else {
          deleteBtn = `<button class="btn btn-danger btn-sm" data-perm="organization:roles:manage" onclick="handleDeleteRole('${r.role_id}', '${escapeHtml(r.name)}')">Delete</button>`;
        }

        return `
          <tr>
            <td>
              <strong style="color: var(--text-primary);">${escapeHtml(r.name)}</strong>
              ${r.description ? `<p style="font-size: 0.75rem; color: var(--text-muted); margin: 2px 0 0 0;">${escapeHtml(r.description)}</p>` : ""}
            </td>
            <td>
              <span class="badge ${isSystem ? "badge-env-live" : "badge-env-test"}">${isSystem ? "SYSTEM" : "CUSTOM"}</span>
            </td>
            <td>
              <span class="app-scope-badge ${isOrgWide ? "org-wide" : "app-scoped"}">${escapeHtml(scopeLabel)}</span>
            </td>
            <td>
              <span style="font-size: 0.825rem; color: var(--text-primary); font-weight: 600;">${permsCount}</span>
              <span style="font-size: 0.75rem; color: var(--text-secondary);"> permissions</span>
            </td>
            <td>
              <span style="font-size: 0.825rem; color: ${membersCount > 0 ? "var(--accent-cyan)" : "var(--text-muted)"}; font-weight: 600;">${membersCount}</span>
              <span style="font-size: 0.75rem; color: var(--text-secondary);"> member(s)</span>
            </td>
            <td>
              <div style="display: flex; gap: 6px; align-items: center;">
                <button class="btn btn-secondary btn-sm" onclick="handleViewRoleDetails('${r.role_id}')">Details</button>
                ${deleteBtn}
              </div>
            </td>
          </tr>
        `;
      }).join("");
    }
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" class="loading-cell error">${escapeHtml(err.message)}</td></tr>`;
  }
}

// ----------------------------------------------------
// EMPLOYEE DELETION (Phase 5 Task 5.4)
// ----------------------------------------------------

function openDeleteEmployeeModal(userId, name, email, employeeCode, department, phone, roleName) {
  const idInput = document.getElementById("delete-employee-id");
  const nameEl = document.getElementById("delete-employee-name");
  const emailEl = document.getElementById("delete-employee-email");
  const codeEl = document.getElementById("delete-employee-code");
  const deptEl = document.getElementById("delete-employee-department");
  const phoneEl = document.getElementById("delete-employee-phone");
  const roleEl = document.getElementById("delete-employee-role");

  if (idInput) idInput.value = userId;
  if (nameEl) nameEl.textContent = name || "Employee";
  if (emailEl) emailEl.textContent = email || "Not provided";
  if (codeEl) codeEl.textContent = employeeCode || "Not provided";
  if (deptEl) deptEl.textContent = department || "Not provided";
  if (phoneEl) phoneEl.textContent = phone || "Not provided";
  if (roleEl) roleEl.textContent = roleName || "Employee";

  openModal("modal-delete-employee");
}

async function executeDeleteEmployee() {
  const userId = document.getElementById("delete-employee-id")?.value;
  if (!userId) return;

  const btn = document.getElementById("btn-confirm-delete-employee");
  if (btn) btn.disabled = true;

  try {
    const res = await ApiClient.deleteUser(userId);
    if (res.success) {
      showToast("Employee deleted successfully", "success");
      closeModal("modal-delete-employee");
      await loadOrgUsers();
      if (typeof loadOrgAuditLogs === "function") {
        await loadOrgAuditLogs(1);
      }
    } else {
      showToast(res.message || "Failed to delete employee", "danger");
    }
  } catch (err) {
    showToast(err.message, "danger");
  } finally {
    if (btn) btn.disabled = false;
  }
}

// ----------------------------------------------------
// SECURITY AUDIT LOGS (Phase 5 Task 5.4)
// ----------------------------------------------------

let orgAuditCurrentPage = 1;
let orgAuditLimit = 20;
let orgAuditSearchDebounceTimer = null;
let _cachedAuditLogs = [];

function formatRelativeTime(isoString) {
  if (!isoString) return "";
  try {
    const d = new Date(isoString);
    const now = new Date();
    const diffSec = Math.floor((now - d) / 1000);
    if (diffSec < 45) return "just now";
    const diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHour = Math.floor(diffMin / 60);
    if (diffHour < 24) return `${diffHour}h ago`;
    const diffDay = Math.floor(diffHour / 24);
    if (diffDay === 1) return "yesterday";
    if (diffDay < 30) return `${diffDay}d ago`;
    return d.toLocaleDateString();
  } catch (e) {
    return "";
  }
}

function handleAuditSearchDebounced() {
  if (orgAuditSearchDebounceTimer) clearTimeout(orgAuditSearchDebounceTimer);
  orgAuditSearchDebounceTimer = setTimeout(() => {
    loadOrgAuditLogs(1);
  }, 300);
}

function prevAuditPage() {
  if (orgAuditCurrentPage > 1) {
    loadOrgAuditLogs(orgAuditCurrentPage - 1);
  }
}

function nextAuditPage() {
  loadOrgAuditLogs(orgAuditCurrentPage + 1);
}

async function loadOrgAuditLogs(page = orgAuditCurrentPage) {
  orgAuditCurrentPage = page;
  const tbody = document.getElementById("audit-logs-table-body");
  const emptyState = document.getElementById("audit-empty-state");
  if (!tbody) return;

  tbody.innerHTML = '<tr><td colspan="7" class="loading-cell">Loading security audit trail...</td></tr>';
  if (emptyState) emptyState.style.display = "none";

  const search = document.getElementById("audit-search-input")?.value?.trim() || "";
  const action = document.getElementById("audit-filter-action")?.value || "";
  const result = document.getElementById("audit-filter-result")?.value || "";
  const dateFilter = document.getElementById("audit-filter-date")?.value || "";

  let startDate = "";
  if (dateFilter === "today") {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    startDate = today.toISOString();
  } else if (dateFilter === "7d") {
    const d = new Date();
    d.setDate(d.getDate() - 7);
    startDate = d.toISOString();
  } else if (dateFilter === "30d") {
    const d = new Date();
    d.setDate(d.getDate() - 30);
    startDate = d.toISOString();
  }

  try {
    const filters = {};
    if (search) filters.search = search;
    if (action) filters.action = action;
    if (result) filters.result = result;
    if (startDate) filters.start_date = startDate;

    const res = await ApiClient.listSecurityAuditLogs(page, orgAuditLimit, filters);
    if (res.success && res.data) {
      _cachedAuditLogs = res.data;
      if (res.data.length === 0) {
        tbody.innerHTML = "";
        if (emptyState) emptyState.style.display = "block";
      } else {
        tbody.innerHTML = res.data.map(log => {
          const localTime = log.timestamp ? new Date(log.timestamp).toLocaleString() : "-";
          const relHint = formatRelativeTime(log.timestamp);
          const isSuccess = log.result === "SUCCESS" || !log.result;
          const resultBadge = `<span class="badge badge-${isSuccess ? 'active' : 'inactive'}" style="font-size: 0.68rem;">${escapeHtml(log.result || "SUCCESS")}</span>`;
          const actionBadge = `<span class="badge badge-info" style="font-size: 0.72rem; letter-spacing: 0.3px;">${escapeHtml(log.action_label || log.event_type || "-")}</span>`;

          return `
            <tr>
              <td style="font-size: 0.775rem; color: var(--text-primary); white-space: nowrap;">
                <div>${escapeHtml(localTime)}</div>
                <div style="font-size: 0.7rem; color: var(--text-muted);">${escapeHtml(relHint)}</div>
              </td>
              <td>
                <div style="font-weight: 600; color: var(--text-primary); font-size: 0.85rem;">${escapeHtml(log.actor_name || "System")}</div>
                <div style="font-size: 0.725rem; color: var(--text-muted);">${escapeHtml(log.actor_email || "-")}</div>
              </td>
              <td>${actionBadge}</td>
              <td>
                <div style="font-weight: 500; color: var(--text-primary); font-size: 0.85rem;">${escapeHtml(log.target_name || "-")}</div>
                <div style="font-size: 0.7rem; color: var(--accent-cyan); text-transform: uppercase;">${escapeHtml(log.target_type || "")}</div>
              </td>
              <td style="font-size: 0.825rem; color: var(--text-secondary); max-width: 320px; line-height: 1.4;">
                ${escapeHtml(log.summary || "-")}
              </td>
              <td>${resultBadge}</td>
              <td style="text-align: right; white-space: nowrap;">
                <button class="btn btn-secondary btn-sm" onclick="openAuditDetailsModal('${log.audit_id}')">Details</button>
              </td>
            </tr>
          `;
        }).join("");
      }

      // Update Audit Pagination Bar
      const pagination = res.pagination || { total: res.total_count || 0, page: 1, limit: orgAuditLimit, total_pages: 1 };
      const total = pagination.total || 0;
      const totalPages = pagination.total_pages || 1;
      const start = total === 0 ? 0 : (page - 1) * orgAuditLimit + 1;
      const end = Math.min(page * orgAuditLimit, total);

      const infoEl = document.getElementById("audit-pagination-info");
      const indicatorEl = document.getElementById("audit-page-indicator");
      const prevBtn = document.getElementById("audit-prev-btn");
      const nextBtn = document.getElementById("audit-next-btn");

      if (infoEl) infoEl.textContent = `Showing ${start}-${end} of ${total}`;
      if (indicatorEl) indicatorEl.textContent = `Page ${page} of ${totalPages || 1}`;
      if (prevBtn) prevBtn.disabled = page <= 1;
      if (nextBtn) nextBtn.disabled = page >= totalPages;
    }
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="7" class="loading-cell error">${escapeHtml(err.message)}</td></tr>`;
  }
}

function openAuditDetailsModal(auditId) {
  const log = _cachedAuditLogs.find(l => l.audit_id === auditId);
  if (!log) {
    showToast("Audit event details not found", "warning");
    return;
  }

  const titleEl = document.getElementById("audit-detail-title");
  const resultBadge = document.getElementById("audit-detail-result-badge");
  const summaryBanner = document.getElementById("audit-detail-summary-banner");
  const actorNameEl = document.getElementById("audit-detail-actor-name");
  const actorEmailEl = document.getElementById("audit-detail-actor-email");
  const actorRoleEl = document.getElementById("audit-detail-actor-role");
  const targetNameEl = document.getElementById("audit-detail-target-name");
  const targetTypeEl = document.getElementById("audit-detail-target-type");
  const timeEl = document.getElementById("audit-detail-time");
  const timeHintEl = document.getElementById("audit-detail-time-hint");
  const orgEl = document.getElementById("audit-detail-org");

  if (titleEl) titleEl.textContent = log.action_label || log.event_type || "Audit Event Details";
  if (resultBadge) {
    const isSuccess = log.result === "SUCCESS" || !log.result;
    resultBadge.textContent = log.result || "SUCCESS";
    resultBadge.className = `badge badge-${isSuccess ? 'active' : 'inactive'}`;
  }
  if (summaryBanner) summaryBanner.textContent = log.summary || "No description provided.";
  if (actorNameEl) actorNameEl.textContent = log.actor_name || "System";
  if (actorEmailEl) actorEmailEl.textContent = log.actor_email || "-";
  if (actorRoleEl) {
    actorRoleEl.innerHTML = `<span class="badge badge-secondary" style="font-size: 0.68rem;">${escapeHtml(log.actor_role_label || "Administrator")}</span>`;
  }
  if (targetNameEl) targetNameEl.textContent = log.target_name || "-";
  if (targetTypeEl) targetTypeEl.textContent = `Type: ${log.target_type || "System"}`;
  if (timeEl) timeEl.textContent = log.timestamp ? new Date(log.timestamp).toLocaleString() : "-";
  if (timeHintEl) timeHintEl.textContent = formatRelativeTime(log.timestamp);
  if (orgEl) orgEl.textContent = log.organization_name || "Organization Workspace";

  // Diff rendering
  const diffContainer = document.getElementById("audit-detail-diff-container");
  const diffList = document.getElementById("audit-detail-diff-list");
  if (diffContainer && diffList) {
    const diffObj = log.diff || {};
    const diffKeys = Object.keys(diffObj);
    if (diffKeys.length > 0) {
      diffContainer.style.display = "block";
      diffList.innerHTML = diffKeys.map(k => {
        const item = diffObj[k];
        let beforeVal = "-";
        let afterVal = "-";
        if (typeof item === "object" && item !== null) {
          beforeVal = JSON.stringify(item.before ?? item.old ?? "-");
          afterVal = JSON.stringify(item.after ?? item.new ?? "-");
        } else {
          afterVal = String(item);
        }
        return `
          <div style="display: flex; justify-content: space-between; align-items: center; padding: 6px 0; border-bottom: 1px solid var(--border-color); font-size: 0.8rem;">
            <strong style="color: var(--text-primary); text-transform: capitalize;">${escapeHtml(k.replace(/_/g, " "))}:</strong>
            <div>
              <span style="color: #f87171; text-decoration: line-through; margin-right: 8px;">${escapeHtml(beforeVal)}</span>
              <span style="color: var(--text-muted);">&rarr;</span>
              <span style="color: #4ade80; margin-left: 8px; font-weight: 600;">${escapeHtml(afterVal)}</span>
            </div>
          </div>
        `;
      }).join("");
    } else {
      diffContainer.style.display = "none";
    }
  }

  // Extra details rendering (sanitized, excluding secrets)
  const extraContainer = document.getElementById("audit-detail-extra-container");
  const extraList = document.getElementById("audit-detail-extra-list");
  if (extraContainer && extraList) {
    const details = log.details || {};
    const keys = Object.keys(details).filter(k => !k.toLowerCase().includes("password") && !k.toLowerCase().includes("secret") && !k.toLowerCase().includes("token") && !k.toLowerCase().includes("hash"));
    if (keys.length > 0) {
      extraContainer.style.display = "block";
      extraList.innerHTML = keys.map(k => {
        const v = details[k];
        const valStr = typeof v === "object" ? JSON.stringify(v) : String(v);
        return `<div style="margin-bottom: 4px;"><strong style="color: var(--text-primary);">${escapeHtml(k)}:</strong> <span style="color: var(--accent-cyan);">${escapeHtml(valStr)}</span></div>`;
      }).join("");
    } else {
      extraContainer.style.display = "none";
    }
  }

  openModal("modal-audit-details");
}

// ----------------------------------------------------
// USER & ROLE MODAL HANDLERS
// ----------------------------------------------------

async function openCreateUserModal() {
  await populateUsersFilterDropdowns();

  const roleSelect = document.getElementById("new-user-role-select");
  if (roleSelect) {
    roleSelect.innerHTML = _cachedOrgRoles.map(r =>
      `<option value="${r.role_id}">${escapeHtml(r.name)} (${r.is_system_role ? "System" : "Custom"})</option>`
    ).join("");
  }

  const appScopeSelect = document.getElementById("new-user-app-scope");
  if (appScopeSelect) {
    appScopeSelect.innerHTML = '<option value="">All Applications (Org-wide)</option>' +
      _cachedOrgApps.map(a => `<option value="${a.application_id}">${escapeHtml(a.name)}</option>`).join("");
  }

  document.getElementById("form-create-user")?.reset();
  const empCodeInput = document.getElementById("new-user-employee-code");
  if (empCodeInput) empCodeInput.value = "";
  openModal("modal-create-user");
}

function setupCreateUserForm() {
  document.getElementById("form-create-user")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const selRole = document.getElementById("new-user-role-select").value;
    const appScope = document.getElementById("new-user-app-scope")?.value || null;
    const employeeCode = document.getElementById("new-user-employee-code")?.value.trim().toUpperCase() || "";

    if (!employeeCode) {
      showToast("Employee ID is required", "warning");
      document.getElementById("new-user-employee-code")?.focus();
      return;
    }

    const dept = document.getElementById("new-user-department")?.value.trim() || "";
    const phone = document.getElementById("new-user-phone")?.value.trim() || "";
    if (!dept) {
      showToast("Department is required", "warning");
      document.getElementById("new-user-department")?.focus();
      return;
    }
    if (!phone) {
      showToast("Phone number is required", "warning");
      document.getElementById("new-user-phone")?.focus();
      return;
    }

    const payload = {
      name: document.getElementById("new-user-name").value.trim(),
      email: document.getElementById("new-user-email").value.trim().toLowerCase(),
      employee_code: employeeCode,
      role_ids: selRole ? [selRole] : [],
      role_assignments: selRole ? [{ role_id: selRole, application_id: appScope }] : []
    };
    payload.department = dept;
    payload.phone = phone;

    try {
      const res = await ApiClient.createUser(payload);
      if (res.success) {
        showToast("Employee added. They must activate through their email.", "success");
        closeModal("modal-create-user");
        document.getElementById("form-create-user").reset();
        loadOrgUsers();
      } else {
        showToast(res.message || "Failed to create user", "danger");
      }
    } catch (err) {
      showToast(err.message, "danger");
    }
  });
}

async function handleResendActivationOtp(userId, userName) {
  try {
    const result = await ApiClient.resendActivationOtp(userId);
    if (result.success) {
      showToast(`Activation code queued for ${userName}.`, "success");
    } else {
      showToast(result.message || "Could not resend the activation code.", "danger");
    }
  } catch (error) {
    showToast(error.message || "Could not resend the activation code.", "danger");
  }
}

async function handleToggleUserStatus(userId, userName, currentActive) {
  if (currentActive) {
    showConfirmModal({
      title: "Deactivate Employee",
      message: `Are you sure you want to deactivate "${userName}"? They will immediately lose access to this organization's dashboard and API tokens.`,
      confirmText: "Deactivate Employee",
      confirmClass: "btn-danger",
      onConfirm: async () => {
        try {
          const res = await ApiClient.deactivateUser(userId);
          if (res.success) {
            showToast(`Employee "${userName}" has been deactivated.`, "success");
            loadOrgUsers();
          } else {
            showToast(res.message || "Failed to deactivate employee", "danger");
          }
        } catch (err) {
          showToast(err.message, "danger");
        }
      }
    });
  } else {
    try {
      const res = await ApiClient.activateUser(userId);
      if (res.success) {
        showToast(`Employee "${userName}" has been activated.`, "success");
        loadOrgUsers();
      } else {
        showToast(res.message || "Failed to activate employee", "danger");
      }
    } catch (err) {
      showToast(err.message, "danger");
    }
  }
}

async function handleOpenAssignRoles(userId) {
  await populateUsersFilterDropdowns();

  try {
    const res = await ApiClient.getUser(userId);
    if (!res.success || !res.data) {
      showToast("Unable to load user details", "danger");
      return;
    }

    const u = res.data;
    document.getElementById("assign-role-user-id").value = u.user_id;
    document.getElementById("assign-role-user-name").textContent = u.name;
    document.getElementById("assign-role-user-email").textContent = u.email;
    if (document.getElementById("edit-user-department")) document.getElementById("edit-user-department").value = u.department || "";
    if (document.getElementById("edit-user-phone")) document.getElementById("edit-user-phone").value = u.phone || "";

    _currentRoleAssignments = (u.role_assignments && u.role_assignments.length > 0)
      ? JSON.parse(JSON.stringify(u.role_assignments))
      : (u.role_ids || []).map(rid => ({ role_id: rid, application_id: null }));

    const roleSelect = document.getElementById("assign-role-select");
    if (roleSelect) {
      roleSelect.innerHTML = _cachedOrgRoles.map(r =>
        `<option value="${r.role_id}">${escapeHtml(r.name)} (${r.is_system_role ? "System" : "Custom"})</option>`
      ).join("");
    }

    const appScopeSelect = document.getElementById("assign-role-app-select");
    if (appScopeSelect) {
      appScopeSelect.innerHTML = '<option value="">All Applications (Org-wide)</option>' +
        _cachedOrgApps.map(a => `<option value="${a.application_id}">${escapeHtml(a.name)}</option>`).join("");
    }

    renderRoleAssignmentsList();
    openModal("modal-assign-role");
  } catch (err) {
    showToast(err.message, "danger");
  }
}

function renderRoleAssignmentsList() {
  const container = document.getElementById("assign-role-current-list");
  if (!container) return;

  if (_currentRoleAssignments.length === 0) {
    container.innerHTML = '<span style="font-size: 0.8rem; color: var(--text-muted);">No roles assigned</span>';
    return;
  }

  container.innerHTML = _currentRoleAssignments.map((a, idx) => {
    const role = _cachedOrgRoles.find(r => r.role_id === a.role_id);
    const roleName = role ? role.name : a.role_id;
    let appName = "All Applications (Org-wide)";
    if (a.application_id && a.application_id !== "all") {
      const app = _cachedOrgApps.find(x => x.application_id === a.application_id);
      appName = app ? app.name : a.application_id;
    }
    const isOrgWide = !a.application_id || a.application_id === "all";

    return `
      <span class="role-assignment-pill">
        <strong>${escapeHtml(roleName)}</strong>
        <span class="app-scope-badge ${isOrgWide ? "org-wide" : "app-scoped"}">${escapeHtml(appName)}</span>
        <button type="button" class="remove-btn" onclick="removeRoleAssignmentRow(${idx})" title="Remove assignment">&times;</button>
      </span>
    `;
  }).join("");
}

function addRoleAssignmentRow() {
  const roleSelect = document.getElementById("assign-role-select");
  const appScopeSelect = document.getElementById("assign-role-app-select");

  const roleId = roleSelect?.value;
  const appId = appScopeSelect?.value || null;

  if (!roleId) {
    showToast("Please select a role to add", "warning");
    return;
  }

  // Check duplicate
  const exists = _currentRoleAssignments.some(a => a.role_id === roleId && (a.application_id || null) === (appId || null));
  if (exists) {
    showToast("This role with the selected application scope is already assigned", "warning");
    return;
  }

  _currentRoleAssignments.push({ role_id: roleId, application_id: appId });
  renderRoleAssignmentsList();
}

function removeRoleAssignmentRow(idx) {
  _currentRoleAssignments.splice(idx, 1);
  renderRoleAssignmentsList();
}

async function saveRoleAssignments() {
  const userId = document.getElementById("assign-role-user-id").value;
  if (!userId) return;

  try {
    const dept = document.getElementById("edit-user-department")?.value.trim() || "";
    const phone = document.getElementById("edit-user-phone")?.value.trim() || "";
    if (!dept) {
      showToast("Department is required", "warning");
      document.getElementById("edit-user-department")?.focus();
      return;
    }
    if (!phone) {
      showToast("Phone number is required", "warning");
      document.getElementById("edit-user-phone")?.focus();
      return;
    }
    const payload = {
      role_assignments: _currentRoleAssignments,
      department: dept,
      phone: phone
    };
    const res = await ApiClient.assignUserRoles(userId, payload);
    if (res.success) {
      showToast("Role assignments saved successfully!", "success");
      closeModal("modal-assign-role");
      loadOrgUsers();
      const currentAccount = ApiClient.getStoredAccount();
      if (currentAccount && (userId === currentAccount.id || userId === currentAccount.user_id)) {
        await initOrganizationDashboard(currentAccount);
      }
    } else {
      showToast(res.message || "Failed to update role assignments", "danger");
    }
  } catch (err) {
    showToast(err.message, "danger");
  }
}

async function handleViewUserDetails(userId) {
  try {
    const res = await ApiClient.getUser(userId);
    if (!res.success || !res.data) {
      showToast("Employee details not found", "danger");
      return;
    }

    const u = res.data;
    document.getElementById("detail-user-name").textContent = u.name;
    document.getElementById("detail-user-email").textContent = u.email;
    if (document.getElementById("detail-user-emp-code")) {
      document.getElementById("detail-user-emp-code").textContent = u.employee_code || "No ID";
    }
    if (document.getElementById("detail-user-department")) {
      document.getElementById("detail-user-department").textContent = u.department || "Not provided";
    }
    if (document.getElementById("detail-user-phone")) {
      document.getElementById("detail-user-phone").textContent = u.phone || "Not provided";
    }
    if (document.getElementById("detail-user-id")) {
      document.getElementById("detail-user-id").textContent = "";
    }
    document.getElementById("detail-user-created").textContent = `Created: ${u.created_at ? new Date(u.created_at).toLocaleDateString() : "-"}`;

    const badge = document.getElementById("detail-user-status-badge");
    if (badge) {
      badge.textContent = u.is_active ? "ACTIVE" : "INACTIVE";
      badge.className = `badge badge-${u.is_active ? "active" : "inactive"}`;
    }

    // Render assigned roles
    const rolesContainer = document.getElementById("detail-user-roles-list");
    if (rolesContainer) {
      if (u.roles && u.roles.length > 0) {
        rolesContainer.innerHTML = u.roles.map(r => {
          const isOrgWide = !r.application_id || r.application_id === "all";
          const scope = r.application_name || (isOrgWide ? "Org-wide" : "App-scoped");
          return `
            <span class="role-assignment-pill" style="margin-right: 6px; margin-bottom: 6px;">
              <strong>${escapeHtml(r.name)}</strong>
              <span class="app-scope-badge ${isOrgWide ? "org-wide" : "app-scoped"}">${escapeHtml(scope)}</span>
            </span>
          `;
        }).join("");
      } else {
        rolesContainer.innerHTML = '<span class="subtitle" style="font-size: 0.8rem;">No roles assigned</span>';
      }
    }

    // Render Permission Matrix across connected applications
    const matrixTbody = document.getElementById("matrix-table-body");
    const matrixColApps = document.getElementById("matrix-col-apps");
    if (matrixTbody) {
      const apps = _cachedOrgApps || [];
      if (matrixColApps) {
        matrixColApps.textContent = apps.length > 0 
          ? `Apps (${apps.map(a => a.name).join(", ")})` 
          : "Connected Applications";
      }

      // Collect org-wide permissions vs app-scoped permissions
      const orgWidePerms = new Set();
      const appPermsMap = {}; // appId -> Set of perms

      (u.roles || []).forEach(r => {
        const pList = r.permissions || [];
        if (!r.application_id || r.application_id === "all") {
          pList.forEach(p => orgWidePerms.add(p));
        } else {
          if (!appPermsMap[r.application_id]) appPermsMap[r.application_id] = new Set();
          pList.forEach(p => appPermsMap[r.application_id].add(p));
        }
      });

      // Get list of all known permissions
      let allPerms = [];
      const permRes = await ApiClient.listPermissions();
      if (permRes.success && permRes.data) {
        allPerms = permRes.data;
      }

      matrixTbody.innerHTML = allPerms.map(p => {
        const hasOrg = orgWidePerms.has(p);
        let appScopeDetails = "-";

        if (hasOrg) {
          appScopeDetails = '<span style="color: var(--status-success); font-weight: 600;">Inherited Everywhere</span>';
        } else {
          const grantedApps = [];
          for (const [appId, pSet] of Object.entries(appPermsMap)) {
            if (pSet.has(p)) {
              const a = apps.find(x => x.application_id === appId);
              grantedApps.push(a ? a.name : appId);
            }
          }
          if (grantedApps.length > 0) {
            appScopeDetails = grantedApps.map(name =>
              `<span class="app-scope-badge app-scoped" style="margin-right: 4px;">${escapeHtml(name)}</span>`
            ).join("");
          }
        }

        return `
          <tr>
            <td style="font-family: var(--font-mono); font-size: 0.775rem;">${escapeHtml(p)}</td>
            <td class="${hasOrg ? "granted" : "denied"}">${hasOrg ? "GRANTED" : "DENIED"}</td>
            <td>${appScopeDetails}</td>
          </tr>
        `;
      }).join("");
    }

    openModal("modal-user-details");
  } catch (err) {
    showToast(err.message, "danger");
  }
}

// ----------------------------------------------------
// CUSTOM ROLE CREATION & MANAGEMENT
// ----------------------------------------------------

async function openCreateRoleModal() {
  await populateUsersFilterDropdowns();

  const appScopeSelect = document.getElementById("new-role-app-scope");
  if (appScopeSelect) {
    appScopeSelect.innerHTML = '<option value="">All Applications (Org-wide)</option>' +
      _cachedOrgApps.map(a => `<option value="${a.application_id}">${escapeHtml(a.name)}</option>`).join("");
  }

  const container = document.getElementById("create-role-permissions-container");
  if (container) {
    container.innerHTML = '<div class="loading-cell">Loading permissions...</div>';
    try {
      const res = await ApiClient.listPermissions();
      if (res.success && res.categories) {
        container.innerHTML = Object.entries(res.categories).map(([cat, perms]) => {
          return `
            <div class="permission-category-card">
              <div class="permission-category-header">
                <span>${escapeHtml(cat)}</span>
                <label style="font-size: 0.7rem; font-weight: normal; cursor: pointer; text-transform: none; color: var(--text-secondary);">
                  <input type="checkbox" onchange="toggleCategoryPermissions('${cat}', this.checked)" style="vertical-align: middle; margin-right: 2px;" /> All
                </label>
              </div>
              <div class="permission-list" data-category="${escapeHtml(cat)}">
                ${perms.map(p => `
                  <label class="permission-checkbox-item">
                    <input type="checkbox" value="${escapeHtml(p)}" class="role-perm-checkbox" data-cat="${escapeHtml(cat)}" />
                    <span style="font-family: var(--font-mono); font-size: 0.725rem;">${escapeHtml(p.replace("organization:", ""))}</span>
                  </label>
                `).join("")}
              </div>
            </div>
          `;
        }).join("");
      }
    } catch (err) {
      container.innerHTML = `<div class="loading-cell error">${escapeHtml(err.message)}</div>`;
    }
  }

  document.getElementById("form-create-role")?.reset();
  openModal("modal-create-role");
}

function toggleAllRolePermissions(selectAll) {
  const checkboxes = document.querySelectorAll(".role-perm-checkbox");
  checkboxes.forEach(cb => cb.checked = selectAll);
}

function toggleCategoryPermissions(cat, selectAll) {
  const checkboxes = document.querySelectorAll(`.role-perm-checkbox[data-cat="${cat}"]`);
  checkboxes.forEach(cb => cb.checked = selectAll);
}

function setupCreateRoleForm() {
  document.getElementById("form-create-role")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const name = document.getElementById("new-role-name").value.trim().replace(/\s+/g, " ");
    const description = document.getElementById("new-role-desc")?.value?.trim() || "";
    const appScope = document.getElementById("new-role-app-scope")?.value || null;

    const checkedPerms = Array.from(document.querySelectorAll(".role-perm-checkbox:checked")).map(cb => cb.value);

    if (checkedPerms.length === 0) {
      showToast("Please select at least one permission for this role", "warning");
      return;
    }

    const payload = {
      name,
      description,
      application_id: appScope,
      permissions: checkedPerms
    };

    try {
      const res = await ApiClient.createRole(payload);
      if (res.success) {
        showToast(`Role "${name}" created successfully!`, "success");
        closeModal("modal-create-role");
        document.getElementById("form-create-role").reset();
        loadOrgRoles();
        populateUsersFilterDropdowns();
      } else {
        showToast(res.message || "Failed to create custom role", "danger");
      }
    } catch (err) {
      showToast(err.message, "danger");
    }
  });
}

async function handleViewRoleDetails(roleId) {
  try {
    const res = await ApiClient.getRole(roleId);
    if (!res.success || !res.data) {
      showToast("Role details not found", "danger");
      return;
    }

    const r = res.data;
    _activeViewingRoleId = r.role_id;

    document.getElementById("detail-role-name").textContent = r.name;
    document.getElementById("detail-role-desc").textContent = r.description || "No description provided.";
    
    const isOrgWide = !r.application_id || r.application_id === "all";
    document.getElementById("detail-role-scope").textContent = `Scope: ${isOrgWide ? "All Applications (Org-wide)" : (r.application_name || r.application_id)}`;

    const typeBadge = document.getElementById("detail-role-type-badge");
    const isSystem = r.is_system_role || r.name === "ORG_ADMIN";
    if (typeBadge) {
      typeBadge.textContent = isSystem ? "SYSTEM ROLE" : "CUSTOM ROLE";
      typeBadge.className = `badge ${isSystem ? "badge-env-live" : "badge-env-test"}`;
    }

    // Permissions
    const permList = document.getElementById("detail-role-permissions-list");
    if (permList) {
      permList.innerHTML = (r.permissions || []).map(p =>
        `<span class="app-scope-badge org-wide" style="font-family: var(--font-mono); font-size: 0.725rem;">${escapeHtml(p)}</span>`
      ).join("");
    }

    // Assigned employees
    const membersCount = document.getElementById("detail-role-members-count");
    const membersList = document.getElementById("detail-role-members-list");
    const employees = r.assigned_employees || [];
    if (membersCount) membersCount.textContent = employees.length;

    if (membersList) {
      if (employees.length === 0) {
        membersList.innerHTML = '<span class="subtitle" style="font-size: 0.8rem;">No active employees currently assigned to this role</span>';
      } else {
        membersList.innerHTML = employees.map(emp => `
          <div style="display: flex; justify-content: space-between; align-items: center; padding: 6px 0; border-bottom: 1px solid var(--border-color);">
            <div>
              <strong style="color: var(--text-primary); font-size: 0.85rem;">${escapeHtml(emp.name)}</strong>
              <span style="font-size: 0.75rem; color: var(--text-secondary); margin-left: 8px;">${escapeHtml(emp.email)}</span>
            </div>
            <span class="badge badge-active" style="font-size: 0.65rem;">ACTIVE</span>
          </div>
        `).join("");
      }
    }

    // Delete role button configuration
    const deleteBtn = document.getElementById("btn-delete-role-action");
    if (deleteBtn) {
      if (isSystem) {
        deleteBtn.style.display = "none";
      } else {
        deleteBtn.style.display = "block";
        if (employees.length > 0) {
          deleteBtn.disabled = true;
          deleteBtn.title = `Cannot delete role with ${employees.length} active member(s)`;
          deleteBtn.style.opacity = "0.5";
          deleteBtn.style.cursor = "not-allowed";
        } else {
          deleteBtn.disabled = false;
          deleteBtn.title = "Delete this custom role";
          deleteBtn.style.opacity = "1";
          deleteBtn.style.cursor = "pointer";
        }
      }
    }

    openModal("modal-role-details");
  } catch (err) {
    showToast(err.message, "danger");
  }
}

function handleDeleteCurrentRole() {
  if (!_activeViewingRoleId) return;
  const role = _cachedOrgRoles.find(r => r.role_id === _activeViewingRoleId);
  const roleName = role ? role.name : _activeViewingRoleId;
  closeModal("modal-role-details");
  handleDeleteRole(_activeViewingRoleId, roleName);
}

function handleDeleteRole(roleId, roleName) {
  showConfirmModal({
    title: "Delete Custom Role",
    message: `Are you sure you want to delete custom role "${roleName}"? This action cannot be undone.`,
    confirmText: "Delete Role",
    confirmClass: "btn-danger",
    onConfirm: async () => {
      try {
        const res = await ApiClient.deleteRole(roleId);
        if (res.success) {
          showToast(`Role "${roleName}" deleted successfully!`, "success");
          loadOrgRoles();
          populateUsersFilterDropdowns();
        } else {
          showToast(res.message || "Failed to delete role", "danger");
        }
      } catch (err) {
        showToast(err.message, "danger");
      }
    }
  });
}

function handleProviderSelectChange() {
  const provider = document.getElementById("cfg-provider")?.value;
  const sgFields = document.getElementById("cfg-sendgrid-fields");
  const twilioFields = document.getElementById("cfg-twilio-fields");
  const metaFields = document.getElementById("cfg-meta-fields");
  const teamsFields = document.getElementById("cfg-teams-fields");

  if (sgFields) sgFields.style.display = (provider === "sendgrid" || provider === "ses" || provider === "smtp") ? "block" : "none";
  if (twilioFields) twilioFields.style.display = provider === "twilio" ? "block" : "none";
  if (metaFields) metaFields.style.display = (provider === "meta" || provider === "whatsapp") ? "block" : "none";
  if (teamsFields) teamsFields.style.display = (provider === "teams" || provider === "microsoft_teams") ? "block" : "none";
}

function setupProviderConfigForm() {
  document.getElementById("provider-config-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const provider = document.getElementById("cfg-provider").value;
    let credentials = {};

    if (provider === "twilio") {
      const accountSid = document.getElementById("cfg-twilio-account-sid").value.trim();
      const authToken = document.getElementById("cfg-twilio-auth-token").value.trim();
      const fromNumber = document.getElementById("cfg-twilio-from-number").value.trim();
      const messagingServiceSid = document.getElementById("cfg-twilio-messaging-service-sid").value.trim();
      const statusCallback = document.getElementById("cfg-twilio-status-callback").value.trim();

      credentials = {
        account_sid: accountSid,
        auth_token: authToken
      };
      if (fromNumber) credentials.from_number = fromNumber;
      if (messagingServiceSid) credentials.messaging_service_sid = messagingServiceSid;
      if (statusCallback) credentials.status_callback_url = statusCallback;
    } else if (provider === "meta" || provider === "whatsapp") {
      const accessToken = document.getElementById("cfg-meta-access-token").value.trim();
      const phoneId = document.getElementById("cfg-meta-phone-id").value.trim();
      const wabaId = document.getElementById("cfg-meta-waba-id").value.trim();
      const appSecret = document.getElementById("cfg-meta-app-secret").value.trim();
      const verifyToken = document.getElementById("cfg-meta-verify-token").value.trim();

      credentials = {
        access_token: accessToken,
        phone_number_id: phoneId
      };
      if (wabaId) credentials.business_account_id = wabaId;
      if (appSecret) credentials.app_secret = appSecret;
      if (verifyToken) credentials.webhook_verify_token = verifyToken;
    } else if (provider === "teams" || provider === "microsoft_teams") {
      const tenantId = document.getElementById("cfg-teams-tenant-id").value.trim();
      const clientId = document.getElementById("cfg-teams-client-id").value.trim();
      const clientSecret = document.getElementById("cfg-teams-client-secret").value.trim();
      const defaultTeamId = document.getElementById("cfg-teams-default-team-id").value.trim();
      const defaultChannelId = document.getElementById("cfg-teams-default-channel-id").value.trim();

      credentials = {
        tenant_id: tenantId,
        client_id: clientId,
        client_secret: clientSecret
      };
      if (defaultTeamId) credentials.default_team_id = defaultTeamId;
      if (defaultChannelId) credentials.default_channel_id = defaultChannelId;
    } else {
      const apiKey = document.getElementById("cfg-api-key").value.trim();
      const fromEmail = document.getElementById("cfg-from-email").value.trim();
      credentials = {
        api_key: apiKey,
        from_email: fromEmail
      };
    }

    try {
      const res = await ApiClient.saveProviderConfig(provider, credentials);
      if (res.success) {
        showToast(`${provider.toUpperCase()} credentials encrypted and saved securely!`, "success");
      } else {
        showToast(res.message || "Failed to save configuration", "danger");
      }
    } catch (err) {
      showToast(err.message, "danger");
    }
  });
}

async function loadOrgAnalytics() {
  try {
    const res = await ApiClient.getOrganizationAnalytics();
    if (res.success && res.overview) {
      document.getElementById("org-m-total").textContent = res.overview.total_messages;
      document.getElementById("org-m-sent").textContent = res.overview.sent;
      document.getElementById("org-m-failed").textContent = res.overview.failed;
      document.getElementById("org-m-dead").textContent = res.overview.dead;
      document.getElementById("org-m-rate").textContent = `${res.overview.delivery_rate_percent}%`;

      // Render daily chart
      const chartContainer = document.getElementById("analytics-daily-chart");
      const trends = res.daily_trends || [];
      const hasTrends = trends.some((t) => t.total > 0);

      if (chartContainer) {
        if (hasTrends && trends.length > 0) {
          const maxTotal = Math.max(...trends.map((t) => t.total), 1);
          chartContainer.innerHTML = trends.map((t) => {
            const heightPercent = Math.max(Math.round((t.total / maxTotal) * 100), 6);
            const shortDate = t.date ? t.date.substring(5) : "";
            return `
              <div class="bar-col" title="${t.date}: ${t.total} messages (${t.sent} sent, ${t.failed} failed)">
                <div class="bar-fill-wrapper">
                  <div class="bar-fill" style="height: ${heightPercent}%;"></div>
                </div>
                <span class="bar-col-label">${shortDate}</span>
              </div>
            `;
          }).join("");
        } else {
          chartContainer.innerHTML = `
            <div class="empty-state" style="width: 100%; border: none; padding: 24px 0;">
              <span class="subtitle">No daily dispatch activity recorded in this period.</span>
            </div>
          `;
        }
      }

      // Render provider list
      const providersList = document.getElementById("analytics-providers-list");
      const providers = (res.providers || []).filter((p) => p.count > 0);
      if (providersList) {
        if (providers.length > 0) {
          providersList.innerHTML = providers.map((p) => `
            <div class="channel-item">
              <div class="channel-header">
                <span class="channel-name">${escapeHtml(p.provider)}</span>
                <span class="channel-count">${p.sent}/${p.count} delivered (${p.success_rate_percent}%)</span>
              </div>
              <div class="progress-bar-bg">
                <div class="progress-bar-fill" style="width: ${p.success_rate_percent}%;"></div>
              </div>
            </div>
          `).join("");
        } else {
          providersList.innerHTML = `
            <div class="empty-state" style="width: 100%; border: none; padding: 24px 0;">
              <span class="subtitle">No provider dispatches recorded yet.</span>
            </div>
          `;
        }
      }
    }
  } catch (err) {
    console.error(err);
  }
}

// ----------------------------------------------------
// PHASE 5 TASK 1: ORGANIZATION DASHBOARD OPERATIONS
// ----------------------------------------------------

// 1. Overview Operations
async function loadOrgOverview() {
  const isOrgAdmin = currentUserDashboardContext?.is_org_admin || false;
  const emptyModulesEl = document.getElementById("overview-empty-modules");

  // If user is an employee with zero effective permissions, show empty state and hide cards
  if (!isOrgAdmin && currentUserPermissions.size === 0) {
    if (emptyModulesEl) emptyModulesEl.style.display = "block";
    document.querySelectorAll("#tab-org-overview [data-perm]").forEach((el) => {
      el.style.display = "none";
    });
    return;
  }
  if (emptyModulesEl) emptyModulesEl.style.display = "none";

  const reqAnalytics = isOrgAdmin || hasPermission("organization:analytics:read");
  const reqApps = isOrgAdmin || hasPermission("organization:configuration:manage");
  const reqPayloads = isOrgAdmin || hasPermission("organization:payloads:read");
  const reqDlq = isOrgAdmin || hasPermission("organization:dead_letters:read");

  const [analyticsRes, appsRes, payloadsRes, dlqRes] = await Promise.allSettled([
    reqAnalytics ? ApiClient.getOrganizationAnalytics() : Promise.resolve({ success: false }),
    reqApps ? ApiClient.listApplications(1, 100) : Promise.resolve({ success: false, data: [] }),
    reqPayloads ? ApiClient.listPayloads(1, 5) : Promise.resolve({ success: false, data: [] }),
    reqDlq ? ApiClient.listDlq(1, 5) : Promise.resolve({ success: false, data: [] })
  ]);

  const analytics = analyticsRes.status === "fulfilled" && analyticsRes.value.success ? analyticsRes.value : null;
  const apps = appsRes.status === "fulfilled" && appsRes.value.success ? (appsRes.value.data || []) : [];
  
  const payloadData = payloadsRes.status === "fulfilled" && payloadsRes.value.success ? payloadsRes.value.data : null;
  const payloads = Array.isArray(payloadData) ? payloadData : (payloadData?.items || []);
  const dlqItems = dlqRes.status === "fulfilled" && dlqRes.value.success ? (dlqRes.value.data || []) : [];
  const totalPayloadsCount = payloadsRes.status === "fulfilled" ? (payloadData?.pagination?.total ?? payloadsRes.value.total ?? payloads.length) : 0;

  // 1. Update 6 Metric Cards
  const appsEl = document.getElementById("overview-m-apps");
  if (appsEl) appsEl.textContent = apps.length;
  const reqEl = document.getElementById("overview-m-requests");
  if (reqEl) reqEl.textContent = totalPayloadsCount;

  const overview = analytics?.overview || {};
  const totalMsgs = overview.total_messages || 0;
  const sentMsgs = overview.sent || 0;
  const failedMsgs = (overview.failed || 0) + (overview.dead || 0);
  const dlqCount = analytics?.dead_letter_queue?.pending_review ?? dlqItems.length;

  const msgsEl = document.getElementById("overview-m-messages");
  if (msgsEl) msgsEl.textContent = totalMsgs;
  const delivEl = document.getElementById("overview-m-delivered");
  if (delivEl) delivEl.textContent = sentMsgs;
  const failEl = document.getElementById("overview-m-failed");
  if (failEl) failEl.textContent = failedMsgs;
  const dlqEl = document.getElementById("overview-m-dlq");
  if (dlqEl) dlqEl.textContent = dlqCount;
  const rateEl = document.getElementById("overview-m-deliv-rate");
  if (rateEl) rateEl.textContent = `${overview.delivery_rate_percent || 0}% delivery rate`;

  // 2. Activity Chart (14-day trends)
  const chartContainer = document.getElementById("overview-activity-chart");
  const trends = analytics?.daily_trends || [];
  const hasTrends = trends.some((t) => t.total > 0);

  if (chartContainer) {
    if (hasTrends && trends.length > 0) {
      const maxTotal = Math.max(...trends.map((t) => t.total), 1);
      chartContainer.innerHTML = trends.map((t) => {
        const heightPercent = Math.max(Math.round((t.total / maxTotal) * 100), 6);
        const shortDate = t.date ? t.date.substring(5) : "";
        return `
          <div class="bar-col" title="${t.date}: ${t.total} total (${t.sent} sent, ${t.failed} failed)">
            <div class="bar-fill-wrapper">
              <div class="bar-fill" style="height: ${heightPercent}%;"></div>
            </div>
            <span class="bar-col-label">${shortDate}</span>
          </div>
        `;
      }).join("");
    } else {
      chartContainer.innerHTML = `
        <div class="empty-state" style="width: 100%; border: none; padding: 24px 0;">
          <span class="subtitle">No message activity recorded in the last 14 days.</span>
        </div>
      `;
    }
  }

  // 3. Channel Distribution
  const channelListEl = document.getElementById("overview-channel-list");
  const channels = (analytics?.channels || []).filter((c) => c.count > 0);
  if (channelListEl) {
    if (channels.length > 0) {
      const maxChannelCount = Math.max(...channels.map((c) => c.count), 1);
      channelListEl.innerHTML = channels.map((c) => {
        const percent = Math.round((c.count / (totalMsgs || maxChannelCount)) * 100);
        return `
          <div class="channel-item">
            <div class="channel-header">
              <span class="channel-name">${escapeHtml(c.channel)}</span>
              <span class="channel-count">${c.count} (${percent}%)</span>
            </div>
            <div class="progress-bar-bg">
              <div class="progress-bar-fill" style="width: ${percent}%;"></div>
            </div>
          </div>
        `;
      }).join("");
    } else {
      channelListEl.innerHTML = `
        <div class="empty-state" style="width: 100%; border: none; padding: 24px 0;">
          <span class="subtitle">No channel activity recorded yet.</span>
        </div>
      `;
    }
  }

  // 4. Recent Payloads Table
  const payloadsBody = document.getElementById("overview-payloads-body");
  if (payloadsBody) {
    if (payloads.length > 0) {
      payloadsBody.innerHTML = payloads.map((p) => `
        <tr>
          <td><code>${escapeHtml((p.payload_id || "").substring(0, 16))}...</code></td>
          <td>${escapeHtml(p.application_id || "direct")}</td>
          <td><span class="badge badge-processing">${escapeHtml(p.channel || "unassigned")}</span></td>
          <td><span class="badge badge-${(p.validation_status || "valid").toLowerCase()}">${escapeHtml(p.validation_status || "VALID")}</span></td>
          <td>${p.received_at ? new Date(p.received_at).toLocaleTimeString() : "-"}</td>
        </tr>
      `).join("");
    } else {
      payloadsBody.innerHTML = '<tr><td colspan="5" class="loading-cell">No inbound JSON requests recorded yet.</td></tr>';
    }
  }

  // 5. Recent Delivery Failures Table
  const failuresBody = document.getElementById("overview-failures-body");
  if (failuresBody) {
    if (dlqItems.length > 0) {
      failuresBody.innerHTML = dlqItems.slice(0, 5).map((d) => `
        <tr>
          <td>${escapeHtml(d.recipient || "-")}</td>
          <td title="${escapeHtml(d.last_error || "")}">${escapeHtml((d.last_error || "Dispatch failed").substring(0, 24))}...</td>
          <td><span class="badge badge-failed">${escapeHtml(d.dead_letter_status || "DEAD")}</span></td>
        </tr>
      `).join("");
    } else {
      failuresBody.innerHTML = '<tr><td colspan="3" class="loading-cell">No delivery failures. All systems operational.</td></tr>';
    }
  }

  // 6. Connected Applications Summary Table
  const appsBody = document.getElementById("overview-apps-body");
  if (appsBody) {
    if (apps.length > 0) {
      appsBody.innerHTML = apps.slice(0, 5).map((a) => `
        <tr>
          <td><strong>${escapeHtml(a.name)}</strong></td>
          <td><span class="badge badge-env-${(a.environment || "all").toLowerCase()}">${(a.environment || "all").toUpperCase()}</span></td>
          <td><span class="badge badge-${(a.status || "active").toLowerCase()}">${a.status || "ACTIVE"}</span></td>
        </tr>
      `).join("");
    } else {
      appsBody.innerHTML = '<tr><td colspan="3" class="loading-cell">No connected applications registered.</td></tr>';
    }
  }

  applyPermissionVisibility();
}

// 2. Connected Applications Operations
async function loadOrgApplications() {
  const tbody = document.getElementById("apps-table-body");
  const emptyState = document.getElementById("apps-empty-state");
  const table = document.getElementById("apps-table");
  const statusFilter = document.getElementById("apps-filter-status")?.value;

  tbody.innerHTML = '<tr><td colspan="6" class="loading-cell">Loading connected applications...</td></tr>';

  try {
    const res = await ApiClient.listApplications(1, 50, statusFilter);
    if (res.success && res.data) {
      cachedApplicationsList = res.data;
      if (res.data.length === 0) {
        tbody.innerHTML = "";
        if (emptyState) emptyState.style.display = "flex";
        if (table) table.style.display = "none";
        return;
      }

      if (emptyState) emptyState.style.display = "none";
      if (table) table.style.display = "table";

      tbody.innerHTML = res.data.map((app) => {
        const envClass = `badge-env-${(app.environment || "all").toLowerCase()}`;
        const statusClass = `badge-${(app.status || "active").toLowerCase()}`;
        const createdDate = app.created_at ? new Date(app.created_at).toLocaleDateString() : "-";
        const isActive = app.status === "ACTIVE";

        return `
          <tr>
            <td>
              <strong>${escapeHtml(app.name)}</strong>
              ${app.description ? `<div class="subtitle" style="font-size: 0.75rem;">${escapeHtml(app.description)}</div>` : ""}
            </td>
            <td><span class="badge ${envClass}">${(app.environment || "all").toUpperCase()}</span></td>
            <td><span class="badge ${statusClass}">${app.status || "ACTIVE"}</span></td>
            <td>${createdDate}</td>
            <td>
              <div class="table-cell-actions">
                <button class="btn btn-secondary btn-sm" onclick="viewAppDetails('${app.application_id}')">Details</button>
                ${
                  isActive
                    ? `<button class="btn btn-outline btn-sm" data-perm="organization:configuration:manage" onclick="handleDeactivateApp('${app.application_id}', '${escapeHtml(app.name)}')">Deactivate</button>`
                    : `<button class="btn btn-primary btn-sm" data-perm="organization:configuration:manage" onclick="handleActivateApp('${app.application_id}', '${escapeHtml(app.name)}')">Activate</button>`
                }
              </div>
            </td>
          </tr>
        `;
      }).join("");

      applyPermissionVisibility();
    }
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" class="loading-cell error">${escapeHtml(err.message)}</td></tr>`;
  }
}

function setupRegisterAppForm() {
  document.getElementById("form-register-app")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const name = document.getElementById("new-app-name").value.trim();
    const description = document.getElementById("new-app-description").value.trim();
    const environment = document.getElementById("new-app-environment").value;

    const btn = document.getElementById("btn-submit-register-app");
    btn.disabled = true;
    btn.textContent = "Registering...";

    try {
      const res = await ApiClient.registerApplication({ name, description, environment });
      if (res.success) {
        showToast("Connected application registered successfully!", "success");
        closeModal("modal-register-app");
        document.getElementById("form-register-app").reset();
        await loadOrgApplications();
      } else {
        showToast(res.message || "Failed to register application", "danger");
      }
    } catch (err) {
      showToast(err.message || "Network error", "danger");
    } finally {
      btn.disabled = false;
      btn.textContent = "Register Application";
    }
  });
}

async function viewAppDetails(appId) {
  let app = cachedApplicationsList.find((a) => a.application_id === appId);
  if (!app) {
    try {
      const res = await ApiClient.getApplication(appId);
      if (res.success && res.data) app = res.data;
    } catch {
      showToast("Could not fetch application details", "danger");
      return;
    }
  }

  document.getElementById("app-details-title").textContent = app.name || "Connected Application Details";
  if (document.getElementById("app-details-id")) document.getElementById("app-details-id").textContent = "";
  document.getElementById("app-details-description").textContent = app.description || "No description provided.";
  document.getElementById("app-details-created").textContent = app.created_at ? new Date(app.created_at).toLocaleString() : "-";
  
  const statusBadge = document.getElementById("app-details-status-badge");
  statusBadge.className = `badge badge-${(app.status || "active").toLowerCase()}`;
  statusBadge.textContent = app.status || "ACTIVE";

  const envBadge = document.getElementById("app-details-env-badge");
  envBadge.className = `badge badge-env-${(app.environment || "all").toLowerCase()}`;
  envBadge.textContent = (app.environment || "all").toUpperCase();

  // Reset telemetry cards before fetch
  document.getElementById("app-stats-total").textContent = "...";
  document.getElementById("app-stats-keys").textContent = "...";
  document.getElementById("app-stats-error-rate").textContent = "...";

  openModal("modal-app-details");

  try {
    const statsRes = await ApiClient.getApplicationStats(appId);
    if (statsRes.success && statsRes.data) {
      const stats = statsRes.data;
      const totalPayloads = stats.ingested_payloads_count ?? stats.total_payloads ?? 0;
      const activeKeys = stats.active_credentials ?? 0;
      const dlqCount = stats.dead_letters_count ?? 0;
      const errorRate = totalPayloads > 0 ? Math.round((dlqCount / totalPayloads) * 100) : 0;

      document.getElementById("app-stats-total").textContent = totalPayloads;
      document.getElementById("app-stats-keys").textContent = activeKeys;
      document.getElementById("app-stats-error-rate").textContent = `${errorRate}%`;
    }
  } catch {
    document.getElementById("app-stats-total").textContent = "-";
    document.getElementById("app-stats-keys").textContent = "-";
    document.getElementById("app-stats-error-rate").textContent = "-";
  }
}

function handleDeactivateApp(appId, appName) {
  showConfirmModal({
    title: "Deactivate Application",
    message: `Deactivating application "${appName}" will immediately REVOKE all active API credentials and reject subsequent incoming payloads. Proceed?`,
    confirmText: "Deactivate Application",
    confirmClass: "btn-danger",
    onConfirm: async () => {
      try {
        const res = await ApiClient.deactivateApplication(appId);
        if (res.success) {
          showToast(`Application "${appName}" deactivated.`, "warning");
          loadOrgApplications();
        } else {
          showToast(res.message || "Failed to deactivate application", "danger");
        }
      } catch (err) {
        showToast(err.message, "danger");
      }
    }
  });
}

function handleActivateApp(appId, appName) {
  showConfirmModal({
    title: "Activate Application",
    message: `Reactivate application "${appName}"? This will allow new API credentials to be generated and authenticated.`,
    confirmText: "Activate Application",
    confirmClass: "btn-primary",
    onConfirm: async () => {
      try {
        const res = await ApiClient.activateApplication(appId);
        if (res.success) {
          showToast(`Application "${appName}" reactivated.`, "success");
          loadOrgApplications();
        } else {
          showToast(res.message || "Failed to activate application", "danger");
        }
      } catch (err) {
        showToast(err.message, "danger");
      }
    }
  });
}

// 3. API Credentials Operations
async function loadOrgCredentials() {
  const tbody = document.getElementById("creds-table-body");
  const emptyState = document.getElementById("creds-empty-state");
  const table = document.getElementById("creds-table");

  tbody.innerHTML = '<tr><td colspan="8" class="loading-cell">Loading API credentials...</td></tr>';

  try {
    // Ensure applications are loaded to show app names
    if (!cachedApplicationsList || cachedApplicationsList.length === 0) {
      const appsRes = await ApiClient.listApplications(1, 100);
      if (appsRes.success && appsRes.data) cachedApplicationsList = appsRes.data;
    }

    const appMap = new Map((cachedApplicationsList || []).map((a) => [a.application_id, a.name]));

    const res = await ApiClient.listCredentials();
    if (res.success && res.data) {
      if (res.data.length === 0) {
        tbody.innerHTML = "";
        if (emptyState) emptyState.style.display = "flex";
        if (table) table.style.display = "none";
        return;
      }

      if (emptyState) emptyState.style.display = "none";
      if (table) table.style.display = "table";

      tbody.innerHTML = res.data.map((cred) => {
        const envClass = `badge-env-${(cred.environment || "live").toLowerCase()}`;
        const statusClass = cred.status === "ACTIVE" ? "badge-active" : "badge-revoked";
        const appName = appMap.get(cred.application_id) || cred.application_id;
        const lastUsed = cred.last_used_at ? new Date(cred.last_used_at).toLocaleString() : "Never";
        const createdDate = cred.created_at ? new Date(cred.created_at).toLocaleDateString() : "-";
        const isActive = cred.status === "ACTIVE";

        return `
          <tr>
            <td><strong>${escapeHtml(cred.name)}</strong></td>
            <td><code>${escapeHtml(cred.key_prefix || "sx_••••")}••••</code></td>
            <td>${escapeHtml(appName)}</td>
            <td><span class="badge ${envClass}">${(cred.environment || "live").toUpperCase()}</span></td>
            <td><span class="badge ${statusClass}">${cred.status || "ACTIVE"}</span></td>
            <td><small>${lastUsed}</small></td>
            <td>${createdDate}</td>
            <td>
              <div class="table-cell-actions">
                ${
                  isActive
                    ? `
                      <button class="btn btn-secondary btn-sm" data-perm="organization:configuration:manage" onclick="handleRotateCredential('${cred.credential_id}', '${escapeHtml(cred.name)}', '${cred.environment || "live"}')">Rotate</button>
                      <button class="btn btn-outline btn-sm" data-perm="organization:configuration:manage" onclick="handleRevokeCredential('${cred.credential_id}', '${escapeHtml(cred.name)}')">Revoke</button>
                    `
                    : '<span class="subtitle" style="font-size: 0.75rem;">Revoked</span>'
                }
              </div>
            </td>
          </tr>
        `;
      }).join("");

      applyPermissionVisibility();
    }
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="8" class="loading-cell error">${escapeHtml(err.message)}</td></tr>`;
  }
}

async function openGenerateCredentialModal() {
  const appSelect = document.getElementById("new-cred-app");
  appSelect.innerHTML = '<option value="">Loading applications...</option>';

  try {
    const res = await ApiClient.listApplications(1, 100, "ACTIVE");
    if (res.success && res.data) {
      cachedApplicationsList = res.data;
      if (res.data.length === 0) {
        showToast("Please register and activate an application before generating credentials", "warning");
        openModal("modal-register-app");
        return;
      }
      appSelect.innerHTML = '<option value="">Select connected application...</option>' +
        res.data.map((a) => `<option value="${a.application_id}">${escapeHtml(a.name)} (${a.environment.toUpperCase()})</option>`).join("");
    }
  } catch {
    appSelect.innerHTML = '<option value="">Failed to load applications</option>';
  }

  document.getElementById("form-generate-credential").reset();
  openModal("modal-generate-credential");
}

function setupGenerateCredentialForm() {
  document.getElementById("form-generate-credential")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const name = document.getElementById("new-cred-name").value.trim();
    const applicationId = document.getElementById("new-cred-app").value;
    const environment = document.getElementById("new-cred-env").value;
    const includeMessages = document.getElementById("cred-scope-messages")?.checked;

    const scopes = ["payloads:write"];
    if (includeMessages) scopes.push("messages:write");

    const btn = document.getElementById("btn-submit-generate-cred");
    btn.disabled = true;
    btn.textContent = "Generating Key...";

    try {
      const res = await ApiClient.createCredential({
        name,
        application_id: applicationId,
        environment,
        scopes
      });

      const rawKey = res.raw_key || res.api_key || res.data?.api_key;
      if (res.success && rawKey) {
        closeModal("modal-generate-credential");
        displayOneTimeSecret({
          title: "API Credential Generated",
          name,
          appName: document.getElementById("new-cred-app").selectedOptions[0]?.text || applicationId,
          environment,
          rawKey
        });
        showToast("API key generated successfully! Make sure to copy it.", "warning");
        await loadOrgCredentials();
      } else {
        showToast(res.message || "Failed to generate API credential", "danger");
      }
    } catch (err) {
      showToast(err.message || "Network error", "danger");
    } finally {
      btn.disabled = false;
      btn.textContent = "Generate Key";
    }
  });
}

function displayOneTimeSecret({ title, name, appName, environment, rawKey }) {
  hasCopiedSecretKey = false;
  document.getElementById("secret-modal-title").textContent = title || "API Key Generated";
  document.getElementById("secret-cred-name").textContent = name;
  document.getElementById("secret-cred-app").textContent = appName;
  
  const envBadge = document.getElementById("secret-cred-env-badge");
  envBadge.className = `badge badge-env-${(environment || "live").toLowerCase()}`;
  envBadge.textContent = (environment || "live").toUpperCase();

  document.getElementById("secret-key-display").textContent = rawKey;
  document.getElementById("btn-copy-secret-text").textContent = "Copy Key";

  openModal("modal-one-time-secret");
}

function copySecretKey() {
  const keyText = document.getElementById("secret-key-display").textContent;
  if (!keyText) return;

  const copyBtnText = document.getElementById("btn-copy-secret-text");

  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(keyText).then(() => {
      hasCopiedSecretKey = true;
      copyBtnText.textContent = "Copied!";
      showToast("API key copied to clipboard!", "success");
      setTimeout(() => { copyBtnText.textContent = "Copy Key"; }, 3000);
    }).catch(() => fallbackCopy(keyText));
  } else {
    fallbackCopy(keyText);
  }
}

function fallbackCopy(text) {
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.select();
  try {
    document.execCommand("copy");
    hasCopiedSecretKey = true;
    document.getElementById("btn-copy-secret-text").textContent = "Copied!";
    showToast("API key copied to clipboard!", "success");
  } catch {
    showToast("Could not copy automatically. Please select and copy manually.", "warning");
  }
  document.body.removeChild(textarea);
}

function dismissSecretModal() {
  if (!hasCopiedSecretKey) {
    const confirmDismiss = window.confirm("Security Warning: You haven't copied your secret key yet. It cannot be recovered once you close this window. Are you sure you want to proceed?");
    if (!confirmDismiss) return;
  }
  closeModal("modal-one-time-secret");
}

function handleRevokeCredential(credId, credName) {
  showConfirmModal({
    title: "Revoke API Credential",
    message: `Are you sure you want to revoke API key "${credName}"? Any external service or website attempting to authenticate with this key will immediately be rejected. This action cannot be reversed.`,
    confirmText: "Revoke Credential",
    confirmClass: "btn-danger",
    onConfirm: async () => {
      try {
        const res = await ApiClient.revokeCredential(credId);
        if (res.success) {
          showToast(`API Credential "${credName}" revoked.`, "success");
          loadOrgCredentials();
        } else {
          showToast(res.message || "Failed to revoke credential", "danger");
        }
      } catch (err) {
        showToast(err.message, "danger");
      }
    }
  });
}

function handleRotateCredential(credId, credName, env) {
  showConfirmModal({
    title: "Rotate API Key",
    message: `Rotating "${credName}" will immediately REVOKE the existing API key and issue a NEW raw secret. You will be shown the new secret only once. Proceed?`,
    confirmText: "Rotate & Generate New Key",
    confirmClass: "btn-primary",
    onConfirm: async () => {
      try {
        const res = await ApiClient.rotateCredential(credId, env);
        const rawKey = res.raw_key || res.api_key || res.data?.api_key;
        if (res.success && rawKey) {
          displayOneTimeSecret({
            title: "API Credential Rotated",
            name: credName,
            appName: res.data?.application_id || "Connected App",
            environment: env,
            rawKey
          });
          showToast("API key rotated! Copy your new secret key.", "warning");
          loadOrgCredentials();
        } else {
          showToast(res.message || "Failed to rotate credential", "danger");
        }
      } catch (err) {
        showToast(err.message, "danger");
      }
    }
  });
}

// 4. Ingested JSON Requests Operations
async function loadOrgJsonRequests() {
  const tbody = document.getElementById("payloads-table-body");
  const emptyState = document.getElementById("payloads-empty-state");
  const table = document.getElementById("payloads-table");
  const channel = document.getElementById("payloads-filter-channel")?.value;
  const status = document.getElementById("payloads-filter-status")?.value;

  tbody.innerHTML = '<tr><td colspan="6" class="loading-cell">Loading received JSON requests...</td></tr>';

  try {
    const res = await ApiClient.listPayloads(1, 50, { channel, validation_status: status });
    if (res.success && res.data) {
      const items = Array.isArray(res.data) ? res.data : (res.data.items || []);
      if (items.length === 0) {
        tbody.innerHTML = "";
        if (emptyState) emptyState.style.display = "flex";
        if (table) table.style.display = "none";
        return;
      }

      if (emptyState) emptyState.style.display = "none";
      if (table) table.style.display = "table";

      tbody.innerHTML = items.map((p) => {
        const valStatus = p.validation_status || "VALID";
        const valClass = valStatus === "VALID" ? "badge-valid" : "badge-invalid";
        const receivedAt = p.received_at ? new Date(p.received_at).toLocaleString() : "-";

        return `
          <tr>
            <td><code>${escapeHtml(p.payload_id)}</code></td>
            <td>${escapeHtml(p.application_id || "direct")}</td>
            <td><span class="badge badge-processing">${escapeHtml(p.channel || "unassigned")}</span></td>
            <td><span class="badge ${valClass}">${escapeHtml(valStatus)}</span></td>
            <td>${receivedAt}</td>
            <td>
              <button class="btn btn-secondary btn-sm" onclick="viewPayloadDetails('${p.payload_id}')">View Details</button>
            </td>
          </tr>
        `;
      }).join("");
    }
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" class="loading-cell error">${escapeHtml(err.message)}</td></tr>`;
  }
}

async function viewPayloadDetails(payloadId) {
  try {
    const res = await ApiClient.getPayload(payloadId);
    if (res.success && res.data) {
      const p = res.data;
      document.getElementById("view-payload-id").textContent = p.payload_id || payloadId;
      document.getElementById("view-payload-app").textContent = p.application_id || "direct / organization";
      document.getElementById("view-payload-timestamp").textContent = p.received_at ? new Date(p.received_at).toLocaleString() : "-";
      
      const channelBadge = document.getElementById("view-payload-channel");
      channelBadge.textContent = (p.channel || "UNKNOWN").toUpperCase();

      const valBadge = document.getElementById("view-payload-status");
      const status = p.validation_status || "VALID";
      valBadge.textContent = status;
      valBadge.className = `badge badge-${status.toLowerCase()}`;

      // Show the immutable original payload
      const content = p.original_payload || p.active_payload || p;
      document.getElementById("view-payload-json").textContent = JSON.stringify(content, null, 2);

      openModal("modal-view-payload");
    } else {
      showToast(res.message || "Failed to load payload details", "danger");
    }
  } catch (err) {
    showToast(err.message, "danger");
  }
}

// 5. Organization Settings Operations (Phase 5 Task 5.3)
async function loadOrgSettings() {
  try {
    const res = await ApiClient.getCurrentOrganization();
    if (res.success && res.data) {
      const org = res.data;
      currentOrgProfile = org;
      const nameEl = document.getElementById("settings-org-name");
      const slugEl = document.getElementById("settings-org-slug");
      const idEl = document.getElementById("settings-org-id");
      const statusEl = document.getElementById("settings-org-status");
      const createdEl = document.getElementById("settings-org-created");

      if (nameEl) nameEl.textContent = org.name || "-";
      if (slugEl) slugEl.textContent = org.slug || "-";
      if (idEl) idEl.textContent = org.organization_id || "-";
      if (statusEl) {
        statusEl.textContent = org.status || "ACTIVE";
        statusEl.className = `badge badge-${(org.status || "active").toLowerCase()}`;
      }
      if (createdEl) createdEl.textContent = org.created_at ? new Date(org.created_at).toLocaleDateString() : "Active";
    }
  } catch {
    const account = ApiClient.getStoredAccount();
    if (account) {
      const nameEl = document.getElementById("settings-org-name");
      const slugEl = document.getElementById("settings-org-slug");
      const idEl = document.getElementById("settings-org-id");
      if (nameEl) nameEl.textContent = "Organization Workspace";
      if (slugEl) slugEl.textContent = account.organization_id || "-";
      if (idEl) idEl.textContent = account.organization_id || "-";
    }
  }

  // Populate Admin Self-Profile form with current user info
  const storedAccount = ApiClient.getStoredAccount();
  if (storedAccount) {
    const selfName = document.getElementById("self-profile-name");
    const selfEmail = document.getElementById("self-profile-email");
    if (selfName && !selfName.value) selfName.value = storedAccount.name || "";
    if (selfEmail && !selfEmail.value) selfEmail.value = storedAccount.email || "";
  }

  // Load identity change requests history
  await loadOrgChangeRequests();
}

async function loadOrgChangeRequests() {
  const tbody = document.getElementById("org-cr-table")?.querySelector("tbody");
  if (!tbody) return;
  tbody.innerHTML = '<tr><td colspan="7" class="loading-cell">Loading change requests...</td></tr>';

  try {
    const res = await ApiClient.listOrgChangeRequests();
    if (res.success && res.data) {
      const requests = res.data;
      const pendingReq = requests.find((r) => r.status === "PENDING");

      const indicator = document.getElementById("cr-pending-indicator");
      const banner = document.getElementById("cr-pending-banner");
      const submitBtn = document.getElementById("btn-submit-cr");
      const reqNameInput = document.getElementById("cr-req-name");
      const reqSlugInput = document.getElementById("cr-req-slug");
      const reqReasonInput = document.getElementById("cr-req-reason");

      if (pendingReq) {
        if (indicator) indicator.style.display = "inline-flex";
        if (banner) banner.style.display = "block";
        if (submitBtn) {
          submitBtn.disabled = true;
          submitBtn.title = "A change request is already pending review";
        }
        if (reqNameInput) reqNameInput.disabled = true;
        if (reqSlugInput) reqSlugInput.disabled = true;
        if (reqReasonInput) reqReasonInput.disabled = true;
      } else {
        if (indicator) indicator.style.display = "none";
        if (banner) banner.style.display = "none";
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.title = "";
        }
        if (reqNameInput) reqNameInput.disabled = false;
        if (reqSlugInput) reqSlugInput.disabled = false;
        if (reqReasonInput) reqReasonInput.disabled = false;
      }

      if (requests.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="loading-cell">No change requests recorded yet.</td></tr>';
      } else {
        tbody.innerHTML = requests
          .map((cr) => {
            let statusBadge = `<span class="badge badge-warning">${escapeHtml(cr.status)}</span>`;
            if (cr.status === "APPROVED") statusBadge = `<span class="badge badge-active">APPROVED</span>`;
            else if (cr.status === "REJECTED") statusBadge = `<span class="badge badge-inactive">REJECTED</span>`;
            else if (cr.status === "CANCELLED") statusBadge = `<span class="badge badge-secondary">CANCELLED</span>`;

            const submittedAt = cr.created_at ? new Date(cr.created_at).toLocaleString() : "-";
            let resolution = "-";
            if (cr.status === "APPROVED") {
              resolution = `<div style="font-size: 0.75rem; color: #4ade80;">Approved on ${cr.reviewed_at ? new Date(cr.reviewed_at).toLocaleDateString() : ""}</div>`;
            } else if (cr.status === "REJECTED") {
              resolution = `<div style="font-size: 0.75rem; color: #f87171;" title="${escapeHtml(cr.rejection_reason || "")}">Rejected: ${escapeHtml(cr.rejection_reason || "No reason")}</div>`;
            }

            let actionBtn = "-";
            if (cr.status === "PENDING") {
              actionBtn = `<button class="btn btn-secondary btn-sm" onclick="handleCancelChangeRequest('${cr.request_id}')">Cancel</button>`;
            }

            return `
              <tr>
                <td><strong>${escapeHtml(cr.requested_name || "-")}</strong></td>
                <td><code>${escapeHtml(cr.requested_slug || "-")}</code></td>
                <td style="max-width: 200px; white-space: normal; font-size: 0.8rem;">${escapeHtml(cr.reason || "-")}</td>
                <td>${statusBadge}</td>
                <td style="font-size: 0.75rem;">${submittedAt}</td>
                <td>${resolution}</td>
                <td style="text-align: right;">${actionBtn}</td>
              </tr>
            `;
          })
          .join("");
      }
    } else {
      tbody.innerHTML = `<tr><td colspan="7" class="loading-cell error">${res.message || "Failed to load requests"}</td></tr>`;
    }
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="7" class="loading-cell error">${err.message}</td></tr>`;
  }
}

async function handleSaveAdminProfile(event) {
  event.preventDefault();
  const name = document.getElementById("self-profile-name").value.trim();
  const email = document.getElementById("self-profile-email").value.trim();
  const currentPassword = document.getElementById("self-profile-current-pwd").value;
  const newPassword = document.getElementById("self-profile-new-pwd").value;

  const btn = document.getElementById("btn-save-self-profile");
  if (btn) btn.disabled = true;

  try {
    const payload = { name, email };
    if (currentPassword) payload.current_password = currentPassword;
    if (newPassword) payload.new_password = newPassword;

    const res = await ApiClient.updateMyProfile(payload);
    if (res.success) {
      showToast("Profile updated successfully!", "success");
      // Clear password fields
      const curPwdEl = document.getElementById("self-profile-current-pwd");
      const newPwdEl = document.getElementById("self-profile-new-pwd");
      if (curPwdEl) curPwdEl.value = "";
      if (newPwdEl) newPwdEl.value = "";

      // If tokens returned (e.g. password changed and new tokens issued)
      if (res.data && res.data.access_token) {
        ApiClient.setTokens(res.data.access_token, res.data.refresh_token);
      }

      // Update stored account
      const currentAccount = ApiClient.getStoredAccount();
      if (currentAccount && res.data?.user) {
        currentAccount.name = res.data.user.name;
        currentAccount.email = res.data.user.email;
        ApiClient.setStoredAccount(currentAccount);
      }
      await loadDashboardContext();
    } else {
      showToast(res.message || "Failed to update profile", "danger");
    }
  } catch (err) {
    showToast(err.message || "Error updating profile", "danger");
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function handleSubmitChangeRequest(event) {
  event.preventDefault();
  const requestedName = document.getElementById("cr-req-name").value.trim();
  const requestedSlug = document.getElementById("cr-req-slug").value.trim();
  const reason = document.getElementById("cr-req-reason").value.trim();

  if (!requestedName && !requestedSlug) {
    showToast("Please provide either a requested name or requested slug", "warning");
    return;
  }
  if (!reason) {
    showToast("Business justification reason is required", "warning");
    return;
  }

  const btn = document.getElementById("btn-submit-cr");
  if (btn) btn.disabled = true;

  try {
    const payload = {
      requested_name: requestedName || undefined,
      requested_slug: requestedSlug || undefined,
      reason
    };
    const res = await ApiClient.submitChangeRequest(payload);
    if (res.success) {
      showToast("Organization change request submitted for review!", "success");
      document.getElementById("form-submit-change-request").reset();
      await loadOrgChangeRequests();
    } else {
      showToast(res.message || "Failed to submit change request", "danger");
    }
  } catch (err) {
    showToast(err.message || "Error submitting change request", "danger");
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function handleCancelChangeRequest(requestId) {
  if (!confirm("Are you sure you want to cancel this pending change request?")) return;
  try {
    const res = await ApiClient.cancelChangeRequest(requestId);
    if (res.success) {
      showToast("Change request cancelled", "success");
      await loadOrgChangeRequests();
    } else {
      showToast(res.message || "Failed to cancel change request", "danger");
    }
  } catch (err) {
    showToast(err.message || "Error cancelling change request", "danger");
  }
}

// ----------------------------------------------------
// PLATFORM CHANGE REQUESTS OPERATIONS (Phase 5 Task 5.3)
// ----------------------------------------------------
let platformCrCurrentPage = 1;
let platformCrLimit = 20;
let platformCrStatus = "PENDING";
let platformCrSearch = "";
let platformCrDebounceTimer = null;
let currentRejectRequestId = null;

async function loadPlatformChangeRequests(page = platformCrCurrentPage) {
  platformCrCurrentPage = page;
  const tbody = document.getElementById("platform-cr-table-body");
  if (!tbody) return;
  tbody.innerHTML = '<tr><td colspan="7" class="loading-cell">Loading change requests...</td></tr>';

  try {
    const filters = {
      status: platformCrStatus,
      search: platformCrSearch
    };
    const res = await ApiClient.listPlatformChangeRequests(page, platformCrLimit, filters);
    if (res.success && res.data) {
      const items = res.data;
      if (items.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="loading-cell">No change requests found.</td></tr>';
      } else {
        tbody.innerHTML = items
          .map((cr) => {
            let statusBadge = `<span class="badge badge-warning">${escapeHtml(cr.status)}</span>`;
            if (cr.status === "APPROVED") statusBadge = `<span class="badge badge-active">APPROVED</span>`;
            else if (cr.status === "REJECTED") statusBadge = `<span class="badge badge-inactive">REJECTED</span>`;
            else if (cr.status === "CANCELLED") statusBadge = `<span class="badge badge-secondary">CANCELLED</span>`;

            const submittedAt = cr.created_at ? new Date(cr.created_at).toLocaleDateString() : "-";

            let requestedChanges = [];
            if (cr.requested_name) requestedChanges.push(`<div>Name: <strong>${escapeHtml(cr.requested_name)}</strong></div>`);
            if (cr.requested_slug) requestedChanges.push(`<div>Slug: <code>${escapeHtml(cr.requested_slug)}</code></div>`);
            const requestedHtml = requestedChanges.length > 0 ? requestedChanges.join("") : "<em>No identity changes</em>";

            let actionsHtml = "-";
            if (cr.status === "PENDING") {
              actionsHtml = `
                <div style="display: inline-flex; gap: 6px; justify-content: flex-end;">
                  <button class="btn btn-primary btn-sm" onclick="handleApproveChangeRequest('${cr.request_id}', '${escapeHtml(cr.organization_name || "Organization")}')">Approve</button>
                  <button class="btn btn-danger btn-sm" onclick="openRejectChangeRequestModal('${cr.request_id}', '${escapeHtml(cr.organization_name || "Organization")}')">Reject</button>
                </div>
              `;
            } else if (cr.status === "APPROVED") {
              actionsHtml = `<span style="font-size: 0.75rem; color: #4ade80;">Approved</span>`;
            } else if (cr.status === "REJECTED") {
              actionsHtml = `<span style="font-size: 0.75rem; color: #f87171;" title="${escapeHtml(cr.rejection_reason || "")}">Rejected</span>`;
            }

            return `
              <tr>
                <td>
                  <div style="font-weight: 600; color: var(--text-primary);">${escapeHtml(cr.organization_name || "-")}</div>
                  <div style="font-size: 0.75rem; color: var(--text-muted);">${escapeHtml(cr.requester_name || "-")} (${escapeHtml(cr.requester_email || "-")})</div>
                </td>
                <td>
                  <div>${escapeHtml(cr.current_name || "-")}</div>
                  <div style="font-family: var(--font-mono); font-size: 0.75rem; color: #38bdf8;">${escapeHtml(cr.current_slug || "-")}</div>
                </td>
                <td>${requestedHtml}</td>
                <td style="max-width: 220px; white-space: normal; font-size: 0.8rem;">${escapeHtml(cr.reason || "-")}</td>
                <td>${statusBadge}</td>
                <td style="font-size: 0.75rem;">${submittedAt}</td>
                <td style="text-align: right;">${actionsHtml}</td>
              </tr>
            `;
          })
          .join("");
      }

      // Pagination
      const pagination = res.pagination || { total: res.total_count || 0, page: 1, limit: platformCrLimit, total_pages: 1 };
      const total = pagination.total || 0;
      const totalPages = pagination.total_pages || 1;
      const start = total === 0 ? 0 : (page - 1) * platformCrLimit + 1;
      const end = Math.min(page * platformCrLimit, total);

      const pagBar = document.getElementById("platform-cr-pagination");
      const infoEl = document.getElementById("platform-cr-pagination-info");
      const indicatorEl = document.getElementById("platform-cr-page-indicator");
      const prevBtn = document.getElementById("platform-cr-prev-btn");
      const nextBtn = document.getElementById("platform-cr-next-btn");

      if (pagBar) pagBar.style.display = total > 0 ? "flex" : "none";
      if (infoEl) infoEl.textContent = `Showing ${start} - ${end} of ${total} requests`;
      if (indicatorEl) indicatorEl.textContent = `Page ${page} of ${totalPages}`;
      if (prevBtn) prevBtn.disabled = page <= 1;
      if (nextBtn) nextBtn.disabled = page >= totalPages;
    } else {
      tbody.innerHTML = `<tr><td colspan="7" class="loading-cell error">${res.message || "Failed to load change requests"}</td></tr>`;
    }
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="7" class="loading-cell error">${err.message}</td></tr>`;
  }
}

function debounceFilterPlatformChangeRequests() {
  clearTimeout(platformCrDebounceTimer);
  platformCrDebounceTimer = setTimeout(() => {
    const input = document.getElementById("platform-cr-search");
    platformCrSearch = input ? input.value.trim() : "";
    loadPlatformChangeRequests(1);
  }, 250);
}

function handlePlatformCrStatusChange(val) {
  platformCrStatus = val;
  loadPlatformChangeRequests(1);
}

function handlePlatformCrPrevPage() {
  if (platformCrCurrentPage > 1) {
    loadPlatformChangeRequests(platformCrCurrentPage - 1);
  }
}

function handlePlatformCrNextPage() {
  loadPlatformChangeRequests(platformCrCurrentPage + 1);
}

async function handleApproveChangeRequest(requestId, orgName) {
  if (!confirm(`Are you sure you want to APPROVE the change request for "${orgName}"? This will immediately rebrand the organization and update its slug.`)) return;

  try {
    const res = await ApiClient.approveChangeRequest(requestId);
    if (res.success) {
      showToast(`Change request for "${orgName}" approved successfully!`, "success");
      loadPlatformChangeRequests();
    } else {
      showToast(res.message || "Failed to approve change request", "danger");
    }
  } catch (err) {
    showToast(err.message || "Error approving change request", "danger");
  }
}

function openRejectChangeRequestModal(requestId, orgName) {
  currentRejectRequestId = requestId;
  const nameEl = document.getElementById("reject-cr-org-name");
  if (nameEl) nameEl.textContent = orgName;
  const reasonEl = document.getElementById("reject-cr-reason");
  if (reasonEl) reasonEl.value = "";
  openModal("modal-reject-change-request");
}

async function executeRejectChangeRequest() {
  const reasonEl = document.getElementById("reject-cr-reason");
  const reason = reasonEl ? reasonEl.value.trim() : "";
  if (!reason) {
    showToast("Rejection reason is required", "warning");
    return;
  }

  const btn = document.getElementById("btn-confirm-reject-cr");
  if (btn) btn.disabled = true;

  try {
    const res = await ApiClient.rejectChangeRequest(currentRejectRequestId, reason);
    if (res.success) {
      showToast("Change request rejected", "success");
      closeModal("modal-reject-change-request");
      loadPlatformChangeRequests();
    } else {
      showToast(res.message || "Failed to reject change request", "danger");
    }
  } catch (err) {
    showToast(err.message || "Error rejecting change request", "danger");
  } finally {
    if (btn) btn.disabled = false;
  }
}

// ----------------------------------------------------
// PLATFORM ORGANIZATION DELETION (Phase 5 Task 5.3)
// ----------------------------------------------------
let currentDeleteOrgId = null;
let currentDeleteOrgSlug = null;

async function openDeleteOrgModal(orgId, name, slug) {
  currentDeleteOrgId = orgId;
  currentDeleteOrgSlug = slug;

  document.getElementById("delete-org-target-name").textContent = name;
  document.getElementById("delete-org-target-slug").textContent = slug;
  document.getElementById("delete-org-match-slug").textContent = slug;
  document.getElementById("delete-org-slug-input").value = "";
  document.getElementById("btn-confirm-delete-org").disabled = true;

  document.getElementById("delete-org-user-count").textContent = "...";
  document.getElementById("delete-org-app-count").textContent = "...";
  document.getElementById("delete-org-msg-count").textContent = "...";

  openModal("modal-delete-org");

  try {
    const res = await ApiClient.getOrgDeletionSummary(orgId);
    if (res.success && res.data) {
      document.getElementById("delete-org-user-count").textContent = res.data.users_count !== undefined ? res.data.users_count : 0;
      document.getElementById("delete-org-app-count").textContent = res.data.applications_count !== undefined ? res.data.applications_count : 0;
      document.getElementById("delete-org-msg-count").textContent = res.data.messages_count !== undefined ? res.data.messages_count : 0;
    }
  } catch (err) {
    console.error("Failed to load org deletion summary", err);
  }
}

function checkDeleteOrgSlugMatch() {
  const inputVal = document.getElementById("delete-org-slug-input")?.value?.trim();
  const btn = document.getElementById("btn-confirm-delete-org");
  if (btn) {
    btn.disabled = inputVal !== currentDeleteOrgSlug;
  }
}

async function executeDeleteOrganization() {
  const inputVal = document.getElementById("delete-org-slug-input")?.value?.trim();
  if (inputVal !== currentDeleteOrgSlug) {
    showToast("Typed slug does not match the organization slug", "warning");
    return;
  }

  const btn = document.getElementById("btn-confirm-delete-org");
  if (btn) btn.disabled = true;

  try {
    const res = await ApiClient.deleteOrganization(currentDeleteOrgId, inputVal);
    if (res.success) {
      showToast("Organization deleted (soft-deleted and cascaded) successfully!", "success");
      closeModal("modal-delete-org");
      await loadOrganizations();
    } else {
      showToast(res.message || "Failed to delete organization", "danger");
      if (btn) btn.disabled = false;
    }
  } catch (err) {
    showToast(err.message || "Error deleting organization", "danger");
    if (btn) btn.disabled = false;
  }
}


// 6. User Deactivation Handler
function handleDeactivateUser(userId, userName) {
  showConfirmModal({
    title: "Deactivate Member",
    message: `Are you sure you want to deactivate member "${userName}"? They will immediately lose access to this organization's dashboard and API tokens.`,
    confirmText: "Deactivate User",
    confirmClass: "btn-danger",
    onConfirm: async () => {
      try {
        const res = await ApiClient.deactivateUser(userId);
        if (res.success) {
          showToast(`User "${userName}" has been deactivated.`, "success");
          loadOrgUsers();
        } else {
          showToast(res.message || "Failed to deactivate user", "danger");
        }
      } catch (err) {
        showToast(err.message, "danger");
      }
    }
  });
}

// 7. Generic Confirmation Modal
function showConfirmModal({ title, message, confirmText = "Confirm", confirmClass = "btn-danger", onConfirm }) {
  document.getElementById("confirm-modal-title").textContent = title || "Confirm Action";
  document.getElementById("confirm-modal-message").textContent = message || "Are you sure you want to proceed?";
  
  const submitBtn = document.getElementById("btn-confirm-action-submit");
  submitBtn.textContent = confirmText;
  submitBtn.className = `btn ${confirmClass}`;
  
  submitBtn.onclick = async () => {
    closeModal("modal-confirm-action");
    if (typeof onConfirm === "function") {
      await onConfirm();
    }
  };

  openModal("modal-confirm-action");
}

// ----------------------------------------------------
// EMAIL TEMPLATES OPERATIONS (Phase 3 Task 2)
// ----------------------------------------------------
async function loadOrgTemplates() {
  const tbody = document.getElementById("templates-table-body");
  if (!tbody) return;
  tbody.innerHTML = '<tr><td colspan="7" class="loading-cell">Loading email templates...</td></tr>';

  const category = document.getElementById("tpl-filter-category")?.value || "";
  const status = document.getElementById("tpl-filter-status")?.value || "";

  try {
    const res = await ApiClient.listTemplates(1, 50, { category, status });
    if (res.success && res.items) {
      if (res.items.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="loading-cell">No email templates found. Click "+ New Template" to create one.</td></tr>';
        return;
      }

      tbody.innerHTML = res.items.map((t) => {
        const statusBadge = `<span class="badge badge-${t.status.toLowerCase()}">${t.status}</span>`;
        const vars = (t.variables || []).map((v) => `<span class="var-tag">${escapeHtml(v.name)}</span>`).join("");

        let actions = `
          <button class="btn btn-secondary btn-sm" onclick="openTemplatePreview('${t.template_id}')">Preview</button>
          <button class="btn btn-secondary btn-sm" onclick="duplicateTemplate('${t.template_id}')">Duplicate</button>
        `;

        if (t.status === "DRAFT") {
          actions = `
            <button class="btn btn-secondary btn-sm" onclick="editTemplate('${t.template_id}')">Edit</button>
            <button class="btn btn-primary btn-sm" onclick="publishTemplate('${t.template_id}')">Publish</button>
            ${actions}
            <button class="btn btn-outline btn-sm" onclick="deleteTemplate('${t.template_id}')">Delete</button>
          `;
        } else if (t.status === "ACTIVE") {
          actions = `
            <button class="btn btn-secondary btn-sm" onclick="editTemplate('${t.template_id}')">Edit</button>
            <button class="btn btn-secondary btn-sm" onclick="useTemplateInComposer('${t.template_id}')">Use in Composer</button>
            <button class="btn btn-secondary btn-sm" onclick="viewTemplateVersions('${t.template_id}')">Versions</button>
            ${actions}
            <button class="btn btn-outline btn-sm" onclick="archiveTemplate('${t.template_id}')">Archive</button>
          `;
        } else if (t.status === "ARCHIVED") {
          actions = `
            <button class="btn btn-secondary btn-sm" onclick="viewTemplateVersions('${t.template_id}')">Versions</button>
            ${actions}
          `;
        }

        return `
          <tr>
            <td>
              <strong>${escapeHtml(t.name)}</strong>
              ${t.description ? `<br><small style="color:var(--text-secondary);">${escapeHtml(t.description)}</small>` : ""}
            </td>
            <td><span class="var-tag">${escapeHtml(t.category || "general")}</span></td>
            <td><code>${escapeHtml(t.subject)}</code></td>
            <td><strong>v${t.version || 1}</strong></td>
            <td>${statusBadge}</td>
            <td>${vars || '<span style="color:var(--text-secondary); font-size:0.75rem;">None</span>'}</td>
            <td style="white-space: nowrap;">${actions}</td>
          </tr>
        `;
      }).join("");
    } else {
      tbody.innerHTML = `<tr><td colspan="7" class="loading-cell danger">${res.message || "Failed to load templates"}</td></tr>`;
    }
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="7" class="loading-cell danger">${err.message}</td></tr>`;
  }
}

// -----------------------------------------------------------------------------
// EMAIL TEMPLATE STUDIO (Phase 5 Task 5.6)
// -----------------------------------------------------------------------------

let studioIsDirty = false;
let studioDeclaredVariables = [];
let studioPreviewDebounceTimer = null;
let studioCurrentPreviewMode = "html";

function markTemplateDirty() {
  studioIsDirty = true;
  const statusEl = document.getElementById("tpl-save-status");
  if (statusEl) {
    statusEl.innerHTML = '<span style="color: #fbbf24;">● Unsaved changes</span> (Esc will prompt before discard)';
  }
}

function clearTemplateDirty() {
  studioIsDirty = false;
  const statusEl = document.getElementById("tpl-save-status");
  if (statusEl) {
    statusEl.textContent = "All changes saved";
  }
}

function switchStudioEditorTab(tab) {
  const htmlBtn = document.getElementById("btn-tab-html");
  const cssBtn = document.getElementById("btn-tab-css");
  const htmlArea = document.getElementById("tpl-html-body");
  const cssArea = document.getElementById("tpl-css");

  if (tab === "css") {
    htmlBtn.classList.remove("active");
    cssBtn.classList.add("active");
    htmlArea.style.display = "none";
    cssArea.style.display = "block";
  } else {
    cssBtn.classList.remove("active");
    htmlBtn.classList.add("active");
    cssArea.style.display = "none";
    htmlArea.style.display = "block";
  }
}

function switchStudioPreviewMode(mode) {
  studioCurrentPreviewMode = mode;
  const htmlBtn = document.getElementById("btn-preview-html");
  const textBtn = document.getElementById("btn-preview-text");
  const iframe = document.getElementById("tpl-preview-iframe");
  const textPre = document.getElementById("tpl-preview-text");

  if (mode === "text") {
    htmlBtn.classList.remove("active");
    textBtn.classList.add("active");
    iframe.style.display = "none";
    textPre.style.display = "block";
  } else {
    textBtn.classList.remove("active");
    htmlBtn.classList.add("active");
    textPre.style.display = "none";
    iframe.style.display = "block";
  }
}

function setStudioPreviewViewport(width) {
  const btn600 = document.getElementById("btn-viewport-600");
  const btn320 = document.getElementById("btn-viewport-320");
  const iframe = document.getElementById("tpl-preview-iframe");

  if (width === "320") {
    btn600.classList.remove("active");
    btn320.classList.add("active");
    iframe.style.width = "320px";
  } else {
    btn320.classList.remove("active");
    btn600.classList.add("active");
    iframe.style.width = "600px";
  }
}

function onTemplateContentChanged() {
  markTemplateDirty();
  updateStudioCharCounts();
  syncStudioDetectedVariables();

  // Debounce live preview update (350ms)
  if (studioPreviewDebounceTimer) clearTimeout(studioPreviewDebounceTimer);
  studioPreviewDebounceTimer = setTimeout(() => {
    updateStudioLivePreview();
  }, 350);
}

function updateStudioCharCounts() {
  const htmlVal = document.getElementById("tpl-html-body")?.value || "";
  const cssVal = document.getElementById("tpl-css")?.value || "";
  const htmlKb = (new Blob([htmlVal]).size / 1024).toFixed(1);
  const cssKb = (new Blob([cssVal]).size / 1024).toFixed(1);

  const countEl = document.getElementById("tpl-char-count");
  if (countEl) {
    countEl.textContent = `HTML: ${htmlKb} KB / 200 KB | CSS: ${cssKb} KB / 50 KB`;
    if (parseFloat(htmlKb) > 200 || parseFloat(cssKb) > 50) {
      countEl.style.color = "#ef4444";
    } else {
      countEl.style.color = "var(--text-muted)";
    }
  }
}

function syncStudioDetectedVariables() {
  const subjectVal = document.getElementById("tpl-subject")?.value || "";
  const htmlVal = document.getElementById("tpl-html-body")?.value || "";
  const cssVal = document.getElementById("tpl-css")?.value || "";
  const fullText = subjectVal + " " + htmlVal + " " + cssVal;

  const varRegex = /\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)(?:\s*\|[^\}]+)?\s*\}\}/g;
  const detectedNames = new Set();
  let m;
  while ((m = varRegex.exec(fullText)) !== null) {
    detectedNames.add(m[1]);
  }

  // Update existing declared variables and add new detected ones
  const existingMap = new Map();
  studioDeclaredVariables.forEach((v) => existingMap.set(v.name, v));

  const updatedList = [];
  detectedNames.forEach((name) => {
    if (existingMap.has(name)) {
      updatedList.push(existingMap.get(name));
      existingMap.delete(name);
    } else {
      // Auto-inferred defaults based on name convention
      let inferredType = "text";
      if (name.includes("url") || name.includes("link")) inferredType = "url";
      if (name.includes("color")) inferredType = "color";
      if (name === "body_html") inferredType = "rich";

      let sampleVal = `Sample ${name}`;
      if (inferredType === "url") sampleVal = "https://example.com/click";
      if (inferredType === "color") sampleVal = "#2563eb";

      updatedList.push({
        name,
        type: inferredType,
        required: true,
        sample_value: sampleVal,
        max_length: 1000
      });
    }
  });

  // Keep any manually added custom variables that aren't yet referenced in text
  existingMap.forEach((v) => {
    if (v._manual) {
      updatedList.push(v);
    }
  });

  studioDeclaredVariables = updatedList;
  renderStudioVariablesPanel();
}

function renderStudioVariablesPanel() {
  const container = document.getElementById("tpl-variables-list");
  const countBadge = document.getElementById("tpl-var-count-badge");
  if (!container) return;

  if (countBadge) {
    countBadge.textContent = `${studioDeclaredVariables.length} variable${studioDeclaredVariables.length === 1 ? "" : "s"}`;
  }

  if (studioDeclaredVariables.length === 0) {
    container.innerHTML = '<em style="color: var(--text-muted); padding: 8px; display: block;">No variables detected yet. Type {{ variable_name }} in subject, HTML, or CSS.</em>';
    return;
  }

  container.innerHTML = studioDeclaredVariables.map((v, idx) => `
    <div style="display: grid; grid-template-columns: 140px 85px 75px 1fr 24px; gap: 8px; align-items: center; padding: 4px 0; border-bottom: 1px solid rgba(255,255,255,0.05);">
      <div>
        <strong style="color: var(--accent-cyan); font-family: var(--font-mono); font-size: 0.775rem;">{{ ${escapeHtml(v.name)} }}</strong>
      </div>
      <div>
        <select onchange="updateStudioVarProp(${idx}, 'type', this.value)" style="width: 100%; padding: 2px 4px; font-size: 0.725rem;">
          <option value="text" ${v.type === "text" ? "selected" : ""}>Text</option>
          <option value="url" ${v.type === "url" ? "selected" : ""}>HTTPS URL</option>
          <option value="color" ${v.type === "color" ? "selected" : ""}>Hex Color</option>
          <option value="rich" ${v.type === "rich" ? "selected" : ""}>Rich HTML</option>
        </select>
      </div>
      <div style="text-align: center;">
        <label style="font-size: 0.7rem; cursor: pointer; display: flex; align-items: center; gap: 3px; justify-content: center; margin: 0;">
          <input type="checkbox" ${v.required ? "checked" : ""} onchange="updateStudioVarProp(${idx}, 'required', this.checked)" />
          Req
        </label>
      </div>
      <div>
        <input type="text" value="${escapeHtml(v.sample_value || "")}" placeholder="Preview sample value..." style="width: 100%; padding: 2px 6px; font-size: 0.75rem;" oninput="updateStudioVarProp(${idx}, 'sample_value', this.value, true)" />
      </div>
      <div>
        <button type="button" class="btn btn-danger btn-xs" style="padding: 1px 5px; font-size: 0.7rem;" onclick="removeStudioVariable(${idx})" title="Remove Variable">&times;</button>
      </div>
    </div>
  `).join("");
}

function updateStudioVarProp(idx, prop, value, debouncePreview = false) {
  if (studioDeclaredVariables[idx]) {
    studioDeclaredVariables[idx][prop] = value;
    markTemplateDirty();
    if (debouncePreview) {
      if (studioPreviewDebounceTimer) clearTimeout(studioPreviewDebounceTimer);
      studioPreviewDebounceTimer = setTimeout(() => updateStudioLivePreview(), 300);
    } else {
      updateStudioLivePreview();
    }
  }
}

function addCustomStudioVariable() {
  const name = prompt("Enter new variable name (alphanumeric and underscore):");
  if (!name) return;
  const clean = name.trim();
  if (!/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(clean)) {
    showToast("Invalid variable name. Must start with letter/underscore and contain letters/numbers/underscores only.", "danger");
    return;
  }
  if (studioDeclaredVariables.some((v) => v.name === clean)) {
    showToast(`Variable '{{ ${clean} }}' already exists`, "warning");
    return;
  }
  studioDeclaredVariables.push({
    name: clean,
    type: "text",
    required: true,
    sample_value: `Sample ${clean}`,
    max_length: 1000,
    _manual: true
  });
  markTemplateDirty();
  renderStudioVariablesPanel();
  updateStudioLivePreview();
}

function removeStudioVariable(idx) {
  studioDeclaredVariables.splice(idx, 1);
  markTemplateDirty();
  renderStudioVariablesPanel();
  updateStudioLivePreview();
}

async function insertStarterLayout() {
  const htmlArea = document.getElementById("tpl-html-body");
  const cssArea = document.getElementById("tpl-css");
  if (htmlArea.value.trim() && !confirm("Replace current editor contents with the responsive 600px transactional starter layout?")) {
    return;
  }

  try {
    const res = await ApiClient.getStarterLayout();
    if (res.success && res.data) {
      document.getElementById("tpl-subject").value = res.data.subject || "Welcome to {{ brand_name }}!";
      htmlArea.value = res.data.html;
      cssArea.value = res.data.css;
      studioDeclaredVariables = res.data.variables || [];
      markTemplateDirty();
      updateStudioCharCounts();
      renderStudioVariablesPanel();
      await updateStudioLivePreview();
      showToast("Responsive 600px starter layout loaded successfully!", "success");
    }
  } catch (err) {
    showToast("Could not load starter layout: " + err.message, "danger");
  }
}

async function updateStudioLivePreview() {
  const subject = document.getElementById("tpl-subject")?.value || "";
  const html_body = document.getElementById("tpl-html-body")?.value || "";
  const css = document.getElementById("tpl-css")?.value || "";

  // Collect sample data
  const sample_data = {};
  studioDeclaredVariables.forEach((v) => {
    sample_data[v.name] = v.sample_value !== undefined ? v.sample_value : (v.default !== undefined ? v.default : `[${v.name}]`);
  });

  const payload = {
    subject,
    html_body,
    css,
    variables: studioDeclaredVariables,
    sample_data
  };

  const iframe = document.getElementById("tpl-preview-iframe");
  const textPre = document.getElementById("tpl-preview-text");
  const subjectDisplay = document.getElementById("tpl-rendered-subject-display");
  const warningsBox = document.getElementById("tpl-compat-warnings-box");

  try {
    const res = await ApiClient.previewTemplateDraft(payload);
    if (res.success && res.data) {
      if (subjectDisplay) subjectDisplay.textContent = res.data.rendered_subject || "-";
      if (iframe) iframe.srcdoc = res.data.rendered_html || "<p style='color:#999;padding:20px;'>No rendered content</p>";
      if (textPre) textPre.textContent = res.data.rendered_plain_text || "No plain text content";

      // Render compatibility warnings
      const warnings = res.data.compatibility_warnings || [];
      if (warningsBox) {
        if (warnings.length === 0) {
          warningsBox.innerHTML = '<span style="color: #4ade80;">✓ Email client compatibility: No warnings detected (Gmail & Outlook compatible).</span>';
        } else {
          warningsBox.innerHTML = `
            <div style="color: #fbbf24; font-weight: 600; margin-bottom: 2px;">⚠️ Compatibility Warnings (${warnings.length}):</div>
            <ul style="margin: 0; padding-left: 16px; color: var(--text-secondary); line-height: 1.3;">
              ${warnings.map((w) => `<li>${escapeHtml(w)}</li>`).join("")}
            </ul>
          `;
        }
      }
    }
  } catch (err) {
    // If preview fails on syntax/security error, display message gracefully in preview pane
    if (iframe) {
      iframe.srcdoc = `<div style="color:#ef4444;font-family:sans-serif;padding:16px;"><strong>Preview Error:</strong> ${escapeHtml(err.message)}</div>`;
    }
  }
}

async function runStudioValidation() {
  const alertEl = document.getElementById("tpl-editor-error-alert");
  const name = document.getElementById("tpl-name")?.value.trim() || "";
  const subject = document.getElementById("tpl-subject")?.value.trim() || "";
  const html_body = document.getElementById("tpl-html-body")?.value || "";
  const css = document.getElementById("tpl-css")?.value || "";

  const payload = {
    name,
    subject,
    html_body,
    css,
    variables: studioDeclaredVariables
  };

  try {
    const res = await ApiClient.validateTemplate(payload);
    if (alertEl) {
      alertEl.style.display = "block";
      if (res.success && res.data.valid) {
        alertEl.style.background = "rgba(74, 222, 128, 0.12)";
        alertEl.style.border = "1px solid rgba(74, 222, 128, 0.3)";
        alertEl.style.color = "#4ade80";
        alertEl.innerHTML = `
          <strong>✓ Valid Template:</strong> Passed all security checks and syntax validation.
          Found ${res.data.detected_variables.length} variable(s), ${res.data.compatibility_warnings.length} compatibility note(s).
        `;
      } else {
        alertEl.style.background = "rgba(239, 68, 68, 0.12)";
        alertEl.style.border = "1px solid rgba(239, 68, 68, 0.3)";
        alertEl.style.color = "#f87171";

        const errItems = [];
        (res.data.security_findings || []).forEach((f) => errItems.push(`Security: ${f}`));
        (res.data.syntax_errors || []).forEach((e) => errItems.push(`Syntax: ${e}`));
        if (res.data.undeclared_variables && res.data.undeclared_variables.length > 0) {
          errItems.push(`Undeclared Variables: {{ ${res.data.undeclared_variables.join(" }}, {{ ")} }}`);
        }

        alertEl.innerHTML = `
          <strong>Validation Issues Found:</strong>
          <ul style="margin: 4px 0 0 16px; padding: 0;">
            ${errItems.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
          </ul>
        `;
      }
    }
  } catch (err) {
    if (alertEl) {
      alertEl.style.display = "block";
      alertEl.style.background = "rgba(239, 68, 68, 0.12)";
      alertEl.style.border = "1px solid rgba(239, 68, 68, 0.3)";
      alertEl.style.color = "#f87171";
      alertEl.textContent = `Validation failed: ${err.message}`;
    }
  }
}

async function submitTemplateStudio(publish = false) {
  const alertEl = document.getElementById("tpl-editor-error-alert");
  if (alertEl) alertEl.style.display = "none";

  const editId = document.getElementById("tpl-edit-id").value;
  const name = document.getElementById("tpl-name").value.trim();
  const category = document.getElementById("tpl-category").value;
  const description = document.getElementById("tpl-description").value.trim();
  const subject = document.getElementById("tpl-subject").value.trim();
  const html_body = document.getElementById("tpl-html-body").value;
  const css = document.getElementById("tpl-css").value;
  const strict_variables = document.getElementById("tpl-strict-variables").checked;

  if (!name || name.length < 2 || name.length > 80) {
    showStudioError("Template name is required and must be between 2 and 80 characters.");
    return;
  }

  if (!subject) {
    showStudioError("Email template requires a non-empty subject line.");
    return;
  }

  const payload = {
    name,
    category,
    description,
    channel: "email",
    subject,
    html_body,
    css,
    variables: studioDeclaredVariables,
    strict_variables
  };

  try {
    let res;
    if (editId) {
      res = await ApiClient.updateTemplate(editId, payload);
      if (res.success && publish) {
        res = await ApiClient.publishTemplate(editId);
      }
    } else {
      res = await ApiClient.createTemplate(payload);
      if (res.success && publish && res.data?.template_id) {
        res = await ApiClient.publishTemplate(res.data.template_id);
      }
    }

    if (res.success) {
      clearTemplateDirty();
      closeModal("modal-template-editor");
      showToast(publish ? "Template saved and published successfully!" : "Template draft saved successfully!", "success");
      await loadOrgTemplates();
    } else {
      showStudioError(res.message || "Failed to save template");
    }
  } catch (err) {
    showStudioError(err.message || "An error occurred while saving the template");
  }
}

function showStudioError(msg) {
  const alertEl = document.getElementById("tpl-editor-error-alert");
  if (alertEl) {
    alertEl.style.display = "block";
    alertEl.style.background = "rgba(239, 68, 68, 0.12)";
    alertEl.style.border = "1px solid rgba(239, 68, 68, 0.3)";
    alertEl.style.color = "#f87171";
    alertEl.textContent = msg;
  }
  showToast(msg, "danger");
}

function openCreateTemplateModal() {
  document.getElementById("tpl-modal-title").textContent = "Email Template Studio";
  document.getElementById("tpl-modal-badge").textContent = "NEW DRAFT";
  document.getElementById("tpl-edit-id").value = "";
  document.getElementById("tpl-name").value = "";
  document.getElementById("tpl-category").value = "transactional";
  document.getElementById("tpl-description").value = "";
  document.getElementById("tpl-subject").value = "";
  document.getElementById("tpl-html-body").value = "";
  document.getElementById("tpl-css").value = "";
  document.getElementById("tpl-strict-variables").checked = false;

  const alertEl = document.getElementById("tpl-editor-error-alert");
  if (alertEl) alertEl.style.display = "none";

  studioDeclaredVariables = [];
  clearTemplateDirty();
  switchStudioEditorTab("html");
  switchStudioPreviewMode("html");
  setStudioPreviewViewport("600");
  updateStudioCharCounts();
  renderStudioVariablesPanel();

  const iframe = document.getElementById("tpl-preview-iframe");
  if (iframe) iframe.srcdoc = "<div style='color:#94a3b8;font-family:sans-serif;padding:30px;text-align:center;'>Start typing HTML or click 'Start from Starter Layout' to begin.</div>";

  openModal("modal-template-editor");
}

async function editTemplate(templateId) {
  try {
    const res = await ApiClient.getTemplate(templateId);
    if (!res.success || !res.data) {
      showToast(res.message || "Failed to load template", "danger");
      return;
    }

    const t = res.data;
    document.getElementById("tpl-modal-title").textContent = `Email Template Studio — ${t.name}`;
    document.getElementById("tpl-modal-badge").textContent = `${t.status} v${t.version}`;
    document.getElementById("tpl-edit-id").value = t.template_id;
    document.getElementById("tpl-name").value = t.name || "";
    document.getElementById("tpl-category").value = t.category || "general";
    document.getElementById("tpl-description").value = t.description || "";
    document.getElementById("tpl-subject").value = t.subject || "";
    document.getElementById("tpl-html-body").value = t.html_body || "";
    document.getElementById("tpl-css").value = t.css || "";
    document.getElementById("tpl-strict-variables").checked = Boolean(t.strict_variables);

    const alertEl = document.getElementById("tpl-editor-error-alert");
    if (alertEl) alertEl.style.display = "none";

    studioDeclaredVariables = t.variables || [];
    clearTemplateDirty();
    switchStudioEditorTab("html");
    switchStudioPreviewMode("html");
    setStudioPreviewViewport("600");
    updateStudioCharCounts();
    renderStudioVariablesPanel();

    openModal("modal-template-editor");
    await updateStudioLivePreview();
  } catch (err) {
    showToast(err.message, "danger");
  }
}

function closeTemplateStudioModal() {
  if (studioIsDirty) {
    if (!confirm("You have unsaved changes in this template. Are you sure you want to discard them?")) {
      return;
    }
  }
  clearTemplateDirty();
  closeModal("modal-template-editor");
}

function useTemplateInComposer(templateId) {
  switchTab("tab-org-messages");
  switchMessageSubtab("composer");
  const chanSelect = document.getElementById("msg-channel");
  if (chanSelect) chanSelect.value = "email";
  handleChannelChange("email");

  const tplSelect = document.getElementById("msg-template-select");
  if (tplSelect) {
    tplSelect.value = templateId;
    handleTemplateSelect(templateId);
  }
  showToast("Template loaded into Message Composer!", "success");
}

// Global keyboard accessibility: Esc key prompts if dirty in Template Studio
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    const studioModal = document.getElementById("modal-template-editor");
    if (studioModal && studioModal.classList.contains("active")) {
      e.preventDefault();
      closeTemplateStudioModal();
    }
  }
});

async function openTemplatePreview(templateId) {
  try {
    const res = await ApiClient.getTemplate(templateId);
    if (!res.success || !res.data) {
      showToast(res.message || "Failed to load template", "danger");
      return;
    }

    const t = res.data;
    document.getElementById("tpl-preview-id").value = templateId;
    document.getElementById("tpl-preview-subject").textContent = t.subject;

    // Generate sample data object from defined variables
    const sampleDataObj = {};
    (t.variables || []).forEach((v) => {
      sampleDataObj[v.name] = v.sample_value !== undefined ? v.sample_value : (v.default !== undefined ? v.default : `[${v.name}]`);
    });
    document.getElementById("tpl-preview-sample-json").value = JSON.stringify(sampleDataObj, null, 2);

    openModal("modal-template-preview");
    await executeLivePreview();
  } catch (err) {
    showToast(err.message, "danger");
  }
}

async function executeLivePreview() {
  const templateId = document.getElementById("tpl-preview-id").value;
  if (!templateId) return;

  const rawJson = document.getElementById("tpl-preview-sample-json").value.trim();
  let sampleData = {};
  if (rawJson) {
    try {
      sampleData = JSON.parse(rawJson);
    } catch (err) {
      showToast("Invalid JSON in sample variables", "danger");
      return;
    }
  }

  const missingAlert = document.getElementById("tpl-preview-missing-alert");
  const htmlBox = document.getElementById("tpl-preview-html-box");
  const textBox = document.getElementById("tpl-preview-text-box");
  const subjectDisplay = document.getElementById("tpl-preview-subject");

  try {
    const res = await ApiClient.previewTemplate(templateId, sampleData);
    if (res.success && res.data) {
      subjectDisplay.textContent = res.data.rendered_subject || "-";
      htmlBox.innerHTML = res.data.rendered_html || "<em style='color:#999'>No HTML body defined</em>";
      textBox.textContent = res.data.rendered_plain_text || "No plain text body defined";

      if (res.data.missing_variables && res.data.missing_variables.length > 0) {
        missingAlert.style.display = "block";
        missingAlert.textContent = `Warning: Missing required variables: ${res.data.missing_variables.join(", ")}`;
      } else {
        missingAlert.style.display = "none";
      }
    } else {
      showToast(res.message || "Failed to render preview", "danger");
    }
  } catch (err) {
    showToast(err.message, "danger");
  }
}

async function publishTemplate(templateId) {
  try {
    const res = await ApiClient.publishTemplate(templateId);
    if (res.success) {
      showToast("Template published successfully! Ready for message dispatch.", "success");
      await loadOrgTemplates();
    } else {
      showToast(res.message || "Could not publish template", "danger");
    }
  } catch (err) {
    showToast(err.message, "danger");
  }
}

async function archiveTemplate(templateId) {
  if (!confirm("Are you sure you want to archive this template? Active messages referencing this template may be affected.")) return;
  try {
    const res = await ApiClient.archiveTemplate(templateId);
    if (res.success) {
      showToast("Template archived successfully", "success");
      await loadOrgTemplates();
    } else {
      showToast(res.message || "Could not archive template", "danger");
    }
  } catch (err) {
    showToast(err.message, "danger");
  }
}

async function duplicateTemplate(templateId) {
  try {
    const res = await ApiClient.duplicateTemplate(templateId);
    if (res.success) {
      showToast("Template cloned as a new DRAFT!", "success");
      await loadOrgTemplates();
    } else {
      showToast(res.message || "Could not duplicate template", "danger");
    }
  } catch (err) {
    showToast(err.message, "danger");
  }
}

async function deleteTemplate(templateId) {
  if (!confirm("Permanently delete this template? This action cannot be undone.")) return;
  try {
    const res = await ApiClient.deleteTemplate(templateId);
    if (res.success) {
      showToast("Template deleted successfully", "success");
      await loadOrgTemplates();
    } else {
      showToast(res.message || "Could not delete template", "danger");
    }
  } catch (err) {
    showToast(err.message, "danger");
  }
}

async function viewTemplateVersions(templateId) {
  document.getElementById("tpl-history-template-id").value = templateId;
  const tbody = document.getElementById("tpl-versions-table-body");
  const snapshotView = document.getElementById("tpl-version-snapshot-view");
  tbody.innerHTML = '<tr><td colspan="5" class="loading-cell">Loading versions...</td></tr>';
  snapshotView.textContent = "Select a version above to view snapshot details...";

  openModal("modal-template-versions");

  try {
    const res = await ApiClient.getTemplateVersions(templateId);
    if (res.success && res.versions) {
      tbody.innerHTML = res.versions.map((v) => {
        const isCurrent = v.is_current ? '<span class="badge badge-active">CURRENT</span>' : '<span class="badge badge-archived">ARCHIVED</span>';
        const ts = v.archived_at || v.updated_at || "-";
        const author = v.archived_by || v.updated_by || "-";

        return `
          <tr>
            <td><strong>v${v.version}</strong></td>
            <td>${isCurrent}</td>
            <td>${escapeHtml(author)}</td>
            <td><small>${escapeHtml(ts)}</small></td>
            <td>
              <button class="btn btn-secondary btn-sm" onclick="viewHistoricalSnapshot('${templateId}', ${v.version})">View</button>
            </td>
          </tr>
        `;
      }).join("");
    } else {
      tbody.innerHTML = `<tr><td colspan="5" class="loading-cell danger">${res.message || "Failed to load versions"}</td></tr>`;
    }
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="5" class="loading-cell danger">${err.message}</td></tr>`;
  }
}

async function viewHistoricalSnapshot(templateId, version) {
  const snapshotView = document.getElementById("tpl-version-snapshot-view");
  snapshotView.textContent = "Loading version snapshot...";

  try {
    const res = await ApiClient.getTemplateVersion(templateId, version);
    if (res.success && res.data) {
      snapshotView.textContent = JSON.stringify(res.data, null, 2);
    } else {
      snapshotView.textContent = "Failed to load version snapshot: " + (res.message || "Unknown error");
    }
  } catch (err) {
    snapshotView.textContent = "Error: " + err.message;
  }
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
