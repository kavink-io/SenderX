import React, { useState, useEffect, useCallback, useMemo } from 'react';
import ApiClient from '../../services/api';
import DataGrid from '../../components/tables/DataGrid';
import CreateOrgModal from '../../components/modals/CreateOrgModal';
import OrgDetailsModal from '../../components/modals/OrgDetailsModal';
import DeleteOrgModal from '../../components/modals/DeleteOrgModal';
import { useToast } from '../../context/ToastContext';

export default function PlatformOrganizations() {
  const [organizations, setOrganizations] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [isLoading, setIsLoading] = useState(true);

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [selectedOrg, setSelectedOrg] = useState(null);
  const [isDetailsOpen, setIsDetailsOpen] = useState(false);
  const [isDeleteOpen, setIsDeleteOpen] = useState(false);

  const { showToast } = useToast();

  const fetchOrgs = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await ApiClient.listOrganizations(page, 20, {
        search: search.trim() || undefined,
        status: statusFilter !== 'ALL' ? statusFilter : undefined,
      });
      if (res?.success) {
        const orgList = Array.isArray(res.data) ? res.data : (res.data?.items || res.items || []);
        const total = res.total_count ?? res.pagination?.total ?? res.data?.total ?? orgList.length;
        setOrganizations(orgList);
        setTotalCount(total);
      }
    } catch (err) {
      console.error('Failed to load organizations:', err);
      showToast('Could not load organizations list', 'error');
    } finally {
      setIsLoading(false);
    }
  }, [page, search, statusFilter, showToast]);

  useEffect(() => {
    fetchOrgs();
  }, [fetchOrgs]);

  const handleToggleStatus = useCallback(async (org) => {
    const orgId = org.organization_id || org._id || org.id;
    const nextStatus = org.status === 'ACTIVE' ? 'SUSPENDED' : 'ACTIVE';
    try {
      const res = await ApiClient.updateOrganizationStatus(orgId, nextStatus);
      if (res.success) {
        showToast(`Organization status changed to ${nextStatus}`, 'success');
        fetchOrgs();
      } else {
        showToast(res.message || 'Status change failed', 'error');
      }
    } catch (err) {
      showToast(err?.message || 'Error changing organization status', 'error');
    }
  }, [fetchOrgs, showToast]);

  const columnDefs = useMemo(() => [
    {
      headerName: 'Organization',
      field: 'name',
      minWidth: 200,
      flex: 1.4,
      autoHeight: true,
      wrapText: true,
      cellRenderer: ({ data: org }) => (
        <div style={{ minWidth: 0 }}>
          <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{org.name}</div>
          {org.description && (
            <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {org.description}
            </div>
          )}
        </div>
      ),
    },
    {
      headerName: 'Slug',
      field: 'slug',
      minWidth: 140,
      cellRenderer: ({ value }) => (
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85rem', color: 'var(--accent-cyan)' }}>
          {value}
        </span>
      ),
    },
    {
      headerName: 'Status',
      field: 'status',
      minWidth: 120,
      maxWidth: 145,
      cellRenderer: ({ value }) => (
        <span className={`badge ${value === 'ACTIVE' ? 'badge-success' : 'badge-danger'}`}>
          {value}
        </span>
      ),
    },
    {
      headerName: 'Created',
      field: 'created_at',
      minWidth: 120,
      maxWidth: 150,
      valueFormatter: ({ value }) => (value ? new Date(value).toLocaleDateString() : 'N/A'),
      cellStyle: { fontSize: '0.85rem', color: 'var(--text-secondary)' },
    },
    {
      headerName: 'Actions',
      colId: 'actions',
      minWidth: 225,
      maxWidth: 250,
      sortable: false,
      filter: false,
      resizable: false,
      suppressHeaderMenuButton: true,
      headerClass: 'ag-right-aligned-header',
      cellClass: 'ag-actions-cell',
      cellRenderer: ({ data: org }) => {
        const isActive = org.status === 'ACTIVE';
        return (
          <div style={{ display: 'inline-flex', gap: '6px' }}>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => {
                setSelectedOrg(org);
                setIsDetailsOpen(true);
              }}
            >
              Details
            </button>
            <button
              type="button"
              className={`btn btn-sm ${isActive ? 'btn-secondary' : 'btn-success'}`}
              onClick={() => handleToggleStatus(org)}
            >
              {isActive ? 'Suspend' : 'Activate'}
            </button>
            <button
              type="button"
              className="btn btn-danger btn-sm"
              onClick={() => {
                setSelectedOrg(org);
                setIsDeleteOpen(true);
              }}
            >
              Delete
            </button>
          </div>
        );
      },
    },
  ], [handleToggleStatus]);

  return (
    <div className="tab-pane active" id="tab-platform-overview">
      {/* Control bar */}
      <div className="card" style={{ marginBottom: '1.5rem', padding: '1rem 1.25rem' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1rem', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center', flex: 1, minWidth: '260px' }}>
            <input
              type="text"
              className="form-control"
              placeholder="Search organizations by name or slug..."
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
              <option value="ACTIVE">Active</option>
              <option value="SUSPENDED">Suspended</option>
              <option value="DEACTIVATED">Deactivated</option>
            </select>
          </div>

          <button
            type="button"
            className="btn btn-primary"
            onClick={() => setIsCreateOpen(true)}
            id="btn-open-create-org"
          >
            + New Organization
          </button>
        </div>
      </div>

      {/* Organizations Table */}
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <DataGrid
          rowData={organizations}
          columnDefs={columnDefs}
          loading={isLoading}
          emptyMessage="No organizations match your filters."
          getRowId={({ data }) => String(data.organization_id || data._id || data.id)}
        />

        {/* Pagination */}
        {totalCount > 20 && (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '1rem', borderTop: '1px solid var(--glass-border)' }}>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              Showing {organizations.length} of {totalCount}
            </span>
            <div style={{ display: 'flex', gap: '6px' }}>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                Previous
              </button>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                disabled={page * 20 >= totalCount}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>

      <CreateOrgModal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        onCreated={fetchOrgs}
      />

      <OrgDetailsModal
        isOpen={isDetailsOpen}
        onClose={() => setIsDetailsOpen(false)}
        org={selectedOrg}
      />

      <DeleteOrgModal
        isOpen={isDeleteOpen}
        onClose={() => setIsDeleteOpen(false)}
        org={selectedOrg}
        onDeleted={fetchOrgs}
      />
    </div>
  );
}
