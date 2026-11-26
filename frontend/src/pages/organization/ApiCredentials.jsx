import React, { useState, useEffect, useCallback } from 'react';
import ApiClient from '../../services/api';
import GenerateCredentialModal from '../../components/modals/GenerateCredentialModal';
import SecretRevealModal from '../../components/modals/SecretRevealModal';
import { useToast } from '../../context/ToastContext';
import { useAuth } from '../../context/AuthContext';
import { useAppScope } from '../../context/ScopeContext';

export default function ApiCredentials() {
  const [credentials, setCredentials] = useState([]);
  const [apps, setApps] = useState([]);
  const [isLoading, setIsLoading] = useState(true);

  const [isGenerateOpen, setIsGenerateOpen] = useState(false);
  const [revealedSecret, setRevealedSecret] = useState(null);
  const [revealedKeyName, setRevealedKeyName] = useState('');

  const { showToast } = useToast();
  const { hasPermission } = useAuth();
  const { activeAppId } = useAppScope();
  const canManage = hasPermission('organization:configuration:manage');

  const fetchCredentials = useCallback(async () => {
    setIsLoading(true);
    try {
      const [credsRes, appsRes] = await Promise.all([
        ApiClient.listCredentials(activeAppId || undefined),
        ApiClient.listApplications(1, 100),
      ]);

      if (credsRes?.success) {
        setCredentials(credsRes.data?.items || credsRes.data || []);
      }
      if (appsRes?.success) {
        setApps(Array.isArray(appsRes.data) ? appsRes.data : (appsRes.data?.items || []));
      }
    } catch (err) {
      console.error('Failed to load credentials:', err);
      showToast('Could not load API credentials', 'error');
    } finally {
      setIsLoading(false);
    }
  }, [activeAppId, showToast]);

  useEffect(() => {
    fetchCredentials();
  }, [fetchCredentials]);

  const handleRotate = async (cred) => {
    const credId = cred.credential_id || cred._id || cred.id;
    if (!window.confirm(`Rotate API credential "${cred.name || credId}"? The previous key will be immediately invalidated.`)) {
      return;
    }

    try {
      const res = await ApiClient.rotateCredential(credId, cred.environment || 'live');
      const rawSecret = res.data?.raw_key || res.data?.secret_key || res.data?.api_key || res.raw_key || res.api_key;
      if (res.success && rawSecret) {
        showToast('Credential rotated successfully!', 'success');
        setRevealedSecret(rawSecret);
        setRevealedKeyName(cred.name || 'Rotated Key');
        fetchCredentials();
      } else {
        showToast(res.message || 'Rotation failed', 'error');
      }
    } catch (err) {
      showToast(err?.message || 'Error rotating credential', 'error');
    }
  };

  const handleRevoke = async (cred) => {
    const credId = cred.credential_id || cred._id || cred.id;
    if (!window.confirm(`Revoke API credential "${cred.name || credId}"? Inbound requests using this key will be rejected.`)) {
      return;
    }

    try {
      const res = await ApiClient.revokeCredential(credId);
      if (res.success) {
        showToast('Credential revoked successfully', 'info');
        fetchCredentials();
      } else {
        showToast(res.message || 'Revocation failed', 'error');
      }
    } catch (err) {
      showToast(err?.message || 'Error revoking credential', 'error');
    }
  };

  return (
    <div className="tab-pane active" id="tab-org-credentials">
      <div className="card" style={{ marginBottom: '1.5rem', padding: '1rem 1.25rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h3 style={{ fontSize: '1rem', margin: '0 0 0.25rem', color: 'var(--text-primary)' }}>
              API Access Credentials
            </h3>
            <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              Bearer keys utilized by external applications to route high-volume notifications.
            </p>
          </div>

          {canManage && (
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => setIsGenerateOpen(true)}
              id="btn-open-generate-credential"
            >
              + Generate Key
            </button>
          )}
        </div>
      </div>

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div className="table-responsive-wrapper">
          <table className="data-table" style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                <th>Key Name</th>
                <th>Prefix</th>
                <th>Application</th>
                <th>Environment</th>
                <th>Status</th>
                <th>Created</th>
                <th style={{ textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={7} style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                    Loading credentials...
                  </td>
                </tr>
              ) : credentials.length === 0 ? (
                <tr>
                  <td colSpan={7} style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                    No API credentials found for this scope.
                  </td>
                </tr>
              ) : (
                credentials.map((cred) => {
                  const credId = cred.credential_id || cred._id || cred.id;
                  const isActive = cred.status === 'ACTIVE' || cred.status === 'active';

                  return (
                    <tr key={credId}>
                      <td style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                        {cred.name || 'API Key'}
                      </td>
                      <td>
                        <code style={{ color: 'var(--accent-cyan)' }}>
                          {cred.key_prefix || cred.prefix || 'sx_live_****'}
                        </code>
                      </td>
                      <td style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                        {cred.application_name || cred.application_id}
                      </td>
                      <td>
                        <span className="badge badge-info">{cred.environment || 'live'}</span>
                      </td>
                      <td>
                        <span className={`badge ${isActive ? 'badge-success' : 'badge-danger'}`}>
                          {cred.status}
                        </span>
                      </td>
                      <td style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                        {cred.created_at ? new Date(cred.created_at).toLocaleDateString() : 'N/A'}
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        {canManage && isActive && (
                          <div style={{ display: 'inline-flex', gap: '6px' }}>
                            <button
                              type="button"
                              className="btn btn-secondary btn-sm"
                              onClick={() => handleRotate(cred)}
                            >
                              Rotate
                            </button>
                            <button
                              type="button"
                              className="btn btn-danger btn-sm"
                              onClick={() => handleRevoke(cred)}
                            >
                              Revoke
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      <GenerateCredentialModal
        isOpen={isGenerateOpen}
        onClose={() => setIsGenerateOpen(false)}
        apps={apps}
        onGenerated={(secret, name) => {
          setRevealedSecret(secret);
          setRevealedKeyName(name);
          fetchCredentials();
        }}
      />

      <SecretRevealModal
        isOpen={Boolean(revealedSecret)}
        onClose={() => setRevealedSecret(null)}
        secretKey={revealedSecret}
        keyName={revealedKeyName}
      />
    </div>
  );
}
