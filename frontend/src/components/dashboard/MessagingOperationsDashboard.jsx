import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAppScope } from '../../context/ScopeContext';
import { useAuth } from '../../context/AuthContext';
import ApiClient from '../../services/api';
import { AnimatedNumber, GlassCard, GlassSkeleton } from '../glass';

function getItems(response) {
  const data = response?.data;
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.items)) return data.items;
  if (Array.isArray(response?.items)) return response.items;
  return [];
}

function asResult(result, hasPermission, label) {
  if (!hasPermission) return { status: 'forbidden', data: null };
  if (result.status === 'fulfilled' && result.value?.success) {
    return { status: 'ready', data: result.value };
  }
  const error = result.status === 'rejected' ? result.reason : result.value;
  console.warn(`Could not load ${label}:`, error);
  return { status: 'error', data: null };
}

function MetricCard({ label, value, note, isLoading }) {
  return (
    <div className="saas-metric">
      <div className="saas-metric-label">{label}</div>
      <div className="saas-metric-value">
        {isLoading ? <GlassSkeleton width="86px" height="27px" /> : value === null ? '—' : (
          typeof value === 'number' ? <AnimatedNumber value={value} /> : value
        )}
      </div>
      <div className="saas-metric-note">{note}</div>
    </div>
  );
}

function WidgetState({ status, empty = 'No activity is available yet.' }) {
  if (status === 'loading') return <GlassSkeleton width="100%" height="112px" />;
  if (status === 'forbidden') return <div className="saas-empty-state">This information is not available to your role.</div>;
  if (status === 'error') return <div className="saas-empty-state" role="status">SenderX could not load this information.</div>;
  return <div className="saas-empty-state">{empty}</div>;
}

function messageTone(status) {
  const normalized = String(status || '').toUpperCase();
  if (['SENT', 'DELIVERED', 'READ'].includes(normalized)) return 'success';
  if (['FAILED', 'DEAD', 'ERROR'].includes(normalized)) return 'error';
  return 'pending';
}

function formatDate(value) {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString();
}

const DASHBOARD_REFRESH_MS = 60000;
const MAX_REFRESH_BACKOFF_MS = 300000;

export default function MessagingOperationsDashboard() {
  const { activeAppId } = useAppScope();
  const { account, hasPermission } = useAuth();
  const [snapshot, setSnapshot] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [connectionState, setConnectionState] = useState('connecting');
  const [lastUpdatedAt, setLastUpdatedAt] = useState(null);
  const [currentTime, setCurrentTime] = useState(() => new Date());

  const permissions = useMemo(() => ({
    analytics: hasPermission('organization:analytics:read'),
    messages: hasPermission('organization:messages:read'),
    applications: hasPermission('organization:configuration:manage'),
    providers: hasPermission('organization:providers:read'),
    createMessage: hasPermission('organization:messages:create'),
    createTemplate: hasPermission('organization:templates:create'),
    viewTemplates: hasPermission('organization:templates:read'),
    manageProviders: hasPermission('organization:providers:manage'),
    viewDeadLetters: hasPermission('organization:dead_letters:read'),
  }), [hasPermission]);

  useEffect(() => {
    let active = true;
    let hasLoaded = false;
    let isFetching = false;
    let consecutiveFailures = 0;
    let refreshTimer;
    setSnapshot(null);
    setIsLoading(true);
    setConnectionState('connecting');
    setLastUpdatedAt(null);
    const applicationFilter = activeAppId ? { application_id: activeAppId } : {};
    const entries = [
      ['analytics', () => permissions.analytics ? ApiClient.getOrganizationAnalytics() : null, permissions.analytics],
      ['messages', () => permissions.messages ? ApiClient.listMessages(1, 6, applicationFilter) : null, permissions.messages],
      ['failed', () => permissions.messages ? ApiClient.listMessages(1, 5, { ...applicationFilter, status: 'FAILED' }) : null, permissions.messages],
      ['dead', () => permissions.messages ? ApiClient.listMessages(1, 5, { ...applicationFilter, status: 'DEAD' }) : null, permissions.messages],
      ['applications', () => permissions.applications ? ApiClient.listApplications(1, 100, 'ACTIVE') : null, permissions.applications],
      ['providers', () => permissions.providers ? ApiClient.getOrganizationProviderConfigs() : null, permissions.providers],
    ];

    const scheduleRefresh = (delay) => {
      if (!active) return;
      window.clearTimeout(refreshTimer);
      refreshTimer = window.setTimeout(loadDashboard, delay);
    };

    async function loadDashboard() {
      if (!active || isFetching) return;
      if (document.visibilityState === 'hidden') {
        setConnectionState('paused');
        scheduleRefresh(DASHBOARD_REFRESH_MS);
        return;
      }

      isFetching = true;
      if (!hasLoaded) setIsLoading(true);
      setConnectionState(hasLoaded ? 'updating' : 'connecting');
      const results = await Promise.allSettled(
        entries.map(([, request]) => request() || Promise.resolve(null))
      );
      if (!active) {
        isFetching = false;
        return;
      }

      const normalized = {};
      entries.forEach(([key, , allowed], index) => {
        normalized[key] = asResult(results[index], allowed, key);
      });
      const requestFailed = entries.some(([, , allowed], index) => (
        allowed && (
          results[index].status === 'rejected'
          || !results[index].value?.success
        )
      ));

      setSnapshot(normalized);
      setLastUpdatedAt(new Date());
      setConnectionState(requestFailed ? 'degraded' : 'connected');
      setIsLoading(false);
      hasLoaded = true;
      isFetching = false;
      consecutiveFailures = requestFailed ? consecutiveFailures + 1 : 0;

      const backoff = Math.min(
        DASHBOARD_REFRESH_MS * (2 ** Math.min(consecutiveFailures, 4)),
        MAX_REFRESH_BACKOFF_MS
      );
      scheduleRefresh(requestFailed ? backoff : DASHBOARD_REFRESH_MS);
    }

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') scheduleRefresh(0);
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    loadDashboard();
    return () => {
      active = false;
      window.clearTimeout(refreshTimer);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [activeAppId, permissions]);

  useEffect(() => {
    const updateTime = () => setCurrentTime(new Date());
    const timer = window.setInterval(updateTime, 60000);
    document.addEventListener('visibilitychange', updateTime);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener('visibilitychange', updateTime);
    };
  }, []);

  const analytics = snapshot?.analytics?.data;
  const overview = analytics?.overview;
  const today = analytics?.today;
  const messages = getItems(snapshot?.messages?.data);
  const failedMessages = useMemo(() => {
    const rows = [
      ...getItems(snapshot?.failed?.data),
      ...getItems(snapshot?.dead?.data),
    ];
    const unique = new Map(rows.map((message) => [message.message_id || message._id, message]));
    return Array.from(unique.values())
      .sort((left, right) => new Date(right.created_at || 0) - new Date(left.created_at || 0))
      .slice(0, 5);
  }, [snapshot]);
  const applications = getItems(snapshot?.applications?.data);
  const providers = getItems(snapshot?.providers?.data);
  const channels = Array.isArray(analytics?.channels) ? analytics.channels : [];
  const activeApplicationCount = snapshot?.applications?.data?.pagination?.total;
  const recentApiActivity = applications
    .filter((application) => application.last_activity_at)
    .sort((left, right) => new Date(right.last_activity_at) - new Date(left.last_activity_at))
    .slice(0, 5);
  const failedMessagesStatus = isLoading
    ? 'loading'
    : snapshot?.failed?.status === 'forbidden' || snapshot?.dead?.status === 'forbidden'
      ? 'forbidden'
      : 'error';
  const quickActions = [
    permissions.messages && permissions.createMessage && { to: '/org/messages', label: 'Send Message', detail: 'Compose and send a message' },
    permissions.viewTemplates && permissions.createTemplate && { to: '/org/templates', label: 'Create Template', detail: 'Open the template studio' },
    permissions.manageProviders && { to: '/org/channels', label: 'Connect Integration', detail: 'Configure messaging providers' },
    permissions.viewDeadLetters && { to: '/org/dlq', label: 'View Failed Messages', detail: 'Review and reprocess dead letters' },
  ].filter(Boolean);
  const hour = currentTime.getHours();
  const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';
  const displayName = account?.first_name?.trim() || account?.name?.trim() || account?.email || 'there';
  const connectionText = connectionState === 'connected'
    ? `Connected · Updated ${lastUpdatedAt?.toLocaleTimeString() || ''}`
    : connectionState === 'updating'
      ? 'Updating dashboard…'
      : connectionState === 'degraded'
        ? 'Updates unavailable · Retrying'
        : connectionState === 'paused'
          ? 'Updates paused while this tab is hidden'
          : 'Connecting to SenderX…';

  const pendingCount = overview
    ? (Number(overview.queued) || 0) + (Number(overview.processing) || 0)
    : null;
  const failedToday = today
    ? (Number(today.failed) || 0) + (Number(today.dead) || 0)
    : null;
  const deliverySuccessRate = today
    ? `${today.total_messages > 0
      ? ((Number(today.delivered) || 0) / Number(today.total_messages) * 100).toFixed(1)
      : '0.0'}%`
    : null;
  const configuredIntegrations = snapshot?.providers?.status === 'ready'
    ? providers.filter((provider) => provider.configured).length
    : null;

  return (
    <div className="tab-pane active saas-dashboard saas-operations-dashboard" id="tab-org-overview">
      <div className="saas-dashboard-welcome">
        <div>
          <h1>{greeting}, {displayName}!</h1>
          <p>Here’s what’s happening with your messaging operations today.</p>
        </div>
        <div className={`saas-dashboard-connection is-${connectionState}`} role="status" aria-live="polite">
          <span aria-hidden="true" />
          {connectionText}
        </div>
      </div>

      <div className="saas-metrics-card saas-operations-metrics-card">
        <MetricCard label="Messages Today" value={today ? today.total_messages : null} note="Created today in UTC" isLoading={isLoading} />
        <MetricCard label="Delivered Today" value={today ? today.delivered : null} note="Successfully handed off or delivered" isLoading={isLoading} />
        <MetricCard label="Failed Today" value={failedToday} note="Failed or dead-lettered today" isLoading={isLoading} />
        <MetricCard label="Pending Messages" value={pendingCount} note="Queued or processing now" isLoading={isLoading} />
        <MetricCard label="Configured Integrations" value={configuredIntegrations} note="Saved provider configurations" isLoading={isLoading} />
        <MetricCard label="Delivery Success Rate" value={deliverySuccessRate} note="Delivered messages today" isLoading={isLoading} />
      </div>

      {quickActions.length > 0 && (
        <section className="saas-quick-actions" aria-label="Quick actions">
          {quickActions.map((action) => (
            <Link to={action.to} className="saas-quick-action" key={action.to}>
              <strong>{action.label}</strong>
              <span>{action.detail}</span>
              <b aria-hidden="true">→</b>
            </Link>
          ))}
        </section>
      )}

      <div className="saas-operations-grid">
        <GlassCard className="saas-support-card saas-operations-card">
          <div className="saas-section-heading">
            <h2>Integration Health</h2>
            <p>Provider configuration status; live connectivity checks are not exposed here.</p>
          </div>
          {snapshot?.providers?.status === 'ready' ? (
            providers.length ? (
              <div className="saas-health-list">
                {providers.map((provider) => (
                  <div className="saas-health-item" key={provider.provider}>
                    <span className={`saas-health-dot ${provider.configured ? 'connected' : ''}`} />
                    <span>{provider.provider}</span>
                    <strong>{provider.configured ? 'Configured' : 'Not configured'}</strong>
                  </div>
                ))}
              </div>
            ) : <WidgetState status="empty" empty="No provider integrations are configured." />
          ) : <WidgetState status={isLoading ? 'loading' : snapshot?.providers?.status || 'error'} />}
        </GlassCard>

        <GlassCard className="saas-support-card saas-operations-card">
          <div className="saas-section-heading">
            <h2>Channel Status</h2>
            <p>Message activity by channel in the current organization and application scope.</p>
          </div>
          {snapshot?.analytics?.status === 'ready' ? (
            channels.length ? (
              <div className="saas-health-list">
                {channels.map((channel) => (
                  <div className="saas-health-item" key={channel.channel}>
                    <span className={`saas-health-dot ${channel.count > 0 ? 'connected' : ''}`} />
                    <span>{channel.channel || 'Other'}</span>
                    <strong>{Number(channel.count || 0).toLocaleString()} messages</strong>
                  </div>
                ))}
              </div>
            ) : <WidgetState status="empty" empty="No channel activity has been recorded." />
          ) : <WidgetState status={isLoading ? 'loading' : snapshot?.analytics?.status || 'error'} />}
        </GlassCard>

        <GlassCard className="saas-support-card saas-operations-card">
          <div className="saas-section-heading saas-activity-heading">
            <div>
              <h2>Recent Failed Messages</h2>
              <p>Failed and dead-lettered messages in the current scope.</p>
            </div>
            {permissions.viewDeadLetters && <Link to="/org/dlq">View failed queue <span aria-hidden="true">→</span></Link>}
          </div>
          {snapshot?.failed?.status === 'ready' && snapshot?.dead?.status === 'ready' ? (
            failedMessages.length ? (
              <div className="saas-message-list">
                {failedMessages.map((message) => {
                  const status = String(message.status || 'FAILED').toUpperCase();
                  return (
                    <div className="saas-message-row saas-compact-message-row" key={message.message_id || message._id}>
                      <span className="saas-message-status" data-status={messageTone(status)} />
                      <span className="saas-message-recipient">{message.recipient || message.to || 'Unknown recipient'}</span>
                      <span className="saas-message-channel">{message.channel || '—'}</span>
                      <span className={`saas-message-badge ${messageTone(status)}`}>{status}</span>
                    </div>
                  );
                })}
              </div>
            ) : <WidgetState status="empty" empty="No failed messages are available in this scope." />
          ) : <WidgetState status={failedMessagesStatus} />}
        </GlassCard>

        <GlassCard className="saas-support-card saas-operations-card">
          <div className="saas-section-heading saas-activity-heading">
            <div>
              <h2>Active Connected Applications</h2>
              <p>Applications currently enabled for this organization.</p>
            </div>
            {permissions.applications && <Link to="/org/applications">Manage <span aria-hidden="true">→</span></Link>}
          </div>
          {snapshot?.applications?.status === 'ready' ? (
            applications.length ? (
              <>
                <div className="saas-operations-count">{Number(activeApplicationCount || 0).toLocaleString()} active applications</div>
                <div className="saas-health-list">
                  {applications.slice(0, 5).map((application) => (
                    <div className="saas-health-item" key={application.application_id || application._id}>
                      <span className="saas-health-dot connected" />
                      <span>{application.name || application.application_id}</span>
                      <strong>{application.environment || '—'}</strong>
                    </div>
                  ))}
                </div>
              </>
            ) : <WidgetState status="empty" empty="No active connected applications." />
          ) : <WidgetState status={isLoading ? 'loading' : snapshot?.applications?.status || 'error'} />}
        </GlassCard>

        <GlassCard className="saas-support-card saas-operations-card">
          <div className="saas-section-heading">
            <h2>Recent API Activity</h2>
            <p>Last activity timestamps recorded for active connected applications.</p>
          </div>
          {snapshot?.applications?.status === 'ready' ? (
            recentApiActivity.length ? (
              <div className="saas-activity-list">
                {recentApiActivity.map((application) => (
                  <div className="saas-activity-item" key={application.application_id || application._id}>
                    <span>
                      <strong>{application.name || application.application_id}</strong>
                      <small>{application.application_id || 'Connected application'}</small>
                    </span>
                    <time>{formatDate(application.last_activity_at)}</time>
                  </div>
                ))}
              </div>
            ) : <WidgetState status="empty" empty="No API activity timestamps are available." />
          ) : <WidgetState status={isLoading ? 'loading' : snapshot?.applications?.status || 'error'} />}
        </GlassCard>
      </div>

      <GlassCard className="saas-support-card saas-operations-table-card">
        <div className="saas-section-heading saas-activity-heading">
          <div>
            <h2>Recent Message Activity</h2>
            <p>Latest messages in the selected application scope.</p>
          </div>
          {permissions.messages && <Link to="/org/messages">View all <span aria-hidden="true">→</span></Link>}
        </div>
        {snapshot?.messages?.status === 'ready' ? (
          messages.length ? (
            <div className="saas-operations-table-wrap">
              <table className="saas-operations-table">
                <thead>
                  <tr>
                    <th>Message ID</th>
                    <th>Recipient</th>
                    <th>Channel</th>
                    <th>Status</th>
                    <th>Created At</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {messages.map((message) => {
                    const status = String(message.status || 'UNKNOWN').toUpperCase();
                    return (
                      <tr key={message.message_id || message._id}>
                        <td className="saas-operations-message-id">{message.message_id || message._id || '—'}</td>
                        <td>{message.recipient || message.to || '—'}</td>
                        <td>{message.channel || '—'}</td>
                        <td><span className={`saas-message-badge ${messageTone(status)}`}>{status}</span></td>
                        <td>{formatDate(message.created_at)}</td>
                        <td><Link to="/org/messages" aria-label={`Open messages for ${message.message_id || message._id || 'this message'}`}>View</Link></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : <WidgetState status="empty" empty="No messages are available in this scope." />
        ) : <WidgetState status={isLoading ? 'loading' : snapshot?.messages?.status || 'error'} />}
      </GlassCard>
    </div>
  );
}
