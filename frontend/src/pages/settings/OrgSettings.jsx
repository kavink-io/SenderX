import React, { useCallback, useState, useEffect, lazy, Suspense } from 'react';
import ApiClient from '../../services/api';
import PageLoader from '../../components/common/PageLoader';
import { GlassCard, GlassTabs, GlassBadge } from '../../components/glass';

const ChangeRequestsSection = lazy(() => import('../../components/settings/ChangeRequestsSection'));
const AppearanceSettings = lazy(() => import('../../components/settings/AppearanceSettings'));

export default function OrgSettings({ initialTab, inPanel = false }) {
  const [org, setOrg] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [activeTab, setActiveTab] = useState(() => initialTab || 'IDENTITY');

  const fetchOrg = useCallback(async () => {
    setIsLoading(true);
    setLoadError('');
    try {
      const res = await ApiClient.getCurrentOrganization();
      if (res?.success && res.data) {
        setOrg(res.data);
      } else {
        setLoadError(res?.message || res?.msg || 'Organization details are unavailable.');
      }
    } catch (err) {
      console.warn('Could not load organization identity:', err);
      setLoadError(err?.message || 'Could not load organization details.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (activeTab === 'IDENTITY') fetchOrg();
  }, [activeTab, fetchOrg]);

  useEffect(() => {
    if (initialTab) setActiveTab(initialTab);
  }, [initialTab]);

  return (
    <div className={inPanel ? 'org-settings-panel-content' : 'tab-pane active'} id={inPanel ? undefined : 'tab-org-settings'}>
      {/* Settings Navigation Tabs */}
      <div style={{ marginBottom: '1.35rem' }}>
        <GlassTabs
          activeKey={activeTab}
          onChange={setActiveTab}
          tabs={[
            { key: 'IDENTITY', label: 'Organization Identity' },
            { key: 'APPEARANCE', label: 'Appearance & Layout' },
            { key: 'CHANGES', label: 'Rebranding Requests' },
          ]}
        />
      </div>

      {activeTab === 'IDENTITY' && (
        loadError ? (
          <GlassCard role="alert">
            <h3 style={{ fontSize: '1.05rem', marginBottom: '0.4rem', color: 'var(--text-primary)' }}>
              Organization details unavailable
            </h3>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
              {loadError}
            </p>
            <button type="button" className="btn btn-secondary" onClick={fetchOrg} disabled={isLoading}>
              {isLoading ? 'Retrying...' : 'Retry'}
            </button>
          </GlassCard>
        ) : (
          <GlassCard>
            <h3 style={{ fontSize: '1.05rem', marginBottom: '0.4rem', color: 'var(--text-primary)' }}>
              Organization Identity &amp; Namespace
            </h3>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1.35rem' }}>
              Authoritative multi-tenant isolation parameters defining access scope boundaries.
            </p>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: '1rem' }}>
              <div className="lg-glass-inset" style={{ padding: '12px 14px' }}>
                <span style={{ fontSize: '0.76rem', color: 'var(--text-secondary)' }}>Organization Name</span>
                <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginTop: '4px' }}>
                  {isLoading ? 'Loading...' : org?.name || 'Unavailable'}
                </div>
              </div>

              <div className="lg-glass-inset" style={{ padding: '12px 14px' }}>
                <span style={{ fontSize: '0.76rem', color: 'var(--text-secondary)' }}>Tenant Slug</span>
                <div style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-cyan)', marginTop: '4px' }}>
                  {org?.slug || '—'}
                </div>
              </div>

              <div className="lg-glass-inset" style={{ padding: '12px 14px' }}>
                <span style={{ fontSize: '0.76rem', color: 'var(--text-secondary)' }}>Status</span>
                <div style={{ marginTop: '4px' }}>
                  <GlassBadge tone="success">{org?.status || 'ACTIVE'}</GlassBadge>
                </div>
              </div>

              <div className="lg-glass-inset" style={{ padding: '12px 14px' }}>
                <span style={{ fontSize: '0.76rem', color: 'var(--text-secondary)' }}>Registered Since</span>
                <div style={{ fontSize: '0.85rem', color: 'var(--text-primary)', marginTop: '4px' }}>
                  {org?.created_at ? new Date(org.created_at).toLocaleDateString() : 'N/A'}
                </div>
              </div>
            </div>

            {org?.description && (
              <div className="lg-glass-inset" style={{ marginTop: '1rem', padding: '12px 14px' }}>
                <span style={{ fontSize: '0.76rem', color: 'var(--text-secondary)' }}>Description</span>
                <p style={{ margin: '0.35rem 0 0', color: 'var(--text-primary)', fontSize: '0.85rem' }}>
                  {org.description}
                </p>
              </div>
            )}
          </GlassCard>
        )
      )}

      {activeTab === 'CHANGES' && (
        <Suspense fallback={<PageLoader compact label="Loading rebranding requests..." />}>
          <ChangeRequestsSection />
        </Suspense>
      )}
      {activeTab === 'APPEARANCE' && (
        <Suspense fallback={<PageLoader compact label="Loading appearance settings..." />}>
          <AppearanceSettings />
        </Suspense>
      )}
    </div>
  );
}
