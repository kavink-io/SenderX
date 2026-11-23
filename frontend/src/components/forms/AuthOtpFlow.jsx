import React, { useState, useEffect, useRef } from 'react';
import ApiClient from '../../services/api';
import { useToast } from '../../context/ToastContext';

export default function AuthOtpFlow({ purpose, onCancel, onSuccessDone }) {
  const [step, setStep] = useState('EMAIL'); // EMAIL, CODE, PASSWORD, SUCCESS
  const [email, setEmail] = useState('');
  const [digits, setDigits] = useState(['', '', '', '', '', '']);
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [resetToken, setResetToken] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [expirySeconds, setExpirySeconds] = useState(600); // 10 min
  const [resendSeconds, setResendSeconds] = useState(60); // 60s
  const [successMessage, setSuccessMessage] = useState('');

  const digitRefs = [useRef(), useRef(), useRef(), useRef(), useRef(), useRef()];
  const { showToast } = useToast();

  // Timer effect for code countdown
  useEffect(() => {
    if (step !== 'CODE') return;

    const timer = setInterval(() => {
      setExpirySeconds((prev) => (prev > 0 ? prev - 1 : 0));
      setResendSeconds((prev) => (prev > 0 ? prev - 1 : 0));
    }, 1000);

    return () => clearInterval(timer);
  }, [step]);

  const formatTime = (secs) => {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  };

  const validatePassword = (pwd) => ({
    length: pwd.length >= 8,
    upper: /[A-Z]/.test(pwd),
    lower: /[a-z]/.test(pwd),
    number: /[0-9]/.test(pwd),
    symbol: /[^A-Za-z0-9]/.test(pwd),
  });

  const pwdRules = validatePassword(password);
  const isPwdValid = Object.values(pwdRules).every(Boolean);

  // Step 1: Request OTP code
  const handleRequestCode = async (isResend = false) => {
    setError('');
    setIsLoading(true);

    try {
      const cleanEmail = email.trim().toLowerCase();
      const res = purpose === 'ACTIVATION'
        ? await ApiClient.requestActivationOtp(cleanEmail)
        : await ApiClient.requestPasswordResetOtp(cleanEmail);

      if (res.success) {
        setExpirySeconds(600);
        setResendSeconds(60);
        setStep('CODE');
        setDigits(['', '', '', '', '', '']);
        showToast('Verification code sent to your email', 'info');
        setTimeout(() => digitRefs[0].current?.focus(), 100);
      } else {
        setError(res.message || 'Could not send verification code.');
        if (isResend && res.retry_after) {
          setResendSeconds(Number(res.retry_after));
        }
      }
    } catch (err) {
      setError(err?.message || 'Connection error. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  // Digit input handler
  const handleDigitChange = (index, value) => {
    const clean = value.replace(/\D/g, '');
    if (!clean) {
      const next = [...digits];
      next[index] = '';
      setDigits(next);
      return;
    }

    if (clean.length > 1) {
      // Pasted multiple digits
      const next = [...digits];
      clean.slice(0, 6).split('').forEach((d, i) => {
        if (index + i < 6) next[index + i] = d;
      });
      setDigits(next);
      const focusIndex = Math.min(index + clean.length, 5);
      digitRefs[focusIndex].current?.focus();
    } else {
      const next = [...digits];
      next[index] = clean;
      setDigits(next);
      if (index < 5) {
        digitRefs[index + 1].current?.focus();
      }
    }
  };

  const handleDigitKeyDown = (index, e) => {
    if (e.key === 'Backspace' && !digits[index] && index > 0) {
      digitRefs[index - 1].current?.focus();
    }
  };

  // Step 2: Verify Code
  const handleVerifyCode = async (e) => {
    e.preventDefault();
    const code = digits.join('');
    if (code.length !== 6) {
      setError('Please enter all 6 digits.');
      return;
    }

    setError('');
    setIsLoading(true);

    try {
      const res = await ApiClient.verifyOtp(email.trim().toLowerCase(), purpose, code);
      if (res.success && res.data?.reset_token) {
        setResetToken(res.data.reset_token);
        setStep('PASSWORD');
      } else {
        setError(res.message || 'Invalid or expired code.');
      }
    } catch (err) {
      setError(err?.message || 'Verification error. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  // Step 3: Set New Password
  const handleSetPassword = async (e) => {
    e.preventDefault();
    if (!isPwdValid) {
      setError('Please meet all password requirements.');
      return;
    }

    setError('');
    setIsLoading(true);

    try {
      const res = await ApiClient.setPasswordWithOtp(purpose, resetToken, password);
      if (res.success) {
        setSuccessMessage(res.message || (purpose === 'ACTIVATION' ? 'Account activated successfully!' : 'Password reset successfully!'));
        setStep('SUCCESS');
      } else {
        setError(res.message || 'Could not set password. Please restart the process.');
      }
    } catch (err) {
      setError(err?.message || 'Error updating password.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div id="auth-otp-flow" className="auth-otp-box">
      <div className="otp-header" style={{ marginBottom: '1.25rem', textAlign: 'center' }}>
        <h3 id="otp-flow-title" style={{ fontSize: '1.25rem', marginBottom: '0.35rem', color: 'var(--text-primary)' }}>
          {purpose === 'ACTIVATION' ? 'Activate your account' : 'Reset your password'}
        </h3>
        <p id="otp-flow-description" style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
          {step === 'EMAIL' && (purpose === 'ACTIVATION'
            ? 'Enter your work email to receive a one-time activation code.'
            : 'Enter your account email. If it is eligible, we will send a one-time reset code.')}
          {step === 'CODE' && `Enter the 6-digit code sent to ${email}`}
          {step === 'PASSWORD' && 'Create a strong new password for your account.'}
          {step === 'SUCCESS' && 'Operation completed successfully.'}
        </p>
      </div>

      {error && (
        <div className="error-msg" style={{ display: 'block', marginBottom: '1rem' }}>
          {error}
        </div>
      )}

      {/* STEP 1: EMAIL */}
      {step === 'EMAIL' && (
        <form onSubmit={(e) => { e.preventDefault(); handleRequestCode(false); }}>
          <div className="form-group">
            <label htmlFor="otp-email">Account Email</label>
            <input
              type="email"
              id="otp-email"
              className="form-control"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="user@example.com"
              required
              autoFocus
            />
          </div>
          <button
            type="submit"
            id="btn-request-otp"
            className="btn btn-primary"
            style={{ width: '100%', marginTop: '1rem' }}
            disabled={isLoading || !email.trim()}
          >
            {isLoading ? 'Sending Code...' : 'Send Verification Code'}
          </button>
        </form>
      )}

      {/* STEP 2: CODE */}
      {step === 'CODE' && (
        <form onSubmit={handleVerifyCode} id="otp-code-form">
          <div style={{ display: 'flex', justifyContent: 'center', gap: '8px', margin: '1.5rem 0' }}>
            {digits.map((digit, idx) => (
              <input
                key={idx}
                ref={digitRefs[idx]}
                type="text"
                inputMode="numeric"
                maxLength={6}
                className="otp-digit"
                value={digit}
                onChange={(e) => handleDigitChange(idx, e.target.value)}
                onKeyDown={(e) => handleDigitKeyDown(idx, e)}
                style={{
                  width: '44px',
                  height: '52px',
                  textAlign: 'center',
                  fontSize: '1.25rem',
                  fontWeight: 600,
                  borderRadius: '8px',
                  border: '1px solid var(--glass-border)',
                  background: 'var(--bg-surface)',
                  color: 'var(--text-primary)',
                }}
              />
            ))}
          </div>

          <div style={{ textAlign: 'center', fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
            {expirySeconds > 0 ? (
              <span>Code expires in <strong>{formatTime(expirySeconds)}</strong></span>
            ) : (
              <span style={{ color: 'var(--status-error)' }}>Code expired. Please request a new one.</span>
            )}
          </div>

          <button
            type="submit"
            className="btn btn-primary"
            style={{ width: '100%' }}
            disabled={isLoading || digits.join('').length !== 6 || expirySeconds === 0}
          >
            {isLoading ? 'Verifying...' : 'Verify Code'}
          </button>

          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '8px', marginTop: '1rem', fontSize: '0.85rem' }}>
            <button
              type="button"
              id="btn-resend-otp"
              className="btn-link"
              onClick={() => handleRequestCode(true)}
              disabled={resendSeconds > 0 || isLoading}
              style={{
                background: 'none',
                border: 'none',
                color: resendSeconds > 0 ? 'var(--text-muted)' : 'var(--accent-blue)',
                cursor: resendSeconds > 0 ? 'default' : 'pointer',
              }}
            >
              {resendSeconds > 0 ? `Resend available in ${formatTime(resendSeconds)}` : "Didn't receive code? Resend"}
            </button>
          </div>
        </form>
      )}

      {/* STEP 3: PASSWORD */}
      {step === 'PASSWORD' && (
        <form onSubmit={handleSetPassword} id="otp-password-form">
          <div className="form-group">
            <label htmlFor="otp-new-password">New Password</label>
            <div style={{ position: 'relative' }}>
              <input
                type={showPassword ? 'text' : 'password'}
                id="otp-new-password"
                className="form-control"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter new password"
                required
                autoFocus
                style={{ paddingRight: '4rem' }}
              />
              <button
                type="button"
                className="btn-link"
                onClick={() => setShowPassword((prev) => !prev)}
                style={{
                  position: 'absolute',
                  right: '10px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  background: 'none',
                  border: 'none',
                  color: 'var(--text-secondary)',
                  cursor: 'pointer',
                  fontSize: '0.8rem',
                }}
              >
                {showPassword ? 'Hide' : 'Show'}
              </button>
            </div>
          </div>

          {/* Password criteria checklist */}
          <div className="password-rules" style={{ margin: '1rem 0', fontSize: '0.8rem' }}>
            <div style={{ color: pwdRules.length ? 'var(--status-success)' : 'var(--text-muted)' }}>
              {pwdRules.length ? '✓' : '○'} At least 8 characters
            </div>
            <div style={{ color: pwdRules.upper ? 'var(--status-success)' : 'var(--text-muted)' }}>
              {pwdRules.upper ? '✓' : '○'} Upper case letter
            </div>
            <div style={{ color: pwdRules.lower ? 'var(--status-success)' : 'var(--text-muted)' }}>
              {pwdRules.lower ? '✓' : '○'} Lower case letter
            </div>
            <div style={{ color: pwdRules.number ? 'var(--status-success)' : 'var(--text-muted)' }}>
              {pwdRules.number ? '✓' : '○'} Number
            </div>
            <div style={{ color: pwdRules.symbol ? 'var(--status-success)' : 'var(--text-muted)' }}>
              {pwdRules.symbol ? '✓' : '○'} Special character
            </div>
          </div>

          <button
            type="submit"
            id="btn-set-otp-password"
            className="btn btn-primary"
            style={{ width: '100%' }}
            disabled={isLoading || !isPwdValid}
          >
            {isLoading ? 'Saving Password...' : 'Set New Password'}
          </button>
        </form>
      )}

      {/* STEP 4: SUCCESS */}
      {step === 'SUCCESS' && (
        <div id="otp-success" style={{ textAlign: 'center', padding: '1rem 0' }}>
          <div style={{ color: 'var(--status-success)', fontSize: '2.5rem', marginBottom: '0.75rem' }}>✓</div>
          <p id="otp-success-message" style={{ color: 'var(--text-primary)', marginBottom: '1.5rem' }}>
            {successMessage}
          </p>
          <button
            type="button"
            id="btn-otp-back-to-login"
            className="btn btn-primary"
            onClick={onSuccessDone}
            style={{ width: '100%' }}
          >
            Back to Sign In
          </button>
        </div>
      )}

      {step !== 'SUCCESS' && (
        <div style={{ textAlign: 'center', marginTop: '1.25rem' }}>
          <button
            type="button"
            id="btn-cancel-otp-flow"
            className="btn-link"
            onClick={onCancel}
            style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: '0.85rem' }}
          >
            Cancel and return to Sign In
          </button>
        </div>
      )}
    </div>
  );
}
