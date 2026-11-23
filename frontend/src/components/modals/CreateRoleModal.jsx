import React, { useState, useEffect } from 'react';
import Modal from '../common/Modal';
import ApiClient from '../../services/api';
import { useToast } from '../../context/ToastContext';

export default function CreateRoleModal({ isOpen, onClose, role, onSaved }) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [selectedPermissions, setSelectedPermissions] = useState([]);
  const [availablePermissions, setAvailablePermissions] = useState([]);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { showToast } = useToast();

  useEffect(() => {
    if (!isOpen) return;

    if (role) {
      setName(role.name || '');
      setDescription(role.description || '');
      setSelectedPermissions(role.permissions || []);
    } else {
      setName('');
      setDescription('');
      setSelectedPermissions([]);
    }

    ApiClient.listPermissions()
      .then((res) => {
        if (res?.success) {
          setAvailablePermissions(res.data?.permissions || res.data?.items || res.data || []);
        }
      })
      .catch((err) => console.warn('Could not load permissions list:', err));
  }, [isOpen, role]);

  const handleTogglePerm = (p) => {
    setSelectedPermissions((prev) =>
      prev.includes(p) ? prev.filter((x) => x !== p) : [...prev, p]
    );
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!name.trim()) {
      showToast('Role name is required', 'error');
      return;
    }

    setIsSubmitting(true);
    try {
      const payload = {
        name: name.trim(),
        description: description.trim(),
        permissions: selectedPermissions,
      };

      const rid = role?.role_id || role?._id || role?.id;
      const res = rid
        ? await ApiClient.updateRole(rid, payload)
        : await ApiClient.createRole(payload);

      if (res?.success) {
        showToast(`Role ${rid ? 'updated' : 'created'} successfully!`, 'success');
        onSaved();
        onClose();
      } else {
        showToast(res?.message || 'Failed to save role', 'error');
      }
    } catch (err) {
      showToast(err?.message || 'Error saving role', 'error');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={role ? `Edit Role: ${role.name}` : 'Create Custom Organization Role'}
      maxWidth="650px"
      id="modal-create-role"
    >
      <form id="form-create-role" onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="create-role-name">Role Name *</label>
          <input
            type="text"
            id="create-role-name"
            className="form-control"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g., Marketing Dispatcher"
            required
            autoFocus
          />
        </div>

        <div className="form-group" style={{ marginBottom: '1.25rem' }}>
          <label htmlFor="create-role-desc">Description</label>
          <textarea
            id="create-role-desc"
            className="form-control"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Grants access to edit templates and review delivery telemetry..."
            rows={2}
          />
        </div>

        <div style={{ marginBottom: '1.5rem' }}>
          <label style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.5rem', display: 'block' }}>
            Permissions Matrix:
          </label>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '8px', maxHeight: '200px', overflowY: 'auto' }}>
            {availablePermissions.map((p) => {
              const permKey = typeof p === 'string' ? p : p.key || p.name;
              const permLabel = typeof p === 'string' ? p : p.name || p.description || p.key;
              const isChecked = selectedPermissions.includes(permKey);

              return (
                <label
                  key={permKey}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    padding: '0.5rem',
                    borderRadius: '6px',
                    background: 'var(--bg-surface)',
                    cursor: 'pointer',
                  }}
                >
                  <input
                    type="checkbox"
                    checked={isChecked}
                    onChange={() => handleTogglePerm(permKey)}
                  />
                  <span style={{ fontSize: '0.8rem', fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
                    {permLabel}
                  </span>
                </label>
              );
            })}
          </div>
        </div>

        <div className="modal-actions" style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
          <button type="button" className="btn btn-secondary" onClick={onClose} disabled={isSubmitting}>
            Cancel
          </button>
          <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
            {isSubmitting ? 'Saving...' : 'Save Role'}
          </button>
        </div>
      </form>
    </Modal>
  );
}
