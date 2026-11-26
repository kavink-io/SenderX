import React, { useState, useEffect, useCallback } from 'react';
import ApiClient from '../../services/api';
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

  const handleDelete = async (app) => {
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
  };

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
        <div className="table-responsive-wrapper">
          <table className="data-table" style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                <th>Application Name</th>
                <th>Application ID</th>
                <th>Environment</th>
                <th>Status</th>
                <th style={{ textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={5} style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                    Loading applications...
                  </td>
                </tr>
              ) : apps.length === 0 ? (
                <tr>
                  <td colSpan={5} style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                    No connected applications found.
                  </td>
                </tr>
              ) : (
                apps.map((app) => {
                  const appId = app.application_id || app._id || app.id;
                  const isActive = app.status === 'ACTIVE' || app.status === 'active';

                  return (
                    <tr key={appId}>
                      <td>
                        <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{app.name}</div>
                        {app.description && (
                          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                            {app.description}
                          </div>
                        )}
                      </td>
                      <td>
                        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85rem', color: 'var(--accent-cyan)' }}>
                          {appId}
                        </span>
                      </td>
                      <td>
                        <span className="badge badge-info">{app.environment || 'live'}</span>
                      </td>
                      <td>
                        <span className={`badge ${isActive ? 'badge-success' : 'badge-danger'}`}>
                          {app.status}
                        </span>
                      </td>
                      <td style={{ textAlign: 'right' }}>
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
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
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
