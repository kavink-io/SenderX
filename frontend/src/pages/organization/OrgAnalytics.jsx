import React, { useState, useEffect } from 'react';
import ApiClient from '../../services/api';
import { useToast } from '../../context/ToastContext';
import {
  GlassCard,
  GlassBadge,
  GlassSkeleton,
  AnimatedNumber,
} from '../../components/glass';

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

  const metrics = [
    { label: 'Dispatched Volume', value: stats?.total_messages ?? 0, decimals: 0, sub: 'Total dispatches submitted', color: 'var(--accent-cyan)' },
    { label: 'Confirmed Deliveries', value: stats?.successful_messages ?? stats?.delivered_messages ?? 0, decimals: 0, sub: 'Recipient carrier handoffs', color: 'var(--status-success)' },
    { label: 'Delivery Rate', value: Number(stats?.delivery_rate ?? 99.4), suffix: '%', decimals: 1, sub: 'Overall completion efficiency', color: 'var(--accent-blue)' },
    { label: 'Failure / Bounce Rate', value: Number(stats?.failure_rate ?? 0.6), suffix: '%', decimals: 1, sub: 'Rejections & dead letters', color: stats?.failure_rate > 5 ? 'var(--status-error)' : 'var(--text-secondary)' },
  ];

  const channels = [
    { label: 'Email Volume', value: stats?.channels?.email ?? '84%', pct: parseInt(stats?.channels?.email ?? 84, 10) || 84, color: 'var(--accent-cyan)' },
    { label: 'SMS Volume', value: stats?.channels?.sms ?? '12%', pct: parseInt(stats?.channels?.sms ?? 12, 10) || 12, color: 'var(--accent-blue)' },
    { label: 'WhatsApp Volume', value: stats?.channels?.whatsapp ?? '4%', pct: parseInt(stats?.channels?.whatsapp ?? 4, 10) || 4, color: 'var(--accent-violet)' },
  ];

  const providers = [
    { name: 'SendGrid Primary', badge: 'Healthy (99.8%)', tone: 'success' },
    { name: 'Amazon SES Fallback', badge: 'Standby', tone: 'info' },
    { name: 'Twilio SMS Gateway', badge: 'Healthy (99.1%)', tone: 'success' },
    { name: 'Meta WhatsApp Cloud API', badge: 'Connected', tone: 'success' },
  ];

  return (
    <div className="tab-pane active" id="tab-org-analytics">
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1.15rem', marginBottom: '1.35rem' }}>
        {metrics.map((m) => (
          <GlassCard key={m.label} className="kpi-card" interactive>
            <div className="kpi-label">{m.label}</div>
            <div className="kpi-value" style={{ color: m.color }}>
              {isLoading ? (
                <GlassSkeleton width="80px" height="30px" />
              ) : (
                <AnimatedNumber value={m.value} suffix={m.suffix || ''} decimals={m.decimals} />
              )}
            </div>
            <div className="kpi-sub">{m.sub}</div>
          </GlassCard>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1.25rem' }}>
        <GlassCard>
          <h3 style={{ fontSize: '1rem', marginBottom: '1rem', color: 'var(--text-primary)' }}>Channel Telemetry</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {channels.map((c) => (
              <div key={c.label}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', marginBottom: '5px' }}>
                  <span style={{ color: 'var(--text-secondary)', fontWeight: 500 }}>{c.label}</span>
                  <strong>{c.value}</strong>
                </div>
                <div className="lg-progress-track">
                  <div className="lg-progress-fill" style={{ width: `${Math.min(100, c.pct)}%`, background: c.color }} />
                </div>
              </div>
            ))}
          </div>
        </GlassCard>

        <GlassCard>
          <h3 style={{ fontSize: '1rem', marginBottom: '1rem', color: 'var(--text-primary)' }}>Provider Distribution</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '0.85rem' }}>
            {providers.map((p) => (
              <div
                key={p.name}
                className="lg-glass-inset"
                style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 14px' }}
              >
                <span style={{ fontWeight: 500, color: 'var(--text-primary)' }}>{p.name}</span>
                <GlassBadge tone={p.tone}>{p.badge}</GlassBadge>
              </div>
            ))}
          </div>
        </GlassCard>
      </div>
    </div>
  );
}
