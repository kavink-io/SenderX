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

  // Sidebar Tab Navigation Setup
  setupNavItemListeners();

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
  document.getElementById("auth-view").classList.add("active");
  document.getElementById("app-shell").classList.remove("active");
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

  let ctx = currentUserDashboardContext;
  if (!ctx) {
    ctx = await loadDashboardContext();
  }
  if (!ctx) {
    const stored = ApiClient.getStoredAccount();
    if (stored) {
      ctx = {
        email: stored.email,
        name: stored.name || stored.email,
        organization_id: stored.organization_id,
        employee_code: stored.employee_code,
        organization_name: stored.organization_name || "Organization Workspace",
        is_org_admin: stored.is_org_admin === true,
        roles: stored.roles || [],
        role_assignments: stored.role_assignments || [],
        assigned_applications: stored.assigned_applications || [],
        effective_permissions: stored.effective_permissions || []
      };
    }
  }
  if (!ctx) return;

  const emailEl = document.getElementById("profile-modal-email") || document.getElementById("modal-profile-email");
  const orgEl = document.getElementById("profile-modal-org") || document.getElementById("modal-profile-org");
  const empIdEl = document.getElementById("profile-modal-emp-id");
  const rolesListEl = document.getElementById("profile-modal-roles") || document.getElementById("modal-profile-roles-list");
  const appsListEl = document.getElementById("profile-modal-apps") || document.getElementById("modal-profile-apps-list");
  const permsCountEl = document.getElementById("profile-modal-perm-count");
  const permsListEl = document.getElementById("profile-modal-perms") || document.getElementById("modal-profile-perms-list");

  if (emailEl) {
    emailEl.textContent = ctx.name ? `${ctx.name} (${ctx.email})` : ctx.email;
  }
  if (orgEl) {
    orgEl.textContent = `${ctx.organization_name || "Organization Workspace"} • ID: ${ctx.organization_id || "N/A"}`;
  }
  if (empIdEl) {
    if (ctx.employee_code) {
      empIdEl.textContent = ctx.employee_code;
      empIdEl.style.display = "inline-block";
    } else {
      empIdEl.style.display = "none";
    }
  }

  if (rolesListEl) {
    const roles = ctx.roles || [];
    const assignments = ctx.role_assignments || [];
    if (ctx.is_org_admin) {
      rolesListEl.innerHTML = `
        <div style="background: rgba(99,102,241,0.15); border: 1px solid rgba(99,102,241,0.35); border-radius: 6px; padding: 8px 12px; display: flex; justify-content: space-between; align-items: center;">
          <strong style="color: #818cf8;">ORG_ADMIN (Predefined Organization Admin)</strong>
          <span class="badge badge-primary" style="font-size: 0.75rem;">Organization-Wide</span>
        </div>
      `;
    } else if (assignments.length > 0) {
      rolesListEl.innerHTML = assignments.map((a) => `
        <div style="background: rgba(255,255,255,0.04); border: 1px solid var(--border-color); border-radius: 6px; padding: 8px 12px; display: flex; justify-content: space-between; align-items: center;">
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
        <div style="background: rgba(255,255,255,0.04); border: 1px solid var(--border-color); border-radius: 6px; padding: 8px 12px; display: flex; justify-content: space-between; align-items: center;">
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
    if (ctx.is_org_admin) {
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
    if (ctx.is_org_admin) {
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
              <div style="font-family: var(--font-mono); font-size: 0.725rem; color: var(--text-muted); margin-top: 2px;">ID: ${org.organization_id}</div>
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
                    : `<button class="btn btn-primary btn-sm" onclick="toggleOrgStatus('${org.organization_id}', 'ACTIVE')">Activate</button>`
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
  document.getElementById("org-detail-id").textContent = orgId;
  document.getElementById("org-detail-status-badge").textContent = "...";
  document.getElementById("org-detail-prefix").textContent = "-";
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
      document.getElementById("org-detail-id").textContent = org.organization_id;
      
      const badge = document.getElementById("org-detail-status-badge");
      badge.textContent = org.status || "ACTIVE";
      badge.className = `badge badge-${(org.status || "active").toLowerCase()}`;

      document.getElementById("org-detail-prefix").textContent = org.employee_id_prefix || "None (Default: EMP)";
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
        toggleActionBox.innerHTML = `<button class="btn btn-secondary" onclick="toggleOrgStatusFromModal('${org.organization_id}', 'INACTIVE')">Deactivate Organization</button>`;
      } else {
        toggleActionBox.innerHTML = `<button class="btn btn-primary" onclick="toggleOrgStatusFromModal('${org.organization_id}', 'ACTIVE')">Activate Organization</button>`;
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

        // Action buttons
        let statusToggleBtn = "";
        if (isSelf) {
          statusToggleBtn = `<button class="btn btn-outline btn-sm" disabled style="opacity: 0.5; cursor: not-allowed;" title="You cannot deactivate your own account">Deactivate (You)</button>`;
        } else if (u.is_active) {
          if (isLastAdmin) {
            statusToggleBtn = `<button class="btn btn-outline btn-sm" disabled style="opacity: 0.5; cursor: not-allowed;" title="Cannot deactivate the last active organization administrator">Deactivate (Last Admin)</button>`;
          } else {
            statusToggleBtn = `<button class="btn btn-outline btn-sm" data-perm="organization:users:manage" onclick="handleToggleUserStatus('${u.user_id}', '${escapeHtml(u.name)}', true)">Deactivate</button>`;
          }
        } else {
          statusToggleBtn = `<button class="btn btn-outline btn-sm" style="border-color: var(--status-success); color: var(--status-success);" data-perm="organization:users:manage" onclick="handleToggleUserStatus('${u.user_id}', '${escapeHtml(u.name)}', false)">Activate</button>`;
        }

        const initials = (u.name || "U").split(" ").map(p => p[0]).join("").toUpperCase().slice(0, 2);
        const empCodeHtml = u.employee_code
          ? `<span class="badge-emp-code">${escapeHtml(u.employee_code)}</span>`
          : `<span style="color: var(--text-muted); font-size: 0.775rem;">-</span>`;

        return `
          <tr>
            <td>
              <div class="user-cell-wrapper">
                <div class="user-avatar-circle">${escapeHtml(initials)}</div>
                <div>
                  <strong style="color: var(--text-primary); display: block;">${escapeHtml(u.name)}</strong>
                  <span style="font-family: var(--font-mono); font-size: 0.725rem; color: var(--text-muted);">${escapeHtml(u.user_id)}</span>
                </div>
              </div>
            </td>
            <td>${empCodeHtml}</td>
            <td><span style="color: var(--text-secondary);">${escapeHtml(u.email)}</span></td>
            <td>
              <span class="badge badge-${u.is_active ? "active" : "inactive"}">${u.is_active ? "ACTIVE" : "INACTIVE"}</span>
            </td>
            <td>
              <div style="display: flex; flex-wrap: wrap; max-width: 380px;">${roleTagsHtml}</div>
            </td>
            <td>
              <div style="display: flex; gap: 6px; align-items: center;">
                <button class="btn btn-secondary btn-sm" onclick="handleViewUserDetails('${u.user_id}')">Details</button>
                <button class="btn btn-outline btn-sm" data-perm="organization:roles:manage" onclick="handleOpenAssignRoles('${u.user_id}')">Assign Roles</button>
                ${statusToggleBtn}
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

async function loadOrgAuditLogs() {
  const tbody = document.getElementById("audit-logs-table-body");
  const emptyState = document.getElementById("audit-empty-state");
  if (!tbody) return;

  tbody.innerHTML = '<tr><td colspan="5" class="loading-cell">Loading security audit trail...</td></tr>';
  if (emptyState) emptyState.style.display = "none";

  try {
    const res = await ApiClient.listSecurityAuditLogs(1, 50);
    if (res.success && res.data) {
      if (res.data.length === 0) {
        tbody.innerHTML = "";
        if (emptyState) emptyState.style.display = "block";
        return;
      }

      tbody.innerHTML = res.data.map(log => {
        const timeFormatted = log.timestamp ? new Date(log.timestamp).toLocaleString() : "-";
        const detailsStr = log.details ? JSON.stringify(log.details) : "-";
        return `
          <tr>
            <td style="font-size: 0.775rem; color: var(--text-secondary); white-space: nowrap;">${escapeHtml(timeFormatted)}</td>
            <td><span class="badge badge-active" style="font-size: 0.7rem;">${escapeHtml(log.event_type || "-")}</span></td>
            <td style="font-family: var(--font-mono); font-size: 0.75rem; color: var(--accent-cyan);">${escapeHtml(log.actor_id || "System")}</td>
            <td style="font-family: var(--font-mono); font-size: 0.75rem; color: var(--text-muted);">${escapeHtml(log.target_id || "-")}</td>
            <td style="font-size: 0.75rem; color: var(--text-secondary); max-width: 280px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${escapeHtml(detailsStr)}">
              ${escapeHtml(detailsStr)}
            </td>
          </tr>
        `;
      }).join("");
    }
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="5" class="loading-cell error">${escapeHtml(err.message)}</td></tr>`;
  }
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
  generateRandomUserPassword();
  generateNextEmployeeId();
  openModal("modal-create-user");
}

async function generateNextEmployeeId() {
  const codeInput = document.getElementById("new-user-employee-code");
  if (!codeInput) return;
  try {
    const res = await ApiClient.getNextEmployeeCode();
    if (res && res.success && res.data?.next_code) {
      codeInput.value = res.data.next_code;
    }
  } catch (err) {
    console.warn("Could not prefill employee code:", err);
  }
}

function generateRandomUserPassword() {
  const chars = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789!@#$%&*";
  let pwd = "";
  for (let i = 0; i < 16; i++) {
    pwd += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  const pwdInput = document.getElementById("new-user-password");
  if (pwdInput) {
    pwdInput.value = pwd;
    pwdInput.type = "text";
  }
}

function setupCreateUserForm() {
  document.getElementById("form-create-user")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const selRole = document.getElementById("new-user-role-select").value;
    const appScope = document.getElementById("new-user-app-scope")?.value || null;
    const employeeCode = document.getElementById("new-user-employee-code")?.value.trim().toUpperCase() || null;

    const payload = {
      name: document.getElementById("new-user-name").value.trim(),
      email: document.getElementById("new-user-email").value.trim().toLowerCase(),
      password: document.getElementById("new-user-password").value,
      role_ids: selRole ? [selRole] : [],
      role_assignments: selRole ? [{ role_id: selRole, application_id: appScope }] : []
    };
    if (employeeCode) {
      payload.employee_code = employeeCode;
    }

    try {
      const res = await ApiClient.createUser(payload);
      if (res.success) {
        showToast("Employee added successfully!", "success");
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
    const res = await ApiClient.assignUserRoles(userId, { role_assignments: _currentRoleAssignments });
    if (res.success) {
      showToast("Role assignments saved successfully!", "success");
      closeModal("modal-assign-role");
      loadOrgUsers();
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
    document.getElementById("detail-user-id").textContent = `ID: ${u.user_id}`;
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
    const name = document.getElementById("new-role-name").value.trim().toUpperCase().replace(/\s+/g, "_");
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
          <div style="display: flex; justify-content: space-between; align-items: center; padding: 6px 0; border-bottom: 1px solid rgba(255, 255, 255, 0.05);">
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

  // Load Employee ID Configuration (Phase 5 Task 4)
  try {
    const idRes = await ApiClient.getOrganizationIdentity();
    if (idRes.success && idRes.data) {
      const idData = idRes.data;
      const empPrefixInput = document.getElementById("identity-emp-prefix");
      const previewEl = document.getElementById("identity-preview-code");
      const seqEl = document.getElementById("identity-next-seq");

      if (empPrefixInput) {
        empPrefixInput.value = idData.employee_id_prefix || "";
      }
      if (previewEl) previewEl.textContent = idData.preview_next_code || "-";
      if (seqEl) seqEl.textContent = idData.next_employee_sequence !== undefined ? idData.next_employee_sequence : "-";
    }
  } catch (err) {
    console.warn("Could not load employee ID prefix settings:", err);
  }
}

async function saveOrganizationIdentity(event) {
  if (event) event.preventDefault();
  const empPrefixInput = document.getElementById("identity-emp-prefix");
  const saveBtn = document.getElementById("btn-save-identity");

  const prefix = empPrefixInput ? empPrefixInput.value.trim().toUpperCase() : "";
  if (!prefix) {
    showToast("Please enter an employee ID prefix", "warning");
    return;
  }

  if (saveBtn) saveBtn.disabled = true;
  try {
    const res = await ApiClient.updateOrganizationIdentity({ employee_id_prefix: prefix });
    if (res.success) {
      showToast("Employee ID prefix updated successfully!", "success");
      await loadOrgSettings();
    } else {
      showToast(res.message || "Failed to update employee ID prefix", "danger");
    }
  } catch (err) {
    showToast(err.message || "Error saving employee ID prefix", "danger");
  } finally {
    if (saveBtn) saveBtn.disabled = false;
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
