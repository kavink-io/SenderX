import React, { useCallback, useEffect, useMemo, useState } from 'react';
import ApiClient from '../../services/api';
import DataGrid from '../../components/tables/DataGrid';
import GridActionButton from '../../components/tables/GridActionButton';
import Modal from '../../components/common/Modal';
import { GlassSelect } from '../../components/glass';
import { useToast } from '../../context/ToastContext';
import { useAuth } from '../../context/AuthContext';
import { useAppScope } from '../../context/ScopeContext';

const EMPTY_FORM = {
  name: '',
  application_id: '',
  api_key: '',
  description: '',
  environment: 'live',
  status: 'ACTIVE',
  notes: '',
};

const MASKED_KEY = '••••••••••••••••';

function getApplicationId(application) {
  return String(application.application_id || application.id || application._id || '');
}

export default function ApiCredentials() {
  const [credentials, setCredentials] = useState([]);
  const [apps, setApps] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [panelOpen, setPanelOpen] = useState(false);
  const [panelMode, setPanelMode] = useState('create');
  const [selectedCredential, setSelectedCredential] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const { showToast } = useToast();
  const { hasPermission } = useAuth();
  const { activeAppId } = useAppScope();
  const canManage = hasPermission('organization:configuration:manage');
  const isReadOnly = panelMode === 'view';
  const isEditing = panelMode === 'edit';

  const fetchCredentials = useCallback(async () => {
    setIsLoading(true);
    try {
      const [credentialsResponse, applicationsResponse] = await Promise.all([
        ApiClient.listCredentials(activeAppId || undefined),
        ApiClient.listApplications(1, 100),
      ]);

      if (credentialsResponse?.success) {
        setCredentials(credentialsResponse.data?.items || credentialsResponse.data || []);
      }
      if (applicationsResponse?.success) {
        const applicationList = applicationsResponse.data?.items || applicationsResponse.data || [];
        setApps(Array.isArray(applicationList) ? applicationList : []);
      }
    } catch (error) {
      console.error('Failed to load API credentials:', error);
      showToast('Could not load API credentials', 'error');
    } finally {
      setIsLoading(false);
    }
  }, [activeAppId, showToast]);

  useEffect(() => {
    fetchCredentials();
  }, [fetchCredentials]);

  const applicationNames = useMemo(() => new Map(
    apps.map((application) => [
      getApplicationId(application),
      application.name || application.application_name || getApplicationId(application),
    ])
  ), [apps]);

  const closePanel = useCallback(() => {
    setPanelOpen(false);
    setSelectedCredential(null);
    setForm(EMPTY_FORM);
  }, []);

  const openCreate = () => {
    setPanelMode('create');
    setSelectedCredential(null);
    setForm({
      ...EMPTY_FORM,
      application_id: activeAppId || (apps.length === 1 ? getApplicationId(apps[0]) : ''),
    });
    setPanelOpen(true);
  };

  const openCredential = (credential, mode) => {
    const applicationId = String(credential.application_id || '');
    setPanelMode(mode);
    setSelectedCredential(credential);
    setForm({
      ...EMPTY_FORM,
      name: credential.name || '',
      application_id: applicationId,
      description: credential.description || '',
      environment: credential.environment || 'live',
      status: credential.status || 'ACTIVE',
      notes: credential.notes || '',
      api_key: '',
    });
    setPanelOpen(true);
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (isReadOnly) return;
    if (!form.name.trim() || !form.application_id) {
      showToast('Name and connected application are required', 'error');
      return;
    }
    if (!isEditing && !form.api_key) {
      showToast('Enter the API key supplied by the connected application', 'error');
      return;
    }

    const payload = {
      name: form.name.trim(),
      application_id: form.application_id,
      description: form.description.trim(),
      environment: form.environment,
      status: form.status,
      notes: form.notes.trim(),
    };
    if (form.api_key) payload.api_key = form.api_key;

    setIsSubmitting(true);
    try {
      const response = isEditing
        ? await ApiClient.updateCredential(selectedCredential.credential_id, payload)
        : await ApiClient.createCredential(payload);

      if (!response?.success) {
        showToast(response?.message || 'Could not save API key', 'error');
        return;
      }
      showToast(isEditing ? 'API key updated successfully' : 'API key registered successfully', 'success');
      closePanel();
      await fetchCredentials();
    } catch (error) {
      showToast(error?.message || 'Could not save API key', 'error');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setIsDeleting(true);
    try {
      const response = await ApiClient.deleteCredential(deleteTarget.credential_id);
      if (!response?.success) {
        showToast(response?.message || 'Could not delete API key', 'error');
        return;
      }
      showToast('API key deleted successfully', 'success');
      setDeleteTarget(null);
      await fetchCredentials();
    } catch (error) {
      showToast(error?.message || 'Could not delete API key', 'error');
    } finally {
      setIsDeleting(false);
    }
  };

  const columnDefs = useMemo(() => [
    {
      headerName: 'API Key Name',
      field: 'name',
      minWidth: 150,
      flex: 1.2,
      tooltipField: 'name',
      cellStyle: { fontWeight: 600, color: 'var(--text-primary)' },
    },
    {
      headerName: 'Connected Application',
      field: 'application_id',
      minWidth: 160,
      flex: 1.2,
      valueGetter: ({ data }) => applicationNames.get(String(data.application_id || '')) || 'Unknown application',
      tooltipValueGetter: ({ value }) => value,
      cellStyle: { fontSize: '0.85rem', color: 'var(--text-secondary)' },
    },
    {
      headerName: 'Key Identifier',
      field: 'key_prefix',
      minWidth: 150,
      maxWidth: 185,
      valueGetter: () => MASKED_KEY,
      cellRenderer: ({ value }) => (
        <code aria-label="API key masked" style={{ color: 'var(--text-secondary)', letterSpacing: '0.08em' }}>
          {value}
        </code>
      ),
    },
    {
      headerName: 'Environment',
      field: 'environment',
      minWidth: 112,
      maxWidth: 130,
      valueGetter: ({ data }) => data.environment || 'live',
      cellRenderer: ({ value }) => {
        const label = { live: 'PRODUCTION', test: 'TESTING' }[value] || String(value || 'UNKNOWN').toUpperCase();
        return <span className="badge badge-info">{label}</span>;
      },
    },
    {
      headerName: 'Status',
      field: 'status',
      minWidth: 105,
      maxWidth: 125,
      cellRenderer: ({ value }) => {
        const isActive = value === 'ACTIVE';
        return <span className={`badge ${isActive ? 'badge-success' : 'badge-danger'}`}>{value || 'INACTIVE'}</span>;
      },
    },
    {
      headerName: 'Created At',
      field: 'created_at',
      minWidth: 112,
      maxWidth: 140,
      valueFormatter: ({ value }) => (value ? new Date(value).toLocaleDateString() : 'N/A'),
      cellStyle: { fontSize: '0.85rem', color: 'var(--text-secondary)' },
    },
    {
      headerName: 'Last Updated',
      field: 'updated_at',
      minWidth: 112,
      maxWidth: 140,
      valueFormatter: ({ value }) => (value ? new Date(value).toLocaleDateString() : 'N/A'),
      cellStyle: { fontSize: '0.85rem', color: 'var(--text-secondary)' },
    },
    {
      headerName: 'Actions',
      colId: 'actions',
      minWidth: 112,
      maxWidth: 126,
      sortable: false,
      filter: false,
      resizable: false,
      suppressHeaderMenuButton: true,
      headerClass: 'ag-right-aligned-header',
      cellClass: 'ag-actions-cell',
      cellRenderer: ({ data: credential }) => (
        <div className="ag-icon-actions" role="group" aria-label="API key actions">
          <GridActionButton icon="view" label="View API Key Details" onClick={() => openCredential(credential, 'view')} />
          {canManage && (
            <>
              <GridActionButton icon="edit" label="Edit API Key" onClick={() => openCredential(credential, 'edit')} />
              <GridActionButton
                icon="delete"
                label="Delete API Key"
                variant="danger"
                onClick={() => setDeleteTarget(credential)}
              />
            </>
          )}
        </div>
      ),
    },
  ], [applicationNames, canManage]);

  const connectedApplicationName = deleteTarget
    ? applicationNames.get(String(deleteTarget.application_id || '')) || 'Unknown application'
    : '';

  return (
    <div className="tab-pane active" id="tab-org-credentials">
      <div className="card" style={{ marginBottom: '1.5rem', padding: '1rem 1.25rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
          <div>
            <h3 style={{ fontSize: '1rem', margin: '0 0 0.25rem', color: 'var(--text-primary)' }}>
              API Access Credentials
            </h3>
            <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              Register and manage API keys supplied by your connected applications.
            </p>
          </div>
          {canManage && (
            <button type="button" className="btn btn-primary" onClick={openCreate} id="btn-open-add-credential">
              + Add API Key
            </button>
          )}
        </div>
      </div>

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <DataGrid
          rowData={credentials}
          columnDefs={columnDefs}
          loading={isLoading}
          emptyMessage="No API keys are registered for this scope."
          getRowId={({ data }) => String(data.credential_id || data._id || data.id)}
          pagination={credentials.length > 20}
        />
      </div>

      <Modal
        isOpen={panelOpen}
        onClose={closePanel}
        title={panelMode === 'create' ? 'Add API Key' : panelMode === 'edit' ? 'Edit API Key' : 'API Key Details'}
        description="API keys are supplied by the connected application and stored securely."
        maxWidth="540px"
        id="panel-api-credential"
      >
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="credential-name">API Key Name *</label>
            <input
              id="credential-name"
              className="form-control"
              type="text"
              value={form.name}
              onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
              maxLength={100}
              required
              disabled={isReadOnly || isSubmitting}
              autoComplete="off"
            />
          </div>

          <div className="form-group">
            <label htmlFor="credential-application">Connected Application *</label>
            <GlassSelect
              id="credential-application"
              value={form.application_id}
              onChange={(event) => setForm((current) => ({ ...current, application_id: event.target.value }))}
              required
              disabled={isReadOnly || isSubmitting || isEditing}
            >
              <option value="">Select an application</option>
              {apps.map((application) => {
                const id = getApplicationId(application);
                return <option key={id} value={id}>{application.name || application.application_name || id}</option>;
              })}
            </GlassSelect>
          </div>

          <div className="form-group">
            <label htmlFor="credential-api-key">{isEditing ? 'Replace API Key' : 'API Key Value *'}</label>
            <input
              id="credential-api-key"
              className="form-control"
              type="password"
              value={form.api_key}
              onChange={(event) => setForm((current) => ({ ...current, api_key: event.target.value }))}
              placeholder={isEditing ? 'Leave empty to keep the current key' : 'Paste the key provided by the application'}
              required={!isEditing}
              disabled={isReadOnly || isSubmitting}
              autoComplete="new-password"
            />
            {isEditing && (
              <small style={{ color: 'var(--text-secondary)' }}>
                Current key: {MASKED_KEY}. It will be preserved unless you supply a replacement.
              </small>
            )}
          </div>

          <div className="form-group">
            <label htmlFor="credential-description">Description</label>
            <textarea
              id="credential-description"
              className="form-control"
              value={form.description}
              onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))}
              maxLength={500}
              rows={2}
              disabled={isReadOnly || isSubmitting}
            />
          </div>

          <div className="form-group">
            <label htmlFor="credential-environment">Environment</label>
            <GlassSelect
              id="credential-environment"
              value={form.environment}
              onChange={(event) => setForm((current) => ({ ...current, environment: event.target.value }))}
              disabled={isReadOnly || isSubmitting}
            >
              <option value="live">Production</option>
              <option value="test">Testing</option>
            </GlassSelect>
          </div>

          <div className="form-group">
            <label htmlFor="credential-status">Status</label>
            <GlassSelect
              id="credential-status"
              value={form.status}
              onChange={(event) => setForm((current) => ({ ...current, status: event.target.value }))}
              disabled={isReadOnly || isSubmitting || selectedCredential?.status === 'REVOKED'}
            >
              <option value="ACTIVE">Active</option>
              <option value="INACTIVE">Inactive</option>
              {form.status === 'REVOKED' && <option value="REVOKED">Revoked</option>}
            </GlassSelect>
          </div>

          <div className="form-group" style={{ marginBottom: '1.5rem' }}>
            <label htmlFor="credential-notes">Notes</label>
            <textarea
              id="credential-notes"
              className="form-control"
              value={form.notes}
              onChange={(event) => setForm((current) => ({ ...current, notes: event.target.value }))}
              maxLength={2000}
              rows={2}
              disabled={isReadOnly || isSubmitting}
            />
          </div>

          <div className="modal-actions" style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
            <button type="button" className="btn btn-secondary" onClick={closePanel} disabled={isSubmitting}>
              {isReadOnly ? 'Close' : 'Cancel'}
            </button>
            {!isReadOnly && (
              <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
                {isSubmitting ? 'Saving...' : isEditing ? 'Save Changes' : 'Add API Key'}
              </button>
            )}
          </div>
        </form>
      </Modal>

      <Modal
        isOpen={Boolean(deleteTarget)}
        onClose={() => setDeleteTarget(null)}
        title="Delete API Key"
        maxWidth="440px"
        variant="dialog"
        id="dialog-delete-api-credential"
        footer={
          <div className="modal-actions" style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
            <button type="button" className="btn btn-secondary" onClick={() => setDeleteTarget(null)} disabled={isDeleting}>
              Cancel
            </button>
            <button type="button" className="btn btn-danger" onClick={handleDelete} disabled={isDeleting}>
              {isDeleting ? 'Deleting...' : 'Delete API Key'}
            </button>
          </div>
        }
      >
        <p style={{ color: 'var(--text-secondary)' }}>
          Delete the API key for <strong>{connectedApplicationName}</strong>? This key will no longer authenticate
          requests. The connected application and its other keys will remain.
        </p>
      </Modal>
    </div>
  );
}
