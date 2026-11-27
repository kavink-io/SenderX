import React, { useState, lazy, Suspense } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import LoginForm from '../../components/forms/LoginForm';
import ThemeToggle from '../../components/common/ThemeToggle';
import AuthLoadingScreen from '../../components/common/AuthLoadingScreen';
import PageLoader from '../../components/common/PageLoader';
import { useAuth } from '../../context/AuthContext';
import { getSafeRedirectPath } from '../../utils/authRedirect';

const AuthOtpFlow = lazy(() => import('../../components/forms/AuthOtpFlow'));

export default function AuthPage() {
  const [view, setView] = useState('LOGIN'); // 'LOGIN', 'FORGOT', 'ACTIVATE'
  const { isAuthenticated, isLoading, account } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return <AuthLoadingScreen message="Checking session..." />;
  }

  if (isAuthenticated) {
    const destination = getSafeRedirectPath(location.state?.from, account);
    return <Navigate to={destination} replace />;
  }

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
          <Suspense fallback={<PageLoader compact label="Loading verification..." />}>
            <AuthOtpFlow
              purpose="PASSWORD_RESET"
              onCancel={() => setView('LOGIN')}
              onSuccessDone={() => setView('LOGIN')}
            />
          </Suspense>
        )}

        {view === 'ACTIVATE' && (
          <Suspense fallback={<PageLoader compact label="Loading activation..." />}>
            <AuthOtpFlow
              purpose="ACTIVATION"
              onCancel={() => setView('LOGIN')}
              onSuccessDone={() => setView('LOGIN')}
            />
          </Suspense>
        )}
      </div>
    </div>
  );
}
