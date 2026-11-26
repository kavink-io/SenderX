import React, { useState, useEffect, useCallback, useMemo } from 'react';
import ApiClient from '../../services/api';
import DataGrid from '../tables/DataGrid';
import AuditDetailsModal from '../modals/AuditDetailsModal';
import { useToast } from '../../context/ToastContext';
import { GlassSearch } from '../glass';

export default function AuditLogsList() {
  const [logs, setLogs] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [isLoading, setIsLoading] = useState(true);

  const [selectedLog, setSelectedLog] = useState(null);
  const [isDetailsOpen, setIsDetailsOpen] = useState(false);

  const { showToast } = useToast();

  const fetchAuditLogs = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await ApiClient.listSecurityAuditLogs(page, 25, {
        search: search.trim() || undefined,
      });

      if (res?.success) {
        setLogs(res.data?.items || res.data || []);
        setTotalCount(res.data?.total || 0);
      }
    } catch (err) {
      console.error('Failed to load audit logs:', err);
      showToast('Could not load security audit events', 'error');
    } finally {
      setIsLoading(false);
    }
  }, [page, search, showToast]);

  useEffect(() => {
    fetchAuditLogs();
  }, [fetchAuditLogs]);

  const columnDefs = useMemo(() => [
    {
      headerName: 'Event Type',
      field: 'event_type',
      minWidth: 165,
      valueGetter: ({ data }) => data.event_type || data.action || '',
      cellStyle: { fontWeight: 600, color: 'var(--text-primary)' },
    },
    {
      headerName: 'Actor',
      field: 'actor_email',
      minWidth: 165,
      valueGetter: ({ data }) => data.actor_email || data.actor || 'System',
      cellStyle: { fontSize: '0.85rem', color: 'var(--text-secondary)' },
    },
    {
      headerName: 'Result',
      field: 'result',
      minWidth: 110,
      maxWidth: 135,
      valueGetter: ({ data }) => data.result || data.status || 'OK',
      cellRenderer: ({ data: log, value }) => {
        const isSuccess = log.result === 'SUCCESS' || log.status === 'SUCCESS';
        return <span className={`badge ${isSuccess ? 'badge-success' : 'badge-danger'}`}>{value}</span>;
      },
    },
    {
      headerName: 'Target ID',
      field: 'target_id',
      minWidth: 150,
      valueGetter: ({ data }) => data.target_id || data.target || '—',
      cellRenderer: ({ value }) => (
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem', color: 'var(--accent-cyan)' }}>
          {value}
        </span>
      ),
    },
    {
      headerName: 'Timestamp',
      field: 'created_at',
      minWidth: 165,
      valueFormatter: ({ value }) => (value ? new Date(value).toLocaleString() : 'N/A'),
      cellStyle: { fontSize: '0.85rem', color: 'var(--text-secondary)' },
    },
    {
      headerName: 'Details',
      colId: 'details',
      minWidth: 105,
      maxWidth: 120,
      sortable: false,
      filter: false,
      resizable: false,
      suppressHeaderMenuButton: true,
      headerClass: 'ag-right-aligned-header',
      cellClass: 'ag-actions-cell',
      cellRenderer: ({ data: log }) => (
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={() => {
            setSelectedLog(log);
            setIsDetailsOpen(true);
          }}
        >
          Inspect
        </button>
      ),
    },
  ], []);

  return (
    <div id="view-org-audit">
      <div className="card" style={{ marginBottom: '1.5rem', padding: '1rem 1.25rem' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1rem', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ flex: '1 1 260px', maxWidth: '380px' }}>
            <GlassSearch
              placeholder="Search audit trail by actor, action, or target ID..."
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              onClear={() => {
                setSearch('');
                setPage(1);
              }}
            />
          </div>

          <button
            type="button"
            className="btn btn-secondary"
            onClick={fetchAuditLogs}
          >
            Refresh Audit Trail
          </button>
        </div>
      </div>

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <DataGrid
          rowData={logs}
          columnDefs={columnDefs}
          loading={isLoading}
          emptyMessage="No audit records match the current filter."
        />

        {totalCount > 25 && (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '1rem', borderTop: '1px solid var(--glass-border)' }}>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              Showing {logs.length} of {totalCount}
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
                disabled={page * 25 >= totalCount}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>

      <AuditDetailsModal
        isOpen={isDetailsOpen}
        onClose={() => setIsDetailsOpen(false)}
        log={selectedLog}
      />
    </div>
  );
}
