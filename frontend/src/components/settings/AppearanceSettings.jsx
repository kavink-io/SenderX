import React from 'react';
import { useTheme } from '../../context/ThemeContext';
import { useToast } from '../../context/ToastContext';
import { GlassCard } from '../glass';
import AccentColorPicker from './AccentColorPicker';
import { DEFAULT_ACCENT_COLOR } from '../../utils/colorUtils';

export default function AppearanceSettings() {
  const {
    preferences,
    saveStatus,
    updatePreferences,
    previewAccentColor,
    clearAccentPreview,
    savePreferencesNow,
    resetPreferences,
    themeMode,
  } = useTheme();
  const { showToast } = useToast();

  const optionStyle = (active) => ({
    border: `1px solid ${active ? 'var(--accent-blue)' : 'var(--glass-border)'}`,
    boxShadow: active ? '0 0 0 2px var(--lg-accent-soft)' : 'none',
  });

  const handleSave = async () => {
    const res = await savePreferencesNow();
    if (res?.success) {
      showToast('Appearance & layout preferences saved', 'success');
    } else {
      showToast(res?.message || 'Could not save appearance preferences', 'error');
    }
  };

  const handleReset = async () => {
    const res = await resetPreferences();
    if (res?.success) {
      showToast('Preferences reset to defaults', 'info');
    } else {
      showToast(res?.message || 'Could not reset appearance preferences', 'error');
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
          <AccentColorPicker
            value={preferences.accentColor}
            defaultColor={DEFAULT_ACCENT_COLOR}
            direction={preferences.direction}
            onChange={(color) => updatePreferences({ accentColor: color })}
            onPreviewChange={previewAccentColor}
            onPreviewClear={clearAccentPreview}
          />
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
          <label className="appearance-setting-label">
            Layout density
            <select
              className="form-control"
              value={preferences.density}
              onChange={(e) => updatePreferences({ density: e.target.value })}
            >
              <option value="compact">Compact</option>
              <option value="comfortable">Comfortable</option>
              <option value="spacious">Spacious</option>
            </select>
          </label>
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
          <label className="appearance-setting-label">
            Typography
            <select
              className="form-control"
              value={preferences.fontFamily}
              onChange={(e) => updatePreferences({ fontFamily: e.target.value })}
            >
              <option value="inter">Inter (Default)</option>
              <option value="system">System UI</option>
              <option value="mono">Monospace UI</option>
            </select>
          </label>
          <div className="appearance-choice-row" style={{ marginTop: 10 }}>
            {['small', 'medium', 'large'].map((scale) => (
              <button
                type="button"
                key={scale}
                className="appearance-choice"
                style={optionStyle(preferences.fontScale === scale)}
                onClick={() => updatePreferences({ fontScale: scale })}
              >
                {scale[0].toUpperCase() + scale.slice(1)}
              </button>
            ))}
          </div>
        </GlassCard>

        <GlassCard>
          <h3 className="settings-section-title">Sidebar</h3>
          <div className="appearance-choice-row">
            {['collapsed', 'expanded'].map((mode) => (
              <button
                type="button"
                key={mode}
                className="appearance-choice"
                style={optionStyle(preferences.sidebarMode === mode)}
                onClick={() => updatePreferences({ sidebarMode: mode })}
              >
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
        {saveStatus !== 'idle' && (
          <span
            className={`appearance-save-status is-${saveStatus}`}
            role="status"
            aria-live="polite"
          >
            {saveStatus === 'saving'
              ? 'Saving to account...'
              : saveStatus === 'saved'
                ? 'Saved to account'
                : 'Sync error — retry save'}
          </span>
        )}
        <button type="button" className="btn btn-secondary" onClick={handleReset} disabled={saveStatus === 'saving'}>
          Reset to Defaults
        </button>
        <button type="button" className="btn btn-primary" onClick={handleSave} disabled={saveStatus === 'saving'}>
          {saveStatus === 'saving' ? 'Saving...' : 'Save Preferences'}
        </button>
      </div>
    </div>
  );
}
