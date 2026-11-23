import React from 'react';
import Modal from '../common/Modal';

export default function OrgDetailsModal({ isOpen, onClose, org }) {
  if (!org) return null;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Organization Details"
      maxWidth="650px"
      id="modal-org-details"
    >
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1.25rem', marginBottom: '1.5rem' }}>
        <div>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Organization ID</span>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85rem', color: 'var(--text-primary)', wordBreak: 'break-all' }}>
            {org.organization_id || org._id || org.id}
          </div>
        </div>
        <div>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Organization Name</span>
          <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{org.name}</div>
        </div>
        <div>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Slug</span>
          <div style={{ color: 'var(--accent-cyan)' }}>{org.slug}</div>
        </div>
        <div>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Status</span>
          <div>
            <span className={`badge ${org.status === 'ACTIVE' ? 'badge-success' : 'badge-danger'}`}>
              {org.status}
            </span>
          </div>
        </div>
        <div>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Created At</span>
          <div style={{ color: 'var(--text-primary)', fontSize: '0.85rem' }}>
            {org.created_at ? new Date(org.created_at).toLocaleString() : 'N/A'}
          </div>
        </div>
        <div>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Total Applications</span>
          <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{org.applications_count || 0}</div>
        </div>
      </div>

      {org.description && (
        <div style={{ marginBottom: '1.5rem', background: 'var(--bg-surface)', padding: '0.75rem', borderRadius: '6px' }}>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Description</span>
          <p style={{ margin: '0.25rem 0 0', color: 'var(--text-primary)', fontSize: '0.9rem' }}>{org.description}</p>
        </div>
      )}

      <div className="modal-actions" style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <button type="button" className="btn btn-secondary" onClick={onClose}>
          Close
        </button>
      </div>
    </Modal>
  );
}
