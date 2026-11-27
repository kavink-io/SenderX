import React from 'react';

export default function AuthLoadingScreen({ message = 'Loading workspace...' }) {
  return (
    <div
      className="auth-loading-screen"
      role="status"
      aria-live="polite"
      style={{
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '0.9rem',
        background: 'var(--bg-primary)',
        color: 'var(--text-secondary)',
      }}
    >
      <div
        className="brand-logo"
        style={{
          width: '44px',
          height: '44px',
          fontSize: '1.05rem',
        }}
      >
        SX
      </div>
      <div className="spinner" />
      <p style={{ margin: 0, fontSize: '0.88rem', fontWeight: 500 }}>{message}</p>
    </div>
  );
}
