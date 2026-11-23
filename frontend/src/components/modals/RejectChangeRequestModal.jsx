import React, { useState } from 'react';
import Modal from '../common/Modal';
import ApiClient from '../../services/api';
import { useToast } from '../../context/ToastContext';

export default function RejectChangeRequestModal({ isOpen, onClose, request, onRejected }) {
  const [reason, setReason] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { showToast } = useToast();

  if (!request) return null;
  const requestId = request.request_id || request._id || request.id;

  const handleReject = async (e) => {
    e.preventDefault();
    if (!reason.trim()) {
      showToast('A reason is required to reject this change request', 'error');
      return;
    }

    setIsSubmitting(true);
    try {
      const res = await ApiClient.rejectChangeRequest(requestId, reason.trim());
      if (res.success) {
        showToast('Change request rejected', 'info');
        setReason('');
        onRejected();
        onClose();
      } else {
        showToast(res.message || 'Failed to reject change request', 'error');
      }
    } catch (err) {
      showToast(err?.message || 'Error rejecting request', 'error');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Reject Change Request"
      maxWidth="500px"
      id="modal-reject-change-request"
    >
      <form onSubmit={handleReject}>
        <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
          Provide an explanation for the organization administrator detailing why this rebranding request is being rejected.
        </p>

        <div className="form-group" style={{ marginBottom: '1.25rem' }}>
          <label htmlFor="rejection-reason-input">Rejection Reason *</label>
          <textarea
            id="rejection-reason-input"
            className="form-control"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="e.g., Requested slug conflicts with reserved platform namespace or requires trademark validation..."
            rows={3}
            required
            autoFocus
          />
        </div>

        <div className="modal-actions" style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
          <button type="button" className="btn btn-secondary" onClick={onClose} disabled={isSubmitting}>
            Cancel
          </button>
          <button type="submit" id="btn-confirm-reject-cr" className="btn btn-danger" disabled={isSubmitting || !reason.trim()}>
            {isSubmitting ? 'Rejecting...' : 'Reject Request'}
          </button>
        </div>
      </form>
    </Modal>
  );
}
