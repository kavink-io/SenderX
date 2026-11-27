import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import ApiClient from '../services/api';

const AuthContext = createContext();

export function AuthProvider({ children }) {
  const [account, setAccount] = useState(() => ApiClient.getStoredAccount());
  const [token, setToken] = useState(() => ApiClient.getAccessToken());
  const [dashboardContext, setDashboardContext] = useState(null);
  const [permissions, setPermissions] = useState(new Set());
  const [allowedTabs, setAllowedTabs] = useState(new Set());
  const [isLoading, setIsLoading] = useState(true);

  const isPlatformAdmin = account?.account_type === 'PLATFORM_ADMIN';
  const isOrgAdmin = Boolean(dashboardContext?.is_org_admin || account?.is_org_admin);

  const hasPermission = useCallback((perm) => {
    if (!perm) return true;
    if (isPlatformAdmin) return true;
    if (isOrgAdmin) return true;
    if (permissions.has(perm)) return true;
    if (perm === 'organization:dead_letters:read' && (permissions.has('organization:dlq:read') || permissions.has('organization:dead_letters:read'))) return true;
    if (perm === 'organization:dead_letters:manage' && (permissions.has('organization:dlq:manage') || permissions.has('organization:dead_letters:manage'))) return true;
    return false;
  }, [isPlatformAdmin, isOrgAdmin, permissions]);

  const clearAuthState = useCallback(() => {
    ApiClient.clearTokens();
    setAccount(null);
    setToken(null);
    setDashboardContext(null);
    setPermissions(new Set());
    setAllowedTabs(new Set());
  }, []);

  const logout = useCallback(() => {
    clearAuthState();
    window.dispatchEvent(new CustomEvent('sx_logout', { detail: { source: 'auth' } }));
  }, [clearAuthState]);

  const loadUserContext = useCallback(async () => {
    const activeToken = ApiClient.getAccessToken();
    if (!activeToken) {
      clearAuthState();
      setIsLoading(false);
      return false;
    }

    try {
      const meRes = await ApiClient.getCurrentAccount();
      if (!meRes?.success || !meRes.data) {
        logout();
        return false;
      }

      const resolvedAccount = meRes.data;
      ApiClient.setStoredAccount(resolvedAccount);

      if (resolvedAccount.account_type !== 'PLATFORM_ADMIN') {
        const ctxRes = await ApiClient.getDashboardContext();
        if (ctxRes?.success && ctxRes.data) {
          const ctx = ctxRes.data;
          setDashboardContext(ctx);

          const perms = new Set();
          if (Array.isArray(ctx.roles)) {
            for (const r of ctx.roles) {
              if (Array.isArray(r.permissions)) {
                for (const p of r.permissions) {
                  perms.add(p);
                }
              }
            }
          }
          if (Array.isArray(ctx.permissions)) {
            for (const p of ctx.permissions) {
              perms.add(p);
            }
          }
          setPermissions(perms);

          const tabs = new Set();
          if (Array.isArray(ctx.allowed_tabs)) {
            for (const t of ctx.allowed_tabs) {
              tabs.add(t);
            }
          }
          setAllowedTabs(tabs);
        }
      }

      // Fetch and apply the user's saved appearance & layout preferences BEFORE unlocking protected UI.
      try {
        const prefsRes = await ApiClient.getMyPreferences();
        window.dispatchEvent(new CustomEvent('sx_preferences_sync', {
          detail: {
            account: resolvedAccount,
            preferences: prefsRes?.success ? prefsRes.data : null,
          },
        }));
      } catch (prefErr) {
        console.warn('Could not load saved user preferences; using defaults:', prefErr);
        window.dispatchEvent(new CustomEvent('sx_preferences_sync', {
          detail: {
            account: resolvedAccount,
            preferences: null,
          },
        }));
      }

      setToken(activeToken);
      setAccount(resolvedAccount);
      return true;
    } catch (err) {
      if (err?.name === 'SessionExpiredError' || err?.status === 401) {
        logout();
      } else {
        console.warn('Failed to load user context:', err);
      }
      return false;
    } finally {
      setIsLoading(false);
    }
  }, [clearAuthState, logout]);

  const login = useCallback(async (email, password) => {
    const res = await ApiClient.login(email, password);
    if (res.success && res.data) {
      setIsLoading(true);
      await loadUserContext();
      return { success: true, account: res.data.account };
    }
    return { success: false, message: res.message || 'Login failed' };
  }, [loadUserContext]);

  useEffect(() => {
    const handleLogoutEvent = (event) => {
      if (event?.detail?.source === 'auth') return;
      clearAuthState();
      setIsLoading(false);
    };
    const handlePermDenied = () => {
      if (ApiClient.getAccessToken()) {
        loadUserContext();
      }
    };

    window.addEventListener('sx_logout', handleLogoutEvent);
    window.addEventListener('sx_permission_denied', handlePermDenied);

    loadUserContext();

    return () => {
      window.removeEventListener('sx_logout', handleLogoutEvent);
      window.removeEventListener('sx_permission_denied', handlePermDenied);
    };
  }, [clearAuthState, loadUserContext]);

  return (
    <AuthContext.Provider
      value={{
        account,
        token,
        isAuthenticated: Boolean(token && account),
        isPlatformAdmin,
        isOrgAdmin,
        dashboardContext,
        permissions,
        allowedTabs,
        hasPermission,
        isLoading,
        login,
        logout,
        refreshProfile: loadUserContext,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
