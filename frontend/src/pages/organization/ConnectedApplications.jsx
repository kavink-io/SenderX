import React, { useState, useEffect, useCallback, useMemo } from 'react';
import ApiClient from '../../services/api';
import DataGrid from '../../components/tables/DataGrid';
import RegisterAppModal from '../../components/modals/RegisterAppModal';
import AppDetailsModal from '../../components/modals/AppDetailsModal';
import { useToast } from '../../context/ToastContext';
import { useAuth } from '../../context/AuthContext';

export default function ConnectedApplications() {
  const [apps, setApps] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('ALL');

  const [isRegisterOpen, setIsRegisterOpen] = useState(false);
  const [selectedApp, setSelectedApp] = useState(null);
  const [isDetailsOpen, setIsDetailsOpen] = useState(false);

  const { showToast } = useToast();
  const { hasPermission } = useAuth();
  const canManage = hasPermission('organization:configuration:manage');

  const fetchApps = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await ApiClient.listApplications(1, 100, statusFilter !== 'ALL' ? statusFilter : null);
      if (res?.success) {
        setApps(Array.isArray(res.data) ? res.data : (res.data?.items || []));
      }
    } catch (err) {
      console.error('Failed to load applications:', err);
      showToast('Could not load connected applications', 'error');
    } finally {
      setIsLoading(false);
    }
  }, [statusFilter, showToast]);

  useEffect(() => {
    fetchApps();
  }, [fetchApps]);

  const handleToggleActive = async (app) => {
    const appId = app.application_id || app._id || app.id;
    const isActive = app.status === 'ACTIVE' || app.status === 'active';
    try {
      const res = isActive
        ? await ApiClient.deactivateApplication(appId)
        : await ApiClient.activateApplication(appId);

      if (res.success) {
        showToast(`Application ${isActive ? 'deactivated' : 'activated'} successfully!`, 'success');
        fetchApps();
      } else {
        showToast(res.message || 'Status update failed', 'error');
      }
    } catch (err) {
      showToast(err?.message || 'Error updating application status', 'error');
    }
  };

  const handleDelete = useCallback(async (app) => {
    const appId = app.application_id || app._id || app.id;
    if (!window.confirm(`Delete application "${app.name || appId}"? Its credentials will be revoked and its history retained.`)) return;
    try {
      const res = await ApiClient.deleteApplication(appId);
      if (res.success) {
        showToast('Application deleted and credentials revoked', 'success');
        fetchApps();
      } else {
        showToast(res.message || 'Application deletion failed', 'error');
      }
    } catch (err) {
      showToast(err?.message || 'Error deleting application', 'error');
    }
  }, [fetchApps, showToast]);

  const columnDefs = useMemo(() => [
    {
      headerName: 'Application Name',
      field: 'name',
      minWidth: 200,
      flex: 1.4,
      autoHeight: true,
      wrapText: true,
      cellRenderer: ({ data: app }) => (
        <div>
          <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{app.name}</div>
          {app.description && (
            <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{app.description}</div>
          )}
        </div>
      ),
    },
    {
      headerName: 'Application ID',
      field: 'application_id',
      minWidth: 165,
      valueGetter: ({ data }) => data.application_id || data._id || data.id || '',
      cellRenderer: ({ value }) => (
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85rem', color: 'var(--accent-cyan)' }}>
          {value}
        </span>
      ),
    },
    {
      headerName: 'Environment',
      field: 'environment',
      minWidth: 115,
      maxWidth: 140,
      valueGetter: ({ data }) => data.environment || 'live',
      cellRenderer: ({ value }) => <span className="badge badge-info">{value}</span>,
    },
    {
      headerName: 'Status',
      field: 'status',
      minWidth: 115,
      maxWidth: 140,
      cellRenderer: ({ value }) => {
        const isActive = value === 'ACTIVE' || value === 'active';
        return <span className={`badge ${isActive ? 'badge-success' : 'badge-danger'}`}>{value}</span>;
      },
    },
    {
      headerName: 'Actions',
      colId: 'actions',
      minWidth: 230,
      maxWidth: 255,
      sortable: false,
      filter: false,
      resizable: false,
      suppressHeaderMenuButton: true,
      headerClass: 'ag-right-aligned-header',
      cellClass: 'ag-actions-cell',
      cellRenderer: ({ data: app }) => {
        const isActive = app.status === 'ACTIVE' || app.status === 'active';
        return (
          <div style={{ display: 'inline-flex', gap: '6px' }}>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => {
                setSelectedApp(app);
                setIsDetailsOpen(true);
              }}
            >
              Details
            </button>
            {canManage && (
              <>
                <button
                  type="button"
                  className={`btn btn-sm ${isActive ? 'btn-secondary' : 'btn-success'}`}
                  onClick={() => handleToggleActive(app)}
                >
                  {isActive ? 'Deactivate' : 'Activate'}
                </button>
                <button type="button" className="btn btn-danger btn-sm" onClick={() => handleDelete(app)}>
                  Delete
                </button>
              </>
            )}
          </div>
        );
      },
    },
  ], [canManage, handleDelete]);

  return (
    <div className="tab-pane active" id="tab-org-applications">
      <div className="card" style={{ marginBottom: '1.5rem', padding: '1rem 1.25rem' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1rem', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
            <select
              className="form-control"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              style={{ maxWidth: '160px' }}
            >
              <option value="ALL">All Statuses</option>
              <option value="ACTIVE">Active</option>
              <option value="INACTIVE">Inactive</option>
            </select>
          </div>

          {canManage && (
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => setIsRegisterOpen(true)}
              id="btn-open-register-app"
            >
              + Register Application
            </button>
          )}
        </div>
      </div>

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <DataGrid
          rowData={apps}
          columnDefs={columnDefs}
          loading={isLoading}
          emptyMessage="No connected applications found."
          getRowId={({ data }) => String(data.application_id || data._id || data.id)}
          pagination={apps.length > 20}
        />
      </div>

      <RegisterAppModal
        isOpen={isRegisterOpen}
        onClose={() => setIsRegisterOpen(false)}
        onRegistered={fetchApps}
      />

      <AppDetailsModal
        isOpen={isDetailsOpen}
        onClose={() => setIsDetailsOpen(false)}
        app={selectedApp}
      />
    </div>
  );
}
