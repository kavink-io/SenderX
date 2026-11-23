import React, { useState, useEffect } from 'react';
import Modal from '../common/Modal';
import ApiClient from '../../services/api';

export default function AppDetailsModal({ isOpen, onClose, app }) {
  const [stats, setStats] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!isOpen || !app) return;
    const appId = app.application_id || app._id || app.id;
    setIsLoading(true);

    ApiClient.getApplicationStats(appId)
      .then((res) => {
        if (res.success && res.data) {
          setStats(res.data);
        }
      })
      .catch((err) => console.warn('Could not load app stats:', err))
      .finally(() => setIsLoading(false));
  }, [isOpen, app]);

  if (!app) return null;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Application Telemetry & Details"
      maxWidth="600px"
      id="modal-app-details"
    >
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1.25rem', marginBottom: '1.5rem' }}>
        <div>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Application ID</span>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85rem', color: 'var(--accent-cyan)' }}>
            {app.application_id || app._id || app.id}
          </div>
        </div>
        <div>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Name</span>
          <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{app.name}</div>
        </div>
        <div>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Environment</span>
          <div>
            <span className="badge badge-info">{app.environment || 'live'}</span>
          </div>
        </div>
        <div>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Status</span>
          <div>
            <span className={`badge ${app.status === 'ACTIVE' || app.status === 'active' ? 'badge-success' : 'badge-danger'}`}>
              {app.status}
            </span>
          </div>
        </div>
      </div>

      {app.description && (
        <div style={{ background: 'var(--bg-surface)', padding: '0.75rem', borderRadius: '6px', marginBottom: '1.25rem' }}>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Description</span>
          <p style={{ margin: '0.25rem 0 0', color: 'var(--text-primary)', fontSize: '0.9rem' }}>{app.description}</p>
        </div>
      )}

      <div style={{ borderTop: '1px solid var(--glass-border)', paddingTop: '1rem', marginBottom: '1.5rem' }}>
        <h4 style={{ fontSize: '0.95rem', marginBottom: '0.75rem', color: 'var(--text-primary)' }}>Telemetry Stats</h4>
        {isLoading ? (
          <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>Loading telemetry...</p>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '10px' }}>
            <div style={{ background: 'var(--bg-surface)', padding: '0.75rem', borderRadius: '6px', textAlign: 'center' }}>
              <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--accent-cyan)' }}>
                {stats?.total_messages ?? 0}
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Messages</div>
            </div>
            <div style={{ background: 'var(--bg-surface)', padding: '0.75rem', borderRadius: '6px', textAlign: 'center' }}>
              <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--status-success)' }}>
                {stats?.delivery_rate ?? '99.5%'}
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Success Rate</div>
            </div>
            <div style={{ background: 'var(--bg-surface)', padding: '0.75rem', borderRadius: '6px', textAlign: 'center' }}>
              <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--accent-violet)' }}>
                {stats?.credentials_count ?? app.credentials_count ?? 1}
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>API Keys</div>
            </div>
          </div>
        )}
      </div>

      <div className="modal-actions" style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <button type="button" className="btn btn-secondary" onClick={onClose}>
          Close
        </button>
      </div>
    </Modal>
  );
}
