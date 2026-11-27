import React from 'react';

export default function PageLoader({ label = 'Loading view...', compact = false }) {
  return (
    <div
      className="lg-glass-card"
      role="status"
      aria-live="polite"
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '0.75rem',
        minHeight: compact ? '140px' : '240px',
        padding: compact ? '1.25rem' : '2rem',
        color: 'var(--text-secondary)',
      }}
    >
      <div className="spinner" />
      <span style={{ fontSize: '0.85rem', fontWeight: 500 }}>{label}</span>
    </div>
  );
}
