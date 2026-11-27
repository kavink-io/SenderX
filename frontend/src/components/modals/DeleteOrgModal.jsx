import React, { useState, useEffect } from 'react';
import Modal from '../common/Modal';
import ApiClient from '../../services/api';
import { useToast } from '../../context/ToastContext';

export default function DeleteOrgModal({ isOpen, onClose, org, onDeleted }) {
  const [summary, setSummary] = useState(null);
  const [confirmSlug, setConfirmSlug] = useState('');
  const [isDeleting, setIsDeleting] = useState(false);
  const [isLoadingSummary, setIsLoadingSummary] = useState(true);

  const { showToast } = useToast();

  useEffect(() => {
    if (!isOpen || !org) return;
    setConfirmSlug('');
    setIsLoadingSummary(true);

    const orgId = org.organization_id || org._id || org.id;
    ApiClient.getOrgDeletionSummary(orgId)
      .then((res) => {
        if (res.success && res.data) {
          setSummary(res.data);
        }
      })
      .catch((err) => console.warn('Could not load deletion summary:', err))
      .finally(() => setIsLoadingSummary(false));
  }, [isOpen, org]);

  if (!org) return null;

  const orgId = org.organization_id || org._id || org.id;
  const isMatch = confirmSlug.trim().toLowerCase() === (org.slug || '').toLowerCase();

  const handleDelete = async (e) => {
    e.preventDefault();
    if (!isMatch) return;

    setIsDeleting(true);
    try {
      const res = await ApiClient.deleteOrganization(orgId, confirmSlug.trim());
      if (res.success) {
        showToast(`Organization "${org.name}" permanently deleted.`, 'success');
        onDeleted();
        onClose();
      } else {
        showToast(res.message || 'Deletion failed', 'error');
      }
    } catch (err) {
      showToast(err?.message || 'Error executing deletion', 'error');
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Delete Organization"
      maxWidth="560px"
      id="modal-delete-org"
      variant="dialog"
    >
      <form onSubmit={handleDelete}>
        <div style={{ color: 'var(--status-error)', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polygon points="7.86 2 16.14 2 22 7.86 22 16.14 16.14 22 7.86 22 2 16.14 2 7.86 7.86 2"/>
            <line x1="12" y1="8" x2="12" y2="12"/>
            <line x1="12" y1="16" x2="12.01" y2="16"/>
          </svg>
          <strong>Warning: This action is irreversible!</strong>
        </div>

        <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
          Deleting <strong>{org.name}</strong> will remove all associated tenant users, credentials, connected applications, and dispatch history.
        </p>

        {isLoadingSummary ? (
          <div style={{ padding: '1rem', textAlign: 'center', color: 'var(--text-muted)' }}>Loading impact summary...</div>
        ) : summary ? (
          <div style={{ background: 'var(--bg-surface)', padding: '0.75rem 1rem', borderRadius: '6px', marginBottom: '1.25rem', fontSize: '0.85rem' }}>
            <div style={{ fontWeight: 600, marginBottom: '0.35rem', color: 'var(--text-primary)' }}>Impact Summary:</div>
            <div>• Users removed: <strong>{summary.users_count || 0}</strong></div>
            <div>• Applications removed: <strong>{summary.applications_count || 0}</strong></div>
            <div>• Credentials revoked: <strong>{summary.credentials_count || 0}</strong></div>
            <div>• Messages purged: <strong>{summary.messages_count || 0}</strong></div>
          </div>
        ) : null}

        <div className="form-group" style={{ marginBottom: '1.5rem' }}>
          <label style={{ fontSize: '0.85rem' }}>
            Type the organization slug <strong>{org.slug}</strong> to confirm:
          </label>
          <input
            type="text"
            className="form-control"
            value={confirmSlug}
            onChange={(e) => setConfirmSlug(e.target.value)}
            placeholder={org.slug}
            required
            autoFocus
          />
        </div>

        <div className="modal-actions" style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
          <button type="button" className="btn btn-secondary" onClick={onClose} disabled={isDeleting}>
            Cancel
          </button>
          <button type="submit" className="btn btn-danger" disabled={!isMatch || isDeleting}>
            {isDeleting ? 'Deleting...' : 'Delete Organization'}
          </button>
        </div>
      </form>
    </Modal>
  );
}
