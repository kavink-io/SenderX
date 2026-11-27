import React, { useState } from 'react';
import OffCanvasPanel from '../common/OffCanvasPanel';
import { useToast } from '../../context/ToastContext';

function formatDetail(value) {
  if (value === null || value === undefined || value === '') return 'N/A';
  return typeof value === 'string' || typeof value === 'number' ? String(value) : JSON.stringify(value);
}

function formatTimestamp(value) {
  if (!value) return 'N/A';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'N/A';
  return date.toLocaleString('en-GB', {
    dateStyle: 'short',
    timeStyle: 'medium',
    hourCycle: 'h23',
  });
}

function DetailRow({ label, children, valueClassName = '' }) {
  return (
    <div className="message-details-row">
      <dt>{label}</dt>
      <dd className={valueClassName}>{children}</dd>
    </div>
  );
}

export default function MessageDetailsModal({ isOpen, onClose, message, onRetryTrigger }) {
  const [copied, setCopied] = useState(false);
  const { showToast } = useToast();

  if (!message) return null;

  const msgId = message.message_id || message._id || message.id || 'N/A';
  const status = message.status || 'UNKNOWN';
  const normalizedStatus = String(status).toUpperCase();
  const isFailed = ['FAILED', 'ERROR', 'DEAD'].includes(normalizedStatus);
  const statusClass = ['SENT', 'DELIVERED', 'READ'].includes(normalizedStatus)
    ? 'badge-success'
    : isFailed
      ? 'badge-danger'
      : 'badge-warning';

  const handleCopyJson = async () => {
    try {
      await navigator.clipboard.writeText(JSON.stringify(message, null, 2));
      setCopied(true);
      showToast('Message details copied to clipboard!', 'success');
      window.setTimeout(() => setCopied(false), 2000);
    } catch (error) {
      console.error('Failed to copy message details:', error);
      showToast('Could not copy message details', 'error');
    }
  };

  return (
    <OffCanvasPanel
      isOpen={isOpen}
      onClose={onClose}
      title="Message Lifecycle & Delivery Details"
      size="large"
      id="panel-msg-details"
      className="message-details-panel"
    >
      <dl className="message-details-list">
        <DetailRow label="Message ID" valueClassName="message-details-mono">
          {msgId}
        </DetailRow>
        <DetailRow label="Status">
          <span className={`badge ${statusClass}`}>{status}</span>
        </DetailRow>
        <DetailRow label="Recipient">
          {formatDetail(message.recipient ?? message.to)}
        </DetailRow>
        <DetailRow label="Channel & Provider">
          {formatDetail(message.channel)}
          <span className="message-details-separator" aria-hidden="true">•</span>
          {formatDetail(message.provider || 'default')}
        </DetailRow>
        <DetailRow label="Created At">
          {formatTimestamp(message.created_at)}
        </DetailRow>
        <DetailRow label="Retry Count">
          {formatDetail(message.retry_count ?? 0)}
        </DetailRow>
      </dl>

      {message.error && (
        <section className="message-details-section message-details-error">
          <h3>Dispatch Failure Diagnostics</h3>
          <p>{typeof message.error === 'string' ? message.error : JSON.stringify(message.error)}</p>
        </section>
      )}

      {message.provider_response && (
        <section className="message-details-section">
          <h3>Provider Response</h3>
          <pre className="message-details-code">{JSON.stringify(message.provider_response, null, 2)}</pre>
        </section>
      )}

      <footer className="message-details-footer">
        <button type="button" className="btn btn-secondary btn-sm" onClick={handleCopyJson}>
          {copied ? 'Copied Details' : 'Copy JSON'}
        </button>
        <div className="message-details-footer-actions">
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
      </footer>
    </OffCanvasPanel>
  );
}
