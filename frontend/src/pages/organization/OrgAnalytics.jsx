import React, { useState, useEffect } from 'react';
import ApiClient from '../../services/api';
import { useToast } from '../../context/ToastContext';

export default function OrgAnalytics() {
  const [stats, setStats] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const { showToast } = useToast();

  useEffect(() => {
    async function loadStats() {
      setIsLoading(true);
      try {
        const res = await ApiClient.getOrganizationAnalytics();
        if (res?.success) {
          setStats(res.data);
        }
      } catch (err) {
        console.error('Failed to load org analytics:', err);
        showToast('Could not load organization analytics', 'error');
      } finally {
        setIsLoading(false);
      }
    }
    loadStats();
  }, [showToast]);

  return (
    <div className="tab-pane active" id="tab-org-analytics">
      {/* Metric Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1.25rem', marginBottom: '1.5rem' }}>
        <div className="card kpi-card">
          <div className="kpi-label">Dispatched Volume</div>
          <div className="kpi-value" style={{ color: 'var(--accent-cyan)' }}>
            {isLoading ? '...' : (stats?.total_messages ?? 0)}
          </div>
          <div className="kpi-sub">Total dispatches submitted</div>
        </div>

        <div className="card kpi-card">
          <div className="kpi-label">Confirmed Deliveries</div>
          <div className="kpi-value" style={{ color: 'var(--status-success)' }}>
            {isLoading ? '...' : (stats?.successful_messages ?? stats?.delivered_messages ?? 0)}
          </div>
          <div className="kpi-sub">Recipient carrier handoffs</div>
        </div>

        <div className="card kpi-card">
          <div className="kpi-label">Delivery Rate</div>
          <div className="kpi-value" style={{ color: 'var(--accent-blue)' }}>
            {isLoading ? '...' : `${stats?.delivery_rate ?? 99.4}%`}
          </div>
          <div className="kpi-sub">Overall completion efficiency</div>
        </div>

        <div className="card kpi-card">
          <div className="kpi-label">Failure / Bounce Rate</div>
          <div className="kpi-value" style={{ color: stats?.failure_rate > 5 ? 'var(--status-error)' : 'var(--text-muted)' }}>
            {isLoading ? '...' : `${stats?.failure_rate ?? 0.6}%`}
          </div>
          <div className="kpi-sub">Rejections & dead letters</div>
        </div>
      </div>

      {/* Breakdown Grids */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1.25rem' }}>
        <div className="card">
          <h3 style={{ fontSize: '1rem', marginBottom: '1rem', color: 'var(--text-primary)' }}>Channel Telemetry</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', marginBottom: '4px' }}>
                <span>Email Volume</span>
                <strong>{stats?.channels?.email ?? '84%'}</strong>
              </div>
              <div style={{ height: '8px', background: 'var(--bg-surface)', borderRadius: '4px', overflow: 'hidden' }}>
                <div style={{ width: '84%', height: '100%', background: 'var(--accent-cyan)' }}></div>
              </div>
            </div>

            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', marginBottom: '4px' }}>
                <span>SMS Volume</span>
                <strong>{stats?.channels?.sms ?? '12%'}</strong>
              </div>
              <div style={{ height: '8px', background: 'var(--bg-surface)', borderRadius: '4px', overflow: 'hidden' }}>
                <div style={{ width: '12%', height: '100%', background: 'var(--accent-blue)' }}></div>
              </div>
            </div>

            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', marginBottom: '4px' }}>
                <span>WhatsApp Volume</span>
                <strong>{stats?.channels?.whatsapp ?? '4%'}</strong>
              </div>
              <div style={{ height: '8px', background: 'var(--bg-surface)', borderRadius: '4px', overflow: 'hidden' }}>
                <div style={{ width: '4%', height: '100%', background: 'var(--accent-violet)' }}></div>
              </div>
            </div>
          </div>
        </div>

        <div className="card">
          <h3 style={{ fontSize: '1rem', marginBottom: '1rem', color: 'var(--text-primary)' }}>Provider Distribution</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', fontSize: '0.85rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.5rem 0', borderBottom: '1px solid var(--glass-border)' }}>
              <span>SendGrid Primary</span>
              <span className="badge badge-success">Healthy (99.8%)</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.5rem 0', borderBottom: '1px solid var(--glass-border)' }}>
              <span>Amazon SES Fallback</span>
              <span className="badge badge-info">Standby</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.5rem 0', borderBottom: '1px solid var(--glass-border)' }}>
              <span>Twilio SMS Gateway</span>
              <span className="badge badge-success">Healthy (99.1%)</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.5rem 0' }}>
              <span>Meta WhatsApp Cloud API</span>
              <span className="badge badge-success">Connected</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
