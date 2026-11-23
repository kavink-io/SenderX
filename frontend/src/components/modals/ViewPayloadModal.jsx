import React, { useState } from 'react';
import Modal from '../common/Modal';
import { useToast } from '../../context/ToastContext';

export default function ViewPayloadModal({ isOpen, onClose, payload }) {
  const [copied, setCopied] = useState(false);
  const { showToast } = useToast();

  if (!payload) return null;

  const rawJson = JSON.stringify(payload.payload_data || payload.data || payload, null, 2);

  const handleCopy = () => {
    navigator.clipboard.writeText(rawJson);
    setCopied(true);
    showToast('Payload copied to clipboard!', 'success');
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Received JSON Request Details"
      maxWidth="700px"
      id="modal-view-payload"
    >
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem', marginBottom: '1.25rem' }}>
        <div>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Payload ID</span>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85rem', color: 'var(--accent-cyan)' }}>
            {payload.payload_id || payload._id || payload.id}
          </div>
        </div>
        <div>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Channel</span>
          <div>
            <span className="badge badge-info">{payload.channel || 'unassigned'}</span>
          </div>
        </div>
        <div>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Validation Status</span>
          <div>
            <span className={`badge ${payload.validation_status === 'VALID' ? 'badge-success' : 'badge-danger'}`}>
              {payload.validation_status || payload.status}
            </span>
          </div>
        </div>
        <div>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Received At</span>
          <div style={{ fontSize: '0.85rem', color: 'var(--text-primary)' }}>
            {payload.created_at ? new Date(payload.created_at).toLocaleString() : 'N/A'}
          </div>
        </div>
      </div>

      {payload.validation_error && (
        <div style={{ background: 'rgba(239, 68, 68, 0.1)', border: '1px solid var(--status-error)', borderRadius: '6px', padding: '0.75rem', marginBottom: '1rem' }}>
          <div style={{ color: 'var(--status-error)', fontWeight: 600, fontSize: '0.85rem', marginBottom: '0.25rem' }}>Validation Error:</div>
          <div style={{ fontSize: '0.85rem', color: 'var(--text-primary)' }}>{payload.validation_error}</div>
        </div>
      )}

      <div style={{ marginBottom: '1rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
          <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)' }}>Raw JSON Payload:</span>
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
            maxHeight: '320px',
            overflowY: 'auto',
            whiteSpace: 'pre-wrap',
          }}
        >
          {rawJson}
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
