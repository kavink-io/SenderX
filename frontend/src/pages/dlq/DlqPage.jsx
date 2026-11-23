import React, { useState, useEffect, useCallback } from 'react';
import ApiClient from '../../services/api';
import ConfirmRetryModal from '../../components/modals/ConfirmRetryModal';
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

  const handleDlqRetry = async (item) => {
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
  };

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
        <div className="table-responsive-wrapper">
          <table className="data-table" style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                <th>Message ID</th>
                <th>Recipient</th>
                <th>Channel</th>
                <th>Error Diagnostics</th>
                <th>Attempts</th>
                <th>Timestamp</th>
                <th style={{ textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={7} style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                    Loading Dead Letter Queue...
                  </td>
                </tr>
              ) : dlqItems.length === 0 ? (
                <tr>
                  <td colSpan={7} style={{ textAlign: 'center', padding: '2rem', color: 'var(--status-success)' }}>
                    ✓ Dead letter queue is empty. All deliveries routed smoothly.
                  </td>
                </tr>
              ) : (
                dlqItems.map((item) => {
                  const mid = item.message_id || item._id || item.id;

                  return (
                    <tr key={mid}>
                      <td>
                        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85rem', color: 'var(--accent-cyan)' }}>
                          {mid}
                        </span>
                      </td>
                      <td style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                        {item.recipient || 'N/A'}
                      </td>
                      <td>
                        <span className="badge badge-info">{item.channel || 'email'}</span>
                      </td>
                      <td style={{ maxWidth: '300px' }}>
                        <div style={{ color: 'var(--status-error)', fontSize: '0.8rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={item.reason || item.error}>
                          {item.reason || item.error || 'Max retries exhausted'}
                        </div>
                      </td>
                      <td>
                        <span className="badge badge-warning">{item.attempts || item.retry_count || 3}</span>
                      </td>
                      <td style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                        {item.created_at ? new Date(item.created_at).toLocaleString() : 'N/A'}
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <button
                          type="button"
                          className="btn btn-primary btn-sm"
                          onClick={() => handleDlqRetry(item)}
                        >
                          Retry Delivery
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
