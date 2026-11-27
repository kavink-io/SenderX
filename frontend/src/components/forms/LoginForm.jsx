import React, { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import { getSafeRedirectPath } from '../../utils/authRedirect';

export default function LoginForm({ onForgotClick, onActivateClick }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const { login } = useAuth();
  const { showToast } = useToast();
  const navigate = useNavigate();
  const location = useLocation();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      const trimmedEmail = email.trim().toLowerCase();
      const res = await login(trimmedEmail, password);
      if (res.success) {
        showToast('Signed in successfully!', 'success');
        const destination = getSafeRedirectPath(location.state?.from, res.account);
        navigate(destination, { replace: true });
      } else {
        setError(res.message || 'Invalid email or password.');
      }
    } catch (err) {
      setError(err?.message || 'Connection error. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div id="login-container">
      <form id="login-form" onSubmit={handleSubmit}>
        {error && (
          <div id="login-error" className="error-msg" style={{ display: 'block', marginBottom: '1rem' }}>
            {error}
          </div>
        )}

        <div className="form-group">
          <label htmlFor="login-email">Email Address</label>
          <input
            type="email"
            id="login-email"
            className="form-control"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="admin@example.com"
            required
            autoComplete="username"
          />
        </div>

        <div className="form-group">
          <label htmlFor="login-password">Password</label>
          <input
            type="password"
            id="login-password"
            className="form-control"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            required
            autoComplete="current-password"
          />
        </div>

        <button
          type="submit"
          className="btn btn-primary"
          style={{ width: '100%', marginTop: '1rem', padding: '0.75rem' }}
          disabled={isLoading}
        >
          {isLoading ? 'Signing In...' : 'Sign In'}
        </button>

        <div id="auth-login-links" className="auth-login-links" style={{ display: 'flex', justifyContent: 'space-between', marginTop: '1.25rem', fontSize: '0.85rem' }}>
          <button
            type="button"
            id="link-forgot-password"
            className="btn-link"
            onClick={onForgotClick}
            style={{ background: 'none', border: 'none', color: 'var(--accent-blue)', cursor: 'pointer', padding: 0 }}
          >
            Forgot password?
          </button>
          <button
            type="button"
            id="link-activate-account"
            className="btn-link"
            onClick={onActivateClick}
            style={{ background: 'none', border: 'none', color: 'var(--accent-cyan)', cursor: 'pointer', padding: 0 }}
          >
            Activate account
          </button>
        </div>
      </form>
    </div>
  );
}
