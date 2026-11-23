import React, { useState, useEffect, useCallback } from 'react';
import ApiClient from '../../services/api';
import { useToast } from '../../context/ToastContext';
import { useAuth } from '../../context/AuthContext';

export default function ChangeRequestsSection() {
  const [requests, setRequests] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [requestedName, setRequestedName] = useState('');
  const [requestedSlug, setRequestedSlug] = useState('');
  const [justification, setJustification] = useState('');

  const { showToast } = useToast();
  const { isOrgAdmin } = useAuth();

  const fetchRequests = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await ApiClient.listOrgChangeRequests(1, 50);
      if (res?.success) {
        setRequests(res.data?.items || res.data || []);
      }
    } catch (err) {
      console.warn('Could not load org change requests:', err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRequests();
  }, [fetchRequests]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!requestedName.trim() && !requestedSlug.trim()) {
      showToast('Provide at least a new name or slug for the request', 'error');
      return;
    }

    setIsSubmitting(true);
    try {
      const res = await ApiClient.submitChangeRequest({
        requested_name: requestedName.trim() || undefined,
        requested_slug: requestedSlug.trim() || undefined,
        justification: justification.trim() || undefined,
      });

      if (res?.success) {
        showToast('Change request submitted for platform review!', 'success');
        setRequestedName('');
        setRequestedSlug('');
        setJustification('');
        fetchRequests();
      } else {
        showToast(res?.message || 'Submission failed', 'error');
      }
    } catch (err) {
      showToast(err?.message || 'Error submitting request', 'error');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCancel = async (req) => {
    const rid = req.request_id || req._id || req.id;
    try {
      const res = await ApiClient.cancelChangeRequest(rid);
      if (res?.success) {
        showToast('Change request cancelled', 'info');
        fetchRequests();
      } else {
        showToast(res?.message || 'Cancellation failed', 'error');
      }
    } catch (err) {
      showToast(err?.message || 'Error cancelling request', 'error');
    }
  };

  return (
    <div style={{ marginTop: '1.5rem' }}>
      {isOrgAdmin && (
        <div className="card" style={{ marginBottom: '1.5rem' }}>
          <h4 style={{ fontSize: '1rem', marginBottom: '0.5rem', color: 'var(--text-primary)' }}>
            Request Organization Rebranding
          </h4>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1.25rem' }}>
            Tenant name or slug rebranding requires platform administrator review and verification.
          </p>

          <form onSubmit={handleSubmit}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem', marginBottom: '1rem' }}>
              <div className="form-group">
                <label>Requested Organization Name</label>
                <input
                  type="text"
                  className="form-control"
                  value={requestedName}
                  onChange={(e) => setRequestedName(e.target.value)}
                  placeholder="New Legal Entity Name"
                />
              </div>

              <div className="form-group">
                <label>Requested Slug</label>
                <input
                  type="text"
                  className="form-control"
                  value={requestedSlug}
                  onChange={(e) => setRequestedSlug(e.target.value.toLowerCase())}
                  placeholder="new-entity-slug"
                />
              </div>
            </div>

            <div className="form-group" style={{ marginBottom: '1rem' }}>
              <label>Business Justification</label>
              <textarea
                className="form-control"
                value={justification}
                onChange={(e) => setJustification(e.target.value)}
                placeholder="Explain the legal or brand motivation for this identifier update..."
                rows={2}
              />
            </div>

            <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
              {isSubmitting ? 'Submitting...' : 'Submit Rebranding Request'}
            </button>
          </form>
        </div>
      )}

      {/* History table */}
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div style={{ padding: '1rem 1.25rem', borderBottom: '1px solid var(--glass-border)' }}>
          <h4 style={{ fontSize: '0.95rem', margin: 0, color: 'var(--text-primary)' }}>
            Change Request Status History
          </h4>
        </div>
        <div className="table-responsive-wrapper">
          <table className="data-table" style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                <th>Requested Changes</th>
                <th>Status</th>
                <th>Submitted</th>
                <th>Decision / Rejection Reason</th>
                <th style={{ textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={5} style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                    Loading change requests...
                  </td>
                </tr>
              ) : requests.length === 0 ? (
                <tr>
                  <td colSpan={5} style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                    No rebranding requests on record.
                  </td>
                </tr>
              ) : (
                requests.map((req) => {
                  const rid = req.request_id || req._id || req.id;
                  const isPending = req.status === 'PENDING';

                  return (
                    <tr key={rid}>
                      <td>
                        <div style={{ fontSize: '0.85rem' }}>
                          {req.requested_name && <div>Name: <strong>{req.requested_name}</strong></div>}
                          {req.requested_slug && <div>Slug: <code>{req.requested_slug}</code></div>}
                        </div>
                      </td>
                      <td>
                        <span className={`badge ${
                          req.status === 'APPROVED' ? 'badge-success' : req.status === 'REJECTED' ? 'badge-danger' : 'badge-warning'
                        }`}>
                          {req.status}
                        </span>
                      </td>
                      <td style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                        {req.created_at ? new Date(req.created_at).toLocaleDateString() : 'N/A'}
                      </td>
                      <td style={{ fontSize: '0.85rem', color: req.rejection_reason ? 'var(--status-error)' : 'var(--text-secondary)' }}>
                        {req.rejection_reason || '—'}
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        {isPending && isOrgAdmin && (
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            onClick={() => handleCancel(req)}
                          >
                            Cancel
                          </button>
                        )}
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
