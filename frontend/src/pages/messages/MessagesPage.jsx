import React, { useState, useEffect, useCallback, useMemo, lazy, Suspense } from 'react';
import ApiClient from '../../services/api';
import DataGrid from '../../components/tables/DataGrid';
import GridActionButton from '../../components/tables/GridActionButton';
import OffCanvasPanel from '../../components/common/OffCanvasPanel';
import PageLoader from '../../components/common/PageLoader';
import { useToast } from '../../context/ToastContext';
import { useAppScope } from '../../context/ScopeContext';
import { GlassSearch, GlassSelect } from '../../components/glass';

const MessageComposer = lazy(() => import('../../components/forms/MessageComposer'));
const MessageDetailsModal = lazy(() => import('../../components/modals/MessageDetailsModal'));
const ConfirmRetryModal = lazy(() => import('../../components/modals/ConfirmRetryModal'));

export default function MessagesPage() {
  const [messages, setMessages] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [page, setPage] = useState(1);
  const [channelFilter, setChannelFilter] = useState('ALL');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [search, setSearch] = useState('');
  const [isLoading, setIsLoading] = useState(true);

  const [selectedMessage, setSelectedMessage] = useState(null);
  const [isDetailsOpen, setIsDetailsOpen] = useState(false);
  const [detailsMounted, setDetailsMounted] = useState(false);
  const [retryTargetMessage, setRetryTargetMessage] = useState(null);
  const [isComposerOpen, setIsComposerOpen] = useState(false);

  const { showToast } = useToast();
  const { activeAppId } = useAppScope();

  const fetchMessages = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await ApiClient.listMessages(page, 20, {
        channel: channelFilter !== 'ALL' ? channelFilter : undefined,
        status: statusFilter !== 'ALL' ? statusFilter : undefined,
        search: search.trim() || undefined,
        application_id: activeAppId || undefined,
      });

      if (res?.success) {
        const msgList = Array.isArray(res.data) ? res.data : (res.data?.items || res.items || []);
        const total = res.total_count ?? res.pagination?.total ?? res.data?.total ?? msgList.length;
        setMessages(msgList);
        setTotalCount(total);
      }
    } catch (err) {
      console.error('Failed to load messages:', err);
      showToast('Could not load messages outbox', 'error');
    } finally {
      setIsLoading(false);
    }
  }, [page, channelFilter, statusFilter, search, activeAppId, showToast]);

  useEffect(() => {
    fetchMessages();
  }, [fetchMessages]);

  const handleCopyId = useCallback(async (mid) => {
    if (!mid) return;
    try {
      await navigator.clipboard.writeText(String(mid));
      showToast('Message ID copied to clipboard', 'success');
    } catch {
      showToast('Could not copy message ID', 'error');
    }
  }, [showToast]);

  const columnDefs = useMemo(() => [
    {
      headerName: 'Message ID',
      colId: 'message_id',
      field: 'message_id',
      minWidth: 118,
      maxWidth: 155,
      flex: 0.9,
      valueGetter: ({ data }) => data.message_id || data._id || data.id || '',
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
      headerName: 'Recipient',
      field: 'recipient',
      minWidth: 165,
      flex: 1.4,
      cellRenderer: ({ value }) => (
        <span className="ag-cell-ellipsis" title={value} style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
          {value || 'N/A'}
        </span>
      ),
    },
    {
      headerName: 'Channel',
      field: 'channel',
      minWidth: 96,
      maxWidth: 118,
      flex: 0.6,
      cellRenderer: ({ value }) => <span className="badge badge-info">{value}</span>,
    },
    {
      headerName: 'Provider',
      field: 'provider',
      minWidth: 96,
      maxWidth: 125,
      flex: 0.75,
      valueGetter: ({ data }) => data.provider || 'default',
      cellRenderer: ({ value }) => (
        <span className="ag-cell-ellipsis" title={value} style={{ fontSize: '0.84rem', color: 'var(--text-secondary)' }}>
          {value}
        </span>
      ),
    },
    {
      headerName: 'Status',
      field: 'status',
      minWidth: 105,
      maxWidth: 126,
      flex: 0.7,
      cellRenderer: ({ value }) => {
        const normalized = String(value || '').toUpperCase();
        const isDelivered = ['DELIVERED', 'SENT', 'READ'].includes(normalized);
        const isFailed = ['FAILED', 'ERROR', 'DEAD'].includes(normalized);
        return (
          <span className={`badge ${isDelivered ? 'badge-success' : isFailed ? 'badge-danger' : 'badge-warning'}`}>
            {value}
          </span>
        );
      },
    },
    {
      headerName: 'Created At',
      field: 'created_at',
      minWidth: 145,
      maxWidth: 175,
      flex: 1,
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
      cellRenderer: ({ data: m }) => {
        const mid = m.message_id || m._id || m.id;
        const normalized = String(m.status || '').toUpperCase();
        const isFailed = ['FAILED', 'ERROR', 'DEAD'].includes(normalized);
        return (
          <div className="ag-icon-actions" role="group" aria-label="Message actions">
            <GridActionButton
              icon="view"
              label="View message details"
              onClick={() => {
                setSelectedMessage(m);
                setDetailsMounted(true);
                setIsDetailsOpen(true);
              }}
            />
            <GridActionButton
              icon="copy"
              label="Copy message ID"
              onClick={() => handleCopyId(mid)}
            />
            {isFailed && (
              <GridActionButton
                icon="refresh"
                label="Retry message"
                onClick={() => setRetryTargetMessage(m)}
              />
            )}
          </div>
        );
      },
    },
  ], [handleCopyId]);

  return (
    <div className="tab-pane active" id="tab-org-messages">
      <div className="saas-message-compose-trigger">
        <button type="button" className="btn btn-primary" onClick={() => setIsComposerOpen(true)}>
          Compose Message
        </button>
      </div>
      <OffCanvasPanel
        isOpen={isComposerOpen}
        onClose={() => setIsComposerOpen(false)}
        title="Compose Message"
        size="large"
        id="panel-message-composer"
      >
        {isComposerOpen && (
          <Suspense fallback={<PageLoader compact label="Loading composer..." />}>
            <MessageComposer onMessageSent={fetchMessages} inPanel />
          </Suspense>
        )}
      </OffCanvasPanel>

      {/* Outbox filtering bar */}
      <div className="card" style={{ marginBottom: '1.5rem', padding: '1rem 1.25rem' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1rem', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center', flex: 1, minWidth: '260px' }}>
            <div style={{ flex: '1 1 220px', maxWidth: '280px' }}>
              <GlassSearch
                placeholder="Search by recipient or message ID..."
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
            <div style={{ minWidth: '145px' }}>
              <GlassSelect
                value={channelFilter}
                onChange={(e) => {
                  setChannelFilter(e.target.value);
                  setPage(1);
                }}
                aria-label="Filter messages by channel"
              >
                <option value="ALL">All Channels</option>
                <option value="email">Email</option>
                <option value="sms">SMS</option>
                <option value="whatsapp">WhatsApp</option>
              </GlassSelect>
            </div>
            <div style={{ minWidth: '145px' }}>
              <GlassSelect
                value={statusFilter}
                onChange={(e) => {
                  setStatusFilter(e.target.value);
                  setPage(1);
                }}
                aria-label="Filter messages by status"
              >
                <option value="ALL">All Statuses</option>
                <option value="PENDING">Pending</option>
                <option value="QUEUED">Queued</option>
                <option value="SENT">Sent</option>
                <option value="DELIVERED">Delivered</option>
                <option value="FAILED">Failed</option>
              </GlassSelect>
            </div>
          </div>

          <button
            type="button"
            className="btn btn-secondary"
            onClick={fetchMessages}
          >
            Refresh Outbox
          </button>
        </div>
      </div>

      {/* Outbox Table */}
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <DataGrid
          rowData={messages}
          columnDefs={columnDefs}
          loading={isLoading}
          emptyMessage="No messages match current filters."
          getRowId={({ data }) => String(data.message_id || data._id || data.id)}
        />

        {totalCount > 20 && (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '1rem', borderTop: '1px solid var(--glass-border)' }}>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              Showing {messages.length} of {totalCount}
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

      {(isDetailsOpen || detailsMounted) && (
        <Suspense fallback={null}>
          <MessageDetailsModal
            isOpen={isDetailsOpen}
            onClose={() => setIsDetailsOpen(false)}
            message={selectedMessage}
            onRetryTrigger={(msg) => setRetryTargetMessage(msg)}
          />
        </Suspense>
      )}

      {Boolean(retryTargetMessage) && (
        <Suspense fallback={null}>
          <ConfirmRetryModal
            isOpen={Boolean(retryTargetMessage)}
            onClose={() => setRetryTargetMessage(null)}
            message={retryTargetMessage}
            onRetried={fetchMessages}
          />
        </Suspense>
      )}
    </div>
  );
}
