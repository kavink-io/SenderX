import React, { useState, useEffect } from 'react';
import Modal from '../common/Modal';
import ApiClient from '../../services/api';
import { useToast } from '../../context/ToastContext';

export default function AssignRoleModal({ isOpen, onClose, employee, onAssigned }) {
  const [roles, setRoles] = useState([]);
  const [apps, setApps] = useState([]);
  const [selectedRoleIds, setSelectedRoleIds] = useState([]);
  const [selectedAppIds, setSelectedAppIds] = useState([]);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { showToast } = useToast();

  useEffect(() => {
    if (!isOpen || !employee) return;

    // Prefill current roles and apps
    const currentRoles = (employee.roles || []).map((r) => r.role_id || r._id);
    setSelectedRoleIds(currentRoles);

    const currentApps = (employee.assigned_applications || []).map((a) => a.application_id || a._id);
    setSelectedAppIds(currentApps);

    Promise.all([
      ApiClient.listRoles().catch(() => null),
      ApiClient.listApplications(1, 100).catch(() => null),
    ]).then(([rolesRes, appsRes]) => {
      if (rolesRes?.success) setRoles(rolesRes.data?.items || rolesRes.data || []);
      if (appsRes?.success) setApps(appsRes.data?.items || []);
    });
  }, [isOpen, employee]);

  if (!employee) return null;
  const userId = employee.user_id || employee._id || employee.id;

  const handleRoleToggle = (rid) => {
    setSelectedRoleIds((prev) =>
      prev.includes(rid) ? prev.filter((id) => id !== rid) : [...prev, rid]
    );
  };

  const handleAppToggle = (aid) => {
    setSelectedAppIds((prev) =>
      prev.includes(aid) ? prev.filter((id) => id !== aid) : [...prev, aid]
    );
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      const payload = {
        role_ids: selectedRoleIds,
        assigned_applications: selectedAppIds,
      };

      const res = await ApiClient.assignUserRoles(userId, payload);
      if (res?.success) {
        showToast('Roles and application scopes assigned!', 'success');
        onAssigned();
        onClose();
      } else {
        showToast(res?.message || 'Assignment failed', 'error');
      }
    } catch (err) {
      showToast(err?.message || 'Error assigning roles', 'error');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`Assign Roles & Scopes: ${employee.name || employee.email}`}
      maxWidth="600px"
      id="modal-assign-role"
    >
      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: '1.25rem' }}>
          <label style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.5rem', display: 'block' }}>
            Select Organization Roles:
          </label>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '8px', maxHeight: '180px', overflowY: 'auto' }}>
            {roles.map((r) => {
              const rid = r.role_id || r._id;
              const isChecked = selectedRoleIds.includes(rid);

              return (
                <label
                  key={rid}
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
                    onChange={() => handleRoleToggle(rid)}
                  />
                  <div>
                    <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)' }}>{r.name}</div>
                    {r.description && (
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>{r.description}</div>
                    )}
                  </div>
                </label>
              );
            })}
          </div>
        </div>

        <div style={{ marginBottom: '1.5rem' }}>
          <label style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.5rem', display: 'block' }}>
            Application Access Scopes:
          </label>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '8px', maxHeight: '160px', overflowY: 'auto' }}>
            {apps.map((a) => {
              const aid = a.application_id || a._id;
              const isChecked = selectedAppIds.includes(aid);

              return (
                <label
                  key={aid}
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
                    onChange={() => handleAppToggle(aid)}
                  />
                  <span style={{ fontSize: '0.85rem', color: 'var(--text-primary)' }}>{a.name}</span>
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
            {isSubmitting ? 'Saving...' : 'Save Assignments'}
          </button>
        </div>
      </form>
    </Modal>
  );
}
