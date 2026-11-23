import React, { useState, useEffect, useCallback } from 'react';
import ApiClient from '../../services/api';
import MessageComposer from '../../components/forms/MessageComposer';
import MessageDetailsModal from '../../components/modals/MessageDetailsModal';
import ConfirmRetryModal from '../../components/modals/ConfirmRetryModal';
import { useToast } from '../../context/ToastContext';
import { useAppScope } from '../../context/ScopeContext';

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
        setMessages(res.data?.items || []);
        setTotalCount(res.data?.total || 0);
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

  return (
    <div className="tab-pane active" id="tab-org-messages">
      {/* Message Composer */}
      <MessageComposer onMessageSent={fetchMessages} />

      {/* Outbox filtering bar */}
      <div className="card" style={{ marginBottom: '1.5rem', padding: '1rem 1.25rem' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1rem', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center', flex: 1, minWidth: '260px' }}>
            <input
              type="text"
              className="form-control"
              placeholder="Search by recipient or message ID..."
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              style={{ maxWidth: '280px' }}
            />
            <select
              className="form-control"
              value={channelFilter}
              onChange={(e) => {
                setChannelFilter(e.target.value);
                setPage(1);
              }}
              style={{ maxWidth: '140px' }}
            >
              <option value="ALL">All Channels</option>
              <option value="email">Email</option>
              <option value="sms">SMS</option>
              <option value="whatsapp">WhatsApp</option>
            </select>
            <select
              className="form-control"
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setPage(1);
              }}
              style={{ maxWidth: '140px' }}
            >
              <option value="ALL">All Statuses</option>
              <option value="PENDING">Pending</option>
              <option value="QUEUED">Queued</option>
              <option value="SENT">Sent</option>
              <option value="DELIVERED">Delivered</option>
              <option value="FAILED">Failed</option>
            </select>
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
        <div className="table-responsive-wrapper">
          <table className="data-table" style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                <th>Recipient</th>
                <th>Channel</th>
                <th>Status</th>
                <th>Provider</th>
                <th>Created</th>
                <th style={{ textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={6} style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                    Loading messages...
                  </td>
                </tr>
              ) : messages.length === 0 ? (
                <tr>
                  <td colSpan={6} style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                    No messages match current filters.
                  </td>
                </tr>
              ) : (
                messages.map((m) => {
                  const mid = m.message_id || m._id || m.id;
                  const isDelivered = m.status === 'DELIVERED' || m.status === 'SENT';
                  const isFailed = m.status === 'FAILED' || m.status === 'ERROR';

                  return (
                    <tr key={mid}>
                      <td>
                        <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{m.recipient}</div>
                        <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--accent-cyan)' }}>
                          {mid}
                        </div>
                      </td>
                      <td>
                        <span className="badge badge-info">{m.channel}</span>
                      </td>
                      <td>
                        <span className={`badge ${isDelivered ? 'badge-success' : isFailed ? 'badge-danger' : 'badge-warning'}`}>
                          {m.status}
                        </span>
                      </td>
                      <td style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                        {m.provider || 'default'}
                      </td>
                      <td style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                        {m.created_at ? new Date(m.created_at).toLocaleString() : 'N/A'}
                      </td>
                      <td style={{ textAlign: 'right' }}>
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
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

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
