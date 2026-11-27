import React, { useEffect, useState } from 'react';
import { useTheme } from '../../context/ThemeContext';
import { useToast } from '../../context/ToastContext';
import { GlassCard } from '../glass';

const PALETTES = [
  ['Indigo', '#4f46e5'], ['Violet', '#7c3aed'], ['Blue', '#2563eb'],
  ['Cyan', '#0891b2'], ['Teal', '#0d9488'], ['Emerald', '#059669'],
  ['Green', '#16a34a'], ['Amber', '#d97706'], ['Orange', '#ea580c'],
  ['Rose', '#e11d48'], ['Red', '#dc2626'],
];

function normalizeHex(value) {
  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  const candidate = trimmed.startsWith('#') ? trimmed : `#${trimmed}`;
  return /^#[0-9a-f]{6}$/i.test(candidate) ? candidate.toUpperCase() : null;
}

export default function AppearanceSettings() {
  const { preferences, updatePreferences, resetPreferences, themeMode } = useTheme();
  const { showToast } = useToast();
  const [hex, setHex] = useState(preferences.accentColor || '#635bdb');
  const [hexError, setHexError] = useState(false);

  useEffect(() => {
    setHex(preferences.accentColor || '#635bdb');
    setHexError(false);
  }, [preferences.accentColor]);

  const applyHex = (value) => {
    setHex(value);
    const color = normalizeHex(value);
    if (color) {
      setHex(color);
      setHexError(false);
      updatePreferences({ accentColor: color });
    }
  };

  const optionStyle = (active) => ({
    border: `1px solid ${active ? 'var(--accent-blue)' : 'var(--glass-border)'}`,
    boxShadow: active ? '0 0 0 2px var(--lg-accent-soft)' : 'none',
  });
  const currentAccent = normalizeHex(preferences.accentColor) || '#635bdb';

  const savePreferences = () => {
    try {
      localStorage.setItem('senderx_preferences', JSON.stringify(preferences));
      showToast('Appearance preferences saved', 'success');
    } catch (error) {
      console.error('Failed to save appearance preferences:', error);
      showToast('Could not save appearance preferences', 'error');
    }
  };

  return (
    <div className="appearance-settings">
      <div className="appearance-settings-grid">
        <GlassCard>
          <h3 className="settings-section-title">Theme</h3>
          <div className="appearance-choice-row">
            {['light', 'dark', 'system'].map((mode) => (
              <button
                type="button"
                key={mode}
                className="appearance-choice"
                style={optionStyle(themeMode === mode)}
                onClick={() => updatePreferences({ themeMode: mode })}
              >
                {mode[0].toUpperCase() + mode.slice(1)}
              </button>
            ))}
          </div>
        </GlassCard>

        <GlassCard>
          <h3 className="settings-section-title">Accent Color</h3>
          <div className="palette-grid" role="group" aria-label="Preset accent colors">
            {PALETTES.map(([name, color]) => {
              const selected = currentAccent.toLowerCase() === color.toLowerCase();
              return (
                <button
                  type="button"
                  key={name}
                  className={`palette-swatch${selected ? ' is-selected' : ''}`}
                  title={`${name}${selected ? ' (selected)' : ''}`}
                  aria-label={`${name}${selected ? ', selected' : ''}`}
                  aria-pressed={selected}
                  onClick={() => {
                    setHex(color);
                    setHexError(false);
                    updatePreferences({ accentColor: color });
                  }}
                  style={{ '--swatch-color': color }}
                >
                  <svg viewBox="0 0 16 16" aria-hidden="true">
                    <path d="m3.5 8.2 2.8 2.7 6.2-6.1" />
                  </svg>
                </button>
              );
            })}
          </div>
          <div className="hex-control">
            <input
              className="form-control"
              type="text"
              value={hex}
              maxLength={7}
              placeholder="#2563EB"
              spellCheck="false"
              aria-label="Custom HEX color"
              aria-invalid={hexError}
              aria-describedby={hexError ? 'accent-hex-error' : undefined}
              onChange={(e) => applyHex(e.target.value)}
              onBlur={() => setHexError(!normalizeHex(hex))}
            />
            <label className="color-picker-control" title="Choose any accent color">
              <input
                type="color"
                value={currentAccent}
                aria-label="Choose custom accent color"
                onChange={(e) => applyHex(e.target.value)}
              />
              <span className="color-preview" style={{ background: currentAccent }} />
            </label>
          </div>
          {hexError && <p className="accent-color-error" id="accent-hex-error" role="alert">Enter a valid 6-digit HEX color.</p>}
        </GlassCard>

        <GlassCard>
          <h3 className="settings-section-title">Layout Direction</h3>
          <div className="appearance-choice-row">
            {['ltr', 'rtl'].map((direction) => (
              <button
                type="button"
                key={direction}
                className="appearance-choice"
                style={optionStyle(preferences.direction === direction)}
                onClick={() => updatePreferences({ direction })}
              >
                {direction.toUpperCase()}
              </button>
            ))}
          </div>
        </GlassCard>

        <GlassCard>
          <h3 className="settings-section-title">Navigation Layout</h3>
          <select
            className="form-control"
            value={preferences.navigationLayout}
            onChange={(e) => updatePreferences({ navigationLayout: e.target.value })}
          >
            <option value="vertical">Vertical Sidebar</option>
            <option value="horizontal">Horizontal Navigation</option>
          </select>
        </GlassCard>

        <GlassCard>
          <h3 className="settings-section-title">Sidebar</h3>
          <div className="appearance-choice-row">
            {['collapsed', 'expanded'].map((mode) => (
              <button type="button" key={mode} className="appearance-choice" style={optionStyle(preferences.sidebarMode === mode)} onClick={() => updatePreferences({ sidebarMode: mode })}>
                {mode[0].toUpperCase() + mode.slice(1)}
              </button>
            ))}
          </div>
          <label className="appearance-setting-label">
            Sidebar behavior
            <select className="form-control" value={preferences.sidebarPosition} onChange={(e) => updatePreferences({ sidebarPosition: e.target.value })}>
              <option value="fixed">Fixed</option>
              <option value="sticky">Sticky</option>
            </select>
          </label>
          <label className="appearance-setting-toggle">
            <span>Allow sidebar collapse</span>
            <input type="checkbox" checked={preferences.sidebarCollapsible} onChange={(e) => updatePreferences({ sidebarCollapsible: e.target.checked })} />
          </label>
        </GlassCard>
      </div>
      <div className="appearance-settings-actions">
        <button type="button" className="btn btn-secondary" onClick={resetPreferences}>Reset to Defaults</button>
        <button type="button" className="btn btn-primary" onClick={savePreferences}>Save Preferences</button>
      </div>
      <GlassCard className="appearance-preview-card">
        <h3 className="settings-section-title">Live Preview</h3>
        <div className="appearance-preview">
          <aside>
            <span className="appearance-preview-logo">S</span>
            <span className="appearance-preview-active">Dashboard</span>
            <span>Messages</span>
            <span>Analytics</span>
          </aside>
          <div className="appearance-preview-main">
            <header><span>SenderX&nbsp; › &nbsp;Overview</span><button type="button">Search here</button></header>
            <div className="appearance-preview-cards">
              <div><small>Total Messages</small><strong>—</strong></div>
              <div><small>Delivered</small><strong>—</strong></div>
              <div><small>Failed</small><strong>—</strong></div>
            </div>
            <div className="appearance-preview-table"><span>Recent message activity</span><span className="appearance-preview-button">Open dashboard</span></div>
          </div>
        </div>
      </GlassCard>
    </div>
  );
}
