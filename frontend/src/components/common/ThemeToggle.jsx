import React from 'react';
import { useTheme } from '../../context/ThemeContext';
import { GlassDropdown } from '../glass';

export default function ThemeToggle() {
  const { isDark, themeMode, updatePreferences } = useTheme();
  const [isOpen, setIsOpen] = React.useState(false);
  const modes = [
    { key: 'light', label: 'Light', icon: '☼' },
    { key: 'dark', label: 'Dark', icon: '☾' },
    { key: 'system', label: 'System', icon: '◉' },
  ];

  return (
    <GlassDropdown
      isOpen={isOpen}
      onClose={() => setIsOpen(false)}
      menuStyle={{
        minWidth: 124,
        padding: 4,
        left: '50%',
        right: 'auto',
        transform: 'translateX(-50%)',
        transformOrigin: 'top center',
      }}
      trigger={
        <button
          id="theme-toggle"
          className="icon-btn"
          onClick={() => setIsOpen((open) => !open)}
          title="Choose theme"
          aria-label="Choose theme"
          aria-expanded={isOpen}
        >
          {isDark ? (
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
            </svg>
          ) : (
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <circle cx="12" cy="12" r="5" />
              <path d="M12 1v2m0 18v2M4.22 4.22l1.42 1.42m12.72 12.72 1.42 1.42M1 12h2m18 0h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
            </svg>
          )}
        </button>
      }
    >
      {modes.map((mode) => (
        <button
          type="button"
          key={mode.key}
          className={`lg-dropdown-item theme-menu-item ${themeMode === mode.key ? 'active' : ''}`}
          onClick={() => {
            updatePreferences({ themeMode: mode.key });
            setIsOpen(false);
          }}
        >
          <span aria-hidden="true">{mode.icon}</span>
          {mode.label}
        </button>
      ))}
    </GlassDropdown>
  );
}
