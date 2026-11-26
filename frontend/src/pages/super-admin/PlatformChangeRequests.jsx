import React, { useState, useEffect, useCallback, useMemo } from 'react';
import ApiClient from '../../services/api';
import DataGrid from '../../components/tables/DataGrid';
import RejectChangeRequestModal from '../../components/modals/RejectChangeRequestModal';
import { useToast } from '../../context/ToastContext';

export default function PlatformChangeRequests() {
  const [requests, setRequests] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [search, setSearch] = useState('');
  const [isLoading, setIsLoading] = useState(true);

  const [selectedRequest, setSelectedRequest] = useState(null);
  const [isRejectOpen, setIsRejectOpen] = useState(false);

  const { showToast } = useToast();

  const fetchRequests = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await ApiClient.listPlatformChangeRequests(page, 20, {
        status: statusFilter !== 'ALL' ? statusFilter : undefined,
        search: search.trim() || undefined,
      });
      if (res?.success) {
        const reqList = Array.isArray(res.data) ? res.data : (res.data?.items || res.items || []);
        const total = res.total_count ?? res.pagination?.total ?? res.data?.total ?? reqList.length;
        setRequests(reqList);
        setTotalCount(total);
      }
    } catch (err) {
      console.error('Failed to load change requests:', err);
      showToast('Could not load change requests', 'error');
    } finally {
      setIsLoading(false);
    }
  }, [page, statusFilter, search, showToast]);

  useEffect(() => {
    fetchRequests();
  }, [fetchRequests]);

  const handleApprove = useCallback(async (req) => {
    const reqId = req.request_id || req._id || req.id;
    try {
      const res = await ApiClient.approveChangeRequest(reqId);
      if (res.success) {
        showToast('Change request approved and applied!', 'success');
        fetchRequests();
      } else {
        showToast(res.message || 'Approval failed', 'error');
      }
    } catch (err) {
      showToast(err?.message || 'Error approving request', 'error');
    }
  }, [fetchRequests, showToast]);

  const columnDefs = useMemo(() => [
    {
      headerName: 'Organization',
      field: 'organization_name',
      minWidth: 190,
      flex: 1.2,
      autoHeight: true,
      wrapText: true,
      valueGetter: ({ data }) => data.organization_name || data.organization_id || '',
      cellRenderer: ({ data: req }) => (
        <div>
          <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
            {req.organization_name || req.organization_id}
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
            Submitted by: {req.submitted_by_email || 'Admin'}
          </div>
        </div>
      ),
    },
    {
      headerName: 'Requested Changes',
      field: 'requested_name',
      minWidth: 220,
      flex: 1.5,
      autoHeight: true,
      wrapText: true,
      valueGetter: ({ data }) => [data.requested_name, data.requested_slug, data.justification].filter(Boolean).join(' '),
      cellRenderer: ({ data: req }) => (
        <div style={{ fontSize: '0.85rem' }}>
          {req.requested_name && <div>Name: <strong>{req.requested_name}</strong></div>}
          {req.requested_slug && <div>Slug: <code style={{ color: 'var(--accent-cyan)' }}>{req.requested_slug}</code></div>}
          {req.justification && (
            <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem', marginTop: '2px' }}>
              Justification: {req.justification}
            </div>
          )}
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
      headerName: 'Actions',
      colId: 'actions',
      minWidth: 170,
      maxWidth: 210,
      sortable: false,
      filter: false,
      resizable: false,
      suppressHeaderMenuButton: true,
      headerClass: 'ag-right-aligned-header',
      cellClass: 'ag-actions-cell',
      cellRenderer: ({ data: req }) => {
        if (req.status !== 'PENDING') {
          return (
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              {req.rejection_reason ? `Rejected: ${req.rejection_reason}` : 'Processed'}
            </span>
          );
        }
        return (
          <div style={{ display: 'inline-flex', gap: '6px' }}>
            <button type="button" className="btn btn-success btn-sm" onClick={() => handleApprove(req)}>
              Approve
            </button>
            <button
              type="button"
              className="btn btn-danger btn-sm"
              onClick={() => {
                setSelectedRequest(req);
                setIsRejectOpen(true);
              }}
            >
              Reject
            </button>
          </div>
        );
      },
    },
  ], [handleApprove]);

  return (
    <div className="tab-pane active" id="tab-platform-change-requests">
      {/* Control bar */}
      <div className="card" style={{ marginBottom: '1.5rem', padding: '1rem 1.25rem' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1rem', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center', flex: 1, minWidth: '260px' }}>
            <input
              type="text"
              className="form-control"
              placeholder="Search by organization name or requested slug..."
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              style={{ maxWidth: '320px' }}
            />
            <select
              className="form-control"
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setPage(1);
              }}
              style={{ maxWidth: '160px' }}
            >
              <option value="ALL">All Statuses</option>
              <option value="PENDING">Pending</option>
              <option value="APPROVED">Approved</option>
              <option value="REJECTED">Rejected</option>
            </select>
          </div>

          <button
            type="button"
            className="btn btn-secondary"
            onClick={fetchRequests}
            title="Refresh requests"
          >
            Refresh
          </button>
        </div>
      </div>

      {/* Requests Table */}
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <DataGrid
          rowData={requests}
          columnDefs={columnDefs}
          loading={isLoading}
          emptyMessage="No change requests found."
          getRowId={({ data }) => String(data.request_id || data._id || data.id)}
          pagination={totalCount > 20 || requests.length > 20}
        />
      </div>

      <RejectChangeRequestModal
        isOpen={isRejectOpen}
        onClose={() => setIsRejectOpen(false)}
        request={selectedRequest}
        onRejected={fetchRequests}
      />
    </div>
  );
}
