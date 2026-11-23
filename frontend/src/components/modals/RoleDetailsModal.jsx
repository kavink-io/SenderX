import React from 'react';
import Modal from '../common/Modal';

export default function RoleDetailsModal({ isOpen, onClose, role }) {
  if (!role) return null;

  const permissions = role.permissions || [];
  const assignedUsers = role.users || role.members || [];

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`Role Details: ${role.name}`}
      maxWidth="650px"
      id="modal-role-details"
    >
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginBottom: '1.25rem' }}>
        <div>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Role Name</span>
          <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{role.name}</div>
        </div>
        <div>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Role ID</span>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85rem', color: 'var(--accent-cyan)' }}>
            {role.role_id || role._id || role.id}
          </div>
        </div>
      </div>

      {role.description && (
        <div style={{ background: 'var(--bg-surface)', padding: '0.75rem', borderRadius: '6px', marginBottom: '1.25rem' }}>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Description</span>
          <p style={{ margin: '0.25rem 0 0', color: 'var(--text-primary)', fontSize: '0.85rem' }}>{role.description}</p>
        </div>
      )}

      {/* Permissions */}
      <div style={{ marginBottom: '1.25rem' }}>
        <h4 style={{ fontSize: '0.95rem', marginBottom: '0.5rem', color: 'var(--text-primary)' }}>Included Permissions</h4>
        {permissions.length === 0 ? (
          <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>No permissions assigned.</p>
        ) : (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', maxHeight: '160px', overflowY: 'auto' }}>
            {permissions.map((p, i) => (
              <span key={i} className="badge badge-scope">{p}</span>
            ))}
          </div>
        )}
      </div>

      {/* Assigned Members */}
      <div>
        <h4 style={{ fontSize: '0.95rem', marginBottom: '0.5rem', color: 'var(--text-primary)' }}>Assigned Members</h4>
        {assignedUsers.length === 0 ? (
          <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>No employees assigned to this role.</p>
        ) : (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
            {assignedUsers.map((u, i) => (
              <span key={i} className="badge badge-primary">{typeof u === 'string' ? u : u.name || u.email}</span>
            ))}
          </div>
        )}
      </div>

      <div className="modal-actions" style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '1.5rem' }}>
        <button type="button" className="btn btn-secondary" onClick={onClose}>
          Close
        </button>
      </div>
    </Modal>
  );
}
