import React, { useState, useEffect, useCallback, useMemo } from 'react';
import ApiClient from '../../services/api';
import DataGrid from '../../components/tables/DataGrid';
import MessageComposer from '../../components/forms/MessageComposer';
import MessageDetailsModal from '../../components/modals/MessageDetailsModal';
import ConfirmRetryModal from '../../components/modals/ConfirmRetryModal';
import OffCanvasPanel from '../../components/common/OffCanvasPanel';
import { useToast } from '../../context/ToastContext';
import { useAppScope } from '../../context/ScopeContext';
import { GlassSearch, GlassSelect } from '../../components/glass';

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

  const columnDefs = useMemo(() => [
    {
      headerName: 'Recipient',
      field: 'recipient',
      minWidth: 210,
      flex: 1.5,
      autoHeight: true,
      wrapText: true,
      cellRenderer: ({ data: m }) => {
        const mid = m.message_id || m._id || m.id;
        return (
          <div>
            <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{m.recipient}</div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--accent-cyan)' }}>
              {mid}
            </div>
          </div>
        );
      },
    },
    {
      headerName: 'Channel',
      field: 'channel',
      minWidth: 110,
      maxWidth: 135,
      cellRenderer: ({ value }) => <span className="badge badge-info">{value}</span>,
    },
    {
      headerName: 'Status',
      field: 'status',
      minWidth: 120,
      maxWidth: 145,
      cellRenderer: ({ value }) => {
        const isDelivered = value === 'DELIVERED' || value === 'SENT';
        const isFailed = value === 'FAILED' || value === 'ERROR';
        return (
          <span className={`badge ${isDelivered ? 'badge-success' : isFailed ? 'badge-danger' : 'badge-warning'}`}>
            {value}
          </span>
        );
      },
    },
    {
      headerName: 'Provider',
      field: 'provider',
      minWidth: 110,
      valueGetter: ({ data }) => data.provider || 'default',
      cellStyle: { fontSize: '0.85rem', color: 'var(--text-secondary)' },
    },
    {
      headerName: 'Created',
      field: 'created_at',
      minWidth: 155,
      valueFormatter: ({ value }) => (value ? new Date(value).toLocaleString() : 'N/A'),
      cellStyle: { fontSize: '0.85rem', color: 'var(--text-secondary)' },
    },
    {
      headerName: 'Actions',
      colId: 'actions',
      minWidth: 150,
      maxWidth: 175,
      sortable: false,
      filter: false,
      resizable: false,
      suppressHeaderMenuButton: true,
      headerClass: 'ag-right-aligned-header',
      cellClass: 'ag-actions-cell',
      cellRenderer: ({ data: m }) => {
        const isFailed = m.status === 'FAILED' || m.status === 'ERROR';
        return (
          <div style={{ display: 'inline-flex', gap: '6px' }}>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => {
                setSelectedMessage(m);
                setIsDetailsOpen(true);
              }}
            >
              Details
            </button>
            {isFailed && (
              <button
                type="button"
                className="btn btn-danger btn-sm"
                onClick={() => setRetryTargetMessage(m)}
              >
                Retry
              </button>
            )}
          </div>
        );
      },
    },
  ], []);

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
        <MessageComposer onMessageSent={fetchMessages} inPanel />
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

      <MessageDetailsModal
        isOpen={isDetailsOpen}
        onClose={() => setIsDetailsOpen(false)}
        message={selectedMessage}
        onRetryTrigger={(msg) => setRetryTargetMessage(msg)}
      />

      <ConfirmRetryModal
        isOpen={Boolean(retryTargetMessage)}
        onClose={() => setRetryTargetMessage(null)}
        message={retryTargetMessage}
        onRetried={fetchMessages}
      />
    </div>
  );
}
