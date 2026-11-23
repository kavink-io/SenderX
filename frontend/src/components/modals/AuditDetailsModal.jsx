import React, { useState } from 'react';
import Modal from '../common/Modal';
import { useToast } from '../../context/ToastContext';

export default function AuditDetailsModal({ isOpen, onClose, log }) {
  const [copied, setCopied] = useState(false);
  const { showToast } = useToast();

  if (!log) return null;

  const handleCopy = () => {
    navigator.clipboard.writeText(JSON.stringify(log, null, 2));
    setCopied(true);
    showToast('Audit event copied to clipboard!', 'success');
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Audit Event Details"
      maxWidth="650px"
      id="modal-audit-details"
    >
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem', marginBottom: '1.25rem' }}>
        <div>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Event Type</span>
          <div style={{ fontWeight: 600, color: 'var(--accent-cyan)' }}>{log.event_type || log.action}</div>
        </div>
        <div>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Actor</span>
          <div style={{ color: 'var(--text-primary)' }}>{log.actor_email || log.actor || 'System'}</div>
        </div>
        <div>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Result</span>
          <div>
            <span className={`badge ${log.result === 'SUCCESS' || log.status === 'SUCCESS' ? 'badge-success' : 'badge-danger'}`}>
              {log.result || log.status || 'LOGGED'}
            </span>
          </div>
        </div>
        <div>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Timestamp</span>
          <div style={{ fontSize: '0.85rem', color: 'var(--text-primary)' }}>
            {log.created_at ? new Date(log.created_at).toLocaleString() : 'N/A'}
          </div>
        </div>
      </div>

      <div style={{ marginBottom: '1rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
          <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)' }}>Structured Audit Details</span>
          <button type="button" className="btn btn-secondary btn-sm" onClick={handleCopy}>
            {copied ? 'Copied!' : 'Copy JSON'}
          </button>
        </div>
        <pre
          style={{
            background: 'var(--bg-main)',
            border: '1px solid var(--glass-border)',
            borderRadius: '6px',
            padding: '1rem',
            fontFamily: 'var(--font-mono)',
            fontSize: '0.8rem',
            color: 'var(--text-primary)',
            maxHeight: '280px',
            overflowY: 'auto',
            whiteSpace: 'pre-wrap',
          }}
        >
          {JSON.stringify(log.details || log, null, 2)}
        </pre>
      </div>

      <div className="modal-actions" style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <button type="button" className="btn btn-secondary" onClick={onClose}>
          Close
        </button>
      </div>
    </Modal>
  );
}
