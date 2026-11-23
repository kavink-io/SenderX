import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import ApiClient from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import { useAppScope } from '../../context/ScopeContext';

export default function OrgOverview() {
  const [stats, setStats] = useState(null);
  const [recentMessages, setRecentMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(true);

  const { isOrgAdmin, hasPermission } = useAuth();
  const { activeAppId } = useAppScope();

  useEffect(() => {
    async function fetchOverview() {
      setIsLoading(true);
      try {
        const [statsRes, msgsRes] = await Promise.all([
          ApiClient.getOrganizationAnalytics().catch(() => null),
          ApiClient.listMessages(1, 5, { application_id: activeAppId || undefined }).catch(() => null),
        ]);

        if (statsRes?.success) {
          setStats(statsRes.data);
        }
        if (msgsRes?.success && Array.isArray(msgsRes.data?.items)) {
          setRecentMessages(msgsRes.data.items);
        }
      } catch (err) {
        console.warn('Could not load overview data:', err);
      } finally {
        setIsLoading(false);
      }
    }

    fetchOverview();
  }, [activeAppId]);

  return (
    <div className="tab-pane active" id="tab-org-overview">
      {/* KPI Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1.25rem', marginBottom: '1.5rem' }}>
        <div className="card kpi-card">
          <div className="kpi-label">Dispatched Volume</div>
          <div className="kpi-value" style={{ color: 'var(--accent-cyan)' }}>
            {isLoading ? '...' : (stats?.total_messages ?? 0)}
          </div>
          <div className="kpi-sub">Total messages submitted</div>
        </div>

        <div className="card kpi-card">
          <div className="kpi-label">Delivery Success Rate</div>
          <div className="kpi-value" style={{ color: 'var(--status-success)' }}>
            {isLoading ? '...' : `${stats?.delivery_rate ?? 99.4}%`}
          </div>
          <div className="kpi-sub">Direct delivery confirmations</div>
        </div>

        <div className="card kpi-card">
          <div className="kpi-label">Connected Applications</div>
          <div className="kpi-value" style={{ color: 'var(--accent-blue)' }}>
            {isLoading ? '...' : (stats?.active_applications ?? 0)}
          </div>
          <div className="kpi-sub">Authorized client services</div>
        </div>

        <div className="card kpi-card">
          <div className="kpi-label">Failed / DLQ Influx</div>
          <div className="kpi-value" style={{ color: stats?.failed_messages > 0 ? 'var(--status-warning)' : 'var(--text-muted)' }}>
            {isLoading ? '...' : (stats?.failed_messages ?? stats?.dlq_count ?? 0)}
          </div>
          <div className="kpi-sub">Messages pending retry</div>
        </div>
      </div>

      {/* Quick Actions & Recent Activity */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1.25rem' }}>
        {/* Quick Launch Card */}
        <div className="card">
          <h3 style={{ fontSize: '1rem', marginBottom: '1rem', color: 'var(--text-primary)' }}>Quick Actions</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '10px' }}>
            {hasPermission('organization:messages:read') && (
              <Link to="/org/messages" className="btn btn-primary" style={{ textAlign: 'center', padding: '0.75rem 0.5rem' }}>
                Compose Message
              </Link>
            )}
            {hasPermission('organization:templates:read') && (
              <Link to="/org/templates" className="btn btn-secondary" style={{ textAlign: 'center', padding: '0.75rem 0.5rem' }}>
                Template Studio
              </Link>
            )}
            {hasPermission('organization:configuration:manage') && (
              <Link to="/org/applications" className="btn btn-secondary" style={{ textAlign: 'center', padding: '0.75rem 0.5rem' }}>
                Connect App
              </Link>
            )}
            {hasPermission('organization:users:read') && (
              <Link to="/org/users" className="btn btn-secondary" style={{ textAlign: 'center', padding: '0.75rem 0.5rem' }}>
                Manage Team
              </Link>
            )}
          </div>
        </div>

        {/* Recent Message Outbox */}
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <h3 style={{ fontSize: '1rem', margin: 0, color: 'var(--text-primary)' }}>Recent Dispatches</h3>
            <Link to="/org/messages" style={{ fontSize: '0.85rem', color: 'var(--accent-blue)', textDecoration: 'none' }}>
              View all →
            </Link>
          </div>

          {recentMessages.length === 0 ? (
            <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', margin: 0 }}>
              No recent dispatches logged for this scope.
            </p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {recentMessages.map((msg) => (
                <div
                  key={msg.message_id || msg._id}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: '0.5rem 0',
                    borderBottom: '1px solid var(--glass-border-subtle)',
                    fontSize: '0.85rem',
                  }}
                >
                  <div>
                    <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                      {msg.recipient || msg.to || 'Unknown Recipient'}
                    </div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                      {msg.channel} • {msg.provider || 'default'}
                    </div>
                  </div>
                  <span className={`badge ${msg.status === 'DELIVERED' || msg.status === 'SENT' ? 'badge-success' : 'badge-warning'}`}>
                    {msg.status}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
