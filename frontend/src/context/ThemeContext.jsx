import React, { createContext, useContext, useState, useEffect } from 'react';

const ThemeContext = createContext();

const DEFAULT_PREFERENCES = {
  themeMode: 'light',
  accentColor: '#635bdb',
  direction: 'ltr',
  navigationLayout: 'vertical',
  sidebarMode: 'expanded',
  sidebarPosition: 'fixed',
  sidebarCollapsible: true,
};

function readPreferences() {
  try {
    const stored = localStorage.getItem('senderx_preferences');
    if (stored) {
      const saved = JSON.parse(stored);
      if (!saved || typeof saved !== 'object' || Array.isArray(saved)) return DEFAULT_PREFERENCES;
      const preferences = { ...DEFAULT_PREFERENCES, ...saved };
      preferences.navigationLayout = saved.navigationLayout === 'horizontal' ? 'horizontal' : 'vertical';
      delete preferences.density;
      delete preferences.radius;
      return preferences;
    }
    const legacyTheme = localStorage.getItem('senderx_theme');
    return {
      ...DEFAULT_PREFERENCES,
      themeMode: legacyTheme === 'light' || legacyTheme === 'dark' ? legacyTheme : DEFAULT_PREFERENCES.themeMode,
    };
  } catch {
    return DEFAULT_PREFERENCES;
  }
}

export function ThemeProvider({ children }) {
  const [preferences, setPreferences] = useState(readPreferences);
  const [systemDark, setSystemDark] = useState(() =>
    typeof window !== 'undefined' ? window.matchMedia('(prefers-color-scheme: dark)').matches : false
  );

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
      root.style.setProperty('--accent-blue', preferences.accentColor);
      root.style.setProperty('--accent-primary', preferences.accentColor);
      root.style.setProperty('--accent-cyan', preferences.accentColor);
      root.style.setProperty('--accent-hover', preferences.accentColor);
      root.style.setProperty('--accent-gradient', `linear-gradient(135deg, ${preferences.accentColor} 0%, ${preferences.accentColor} 100%)`);
      root.style.setProperty('--lg-accent', preferences.accentColor);
      root.style.setProperty('--lg-accent-border', `${preferences.accentColor}55`);
      root.style.setProperty('--lg-accent-soft', `${preferences.accentColor}30`);
      localStorage.setItem('senderx_preferences', JSON.stringify(preferences));
      localStorage.setItem('senderx_theme', theme);
    } catch (error) {
      console.error('Failed to apply appearance preferences:', error);
    }
  }, [theme, preferences]);

  const updatePreferences = (patch) => {
    setPreferences((current) => {
      const next = { ...current, ...patch };
      if (Object.prototype.hasOwnProperty.call(patch, 'navigationLayout')) {
        next.navigationLayout = patch.navigationLayout === 'horizontal' ? 'horizontal' : 'vertical';
      }
      delete next.density;
      delete next.radius;
      return next;
    });
  };

  const toggleTheme = () => {
    setPreferences((current) => ({
      ...current,
      themeMode: theme === 'light' ? 'dark' : 'light',
    }));
  };

  return (
    <ThemeContext.Provider
      value={{
        theme,
        themeMode: preferences.themeMode,
        preferences,
        updatePreferences,
        resetPreferences: () => setPreferences(DEFAULT_PREFERENCES),
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
