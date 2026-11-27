import React, { useState, useEffect, useCallback, useMemo, lazy, Suspense } from 'react';
import ApiClient from '../../services/api';
import DataGrid from '../../components/tables/DataGrid';
import GridActionButton, { GridMoreMenu } from '../../components/tables/GridActionButton';
import JsonAnalyzer from '../../components/dashboard/JsonAnalyzer';
import { useToast } from '../../context/ToastContext';
import { useAppScope } from '../../context/ScopeContext';
import { GlassSelect } from '../../components/glass';

const ViewPayloadModal = lazy(() => import('../../components/modals/ViewPayloadModal'));

export default function JsonRequests() {
  const [payloads, setPayloads] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [page, setPage] = useState(1);
  const [channelFilter, setChannelFilter] = useState('ALL');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [isLoading, setIsLoading] = useState(true);

  const [selectedPayload, setSelectedPayload] = useState(null);
  const [isViewOpen, setIsViewOpen] = useState(false);
  const [viewMounted, setViewMounted] = useState(false);

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

  const handleCopyText = useCallback(async (text, successMessage) => {
    if (!text) return;
    try {
      await navigator.clipboard.writeText(String(text));
      showToast(successMessage, 'success');
    } catch {
      showToast('Could not copy to clipboard', 'error');
    }
  }, [showToast]);

  const openPayloadDetails = useCallback((payloadRecord) => {
    setSelectedPayload(payloadRecord);
    setViewMounted(true);
    setIsViewOpen(true);
  }, []);

  const columnDefs = useMemo(() => [
    {
      headerName: 'Request ID',
      colId: 'payload_id',
      field: 'payload_id',
      minWidth: 118,
      maxWidth: 152,
      flex: 0.9,
      valueGetter: ({ data }) => data.payload_id || data._id || data.id || '',
      cellRenderer: ({ value }) => (
        <span
          className="ag-cell-ellipsis"
          title={value}
          style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem', color: 'var(--accent-color)' }}
        >
          {value}
        </span>
      ),
    },
    {
      headerName: 'Connected Application',
      field: 'application_name',
      minWidth: 135,
      flex: 1.15,
      valueGetter: ({ data }) => data.application_name || data.application_id || 'Global',
      cellRenderer: ({ value }) => (
        <span className="ag-cell-ellipsis" title={value} style={{ fontSize: '0.84rem', color: 'var(--text-primary)', fontWeight: 500 }}>
          {value}
        </span>
      ),
    },
    {
      headerName: 'Channel',
      field: 'channel',
      minWidth: 94,
      maxWidth: 116,
      flex: 0.6,
      valueGetter: ({ data }) => data.channel || 'generic',
      cellRenderer: ({ value }) => <span className="badge badge-info">{value}</span>,
    },
    {
      headerName: 'Received At',
      field: 'received_at',
      minWidth: 145,
      maxWidth: 175,
      flex: 1,
      valueGetter: ({ data }) => data.received_at || data.created_at || '',
      valueFormatter: ({ value }) => (value ? new Date(value).toLocaleString() : 'N/A'),
      cellRenderer: ({ value }) => {
        const formatted = value ? new Date(value).toLocaleString() : 'N/A';
        return (
          <span className="ag-cell-ellipsis" title={formatted} style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
            {formatted}
          </span>
        );
      },
    },
    {
      headerName: 'Processing Status',
      field: 'validation_status',
      minWidth: 115,
      maxWidth: 140,
      flex: 0.75,
      valueGetter: ({ data }) => data.validation_status || data.status || '',
      cellRenderer: ({ value }) => {
        const normalized = String(value || '').toUpperCase();
        const isValid = ['VALID', 'ROUTED', 'DELIVERED', 'SENT'].includes(normalized);
        return <span className={`badge ${isValid ? 'badge-success' : 'badge-danger'}`}>{value}</span>;
      },
    },
    {
      headerName: 'Message ID',
      field: 'message_id',
      minWidth: 112,
      maxWidth: 148,
      flex: 0.85,
      valueGetter: ({ data }) => data.message_id || '—',
      cellRenderer: ({ value }) => (
        <span
          className="ag-cell-ellipsis"
          title={value}
          style={{
            fontFamily: value !== '—' ? 'var(--font-mono)' : 'inherit',
            fontSize: '0.8rem',
            color: value !== '—' ? 'var(--text-primary)' : 'var(--text-muted)',
          }}
        >
          {value}
        </span>
      ),
    },
    {
      headerName: 'Actions',
      colId: 'actions',
      width: 118,
      minWidth: 118,
      maxWidth: 118,
      flex: 0,
      sortable: false,
      filter: false,
      resizable: false,
      suppressHeaderMenuButton: true,
      headerClass: 'ag-right-aligned-header',
      cellClass: 'ag-actions-cell',
      cellRenderer: ({ data: p }) => {
        const requestId = p.payload_id || p._id || p.id || '';
        const rawJson = JSON.stringify(p.payload_data || p.data || p, null, 2);
        return (
          <div className="ag-icon-actions" role="group" aria-label="JSON request actions">
            <GridActionButton
              icon="view"
              label="View Request"
              onClick={() => openPayloadDetails(p)}
            />
            <GridActionButton
              icon="copy"
              label="Copy JSON"
              onClick={() => handleCopyText(rawJson, 'JSON payload copied to clipboard')}
            />
            <GridMoreMenu
              label="More request actions"
              items={[
                {
                  key: 'inspect',
                  icon: 'view',
                  label: 'Inspect JSON & Result',
                  onClick: () => openPayloadDetails(p),
                },
                {
                  key: 'copy-json',
                  icon: 'copy',
                  label: 'Copy JSON Payload',
                  onClick: () => handleCopyText(rawJson, 'JSON payload copied to clipboard'),
                },
                {
                  key: 'copy-req-id',
                  icon: 'copy',
                  label: 'Copy Request ID',
                  hidden: !requestId,
                  onClick: () => handleCopyText(requestId, 'Request ID copied to clipboard'),
                },
                {
                  key: 'copy-msg-id',
                  icon: 'copy',
                  label: 'Copy Message ID',
                  hidden: !p.message_id,
                  onClick: () => handleCopyText(p.message_id, 'Message ID copied to clipboard'),
                },
              ]}
            />
          </div>
        );
      },
    },
  ], [handleCopyText, openPayloadDetails]);

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

      {/* Live Inline Routing & Validation Analyzer */}
      <div style={{ marginTop: '1.75rem' }}>
        <JsonAnalyzer />
      </div>

      {(isViewOpen || viewMounted) && (
        <Suspense fallback={null}>
          <ViewPayloadModal
            isOpen={isViewOpen}
            onClose={() => setIsViewOpen(false)}
            payload={selectedPayload}
          />
        </Suspense>
      )}
    </div>
  );
}
