/**
 * SenderX Frontend API Client
 */

function resolveApiBase() {
  const configured = localStorage.getItem("sx_api_base");
  if (configured) {
    return configured.replace(/\/+$/, "");
  }

  if (typeof window !== "undefined" && window.location) {
    const protocol = window.location.protocol;
    const hostname = window.location.hostname;
    const port = window.location.port;

    if (protocol && protocol.startsWith("http")) {
      if (port === "5000") {
        return `${window.location.origin}/api/v1`;
      }
      if (hostname) {
        return `${protocol}//${hostname}:5000/api/v1`;
      }
    }
  }

  return "http://localhost:5000/api/v1";
}

let API_BASE = resolveApiBase();

const ApiClient = {
  getApiBase() {
    return API_BASE;
  },

  setApiBase(url) {
    if (url) {
      API_BASE = url.replace(/\/+$/, "");
      localStorage.setItem("sx_api_base", API_BASE);
    }
  },
  getAccessToken() {
    return localStorage.getItem("sx_access_token");
  },

  getRefreshToken() {
    return localStorage.getItem("sx_refresh_token");
  },

  setTokens(access, refresh) {
    if (access) localStorage.setItem("sx_access_token", access);
    if (refresh) localStorage.setItem("sx_refresh_token", refresh);
  },

  clearTokens() {
    localStorage.removeItem("sx_access_token");
    localStorage.removeItem("sx_refresh_token");
    localStorage.removeItem("sx_account");
    localStorage.removeItem("sx_active_app_id");
  },

  getActiveApplicationId() {
    return localStorage.getItem("sx_active_app_id") || null;
  },

  setActiveApplicationId(appId) {
    if (appId && appId !== "all" && appId !== "null") {
      localStorage.setItem("sx_active_app_id", appId);
    } else {
      localStorage.removeItem("sx_active_app_id");
    }
  },

  getStoredAccount() {
    try {
      const raw = localStorage.getItem("sx_account");
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  },

  setStoredAccount(account) {
    localStorage.setItem("sx_account", JSON.stringify(account));
  },

  async request(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`;
    const headers = {
      "Content-Type": "application/json",
      ...(options.headers || {})
    };

    const token = this.getAccessToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    const activeApp = this.getActiveApplicationId();
    if (activeApp && !headers["X-Application-ID"]) {
      headers["X-Application-ID"] = activeApp;
    }

    try {
      const response = await fetch(url, { ...options, headers });

      if (response.status === 401 && !endpoint.includes("/auth/login")) {
        // Attempt refresh
        const refreshed = await this.refreshToken();
        if (refreshed) {
          headers["Authorization"] = `Bearer ${this.getAccessToken()}`;
          const retryRes = await fetch(url, { ...options, headers });
          return await retryRes.json();
        } else {
          this.clearTokens();
          window.dispatchEvent(new CustomEvent("sx_logout"));
          throw new Error("Session expired. Please sign in again.");
        }
      }

      const json = await response.json();
      return json;
    } catch (error) {
      console.error("API Request Error:", error);
      throw error;
    }
  },

  async refreshToken() {
    const refreshToken = this.getRefreshToken();
    if (!refreshToken) return false;

    try {
      const res = await fetch(`${API_BASE}/auth/refresh`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${refreshToken}`
        }
      });
      const data = await res.json();
      if (data.success && data.data?.access_token) {
        this.setTokens(data.data.access_token, null);
        return true;
      }
      return false;
    } catch {
      return false;
    }
  },

  // Auth
  async login(email, password) {
    const res = await this.request("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password })
    });
    if (res.success && res.data) {
      this.setTokens(res.data.access_token, res.data.refresh_token);
      this.setStoredAccount(res.data.account);
    }
    return res;
  },

  async getCurrentAccount() {
    return await this.request("/auth/me", { method: "GET" });
  },

  async getDashboardContext() {
    return await this.request("/users/me/dashboard-context", { method: "GET" });
  },

  // Organizations
  async createOrganization(data) {
    return await this.request("/organizations/", {
      method: "POST",
      body: JSON.stringify(data)
    });
  },

  async listOrganizations(page = 1, limit = 50, filters = {}) {
    let query = `?page=${page}&limit=${limit}`;
    if (filters.search) query += `&search=${encodeURIComponent(filters.search)}`;
    if (filters.status && filters.status !== "ALL") query += `&status=${encodeURIComponent(filters.status)}`;
    return await this.request(`/organizations/${query}`);
  },

  async getOrganizationDetails(orgId) {
    return await this.request(`/organizations/${orgId}`);
  },

  async updateOrganizationStatus(orgId, status) {
    return await this.request(`/organizations/${orgId}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status })
    });
  },

  async getCurrentOrganization() {
    return await this.request("/organizations/current");
  },

  async getOrganizationIdentity() {
    return await this.request("/organizations/identity");
  },

  async updateOrganizationIdentity(data) {
    return await this.request("/organizations/identity", {
      method: "PATCH",
      body: JSON.stringify(data)
    });
  },

  // Users & Roles
  async listUsers(page = 1, limit = 50, filters = {}) {
    let query = `?page=${page}&limit=${limit}`;
    if (filters.search) query += `&search=${encodeURIComponent(filters.search)}`;
    if (filters.status) query += `&status=${encodeURIComponent(filters.status)}`;
    if (filters.role_id) query += `&role_id=${encodeURIComponent(filters.role_id)}`;
    if (filters.application_id) query += `&application_id=${encodeURIComponent(filters.application_id)}`;
    if (filters.employee_code) query += `&employee_code=${encodeURIComponent(filters.employee_code)}`;
    return await this.request(`/users/${query}`);
  },

  async getNextEmployeeCode() {
    return await this.request("/users/next-employee-code");
  },

  async getUser(userId) {
    return await this.request(`/users/${userId}`);
  },

  async createUser(data) {
    return await this.request("/users/", {
      method: "POST",
      body: JSON.stringify(data)
    });
  },

  async updateUser(userId, data) {
    return await this.request(`/users/${userId}`, {
      method: "PATCH",
      body: JSON.stringify(data)
    });
  },

  async assignUserRoles(userId, payload) {
    return await this.request(`/users/${userId}/roles`, {
      method: "POST",
      body: JSON.stringify(payload)
    });
  },

  async activateUser(userId) {
    return await this.request(`/users/${userId}/activate`, {
      method: "POST"
    });
  },

  async deactivateUser(userId) {
    return await this.request(`/users/${userId}`, {
      method: "DELETE"
    });
  },

  async listRoles() {
    return await this.request("/users/roles");
  },

  async getRole(roleId) {
    return await this.request(`/users/roles/${roleId}`);
  },

  async createRole(data) {
    return await this.request("/users/roles", {
      method: "POST",
      body: JSON.stringify(data)
    });
  },

  async updateRole(roleId, data) {
    return await this.request(`/users/roles/${roleId}`, {
      method: "PATCH",
      body: JSON.stringify(data)
    });
  },

  async deleteRole(roleId) {
    return await this.request(`/users/roles/${roleId}`, {
      method: "DELETE"
    });
  },

  async listPermissions() {
    return await this.request("/users/permissions");
  },

  async listSecurityAuditLogs(page = 1, limit = 50, filters = {}) {
    let query = `?page=${page}&limit=${limit}`;
    if (filters.target_id) query += `&target_id=${encodeURIComponent(filters.target_id)}`;
    if (filters.event_type) query += `&event_type=${encodeURIComponent(filters.event_type)}`;
    return await this.request(`/users/audit-logs${query}`);
  },

  // Connected Applications (Phase 5 Task 1)
  async listApplications(page = 1, limit = 50, status = null) {
    let query = `?page=${page}&limit=${limit}`;
    if (status) query += `&status=${encodeURIComponent(status)}`;
    return await this.request(`/applications/${query}`);
  },

  async getApplication(applicationId) {
    return await this.request(`/applications/${applicationId}`);
  },

  async registerApplication(data) {
    return await this.request("/applications/", {
      method: "POST",
      body: JSON.stringify(data)
    });
  },

  async updateApplication(applicationId, data) {
    return await this.request(`/applications/${applicationId}`, {
      method: "PATCH",
      body: JSON.stringify(data)
    });
  },

  async deactivateApplication(applicationId) {
    return await this.request(`/applications/${applicationId}/deactivate`, {
      method: "POST"
    });
  },

  async activateApplication(applicationId) {
    return await this.request(`/applications/${applicationId}/activate`, {
      method: "POST"
    });
  },

  async getApplicationStats(applicationId) {
    return await this.request(`/applications/${applicationId}/stats`);
  },

  // API Credentials (Phase 5 Task 1)
  async listCredentials(applicationId = null) {
    let query = "";
    if (applicationId) query = `?application_id=${encodeURIComponent(applicationId)}`;
    return await this.request(`/api-credentials/${query}`);
  },

  async getCredential(credentialId) {
    return await this.request(`/api-credentials/${credentialId}`);
  },

  async createCredential(data) {
    return await this.request("/api-credentials/", {
      method: "POST",
      body: JSON.stringify(data)
    });
  },

  async revokeCredential(credentialId) {
    return await this.request(`/api-credentials/${credentialId}`, {
      method: "DELETE"
    });
  },

  async rotateCredential(credentialId, environment = "live") {
    return await this.request(`/api-credentials/${credentialId}/rotate`, {
      method: "POST",
      body: JSON.stringify({ environment })
    });
  },

  // Ingested JSON Payloads (Phase 5 Task 1)
  async listPayloads(page = 1, limit = 50, filters = {}) {
    let query = `?page=${page}&limit=${limit}`;
    if (filters.status) query += `&status=${encodeURIComponent(filters.status)}`;
    if (filters.channel) query += `&channel=${encodeURIComponent(filters.channel)}`;
    if (filters.validation_status) query += `&validation_status=${encodeURIComponent(filters.validation_status)}`;
    if (filters.application_id) query += `&application_id=${encodeURIComponent(filters.application_id)}`;
    return await this.request(`/payloads/${query}`);
  },

  async getPayload(payloadId) {
    return await this.request(`/payloads/${payloadId}`);
  },

  // Messages
  async createMessage(payload) {
    return await this.request("/messages/", {
      method: "POST",
      body: JSON.stringify(payload)
    });
  },

  async queueMessage(messageId) {
    return await this.request(`/messages/${messageId}/queue`, {
      method: "POST"
    });
  },

  async listMessages(page = 1, limit = 50) {
    return await this.request(`/messages/?page=${page}&limit=${limit}`);
  },

  // DLQ
  async listDlq(page = 1, limit = 50) {
    return await this.request(`/dead-letters/organization?page=${page}&limit=${limit}`);
  },

  async retryDlq(messageId) {
    return await this.request(`/dead-letters/organization/${messageId}/retry`, {
      method: "POST"
    });
  },

  // Provider Config
  async saveProviderConfig(provider, credentials) {
    return await this.request("/provider-config/organization", {
      method: "POST",
      body: JSON.stringify({ provider, credentials })
    });
  },

  // Dynamic JSON Analyzer
  async analyzeJson(payload) {
    return await this.request("/validation/analyze", {
      method: "POST",
      body: JSON.stringify(payload)
    });
  },

  // Analytics
  async getPlatformAnalytics() {
    return await this.request("/analytics/platform");
  },

  async getOrganizationAnalytics() {
    return await this.request("/analytics/organization");
  },

  // Health
  async getDetailedHealth() {
    return await this.request("/health/detailed");
  },

  // Templates (Phase 3 Task 2)
  async listTemplates(page = 1, limit = 50, filters = {}) {
    let query = `?page=${page}&limit=${limit}`;
    if (filters.status) query += `&status=${encodeURIComponent(filters.status)}`;
    if (filters.category) query += `&category=${encodeURIComponent(filters.category)}`;
    if (filters.search) query += `&search=${encodeURIComponent(filters.search)}`;
    return await this.request(`/templates/${query}`);
  },

  async getTemplate(templateId) {
    return await this.request(`/templates/${templateId}`);
  },

  async createTemplate(data) {
    return await this.request("/templates/", {
      method: "POST",
      body: JSON.stringify(data)
    });
  },

  async updateTemplate(templateId, data) {
    return await this.request(`/templates/${templateId}`, {
      method: "PUT",
      body: JSON.stringify(data)
    });
  },

  async deleteTemplate(templateId) {
    return await this.request(`/templates/${templateId}`, {
      method: "DELETE"
    });
  },

  async previewTemplate(templateId, sampleData = {}) {
    return await this.request(`/templates/${templateId}/preview`, {
      method: "POST",
      body: JSON.stringify({ sample_data: sampleData })
    });
  },

  async publishTemplate(templateId) {
    return await this.request(`/templates/${templateId}/publish`, {
      method: "POST"
    });
  },

  async archiveTemplate(templateId) {
    return await this.request(`/templates/${templateId}/archive`, {
      method: "POST"
    });
  },

  async duplicateTemplate(templateId) {
    return await this.request(`/templates/${templateId}/duplicate`, {
      method: "POST"
    });
  },

  async getTemplateVersions(templateId) {
    return await this.request(`/templates/${templateId}/versions`);
  },

  async getTemplateVersion(templateId, version) {
    return await this.request(`/templates/${templateId}/versions/${version}`);
  }
};
