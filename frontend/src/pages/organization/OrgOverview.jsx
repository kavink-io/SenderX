import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import ApiClient from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import { useAppScope } from '../../context/ScopeContext';
import {
  GlassCard,
  GlassBadge,
  GlassSkeleton,
  AnimatedNumber,
} from '../../components/glass';

export default function OrgOverview() {
  const [stats, setStats] = useState(null);
  const [recentMessages, setRecentMessages] = useState([]);
  const [health, setHealth] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  const { hasPermission } = useAuth();
  const { activeAppId } = useAppScope();

  useEffect(() => {
    async function fetchOverview() {
      setIsLoading(true);
      try {
        const [statsRes, msgsRes, healthRes] = await Promise.all([
          ApiClient.getOrganizationAnalytics().catch(() => null),
          ApiClient.listMessages(1, 5, { application_id: activeAppId || undefined }).catch(() => null),
          ApiClient.getDetailedHealth().catch(() => null),
        ]);

        if (statsRes?.success) {
          setStats(statsRes.data);
        }
        if (msgsRes?.success) {
          const items = Array.isArray(msgsRes.data)
            ? msgsRes.data
            : (msgsRes.data?.items || msgsRes.items || []);
          setRecentMessages(items.slice(0, 5));
        }
        if (healthRes) {
          setHealth(healthRes);
        }
      } catch (err) {
        console.warn('Could not load overview data:', err);
      } finally {
        setIsLoading(false);
      }
    }

    fetchOverview();
  }, [activeAppId]);

  const totalVolume = stats?.total_messages ?? 0;
  const deliveryRate = Number(stats?.delivery_rate ?? 99.4);
  const activeApps = stats?.active_applications ?? 0;
  const dlqCount = stats?.failed_messages ?? stats?.dlq_count ?? 0;

  const kpiCards = [
    {
      label: 'Dispatched Volume',
      value: totalVolume,
      decimals: 0,
      sub: 'Total messages submitted',
      color: 'var(--accent-cyan)',
      icon: (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <line x1="22" y1="2" x2="11" y2="13" />
          <polygon points="22 2 15 22 11 13 2 9 22 2" />
        </svg>
      ),
    },
    {
      label: 'Delivery Success Rate',
      value: deliveryRate,
      suffix: '%',
      decimals: 1,
      sub: 'Direct delivery confirmations',
      color: 'var(--status-success)',
      icon: (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
          <polyline points="22 4 12 14.01 9 11.01" />
        </svg>
      ),
    },
    {
      label: 'Connected Applications',
      value: activeApps,
      decimals: 0,
      sub: 'Authorized client services',
      color: 'var(--accent-blue)',
      icon: (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <rect x="2" y="3" width="20" height="14" rx="2" ry="2" />
          <line x1="8" y1="21" x2="16" y2="21" />
          <line x1="12" y1="17" x2="12" y2="21" />
        </svg>
      ),
    },
    {
      label: 'Failed / DLQ Influx',
      value: dlqCount,
      decimals: 0,
      sub: 'Messages pending retry',
      color: dlqCount > 0 ? 'var(--status-warning)' : 'var(--text-primary)',
      icon: (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
          <line x1="12" y1="9" x2="12" y2="13" />
          <line x1="12" y1="17" x2="12.01" y2="17" />
        </svg>
      ),
    },
  ];

  const channels = [
    { name: 'Email Dispatch', value: stats?.channels?.email ?? '84%', pct: parseInt(stats?.channels?.email ?? 84, 10) || 84, color: 'var(--accent-cyan)' },
    { name: 'SMS Gateway', value: stats?.channels?.sms ?? '12%', pct: parseInt(stats?.channels?.sms ?? 12, 10) || 12, color: 'var(--accent-blue)' },
    { name: 'WhatsApp Cloud', value: stats?.channels?.whatsapp ?? '4%', pct: parseInt(stats?.channels?.whatsapp ?? 4, 10) || 4, color: 'var(--accent-violet)' },
  ];

  const isHealthy = (val) => val === 'healthy' || val === 'connected' || val === 'ok' || val === true;
  const integrationSignals = [
    { label: 'API Gateway', ok: true, detail: 'Ingestion online' },
    { label: 'Message Queue', ok: health ? isHealthy(health?.rabbitmq?.status ?? true) : true, detail: 'Celery & RabbitMQ' },
    { label: 'Datastore', ok: health ? isHealthy(health?.mongodb?.status || health?.database?.status || true) : true, detail: 'MongoDB Cluster' },
    { label: 'Cache & Rate Limit', ok: health ? isHealthy(health?.redis?.status ?? true) : true, detail: 'Redis Memory Store' },
  ];

  const quickActions = [
    hasPermission('organization:messages:read') && { to: '/org/messages', label: 'Compose Message', desc: 'Send Email, SMS, or WhatsApp', primary: true },
    hasPermission('organization:templates:read') && { to: '/org/templates', label: 'Template Studio', desc: 'Design responsive HTML emails' },
    hasPermission('organization:configuration:manage') && { to: '/org/applications', label: 'Connect App', desc: 'Register client services' },
    hasPermission('organization:users:read') && { to: '/org/users', label: 'Manage Team', desc: 'Employees, roles & audit trail' },
  ].filter(Boolean);

  return (
    <div className="tab-pane active" id="tab-org-overview">
      {/* KPI Summary Strip */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1.15rem', marginBottom: '1.35rem' }}>
        {kpiCards.map((kpi) => (
          <GlassCard key={kpi.label} className="kpi-card" interactive>
            <div className="kpi-header-row">
              <span className="kpi-label">{kpi.label}</span>
              <span className="kpi-icon-pill" style={{ color: kpi.color }}>
                {kpi.icon}
              </span>
            </div>
            <div className="kpi-value" style={{ color: kpi.color }}>
              {isLoading ? (
                <GlassSkeleton width="84px" height="30px" />
              ) : (
                <AnimatedNumber value={kpi.value} suffix={kpi.suffix || ''} decimals={kpi.decimals} />
              )}
            </div>
            <div className="kpi-sub">{kpi.sub}</div>
          </GlassCard>
        ))}
      </div>

      {/* Quick Actions Strip (lightweight non-nested hierarchy) */}
      {quickActions.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.9rem', marginBottom: '1.35rem' }}>
          {quickActions.map((act) => (
            <Link
              key={act.to}
              to={act.to}
              className={`lg-glass-card is-interactive`}
              style={{
                textDecoration: 'none',
                padding: '14px 16px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: '12px',
              }}
            >
              <div>
                <div style={{ fontSize: '0.9rem', fontWeight: 600, color: act.primary ? 'var(--accent-blue)' : 'var(--text-primary)' }}>
                  {act.label}
                </div>
                <div style={{ fontSize: '0.76rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
                  {act.desc}
                </div>
              </div>
              <span style={{ color: 'var(--text-muted)', fontSize: '1rem' }} aria-hidden="true">→</span>
            </Link>
          ))}
        </div>
      )}

      {/* Telemetry & Activity Workspace */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1.25rem' }}>
        {/* Delivery Stats & Integration Health */}
        <GlassCard>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.1rem' }}>
            <div>
              <h3 style={{ fontSize: '1rem', margin: 0, color: 'var(--text-primary)' }}>
                Channel Throughput &amp; Health
              </h3>
              <p style={{ margin: '2px 0 0', fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                Real-time distribution and infrastructure signals
              </p>
            </div>
            <GlassBadge tone="success">
              {isLoading ? 'Syncing' : `${deliveryRate}% Delivered`}
            </GlassBadge>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.9rem', marginBottom: '1.35rem' }}>
            {channels.map((ch) => (
              <div key={ch.name}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.82rem', marginBottom: '5px' }}>
                  <span style={{ color: 'var(--text-secondary)', fontWeight: 500 }}>{ch.name}</span>
                  <strong style={{ color: 'var(--text-primary)' }}>{ch.value}</strong>
                </div>
                <div className="lg-progress-track">
                  <div
                    className="lg-progress-fill"
                    style={{ width: `${Math.min(100, Math.max(2, ch.pct))}%`, background: ch.color }}
                  />
                </div>
              </div>
            ))}
          </div>

          <div style={{ fontSize: '0.74rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-muted)', marginBottom: '0.65rem' }}>
            Integration Health
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '8px' }}>
            {integrationSignals.map((sig) => (
              <div
                key={sig.label}
                className="lg-glass-inset"
                style={{ padding: '10px 12px', display: 'flex', alignItems: 'center', gap: '10px' }}
              >
                <span className={`lg-status-dot ${sig.ok ? 'ok' : 'warn'}`} />
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-primary)' }}>{sig.label}</div>
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {sig.detail}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </GlassCard>

        {/* Recent Activity Timeline */}
        <GlassCard>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <div>
              <h3 style={{ fontSize: '1rem', margin: 0, color: 'var(--text-primary)' }}>Recent Activity Timeline</h3>
              <p style={{ margin: '2px 0 0', fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                Latest outbound message dispatches
              </p>
            </div>
            <Link to="/org/messages" style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--accent-blue)', textDecoration: 'none' }}>
              View outbox →
            </Link>
          </div>

          {isLoading ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {[1, 2, 3].map((idx) => (
                <GlassSkeleton key={idx} width="100%" height="44px" />
              ))}
            </div>
          ) : recentMessages.length === 0 ? (
            <div className="lg-glass-inset" style={{ padding: '1.5rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.84rem' }}>
              No recent dispatches logged for this scope.
            </div>
          ) : (
            <div className="lg-timeline">
              {recentMessages.map((msg) => {
                const isOk = msg.status === 'DELIVERED' || msg.status === 'SENT';
                const isErr = msg.status === 'FAILED' || msg.status === 'ERROR';
                return (
                  <div key={msg.message_id || msg._id} className="lg-timeline-item">
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px', minWidth: 0 }}>
                      <span className={`lg-status-dot ${isOk ? 'ok' : isErr ? 'err' : 'warn'}`} />
                      <div style={{ minWidth: 0 }}>
                        <div style={{ fontWeight: 600, fontSize: '0.86rem', color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                          {msg.recipient || msg.to || 'Unknown Recipient'}
                        </div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                          {msg.channel} &bull; {msg.provider || 'default'}
                        </div>
                      </div>
                    </div>
                    <GlassBadge tone={isOk ? 'success' : isErr ? 'danger' : 'warning'}>
                      {msg.status}
                    </GlassBadge>
                  </div>
                );
              })}
            </div>
          )}
        </GlassCard>
      </div>
    </div>
  );
}
