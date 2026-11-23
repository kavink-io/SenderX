import React, { useState } from 'react';
import Modal from '../common/Modal';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import ApiClient from '../../services/api';

export default function UserProfileModal({ isOpen, onClose }) {
  const { account, dashboardContext, refreshProfile } = useAuth();
  const { showToast } = useToast();
  const [name, setName] = useState(account?.name || '');
  const [phone, setPhone] = useState(account?.phone_number || '');
  const [department, setDepartment] = useState(account?.department || '');
  const [isSaving, setIsSaving] = useState(false);

  const isPlatformAdmin = account?.account_type === 'PLATFORM_ADMIN';

  const handleSave = async (e) => {
    e.preventDefault();
    if (isPlatformAdmin) {
      onClose();
      return;
    }
    setIsSaving(true);
    try {
      const res = await ApiClient.updateMyProfile({
        name: name.trim(),
        phone_number: phone.trim(),
        department: department.trim(),
      });
      if (res?.success) {
        showToast('Profile updated successfully!', 'success');
        await refreshProfile();
        onClose();
      } else {
        showToast(res?.message || 'Failed to update profile', 'error');
      }
    } catch (err) {
      showToast(err?.message || 'Error saving profile', 'error');
    } finally {
      setIsSaving(false);
    }
  };

  const roles = dashboardContext?.roles || account?.roles || [];
  const assignedApps = dashboardContext?.assigned_applications || [];
  const permissions = Array.from(dashboardContext?.permissions || []);

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="User Profile & Access Scopes"
      maxWidth="680px"
      id="modal-user-profile"
    >
      <form onSubmit={handleSave}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem', marginBottom: '1.25rem' }}>
          <div className="form-group">
            <label>Email Address</label>
            <input
              type="email"
              className="form-control"
              value={account?.email || ''}
              disabled
              style={{ opacity: 0.7 }}
            />
          </div>
          <div className="form-group">
            <label>Full Name</label>
            <input
              type="text"
              className="form-control"
              value={name}
              onChange={(e) => setName(e.target.value)}
              disabled={isPlatformAdmin}
              placeholder="Your full name"
            />
          </div>
          <div className="form-group">
            <label>Phone Number</label>
            <input
              type="text"
              className="form-control"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              disabled={isPlatformAdmin}
              placeholder="+1-555-0123"
            />
          </div>
          <div className="form-group">
            <label>Department</label>
            <input
              type="text"
              className="form-control"
              value={department}
              onChange={(e) => setDepartment(e.target.value)}
              disabled={isPlatformAdmin}
              placeholder="Engineering / Sales"
            />
          </div>
        </div>

        {/* Roles & Scopes info */}
        <div style={{ marginBottom: '1.25rem', borderTop: '1px solid var(--glass-border)', paddingTop: '1rem' }}>
          <h4 style={{ fontSize: '0.95rem', marginBottom: '0.5rem', color: 'var(--text-primary)' }}>Assigned Roles</h4>
          {roles.length === 0 ? (
            <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
              {isPlatformAdmin ? 'Root Platform Administrator' : 'Standard Employee'}
            </p>
          ) : (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
              {roles.map((r, i) => (
                <span key={i} className="badge badge-primary">
                  {r.name || r.role_id}
                </span>
              ))}
            </div>
          )}
        </div>

        {!isPlatformAdmin && (
          <div style={{ marginBottom: '1.25rem' }}>
            <h4 style={{ fontSize: '0.95rem', marginBottom: '0.5rem', color: 'var(--text-primary)' }}>Application Access</h4>
            {dashboardContext?.is_org_admin ? (
              <span className="badge badge-success">All Organization Applications (Admin)</span>
            ) : assignedApps.length === 0 ? (
              <span className="badge badge-secondary">No Assigned Applications</span>
            ) : (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                {assignedApps.map((a, i) => (
                  <span key={i} className="badge badge-info">
                    {a.name || a.application_id}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}

        <div className="modal-actions" style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Close
          </button>
          {!isPlatformAdmin && (
            <button type="submit" className="btn btn-primary" disabled={isSaving}>
              {isSaving ? 'Saving...' : 'Save Profile'}
            </button>
          )}
        </div>
      </form>
    </Modal>
  );
}
