/**
 * SenderX Frontend Application
 */

let currentOrgProfile = null;
let currentUserPermissions = new Set();
let cachedApplicationsList = [];
let hasCopiedSecretKey = false;

document.addEventListener("DOMContentLoaded", () => {
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
  if (m) m.classList.add("active");
}

function closeModal(id) {
  const m = document.getElementById(id);
  if (m) m.classList.remove("active");
}

function initApp() {
  const storedAccount = ApiClient.getStoredAccount();
  const token = ApiClient.getAccessToken();

  if (token && storedAccount) {
    showDashboard(storedAccount);
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
    currentOrgProfile = null;
    showAuth();
  };
  document.getElementById("btn-logout")?.addEventListener("click", handleLogout);
  document.getElementById("btn-header-logout")?.addEventListener("click", handleLogout);

  window.addEventListener("sx_logout", () => {
    handleLogout();
  });

  // Sidebar Tab Navigation with Role Guard
  document.querySelectorAll(".nav-item").forEach((btn) => {
    btn.addEventListener("click", () => {
      const targetId = btn.getAttribute("data-tab");
      const currentAccount = ApiClient.getStoredAccount();

      // Guard: Organization users cannot access platform admin tabs
      if (targetId && targetId.startsWith("tab-platform") && currentAccount?.account_type !== "PLATFORM_ADMIN") {
        showToast("Access denied: Platform Admin privileges required", "danger");
        return;
      }

      document.querySelectorAll(".nav-item").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".tab-pane").forEach((t) => t.classList.remove("active"));

      btn.classList.add("active");
      const targetPane = document.getElementById(targetId);
      if (targetPane) targetPane.classList.add("active");

      // Load tab-specific data
      handleTabActivation(targetId);
    });
  });

  // Setup Top Navigation
  setupTopNav();

  // Setup Forms
  setupCreateOrgForm();
  setupSendMessageForm();
  setupCreateUserForm();
  setupProviderConfigForm();
  setupTemplateEditorForm();
  setupRegisterAppForm();
  setupGenerateCredentialForm();
}

function showAuth() {
  document.getElementById("auth-view").classList.add("active");
  document.getElementById("app-shell").classList.remove("active");
}

function showDashboard(account) {
  document.getElementById("auth-view").classList.remove("active");
  document.getElementById("app-shell").classList.add("active");

  const accountType = account.account_type;
  document.getElementById("current-account-type").textContent = accountType;
  document.getElementById("current-account-name").textContent = account.email;

  // Header profile setup
  const headerEmail = document.getElementById("header-user-email");
  if (headerEmail) headerEmail.textContent = account.email || "user@senderx.io";

  const headerRole = document.getElementById("header-user-role");
  if (headerRole) {
    headerRole.textContent = account.role || (accountType === "PLATFORM_ADMIN" ? "SUPER_ADMIN" : "ORG_ADMIN");
  }

  const avatarInitial = document.getElementById("user-avatar-initial");
  if (avatarInitial) {
    avatarInitial.textContent = (account.email || "U")[0].toUpperCase();
  }

  const navPlatform = document.getElementById("nav-platform");
  const navOrg = document.getElementById("nav-organization");

  if (accountType === "PLATFORM_ADMIN") {
    navPlatform.style.display = "block";
    navOrg.style.display = "block";
    document.querySelector('[data-tab="tab-platform-overview"]')?.click();
  } else {
    navPlatform.style.display = "none";
    navOrg.style.display = "block";
    initOrganizationDashboard(account);
    document.querySelector('[data-tab="tab-org-overview"]')?.click();
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
  return currentUserPermissions.has(perm);
}

function applyPermissionVisibility() {
  document.querySelectorAll("[data-perm]").forEach((el) => {
    const requiredPerm = el.getAttribute("data-perm");
    if (hasPermission(requiredPerm)) {
      el.style.display = "";
    } else {
      el.style.display = "none";
    }
  });
}

function navigateToTab(tabId) {
  document.querySelector(`[data-tab="${tabId}"]`)?.click();
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

  // Resolve user permissions
  currentUserPermissions.clear();
  try {
    const rolesRes = await ApiClient.listRoles();
    if (rolesRes.success && rolesRes.data) {
      const assignedRoleIds = new Set(account.role_ids || []);
      for (const role of rolesRes.data) {
        if (assignedRoleIds.has(role.role_id) || role.name === "ORG_ADMIN") {
          for (const perm of (role.permissions || [])) {
            currentUserPermissions.add(perm);
          }
        }
      }
    }
  } catch {
    // If listRoles is forbidden or not yet loaded, grant standard organization admin permissions if applicable
    currentUserPermissions.add("organization:messages:create");
    currentUserPermissions.add("organization:messages:read");
    currentUserPermissions.add("organization:payloads:read");
    currentUserPermissions.add("organization:dead_letters:read");
    currentUserPermissions.add("organization:configuration:manage");
    currentUserPermissions.add("organization:users:manage");
    currentUserPermissions.add("organization:analytics:read");
  }

  applyPermissionVisibility();
}

async function handleTabActivation(tabId) {
  updateBreadcrumb(tabId);

  switch (tabId) {
    case "tab-platform-overview":
      await loadOrganizations();
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
      await loadRolesDropdown();
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
async function loadOrganizations() {
  const tbody = document.getElementById("orgs-table-body");
  tbody.innerHTML = '<tr><td colspan="5" class="loading-cell">Loading organizations...</td></tr>';

  try {
    const res = await ApiClient.listOrganizations();
    if (res.success && res.data) {
      if (res.data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="loading-cell">No organizations found.</td></tr>';
        return;
      }
      tbody.innerHTML = res.data
        .map(
          (org) => `
        <tr>
          <td><strong>${escapeHtml(org.name)}</strong></td>
          <td><code>${escapeHtml(org.slug)}</code></td>
          <td><span class="badge badge-${(org.status || "active").toLowerCase()}">${org.status || "ACTIVE"}</span></td>
          <td>${new Date(org.created_at).toLocaleDateString()}</td>
          <td>
            ${
              org.status === "ACTIVE"
                ? `<button class="btn btn-secondary btn-sm" onclick="toggleOrgStatus('${org.organization_id}', 'INACTIVE')">Deactivate</button>`
                : `<button class="btn btn-primary btn-sm" onclick="toggleOrgStatus('${org.organization_id}', 'ACTIVE')">Activate</button>`
            }
          </td>
        </tr>
      `
        )
        .join("");
    }
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="5" class="loading-cell error">${err.message}</td></tr>`;
  }
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
        loadOrganizations();
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
async function loadOrgMessages() {
  const tbody = document.getElementById("messages-table-body");
  tbody.innerHTML = '<tr><td colspan="7" class="loading-cell">Loading messages...</td></tr>';

  try {
    const res = await ApiClient.listMessages();
    if (res.success && res.data) {
      if (res.data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="loading-cell">No messages dispatched yet.</td></tr>';
        return;
      }
      tbody.innerHTML = res.data
        .map(
          (m) => `
        <tr>
          <td><code>${escapeHtml(m.message_id.substring(0, 8))}...</code></td>
          <td>${escapeHtml(m.recipient)}</td>
          <td><span class="badge">${m.channel}</span></td>
          <td>${m.provider || "unassigned"}</td>
          <td><span class="badge badge-${(m.status || "").toLowerCase()}">${m.status}</span></td>
          <td>${m.retry_count || 0}</td>
          <td>${new Date(m.created_at).toLocaleTimeString()}</td>
        </tr>
      `
        )
        .join("");
    }
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="7" class="loading-cell error">${err.message}</td></tr>`;
  }
}

function setupSendMessageForm() {
  document.getElementById("send-message-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    let dataObj;
    try {
      dataObj = JSON.parse(document.getElementById("msg-payload").value);
    } catch {
      showToast("Invalid JSON payload format", "danger");
      return;
    }

    const payload = {
      channel: document.getElementById("msg-channel").value,
      provider: document.getElementById("msg-provider").value,
      recipient: document.getElementById("msg-recipient").value.trim(),
      data: dataObj
    };

    try {
      const res = await ApiClient.createMessage(payload);
      if (res.success && res.data?.message?.message_id) {
        showToast("Message created and queued for processing!", "success");
        // Dispatch via dedicated queue endpoint
        await ApiClient.queueMessage(res.data.message.message_id);
        document.querySelector('[data-tab="tab-org-messages"]')?.click();
      } else {
        showToast(res.message || "Failed to create message", "danger");
      }
    } catch (err) {
      showToast(err.message, "danger");
    }
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

async function loadOrgUsers() {
  const tbody = document.getElementById("users-table-body");
  tbody.innerHTML = '<tr><td colspan="5" class="loading-cell">Loading users...</td></tr>';

  try {
    const res = await ApiClient.listUsers();
    if (res.success && res.data) {
      tbody.innerHTML = res.data
        .map(
          (u) => `
        <tr>
          <td><strong>${escapeHtml(u.name)}</strong></td>
          <td>${escapeHtml(u.email)}</td>
          <td><span class="badge badge-${u.is_active ? "active" : "inactive"}">${u.is_active ? "ACTIVE" : "INACTIVE"}</span></td>
          <td>${u.role_ids ? u.role_ids.length : 0} role(s)</td>
          <td>
            ${
              u.is_active
                ? `<button class="btn btn-outline btn-sm" data-perm="organization:users:manage" onclick="handleDeactivateUser('${u.user_id}', '${escapeHtml(u.name)}')">Deactivate</button>`
                : '<span class="subtitle" style="font-size: 0.75rem;">Inactive</span>'
            }
          </td>
        </tr>
      `
        )
        .join("");
    }
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="5" class="loading-cell error">${err.message}</td></tr>`;
  }
}

async function loadRolesDropdown() {
  const sel = document.getElementById("new-user-role-select");
  if (!sel) return;
  try {
    const res = await ApiClient.listRoles();
    if (res.success && res.data) {
      sel.innerHTML = res.data
        .map((r) => `<option value="${r.role_id}">${escapeHtml(r.name)}</option>`)
        .join("");
    }
  } catch (err) {
    console.error(err);
  }
}

function setupCreateUserForm() {
  document.getElementById("form-create-user")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const selRole = document.getElementById("new-user-role-select").value;
    const payload = {
      name: document.getElementById("new-user-name").value.trim(),
      email: document.getElementById("new-user-email").value.trim().toLowerCase(),
      password: document.getElementById("new-user-password").value,
      role_ids: selRole ? [selRole] : []
    };

    try {
      const res = await ApiClient.createUser(payload);
      if (res.success) {
        showToast("User created successfully!", "success");
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
  const [analyticsRes, appsRes, payloadsRes, dlqRes] = await Promise.allSettled([
    ApiClient.getOrganizationAnalytics(),
    ApiClient.listApplications(1, 100),
    ApiClient.listPayloads(1, 5),
    ApiClient.listDlq(1, 5)
  ]);

  const analytics = analyticsRes.status === "fulfilled" && analyticsRes.value.success ? analyticsRes.value : null;
  const apps = appsRes.status === "fulfilled" && appsRes.value.success ? (appsRes.value.data || []) : [];
  
  const payloadData = payloadsRes.status === "fulfilled" && payloadsRes.value.success ? payloadsRes.value.data : null;
  const payloads = Array.isArray(payloadData) ? payloadData : (payloadData?.items || []);
  const dlqItems = dlqRes.status === "fulfilled" && dlqRes.value.success ? (dlqRes.value.data || []) : [];
  const totalPayloadsCount = payloadsRes.status === "fulfilled" ? (payloadData?.pagination?.total ?? payloadsRes.value.total ?? payloads.length) : 0;

  // 1. Update 6 Metric Cards
  document.getElementById("overview-m-apps").textContent = apps.length;
  document.getElementById("overview-m-requests").textContent = totalPayloadsCount;

  const overview = analytics?.overview || {};
  const totalMsgs = overview.total_messages || 0;
  const sentMsgs = overview.sent || 0;
  const failedMsgs = (overview.failed || 0) + (overview.dead || 0);
  const dlqCount = analytics?.dead_letter_queue?.pending_review ?? dlqItems.length;

  document.getElementById("overview-m-messages").textContent = totalMsgs;
  document.getElementById("overview-m-delivered").textContent = sentMsgs;
  document.getElementById("overview-m-failed").textContent = failedMsgs;
  document.getElementById("overview-m-dlq").textContent = dlqCount;
  document.getElementById("overview-m-deliv-rate").textContent = `${overview.delivery_rate_percent || 0}% delivery rate`;

  // 2. Activity Chart (14-day trends)
  const chartContainer = document.getElementById("overview-activity-chart");
  const trends = analytics?.daily_trends || [];
  const hasTrends = trends.some((t) => t.total > 0);

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

  // 3. Channel Distribution
  const channelListEl = document.getElementById("overview-channel-list");
  const channels = (analytics?.channels || []).filter((c) => c.count > 0);
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

  // 4. Recent Payloads Table
  const payloadsBody = document.getElementById("overview-payloads-body");
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

  // 5. Recent Delivery Failures Table
  const failuresBody = document.getElementById("overview-failures-body");
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

  // 6. Connected Applications Summary Table
  const appsBody = document.getElementById("overview-apps-body");
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
            <td><code>${escapeHtml(app.application_id)}</code></td>
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
  document.getElementById("app-details-id").textContent = app.application_id || "-";
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

// 5. Organization Settings Operations
async function loadOrgSettings() {
  try {
    const res = await ApiClient.getCurrentOrganization();
    if (res.success && res.data) {
      const org = res.data;
      currentOrgProfile = org;
      document.getElementById("settings-org-name").textContent = org.name || "-";
      document.getElementById("settings-org-slug").textContent = org.slug || "-";
      document.getElementById("settings-org-id").textContent = org.organization_id || "-";
      document.getElementById("settings-org-status").textContent = org.status || "ACTIVE";
      document.getElementById("settings-org-status").className = `badge badge-${(org.status || "active").toLowerCase()}`;
      document.getElementById("settings-org-created").textContent = org.created_at ? new Date(org.created_at).toLocaleDateString() : "Active";
    }
  } catch {
    const account = ApiClient.getStoredAccount();
    if (account) {
      document.getElementById("settings-org-name").textContent = "Organization Workspace";
      document.getElementById("settings-org-slug").textContent = account.organization_id || "-";
      document.getElementById("settings-org-id").textContent = account.organization_id || "-";
    }
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

function openCreateTemplateModal() {
  document.getElementById("tpl-modal-title").textContent = "Create Email Template";
  document.getElementById("tpl-edit-id").value = "";
  document.getElementById("tpl-name").value = "";
  document.getElementById("tpl-category").value = "general";
  document.getElementById("tpl-description").value = "";
  document.getElementById("tpl-subject").value = "";
  document.getElementById("tpl-header").value = "";
  document.getElementById("tpl-footer").value = "";
  document.getElementById("tpl-html-body").value = "";
  document.getElementById("tpl-plain-body").value = "";
  document.getElementById("tpl-variables-json").value = "[]";
  document.getElementById("btn-save-template").textContent = "Save Draft";
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
    document.getElementById("tpl-modal-title").textContent = `Edit Template (${t.status} v${t.version})`;
    document.getElementById("tpl-edit-id").value = t.template_id;
    document.getElementById("tpl-name").value = t.name || "";
    document.getElementById("tpl-category").value = t.category || "general";
    document.getElementById("tpl-description").value = t.description || "";
    document.getElementById("tpl-subject").value = t.subject || "";
    document.getElementById("tpl-header").value = t.header || "";
    document.getElementById("tpl-footer").value = t.footer || "";
    document.getElementById("tpl-html-body").value = t.html_body || "";
    document.getElementById("tpl-plain-body").value = t.plain_text_body || "";
    document.getElementById("tpl-variables-json").value = JSON.stringify(t.variables || [], null, 2);
    document.getElementById("btn-save-template").textContent = t.status === "ACTIVE" ? "Update (Bumps Version)" : "Save Changes";

    openModal("modal-template-editor");
  } catch (err) {
    showToast(err.message, "danger");
  }
}

function setupTemplateEditorForm() {
  const form = document.getElementById("form-template-editor");
  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const editId = document.getElementById("tpl-edit-id").value;
    const name = document.getElementById("tpl-name").value.trim();
    const category = document.getElementById("tpl-category").value;
    const description = document.getElementById("tpl-description").value.trim();
    const subject = document.getElementById("tpl-subject").value.trim();
    const header = document.getElementById("tpl-header").value;
    const footer = document.getElementById("tpl-footer").value;
    const html_body = document.getElementById("tpl-html-body").value;
    const plain_text_body = document.getElementById("tpl-plain-body").value;

    let variables = [];
    const varsRaw = document.getElementById("tpl-variables-json").value.trim();
    if (varsRaw) {
      try {
        variables = JSON.parse(varsRaw);
        if (!Array.isArray(variables)) {
          showToast("Dynamic variables must be a JSON array of objects", "danger");
          return;
        }
      } catch (err) {
        showToast("Invalid JSON in dynamic variables: " + err.message, "danger");
        return;
      }
    }

    const payload = {
      name,
      category,
      description,
      subject,
      header,
      footer,
      html_body,
      plain_text_body,
      variables
    };

    try {
      let res;
      if (editId) {
        res = await ApiClient.updateTemplate(editId, payload);
      } else {
        res = await ApiClient.createTemplate(payload);
      }

      if (res.success) {
        showToast(res.message || "Template saved successfully!", "success");
        closeModal("modal-template-editor");
        await loadOrgTemplates();
      } else {
        showToast(res.message || "Failed to save template", "danger");
      }
    } catch (err) {
      showToast(err.message, "danger");
    }
  });
}

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
