import React, { useState, useEffect, useCallback } from 'react';
import ApiClient from '../../services/api';
import ViewPayloadModal from '../../components/modals/ViewPayloadModal';
import JsonAnalyzer from '../../components/dashboard/JsonAnalyzer';
import { useToast } from '../../context/ToastContext';
import { useAppScope } from '../../context/ScopeContext';

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

  return (
    <div className="tab-pane active" id="tab-org-json-requests">
      {/* Filters bar */}
      <div className="card" style={{ marginBottom: '1.5rem', padding: '1rem 1.25rem' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1rem', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center' }}>
            <select
              className="form-control"
              value={channelFilter}
              onChange={(e) => {
                setChannelFilter(e.target.value);
                setPage(1);
              }}
              style={{ maxWidth: '160px' }}
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
              style={{ maxWidth: '160px' }}
            >
              <option value="ALL">All Statuses</option>
              <option value="VALID">Valid</option>
              <option value="INVALID">Invalid</option>
              <option value="ROUTED">Routed</option>
              <option value="FAILED">Failed</option>
            </select>
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
        <div className="table-responsive-wrapper">
          <table className="data-table" style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                <th>Payload ID</th>
                <th>Channel</th>
                <th>Status</th>
                <th>Application</th>
                <th>Received</th>
                <th style={{ textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={6} style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                    Loading inbound payloads...
                  </td>
                </tr>
              ) : payloads.length === 0 ? (
                <tr>
                  <td colSpan={6} style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                    No inbound JSON requests recorded for this scope.
                  </td>
                </tr>
              ) : (
                payloads.map((p) => {
                  const pid = p.payload_id || p._id || p.id;
                  const isValid = p.validation_status === 'VALID' || p.status === 'VALID' || p.status === 'ROUTED';

                  return (
                    <tr key={pid}>
                      <td>
                        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85rem', color: 'var(--accent-cyan)' }}>
                          {pid}
                        </span>
                      </td>
                      <td>
                        <span className="badge badge-info">{p.channel || 'generic'}</span>
                      </td>
                      <td>
                        <span className={`badge ${isValid ? 'badge-success' : 'badge-danger'}`}>
                          {p.validation_status || p.status}
                        </span>
                      </td>
                      <td style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                        {p.application_name || p.application_id || 'Global'}
                      </td>
                      <td style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                        {p.created_at ? new Date(p.created_at).toLocaleString() : 'N/A'}
                      </td>
                      <td style={{ textAlign: 'right' }}>
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
