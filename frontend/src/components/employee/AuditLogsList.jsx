import React, { useState, useEffect, useCallback } from 'react';
import ApiClient from '../../services/api';
import AuditDetailsModal from '../modals/AuditDetailsModal';
import { useToast } from '../../context/ToastContext';

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

  return (
    <div id="view-org-audit">
      <div className="card" style={{ marginBottom: '1.5rem', padding: '1rem 1.25rem' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1rem', alignItems: 'center', justifyContent: 'space-between' }}>
          <input
            type="text"
            className="form-control"
            placeholder="Search audit trail by actor, action, or target ID..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            style={{ maxWidth: '380px' }}
          />

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
        <div className="table-responsive-wrapper">
          <table className="data-table" style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                <th>Event Type</th>
                <th>Actor</th>
                <th>Result</th>
                <th>Target ID</th>
                <th>Timestamp</th>
                <th style={{ textAlign: 'right' }}>Details</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={6} style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                    Loading audit trail...
                  </td>
                </tr>
              ) : logs.length === 0 ? (
                <tr>
                  <td colSpan={6} style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                    No audit records match the current filter.
                  </td>
                </tr>
              ) : (
                logs.map((log, i) => {
                  const isSuccess = log.result === 'SUCCESS' || log.status === 'SUCCESS';

                  return (
                    <tr key={i}>
                      <td>
                        <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                          {log.event_type || log.action}
                        </span>
                      </td>
                      <td style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                        {log.actor_email || log.actor || 'System'}
                      </td>
                      <td>
                        <span className={`badge ${isSuccess ? 'badge-success' : 'badge-danger'}`}>
                          {log.result || log.status || 'OK'}
                        </span>
                      </td>
                      <td>
                        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem', color: 'var(--accent-cyan)' }}>
                          {log.target_id || log.target || '—'}
                        </span>
                      </td>
                      <td style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                        {log.created_at ? new Date(log.created_at).toLocaleString() : 'N/A'}
                      </td>
                      <td style={{ textAlign: 'right' }}>
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
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

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
