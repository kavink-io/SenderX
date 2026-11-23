import React from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

export default function AccessDenied({ message = 'You do not have permission to access this resource.' }) {
  const { isPlatformAdmin } = useAuth();

  return (
    <div className="card text-center" style={{ maxWidth: '600px', margin: '3rem auto', padding: '2.5rem' }}>
      <div style={{ color: 'var(--status-error)', marginBottom: '1rem' }}>
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10"></circle>
          <line x1="12" y1="8" x2="12" y2="12"></line>
          <line x1="12" y1="16" x2="12.01" y2="16"></line>
        </svg>
      </div>
      <h3 style={{ marginBottom: '0.75rem', color: 'var(--text-primary)' }}>Access Restricted</h3>
      <p style={{ color: 'var(--text-secondary)', marginBottom: '1.5rem', lineHeight: 1.5 }}>
        {message}
      </p>
      <div>
        <Link
          to={isPlatformAdmin ? '/platform/organizations' : '/org/overview'}
          className="btn btn-primary"
        >
          Return to Dashboard
        </Link>
      </div>
    </div>
  );
}
