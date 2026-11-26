import React, { useState, useEffect } from 'react';
import ApiClient from '../../services/api';
import ChangeRequestsSection from '../../components/settings/ChangeRequestsSection';
import ProviderConfigSection from '../../components/settings/ProviderConfigSection';
import { useToast } from '../../context/ToastContext';
import { useAuth } from '../../context/AuthContext';
import { GlassCard, GlassTabs, GlassBadge } from '../../components/glass';

export default function OrgSettings() {
  const [org, setOrg] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('IDENTITY'); // 'IDENTITY', 'CHANGES', 'PROVIDERS'

  const { isOrgAdmin } = useAuth();
  const { showToast } = useToast();

  useEffect(() => {
    async function fetchOrg() {
      setIsLoading(true);
      try {
        const res = await ApiClient.getCurrentOrganization();
        if (res?.success) {
          setOrg(res.data);
        }
      } catch (err) {
        console.warn('Could not load organization identity:', err);
      } finally {
        setIsLoading(false);
      }
    }
    fetchOrg();
  }, []);

  return (
    <div className="tab-pane active" id="tab-org-settings">
      {/* Settings Navigation Tabs */}
      <div style={{ marginBottom: '1.35rem' }}>
        <GlassTabs
          activeKey={activeTab}
          onChange={setActiveTab}
          tabs={[
            { key: 'IDENTITY', label: 'Organization Identity' },
            { key: 'CHANGES', label: 'Rebranding Requests' },
            { key: 'PROVIDERS', label: 'Provider Configurations' },
          ]}
        />
      </div>

      {activeTab === 'IDENTITY' && (
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
                {org?.name || 'Loading...'}
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
      )}

      {activeTab === 'CHANGES' && <ChangeRequestsSection />}
      {activeTab === 'PROVIDERS' && <ProviderConfigSection />}
    </div>
  );
}
