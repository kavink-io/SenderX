import React, { useState } from 'react';
import Modal from '../common/Modal';
import { useToast } from '../../context/ToastContext';

export default function MessageDetailsModal({ isOpen, onClose, message, onRetryTrigger }) {
  const [copied, setCopied] = useState(false);
  const { showToast } = useToast();

  if (!message) return null;

  const msgId = message.message_id || message._id || message.id;
  const isFailed = message.status === 'FAILED' || message.status === 'ERROR';

  const handleCopyJson = () => {
    navigator.clipboard.writeText(JSON.stringify(message, null, 2));
    setCopied(true);
    showToast('Message details copied to clipboard!', 'success');
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Message Lifecycle & Delivery Details"
      maxWidth="680px"
      id="modal-msg-details"
    >
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1.25rem', marginBottom: '1.5rem' }}>
        <div>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Message ID</span>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85rem', color: 'var(--accent-cyan)' }}>
            {msgId}
          </div>
        </div>
        <div>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Status</span>
          <div>
            <span className={`badge ${message.status === 'DELIVERED' || message.status === 'SENT' ? 'badge-success' : isFailed ? 'badge-danger' : 'badge-warning'}`}>
              {message.status}
            </span>
          </div>
        </div>
        <div>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Channel & Provider</span>
          <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
            {message.channel} • {message.provider || 'default'}
          </div>
        </div>
        <div>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Recipient</span>
          <div style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{message.recipient}</div>
        </div>
        <div>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Created At</span>
          <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            {message.created_at ? new Date(message.created_at).toLocaleString() : 'N/A'}
          </div>
        </div>
        <div>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Retry Count</span>
          <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{message.retry_count ?? 0}</div>
        </div>
      </div>

      {/* Failure details */}
      {message.error && (
        <div style={{ background: 'rgba(239, 68, 68, 0.1)', border: '1px solid var(--status-error)', borderRadius: '6px', padding: '0.75rem', marginBottom: '1.25rem' }}>
          <div style={{ color: 'var(--status-error)', fontWeight: 600, fontSize: '0.85rem', marginBottom: '0.25rem' }}>
            Dispatch Failure Diagnostics:
          </div>
          <div style={{ fontSize: '0.85rem', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
            {typeof message.error === 'string' ? message.error : JSON.stringify(message.error)}
          </div>
        </div>
      )}

      {/* Provider Details */}
      {message.provider_response && (
        <div style={{ background: 'var(--bg-surface)', padding: '0.75rem', borderRadius: '6px', marginBottom: '1.25rem' }}>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Provider Response:</span>
          <pre style={{ margin: '0.25rem 0 0', fontSize: '0.8rem', fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', whiteSpace: 'pre-wrap' }}>
            {JSON.stringify(message.provider_response, null, 2)}
          </pre>
        </div>
      )}

      <div className="modal-actions" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <button type="button" className="btn btn-secondary btn-sm" onClick={handleCopyJson}>
          {copied ? 'Copied Details' : 'Copy JSON'}
        </button>

        <div style={{ display: 'flex', gap: '8px' }}>
          {isFailed && onRetryTrigger && (
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => {
                onClose();
                onRetryTrigger(message);
              }}
            >
              Retry Delivery
            </button>
          )}
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </Modal>
  );
}
