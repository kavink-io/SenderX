import React, { useState } from 'react';
import Modal from '../common/Modal';
import ApiClient from '../../services/api';
import { useToast } from '../../context/ToastContext';

export default function ConfirmRetryModal({ isOpen, onClose, message, onRetried }) {
  const [isRetrying, setIsRetrying] = useState(false);
  const { showToast } = useToast();

  if (!message) return null;
  const msgId = message.message_id || message._id || message.id;

  const handleConfirm = async () => {
    setIsRetrying(true);
    try {
      const res = await ApiClient.retryMessage(msgId);
      if (res.success) {
        showToast('Message re-queued for delivery successfully!', 'success');
        onRetried();
        onClose();
      } else {
        showToast(res.message || 'Retry failed', 'error');
      }
    } catch (err) {
      showToast(err?.message || 'Error executing retry', 'error');
    } finally {
      setIsRetrying(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Confirm Message Retry"
      maxWidth="480px"
      id="modal-confirm-retry"
      variant="dialog"
    >
      <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
        Are you sure you want to re-queue message <code style={{ color: 'var(--accent-cyan)' }}>{msgId}</code> to recipient <strong>{message.recipient}</strong>?
      </p>

      {message.error && (
        <div style={{ background: 'rgba(239, 68, 68, 0.1)', border: '1px solid var(--status-error)', borderRadius: '6px', padding: '0.75rem', marginBottom: '1.25rem', fontSize: '0.85rem' }}>
          <div style={{ fontWeight: 600, color: 'var(--status-error)', marginBottom: '0.25rem' }}>Previous Failure Reason:</div>
          <div>{typeof message.error === 'string' ? message.error : message.error?.message || JSON.stringify(message.error)}</div>
        </div>
      )}

      <div className="modal-actions" style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
        <button type="button" className="btn btn-secondary" onClick={onClose} disabled={isRetrying}>
          Cancel
        </button>
        <button
          type="button"
          id="btn-confirm-retry-execute"
          className="btn btn-primary"
          onClick={handleConfirm}
          disabled={isRetrying}
        >
          {isRetrying ? 'Re-queueing...' : 'Confirm & Re-queue'}
        </button>
      </div>
    </Modal>
  );
}
