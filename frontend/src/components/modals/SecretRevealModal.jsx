import React, { useState } from 'react';
import Modal from '../common/Modal';
import { useToast } from '../../context/ToastContext';

export default function SecretRevealModal({ isOpen, onClose, secretKey, keyName }) {
  const [copied, setCopied] = useState(false);
  const { showToast } = useToast();

  if (!isOpen) return null;

  const handleCopy = () => {
    navigator.clipboard.writeText(secretKey);
    setCopied(true);
    showToast('Secret key copied to clipboard!', 'success');
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Save Your API Secret Key"
      maxWidth="560px"
      id="modal-one-time-secret"
    >
      <div style={{ color: 'var(--status-warning)', display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '1rem' }}>
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/>
          <line x1="12" y1="9" x2="12" y2="13"/>
          <line x1="12" y1="17" x2="12.01" y2="17"/>
        </svg>
        <strong>This key will only be shown once!</strong>
      </div>

      <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', marginBottom: '1.25rem' }}>
        Store this secret key securely. For security purposes, SenderX hashes keys at rest and will not be able to display this secret again.
      </p>

      {keyName && (
        <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
          Key Name: <strong>{keyName}</strong>
        </div>
      )}

      <div style={{ display: 'flex', gap: '8px', marginBottom: '1.5rem' }}>
        <input
          type="text"
          className="form-control"
          value={secretKey || ''}
          readOnly
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '0.85rem',
            background: 'var(--bg-surface)',
            color: 'var(--accent-cyan)',
          }}
        />
        <button
          type="button"
          className="btn btn-secondary"
          onClick={handleCopy}
          id="btn-copy-secret"
        >
          {copied ? 'Copied!' : 'Copy'}
        </button>
      </div>

      <div className="modal-actions" style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <button
          type="button"
          id="btn-dismiss-secret"
          className="btn btn-primary"
          onClick={onClose}
        >
          I Have Saved My Secret Key
        </button>
      </div>
    </Modal>
  );
}
