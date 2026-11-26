import React, { useState, useEffect, useCallback, useMemo } from 'react';
import ApiClient from '../../services/api';
import DataGrid from '../../components/tables/DataGrid';
import ViewPayloadModal from '../../components/modals/ViewPayloadModal';
import JsonAnalyzer from '../../components/dashboard/JsonAnalyzer';
import { useToast } from '../../context/ToastContext';
import { useAppScope } from '../../context/ScopeContext';
import { GlassSelect } from '../../components/glass';

export default function JsonRequests() {
  const [payloads, setPayloads] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [page, setPage] = useState(1);
  const [channelFilter, setChannelFilter] = useState('ALL');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [isLoading, setIsLoading] = useState(true);

  const [selectedPayload, setSelectedPayload] = useState(null);
  const [isViewOpen, setIsViewOpen] = useState(false);

  const { showToast } = useToast();
  const { activeAppId } = useAppScope();

  const fetchPayloads = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await ApiClient.listPayloads(page, 20, {
        channel: channelFilter !== 'ALL' ? channelFilter : undefined,
        status: statusFilter !== 'ALL' ? statusFilter : undefined,
        application_id: activeAppId || undefined,
      });

      if (res?.success) {
        setPayloads(res.data?.items || []);
        setTotalCount(res.data?.total || 0);
      }
    } catch (err) {
      console.error('Failed to load JSON requests:', err);
      showToast('Could not load JSON payloads log', 'error');
    } finally {
      setIsLoading(false);
    }
  }, [page, channelFilter, statusFilter, activeAppId, showToast]);

  useEffect(() => {
    fetchPayloads();
  }, [fetchPayloads]);

  const columnDefs = useMemo(() => [
    {
      headerName: 'Payload ID',
      field: 'payload_id',
      minWidth: 160,
      valueGetter: ({ data }) => data.payload_id || data._id || data.id || '',
      cellRenderer: ({ value }) => (
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85rem', color: 'var(--accent-cyan)' }}>
          {value}
        </span>
      ),
    },
    {
      headerName: 'Channel',
      field: 'channel',
      minWidth: 110,
      maxWidth: 140,
      valueGetter: ({ data }) => data.channel || 'generic',
      cellRenderer: ({ value }) => <span className="badge badge-info">{value}</span>,
    },
    {
      headerName: 'Status',
      field: 'status',
      minWidth: 120,
      maxWidth: 145,
      valueGetter: ({ data }) => data.validation_status || data.status || '',
      cellRenderer: ({ value }) => {
        const isValid = value === 'VALID' || value === 'ROUTED';
        return <span className={`badge ${isValid ? 'badge-success' : 'badge-danger'}`}>{value}</span>;
      },
    },
    {
      headerName: 'Application',
      field: 'application_name',
      minWidth: 140,
      valueGetter: ({ data }) => data.application_name || data.application_id || 'Global',
      cellStyle: { fontSize: '0.85rem', color: 'var(--text-secondary)' },
    },
    {
      headerName: 'Received',
      field: 'created_at',
      minWidth: 160,
      valueFormatter: ({ value }) => (value ? new Date(value).toLocaleString() : 'N/A'),
      cellStyle: { fontSize: '0.85rem', color: 'var(--text-secondary)' },
    },
    {
      headerName: 'Actions',
      colId: 'actions',
      minWidth: 135,
      maxWidth: 155,
      sortable: false,
      filter: false,
      resizable: false,
      suppressHeaderMenuButton: true,
      headerClass: 'ag-right-aligned-header',
      cellClass: 'ag-actions-cell',
      cellRenderer: ({ data: p }) => (
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={() => {
            setSelectedPayload(p);
            setIsViewOpen(true);
          }}
        >
          View Payload
        </button>
      ),
    },
  ], []);

  return (
    <div className="tab-pane active" id="tab-org-json-requests">
      {/* Filters bar */}
      <div className="card" style={{ marginBottom: '1.5rem', padding: '1rem 1.25rem' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1rem', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center' }}>
            <div style={{ minWidth: '155px' }}>
              <GlassSelect
                value={channelFilter}
                onChange={(e) => {
                  setChannelFilter(e.target.value);
                  setPage(1);
                }}
                aria-label="Filter JSON requests by channel"
              >
                <option value="ALL">All Channels</option>
                <option value="email">Email</option>
                <option value="sms">SMS</option>
                <option value="whatsapp">WhatsApp</option>
              </GlassSelect>
            </div>

            <div style={{ minWidth: '155px' }}>
              <GlassSelect
                value={statusFilter}
                onChange={(e) => {
                  setStatusFilter(e.target.value);
                  setPage(1);
                }}
                aria-label="Filter JSON requests by status"
              >
                <option value="ALL">All Statuses</option>
                <option value="VALID">Valid</option>
                <option value="INVALID">Invalid</option>
                <option value="ROUTED">Routed</option>
                <option value="FAILED">Failed</option>
              </GlassSelect>
            </div>
          </div>

          <button
            type="button"
            className="btn btn-secondary"
            onClick={fetchPayloads}
          >
            Refresh Logs
          </button>
        </div>
      </div>

      {/* Payloads table */}
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <DataGrid
          rowData={payloads}
          columnDefs={columnDefs}
          loading={isLoading}
          emptyMessage="No inbound JSON requests recorded for this scope."
          getRowId={({ data }) => String(data.payload_id || data._id || data.id)}
        />

        {totalCount > 20 && (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '1rem', borderTop: '1px solid var(--glass-border)' }}>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              Showing {payloads.length} of {totalCount}
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

      {/* Dynamic JSON Analyzer Sandbox */}
      <JsonAnalyzer />

      <ViewPayloadModal
        isOpen={isViewOpen}
        onClose={() => setIsViewOpen(false)}
        payload={selectedPayload}
      />
    </div>
  );
}
