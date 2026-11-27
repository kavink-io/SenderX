import React, { useState, useEffect, useCallback, useMemo } from 'react';
import ApiClient from '../../services/api';
import DataGrid from '../../components/tables/DataGrid';
import GridActionButton from '../../components/tables/GridActionButton';
import { useToast } from '../../context/ToastContext';

export default function DlqPage() {
  const [dlqItems, setDlqItems] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(true);

  const [retryTargetMessage, setRetryTargetMessage] = useState(null);
  const { showToast } = useToast();

  const fetchDlq = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await ApiClient.listDlq(page, 20);
      if (res?.success) {
        setDlqItems(res.data?.items || res.data || []);
        setTotalCount(res.data?.total || 0);
      }
    } catch (err) {
      console.error('Failed to load DLQ items:', err);
      showToast('Could not load Dead Letter Queue', 'error');
    } finally {
      setIsLoading(false);
    }
  }, [page, showToast]);

  useEffect(() => {
    fetchDlq();
  }, [fetchDlq]);

  const handleDlqRetry = useCallback(async (item) => {
    const mid = item.message_id || item._id || item.id;
    try {
      const res = await ApiClient.retryDlq(mid);
      if (res?.success) {
        showToast('DLQ item re-queued for delivery!', 'success');
        fetchDlq();
      } else {
        showToast(res?.message || 'DLQ retry failed', 'error');
      }
    } catch (err) {
      showToast(err?.message || 'Error executing DLQ retry', 'error');
    }
  }, [fetchDlq, showToast]);

  const columnDefs = useMemo(() => [
    {
      headerName: 'Message ID',
      field: 'message_id',
      minWidth: 160,
      valueGetter: ({ data }) => data.message_id || data._id || data.id || '',
      cellRenderer: ({ value }) => (
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85rem', color: 'var(--accent-cyan)' }}>
          {value}
        </span>
      ),
    },
    {
      headerName: 'Recipient',
      field: 'recipient',
      minWidth: 150,
      valueGetter: ({ data }) => data.recipient || 'N/A',
      cellStyle: { fontWeight: 600, color: 'var(--text-primary)' },
    },
    {
      headerName: 'Channel',
      field: 'channel',
      minWidth: 105,
      maxWidth: 130,
      valueGetter: ({ data }) => data.channel || 'email',
      cellRenderer: ({ value }) => <span className="badge badge-info">{value}</span>,
    },
    {
      headerName: 'Error Diagnostics',
      field: 'reason',
      minWidth: 200,
      flex: 1.5,
      valueGetter: ({ data }) => data.reason || data.error || 'Max retries exhausted',
      cellRenderer: ({ value }) => (
        <div
          style={{ color: 'var(--status-error)', fontSize: '0.8rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}
          title={value}
        >
          {value}
        </div>
      ),
    },
    {
      headerName: 'Attempts',
      field: 'attempts',
      minWidth: 100,
      maxWidth: 120,
      valueGetter: ({ data }) => data.attempts || data.retry_count || 3,
      cellRenderer: ({ value }) => <span className="badge badge-warning">{value}</span>,
    },
    {
      headerName: 'Timestamp',
      field: 'created_at',
      minWidth: 155,
      valueFormatter: ({ value }) => (value ? new Date(value).toLocaleString() : 'N/A'),
      cellStyle: { fontSize: '0.85rem', color: 'var(--text-secondary)' },
    },
    {
      headerName: 'Actions',
      colId: 'actions',
      minWidth: 48,
      maxWidth: 60,
      sortable: false,
      filter: false,
      resizable: false,
      suppressHeaderMenuButton: true,
      headerClass: 'ag-right-aligned-header',
      cellClass: 'ag-actions-cell',
      cellRenderer: ({ data: item }) => (
        <div className="ag-icon-actions" role="group" aria-label="Dead-letter message actions">
          <GridActionButton icon="refresh" label="Retry delivery" onClick={() => handleDlqRetry(item)} />
        </div>
      ),
    },
  ], [handleDlqRetry]);

  return (
    <div className="tab-pane active" id="tab-org-dlq">
      <div className="card" style={{ marginBottom: '1.5rem', padding: '1rem 1.25rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h3 style={{ fontSize: '1.05rem', margin: '0 0 0.25rem', color: 'var(--text-primary)' }}>
            Dead Letter Queue (DLQ)
          </h3>
          <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            Failed dispatches that exhausted provider retries or experienced irrecoverable transport violations.
          </p>
        </div>
        <button type="button" className="btn btn-secondary" onClick={fetchDlq}>
          Refresh Queue
        </button>
      </div>

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <DataGrid
          rowData={dlqItems}
          columnDefs={columnDefs}
          loading={isLoading}
          emptyMessage="Dead letter queue is empty. All deliveries routed smoothly."
          getRowId={({ data }) => String(data.message_id || data._id || data.id)}
          pagination={dlqItems.length > 20 || totalCount > 20}
        />
      </div>
    </div>
  );
}
