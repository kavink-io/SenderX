import React, { useState, useEffect, useCallback, useMemo } from 'react';
import ApiClient from '../../services/api';
import DataGrid from '../../components/tables/DataGrid';
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

  const handleRevoke = useCallback(async (cred) => {
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
  }, [fetchCredentials, showToast]);

  const columnDefs = useMemo(() => [
    {
      headerName: 'Key Name',
      field: 'name',
      minWidth: 160,
      valueGetter: ({ data }) => data.name || 'API Key',
      cellStyle: { fontWeight: 600, color: 'var(--text-primary)' },
    },
    {
      headerName: 'Prefix',
      field: 'key_prefix',
      minWidth: 145,
      valueGetter: ({ data }) => data.key_prefix || data.prefix || 'sx_live_****',
      cellRenderer: ({ value }) => <code style={{ color: 'var(--accent-cyan)' }}>{value}</code>,
    },
    {
      headerName: 'Application',
      field: 'application_name',
      minWidth: 140,
      valueGetter: ({ data }) => data.application_name || data.application_id || '',
      cellStyle: { fontSize: '0.85rem', color: 'var(--text-secondary)' },
    },
    {
      headerName: 'Environment',
      field: 'environment',
      minWidth: 115,
      maxWidth: 135,
      valueGetter: ({ data }) => data.environment || 'live',
      cellRenderer: ({ value }) => <span className="badge badge-info">{value}</span>,
    },
    {
      headerName: 'Status',
      field: 'status',
      minWidth: 110,
      maxWidth: 135,
      cellRenderer: ({ value }) => {
        const isActive = value === 'ACTIVE' || value === 'active';
        return <span className={`badge ${isActive ? 'badge-success' : 'badge-danger'}`}>{value}</span>;
      },
    },
    {
      headerName: 'Created',
      field: 'created_at',
      minWidth: 115,
      maxWidth: 145,
      valueFormatter: ({ value }) => (value ? new Date(value).toLocaleDateString() : 'N/A'),
      cellStyle: { fontSize: '0.85rem', color: 'var(--text-secondary)' },
    },
    {
      headerName: 'Actions',
      colId: 'actions',
      minWidth: 155,
      maxWidth: 180,
      sortable: false,
      filter: false,
      resizable: false,
      suppressHeaderMenuButton: true,
      headerClass: 'ag-right-aligned-header',
      cellClass: 'ag-actions-cell',
      cellRenderer: ({ data: cred }) => {
        const isActive = cred.status === 'ACTIVE' || cred.status === 'active';
        if (!canManage || !isActive) return null;
        return (
          <div style={{ display: 'inline-flex', gap: '6px' }}>
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => handleRotate(cred)}>
              Rotate
            </button>
            <button type="button" className="btn btn-danger btn-sm" onClick={() => handleRevoke(cred)}>
              Revoke
            </button>
          </div>
        );
      },
    },
  ], [canManage, handleRevoke]);

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
        <DataGrid
          rowData={credentials}
          columnDefs={columnDefs}
          loading={isLoading}
          emptyMessage="No API credentials found for this scope."
          getRowId={({ data }) => String(data.credential_id || data._id || data.id)}
          pagination={credentials.length > 20}
        />
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
