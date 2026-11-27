import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import ApiClient from '../services/api';
import { DEFAULT_ACCENT_COLOR, normalizeHexColor } from '../utils/colorUtils';

const ThemeContext = createContext();

export const DEFAULT_PREFERENCES = {
  themeMode: 'light',
  accentColor: DEFAULT_ACCENT_COLOR,
  fontFamily: 'inter',
  fontScale: 'medium',
  direction: 'ltr',
  navigationLayout: 'vertical',
  sidebarMode: 'expanded',
  sidebarPosition: 'fixed',
  sidebarCollapsible: true,
  density: 'comfortable',
};

const FONT_FAMILY_STACKS = {
  inter: "'Inter', 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif",
  system: "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
  mono: "var(--font-mono, 'JetBrains Mono', ui-monospace, monospace)",
};

function applyAccentCssVariables(root, color) {
  const safeColor = normalizeHexColor(color) || DEFAULT_ACCENT_COLOR;
  root.style.setProperty('--accent-blue', safeColor);
  root.style.setProperty('--accent-primary', safeColor);
  root.style.setProperty('--accent-cyan', safeColor);
  root.style.setProperty('--accent-hover', safeColor);
  root.style.setProperty('--accent-gradient', `linear-gradient(135deg, ${safeColor} 0%, ${safeColor} 100%)`);
  root.style.setProperty('--lg-accent', safeColor);
  root.style.setProperty('--lg-accent-cyan', safeColor);
  root.style.setProperty('--lg-accent-border', `${safeColor}55`);
  root.style.setProperty('--lg-accent-soft', `${safeColor}30`);
}

function accountStorageKey(account) {
  if (!account) return null;
  const userId = account.user_id || account.admin_id || account.id;
  if (!userId) return null;
  const orgId = account.organization_id || 'platform';
  return `senderx_prefs_${orgId}_${userId}`;
}

function normalizeClientPreferences(raw) {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    return { ...DEFAULT_PREFERENCES };
  }

  // Support either nested backend DTO ({ appearance, layout }) or flat client state.
  const app = raw.appearance && typeof raw.appearance === 'object' ? raw.appearance : raw;
  const layout = raw.layout && typeof raw.layout === 'object' ? raw.layout : raw;

  const themeModeRaw = app.theme_mode ?? app.themeMode;
  const accentRaw = app.accent_color ?? app.accentColor;
  const fontFamilyRaw = app.font_family ?? app.fontFamily;
  const fontScaleRaw = app.font_scale ?? app.fontScale;

  const directionRaw = layout.direction;
  const navLayoutRaw = layout.navigation_layout ?? layout.navigationLayout;
  const sidebarModeRaw = layout.sidebar_mode ?? layout.sidebarMode;
  const sidebarPosRaw = layout.sidebar_position ?? layout.sidebarPosition;
  const sidebarCollapsibleRaw = layout.sidebar_collapsible ?? layout.sidebarCollapsible;
  const densityRaw = layout.density;

  return {
    themeMode: ['light', 'dark', 'system'].includes(themeModeRaw) ? themeModeRaw : DEFAULT_PREFERENCES.themeMode,
    accentColor: normalizeHexColor(accentRaw) || DEFAULT_PREFERENCES.accentColor,
    fontFamily: ['inter', 'system', 'mono'].includes(fontFamilyRaw) ? fontFamilyRaw : DEFAULT_PREFERENCES.fontFamily,
    fontScale: ['small', 'medium', 'large'].includes(fontScaleRaw) ? fontScaleRaw : DEFAULT_PREFERENCES.fontScale,
    direction: directionRaw === 'rtl' ? 'rtl' : 'ltr',
    navigationLayout: ['vertical', 'horizontal', 'compact', 'mini'].includes(navLayoutRaw)
      ? navLayoutRaw
      : DEFAULT_PREFERENCES.navigationLayout,
    sidebarMode: sidebarModeRaw === 'collapsed' ? 'collapsed' : 'expanded',
    sidebarPosition: sidebarPosRaw === 'sticky' ? 'sticky' : 'fixed',
    sidebarCollapsible: typeof sidebarCollapsibleRaw === 'boolean'
      ? sidebarCollapsibleRaw
      : DEFAULT_PREFERENCES.sidebarCollapsible,
    density: ['compact', 'comfortable', 'spacious'].includes(densityRaw)
      ? densityRaw
      : DEFAULT_PREFERENCES.density,
  };
}

export function toBackendPreferencesPayload(prefs) {
  const normalized = normalizeClientPreferences(prefs);
  return {
    appearance: {
      theme_mode: normalized.themeMode,
      accent_color: normalized.accentColor,
      font_family: normalized.fontFamily,
      font_scale: normalized.fontScale,
    },
    layout: {
      direction: normalized.direction,
      navigation_layout: normalized.navigationLayout,
      sidebar_mode: normalized.sidebarMode,
      sidebar_position: normalized.sidebarPosition,
      sidebar_collapsible: normalized.sidebarCollapsible,
      density: normalized.density,
    },
  };
}

function clearSharedLegacyPreferenceStorage() {
  try {
    localStorage.removeItem('senderx_preferences');
    localStorage.removeItem('senderx_theme');
  } catch {
    // Ignore storage access errors
  }
}

function readInitialPreferences() {
  clearSharedLegacyPreferenceStorage();
  try {
    const account = ApiClient.getStoredAccount();
    const key = accountStorageKey(account);
    if (key && ApiClient.getAccessToken()) {
      const cached = localStorage.getItem(key);
      if (cached) {
        return normalizeClientPreferences(JSON.parse(cached));
      }
    }
  } catch {
    // Fallback to clean defaults
  }
  return { ...DEFAULT_PREFERENCES };
}

export function ThemeProvider({ children }) {
  const [preferences, setPreferences] = useState(readInitialPreferences);
  const [activeAccountKey, setActiveAccountKey] = useState(() => (
    ApiClient.getAccessToken() ? accountStorageKey(ApiClient.getStoredAccount()) : null
  ));
  const [saveStatus, setSaveStatus] = useState('idle'); // 'idle' | 'saving' | 'saved' | 'error'
  const [systemDark, setSystemDark] = useState(() =>
    typeof window !== 'undefined' ? window.matchMedia('(prefers-color-scheme: dark)').matches : false
  );

  const debounceTimerRef = useRef(null);
  const pendingPayloadRef = useRef(null);
  const preferencesRef = useRef(preferences);
  const activeAccountKeyRef = useRef(activeAccountKey);
  preferencesRef.current = preferences;
  activeAccountKeyRef.current = activeAccountKey;

  const theme = preferences.themeMode === 'system'
    ? (systemDark ? 'dark' : 'light')
    : preferences.themeMode;

  useEffect(() => {
    if (preferences.themeMode !== 'system' || typeof window === 'undefined') return undefined;
    const media = window.matchMedia('(prefers-color-scheme: dark)');
    const onChange = (event) => setSystemDark(event.matches);
    setSystemDark(media.matches);
    media.addEventListener?.('change', onChange);
    return () => media.removeEventListener?.('change', onChange);
  }, [preferences.themeMode]);

  useEffect(() => {
    const root = document.documentElement;
    try {
      root.setAttribute('data-theme', theme);
      root.setAttribute('dir', preferences.direction);
      root.setAttribute('data-navigation-layout', preferences.navigationLayout);
      root.setAttribute('data-sidebar-mode', preferences.sidebarMode);
      root.setAttribute('data-sidebar-position', preferences.sidebarPosition);
      root.setAttribute('data-sidebar-collapsible', String(preferences.sidebarCollapsible));
      root.setAttribute('data-density', preferences.density);
      root.setAttribute('data-font-family', preferences.fontFamily);
      root.setAttribute('data-font-scale', preferences.fontScale);
      root.style.setProperty('--font-sans', FONT_FAMILY_STACKS[preferences.fontFamily] || FONT_FAMILY_STACKS.inter);
      applyAccentCssVariables(root, preferences.accentColor);

      clearSharedLegacyPreferenceStorage();
      if (activeAccountKey && ApiClient.getAccessToken()) {
        localStorage.setItem(activeAccountKey, JSON.stringify(preferences));
      }
    } catch (error) {
      console.error('Failed to apply appearance preferences:', error);
    }
  }, [theme, preferences, activeAccountKey]);

  const flushBackendSave = useCallback(async (overridePrefs = null, usePut = false) => {
    if (debounceTimerRef.current) {
      window.clearTimeout(debounceTimerRef.current);
      debounceTimerRef.current = null;
    }

    if (!ApiClient.getAccessToken() || !activeAccountKeyRef.current) {
      return { success: true };
    }

    const expectedKey = activeAccountKeyRef.current;
    const payload = toBackendPreferencesPayload(overridePrefs || preferencesRef.current);
    pendingPayloadRef.current = null;

    setSaveStatus('saving');
    try {
      const res = usePut
        ? await ApiClient.replaceMyPreferences(payload)
        : await ApiClient.updateMyPreferences(payload);
      if (!res?.success) {
        if (activeAccountKeyRef.current === expectedKey) setSaveStatus('error');
        return { success: false, message: res?.message || 'Failed to save preferences' };
      }
      if (activeAccountKeyRef.current === expectedKey) {
        if (res.data) {
          const synced = normalizeClientPreferences(res.data);
          setPreferences(synced);
          localStorage.setItem(expectedKey, JSON.stringify(synced));
        }
        setSaveStatus('saved');
      }
      return { success: true, data: res.data };
    } catch (error) {
      if (activeAccountKeyRef.current === expectedKey) setSaveStatus('error');
      return { success: false, message: error?.message || 'Could not save preferences' };
    }
  }, []);

  const scheduleBackendSave = useCallback((nextPrefs) => {
    if (!ApiClient.getAccessToken() || !activeAccountKeyRef.current) return;
    pendingPayloadRef.current = nextPrefs;
    if (debounceTimerRef.current) {
      window.clearTimeout(debounceTimerRef.current);
    }
    setSaveStatus('saving');
    debounceTimerRef.current = window.setTimeout(() => {
      debounceTimerRef.current = null;
      const pending = pendingPayloadRef.current;
      pendingPayloadRef.current = null;
      if (pending) {
        flushBackendSave(pending, false);
      }
    }, 280);
  }, [flushBackendSave]);

  useEffect(() => {
    const handleSync = (event) => {
      if (debounceTimerRef.current) {
        window.clearTimeout(debounceTimerRef.current);
        debounceTimerRef.current = null;
      }
      pendingPayloadRef.current = null;
      const { account, preferences: serverData } = event.detail || {};
      const key = accountStorageKey(account);
      const next = normalizeClientPreferences(serverData);
      setActiveAccountKey(key);
      setPreferences(next);
      setSaveStatus('idle');
      if (key) {
        try {
          localStorage.setItem(key, JSON.stringify(next));
        } catch {
          // Ignore storage error
        }
      }
    };

    const handleLogout = () => {
      if (debounceTimerRef.current) {
        window.clearTimeout(debounceTimerRef.current);
        debounceTimerRef.current = null;
      }
      pendingPayloadRef.current = null;
      clearSharedLegacyPreferenceStorage();
      if (activeAccountKeyRef.current) {
        try {
          localStorage.removeItem(activeAccountKeyRef.current);
        } catch {
          // Ignore
        }
      }
      setActiveAccountKey(null);
      setPreferences({ ...DEFAULT_PREFERENCES });
      setSaveStatus('idle');
    };

    window.addEventListener('sx_preferences_sync', handleSync);
    window.addEventListener('sx_logout', handleLogout);
    return () => {
      window.removeEventListener('sx_preferences_sync', handleSync);
      window.removeEventListener('sx_logout', handleLogout);
    };
  }, []);

  const updatePreferences = useCallback((patch) => {
    setPreferences((current) => {
      const next = normalizeClientPreferences({ ...current, ...patch });
      scheduleBackendSave(next);
      return next;
    });
  }, [scheduleBackendSave]);

  const resetPreferences = useCallback(async () => {
    const defaults = { ...DEFAULT_PREFERENCES };
    setPreferences(defaults);
    return await flushBackendSave(defaults, true);
  }, [flushBackendSave]);

  const savePreferencesNow = useCallback(async () => {
    return await flushBackendSave(preferencesRef.current, true);
  }, [flushBackendSave]);

  const previewAccentColor = useCallback((color) => {
    const normalized = normalizeHexColor(color);
    if (!normalized) return;
    applyAccentCssVariables(document.documentElement, normalized);
  }, []);

  const clearAccentPreview = useCallback(() => {
    applyAccentCssVariables(document.documentElement, preferencesRef.current.accentColor);
  }, []);

  const toggleTheme = useCallback(() => {
    updatePreferences({ themeMode: theme === 'light' ? 'dark' : 'light' });
  }, [theme, updatePreferences]);

  return (
    <ThemeContext.Provider
      value={{
        theme,
        themeMode: preferences.themeMode,
        preferences,
        saveStatus,
        updatePreferences,
        previewAccentColor,
        clearAccentPreview,
        savePreferencesNow,
        resetPreferences,
        toggleTheme,
        isDark: theme === 'dark',
      }}
    >
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
}
