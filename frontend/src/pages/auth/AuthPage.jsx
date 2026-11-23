import React, { useState } from 'react';
import LoginForm from '../../components/forms/LoginForm';
import AuthOtpFlow from '../../components/forms/AuthOtpFlow';
import ThemeToggle from '../../components/common/ThemeToggle';

export default function AuthPage() {
  const [view, setView] = useState('LOGIN'); // 'LOGIN', 'FORGOT', 'ACTIVATE'

  return (
    <div id="auth-view" className="view active" style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative', padding: '1.5rem' }}>
      <div style={{ position: 'absolute', top: '1.5rem', right: '1.5rem' }}>
        <ThemeToggle />
      </div>

      <div className="auth-card card" style={{ width: '100%', maxWidth: '440px', padding: '2.25rem' }}>
        <div className="auth-header" style={{ textAlign: 'center', marginBottom: '2rem' }}>
          <div className="brand-logo" style={{ margin: '0 auto 1rem', width: '48px', height: '48px', fontSize: '1.2rem' }}>
            SX
          </div>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
            SenderX
          </h1>
          <p style={{ margin: '0.35rem 0 0', color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
            Multi-Tenant High-Throughput Notification Dispatcher
          </p>
        </div>

        {view === 'LOGIN' && (
          <LoginForm
            onForgotClick={() => setView('FORGOT')}
            onActivateClick={() => setView('ACTIVATE')}
          />
        )}

        {view === 'FORGOT' && (
          <AuthOtpFlow
            purpose="PASSWORD_RESET"
            onCancel={() => setView('LOGIN')}
            onSuccessDone={() => setView('LOGIN')}
          />
        )}

        {view === 'ACTIVATE' && (
          <AuthOtpFlow
            purpose="ACTIVATION"
            onCancel={() => setView('LOGIN')}
            onSuccessDone={() => setView('LOGIN')}
          />
        )}
      </div>
    </div>
  );
}
