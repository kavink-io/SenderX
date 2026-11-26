import React, { useState, useEffect, useCallback, useMemo } from 'react';
import ApiClient from '../../services/api';
import DataGrid from '../tables/DataGrid';
import { useToast } from '../../context/ToastContext';
import { useAuth } from '../../context/AuthContext';

export default function ChangeRequestsSection() {
  const [requests, setRequests] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [requestedName, setRequestedName] = useState('');
  const [requestedSlug, setRequestedSlug] = useState('');
  const [justification, setJustification] = useState('');

  const { showToast } = useToast();
  const { isOrgAdmin } = useAuth();

  const fetchRequests = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await ApiClient.listOrgChangeRequests(1, 50);
      if (res?.success) {
        setRequests(res.data?.items || res.data || []);
      }
    } catch (err) {
      console.warn('Could not load org change requests:', err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRequests();
  }, [fetchRequests]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!requestedName.trim() && !requestedSlug.trim()) {
      showToast('Provide at least a new name or slug for the request', 'error');
      return;
    }

    setIsSubmitting(true);
    try {
      const res = await ApiClient.submitChangeRequest({
        requested_name: requestedName.trim() || undefined,
        requested_slug: requestedSlug.trim() || undefined,
        justification: justification.trim() || undefined,
      });

      if (res?.success) {
        showToast('Change request submitted for platform review!', 'success');
        setRequestedName('');
        setRequestedSlug('');
        setJustification('');
        fetchRequests();
      } else {
        showToast(res?.message || 'Submission failed', 'error');
      }
    } catch (err) {
      showToast(err?.message || 'Error submitting request', 'error');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCancel = useCallback(async (req) => {
    const rid = req.request_id || req._id || req.id;
    try {
      const res = await ApiClient.cancelChangeRequest(rid);
      if (res?.success) {
        showToast('Change request cancelled', 'info');
        fetchRequests();
      } else {
        showToast(res?.message || 'Cancellation failed', 'error');
      }
    } catch (err) {
      showToast(err?.message || 'Error cancelling request', 'error');
    }
  }, [fetchRequests, showToast]);

  const columnDefs = useMemo(() => [
    {
      headerName: 'Requested Changes',
      field: 'requested_name',
      minWidth: 200,
      flex: 1.4,
      autoHeight: true,
      wrapText: true,
      valueGetter: ({ data }) => [data.requested_name, data.requested_slug].filter(Boolean).join(' '),
      cellRenderer: ({ data: req }) => (
        <div style={{ fontSize: '0.85rem' }}>
          {req.requested_name && <div>Name: <strong>{req.requested_name}</strong></div>}
          {req.requested_slug && <div>Slug: <code>{req.requested_slug}</code></div>}
        </div>
      ),
    },
    {
      headerName: 'Status',
      field: 'status',
      minWidth: 120,
      maxWidth: 145,
      cellRenderer: ({ value }) => (
        <span className={`badge ${value === 'APPROVED' ? 'badge-success' : value === 'REJECTED' ? 'badge-danger' : 'badge-warning'}`}>
          {value}
        </span>
      ),
    },
    {
      headerName: 'Submitted',
      field: 'created_at',
      minWidth: 120,
      maxWidth: 150,
      valueFormatter: ({ value }) => (value ? new Date(value).toLocaleDateString() : 'N/A'),
      cellStyle: { fontSize: '0.85rem', color: 'var(--text-secondary)' },
    },
    {
      headerName: 'Decision / Rejection Reason',
      field: 'rejection_reason',
      minWidth: 190,
      valueGetter: ({ data }) => data.rejection_reason || '—',
      cellRenderer: ({ data: req, value }) => (
        <span style={{ fontSize: '0.85rem', color: req.rejection_reason ? 'var(--status-error)' : 'var(--text-secondary)' }}>
          {value}
        </span>
      ),
    },
    {
      headerName: 'Actions',
      colId: 'actions',
      minWidth: 105,
      maxWidth: 125,
      sortable: false,
      filter: false,
      resizable: false,
      suppressHeaderMenuButton: true,
      headerClass: 'ag-right-aligned-header',
      cellClass: 'ag-actions-cell',
      cellRenderer: ({ data: req }) => {
        if (req.status !== 'PENDING' || !isOrgAdmin) return null;
        return (
          <button type="button" className="btn btn-secondary btn-sm" onClick={() => handleCancel(req)}>
            Cancel
          </button>
        );
      },
    },
  ], [isOrgAdmin, handleCancel]);

  return (
    <div style={{ marginTop: '1.5rem' }}>
      {isOrgAdmin && (
        <div className="card" style={{ marginBottom: '1.5rem' }}>
          <h4 style={{ fontSize: '1rem', marginBottom: '0.5rem', color: 'var(--text-primary)' }}>
            Request Organization Rebranding
          </h4>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1.25rem' }}>
            Tenant name or slug rebranding requires platform administrator review and verification.
          </p>

          <form onSubmit={handleSubmit}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem', marginBottom: '1rem' }}>
              <div className="form-group">
                <label>Requested Organization Name</label>
                <input
                  type="text"
                  className="form-control"
                  value={requestedName}
                  onChange={(e) => setRequestedName(e.target.value)}
                  placeholder="New Legal Entity Name"
                />
              </div>

              <div className="form-group">
                <label>Requested Slug</label>
                <input
                  type="text"
                  className="form-control"
                  value={requestedSlug}
                  onChange={(e) => setRequestedSlug(e.target.value.toLowerCase())}
                  placeholder="new-entity-slug"
                />
              </div>
            </div>

            <div className="form-group" style={{ marginBottom: '1rem' }}>
              <label>Business Justification</label>
              <textarea
                className="form-control"
                value={justification}
                onChange={(e) => setJustification(e.target.value)}
                placeholder="Explain the legal or brand motivation for this identifier update..."
                rows={2}
              />
            </div>

            <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
              {isSubmitting ? 'Submitting...' : 'Submit Rebranding Request'}
            </button>
          </form>
        </div>
      )}

      {/* History table */}
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div style={{ padding: '1rem 1.25rem', borderBottom: '1px solid var(--glass-border)' }}>
          <h4 style={{ fontSize: '0.95rem', margin: 0, color: 'var(--text-primary)' }}>
            Change Request Status History
          </h4>
        </div>
        <DataGrid
          rowData={requests}
          columnDefs={columnDefs}
          loading={isLoading}
          emptyMessage="No rebranding requests on record."
          getRowId={({ data }) => String(data.request_id || data._id || data.id)}
          pagination={requests.length > 20}
        />
      </div>
    </div>
  );
}
