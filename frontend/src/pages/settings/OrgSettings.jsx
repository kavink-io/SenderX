import React, { useState, useEffect } from 'react';
import ApiClient from '../../services/api';
import ChangeRequestsSection from '../../components/settings/ChangeRequestsSection';
import ProviderConfigSection from '../../components/settings/ProviderConfigSection';
import { useToast } from '../../context/ToastContext';
import { useAuth } from '../../context/AuthContext';

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
      <div style={{ display: 'flex', gap: '8px', marginBottom: '1.5rem', borderBottom: '1px solid var(--glass-border)', paddingBottom: '0.75rem' }}>
        <button
          type="button"
          className={`btn btn-sm ${activeTab === 'IDENTITY' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setActiveTab('IDENTITY')}
        >
          Organization Identity
        </button>
        <button
          type="button"
          className={`btn btn-sm ${activeTab === 'CHANGES' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setActiveTab('CHANGES')}
        >
          Rebranding Requests
        </button>
        <button
          type="button"
          className={`btn btn-sm ${activeTab === 'PROVIDERS' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setActiveTab('PROVIDERS')}
        >
          Provider Configurations
        </button>
      </div>

      {activeTab === 'IDENTITY' && (
        <div className="card">
          <h3 style={{ fontSize: '1.05rem', marginBottom: '0.5rem', color: 'var(--text-primary)' }}>
            Organization Identity & Namespace
          </h3>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1.5rem' }}>
            Authoritative multi-tenant isolation parameters defining access scope boundaries.
          </p>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1.25rem' }}>
            <div>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Organization Name</span>
              <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginTop: '2px' }}>
                {org?.name || 'Loading...'}
              </div>
            </div>

            <div>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Tenant Slug</span>
              <div style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-cyan)', marginTop: '2px' }}>
                {org?.slug || '—'}
              </div>
            </div>

            <div>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Status</span>
              <div style={{ marginTop: '2px' }}>
                <span className="badge badge-success">{org?.status || 'ACTIVE'}</span>
              </div>
            </div>

            <div>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Registered Since</span>
              <div style={{ fontSize: '0.85rem', color: 'var(--text-primary)', marginTop: '2px' }}>
                {org?.created_at ? new Date(org.created_at).toLocaleDateString() : 'N/A'}
              </div>
            </div>
          </div>

          {org?.description && (
            <div style={{ marginTop: '1.25rem', background: 'var(--bg-surface)', padding: '0.75rem', borderRadius: '6px' }}>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Description</span>
              <p style={{ margin: '0.25rem 0 0', color: 'var(--text-primary)', fontSize: '0.85rem' }}>
                {org.description}
              </p>
            </div>
          )}
        </div>
      )}

      {activeTab === 'CHANGES' && <ChangeRequestsSection />}
      {activeTab === 'PROVIDERS' && <ProviderConfigSection />}
    </div>
  );
}
