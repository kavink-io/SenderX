import React, { useEffect, useState } from 'react';
import OffCanvasPanel from '../common/OffCanvasPanel';
import GenderSelect from '../employee/GenderSelect';
import ProfessionalAvatar from '../common/ProfessionalAvatar';
import ApiClient from '../../services/api';
import { useToast } from '../../context/ToastContext';

export default function EditEmployeeModal({ isOpen, onClose, employee, onUpdated }) {
  const [name, setName] = useState('');
  const [department, setDepartment] = useState('');
  const [phone, setPhone] = useState('');
  const [gender, setGender] = useState('');
  const [refreshAvatar, setRefreshAvatar] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const { showToast } = useToast();
  const hasAvatarProfileChanges = Boolean(employee)
    && gender !== (employee.gender || '');

  useEffect(() => {
    if (!isOpen || !employee) return;
    setName(employee.name || '');
    setDepartment(employee.department || '');
    setPhone(employee.phone_number || employee.phone || '');
    setGender(employee.gender || '');
    setRefreshAvatar(false);
  }, [employee, isOpen]);

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!employee || !name.trim()) {
      showToast('Full name is required', 'error');
      return;
    }

    const userId = employee.user_id || employee._id || employee.id;
    setIsSaving(true);
    try {
      const payload = {
        name: name.trim(),
        department: department.trim() || null,
        phone: phone.trim() || null,
        gender: gender || null,
      };
      if (refreshAvatar && hasAvatarProfileChanges) payload.refresh_avatar = true;

      const result = await ApiClient.updateUser(userId, payload);
      if (!result?.success) {
        showToast(result?.message || 'Could not update employee', 'error');
        return;
      }

      showToast('Employee updated successfully', 'success');
      onUpdated(result.data);
      onClose();
    } catch (error) {
      showToast(error?.message || 'Could not update employee', 'error');
    } finally {
      setIsSaving(false);
    }
  };

  if (!employee) return null;

  return (
    <OffCanvasPanel
      isOpen={isOpen}
      onClose={onClose}
      title="Edit Employee"
      description="Update employee profile details and avatar preferences."
      size="large"
      id="panel-edit-employee"
    >
      <form onSubmit={handleSubmit}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px', marginBottom: '1.25rem' }}>
          <ProfessionalAvatar employee={employee} name={employee.name} size={52} />
          <div>
            <strong style={{ display: 'block', color: 'var(--text-primary)' }}>{employee.name || employee.email}</strong>
            <span style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
              Uploaded profile photos are kept unchanged.
            </span>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem' }}>
          <div className="form-group">
            <label htmlFor="edit-user-name">Full Name *</label>
            <input
              id="edit-user-name"
              type="text"
              className="form-control"
              value={name}
              onChange={(event) => setName(event.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="edit-user-email">Work Email</label>
            <input id="edit-user-email" type="email" className="form-control" value={employee.email || ''} disabled />
          </div>

          <div className="form-group">
            <label htmlFor="edit-user-employee-code">Employee Code</label>
            <input
              id="edit-user-employee-code"
              type="text"
              className="form-control"
              value={employee.employee_code || ''}
              disabled
              style={{ fontFamily: 'var(--font-mono)' }}
            />
          </div>

          <div className="form-group">
            <label htmlFor="edit-user-department">Department</label>
            <input
              id="edit-user-department"
              type="text"
              className="form-control"
              value={department}
              onChange={(event) => setDepartment(event.target.value)}
            />
          </div>

          <div className="form-group">
            <label htmlFor="edit-user-phone">Phone Number</label>
            <input
              id="edit-user-phone"
              type="text"
              className="form-control"
              value={phone}
              onChange={(event) => setPhone(event.target.value)}
            />
          </div>

          <GenderSelect
            id="edit-user-gender"
            value={gender}
            onChange={(event) => setGender(event.target.value)}
          />
        </div>

        <div className="form-group" style={{ marginTop: '0.5rem' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: '9px' }}>
            <input
              type="checkbox"
              checked={refreshAvatar}
              disabled={!hasAvatarProfileChanges}
              onChange={(event) => setRefreshAvatar(event.target.checked)}
            />
            Refresh the avatar after changing gender
          </label>
          <small style={{ display: 'block', marginTop: '6px', color: 'var(--text-secondary)' }}>
            Available after changing gender. Uploaded profile photos remain the primary avatar.
          </small>
        </div>

        <div className="modal-actions" style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '1.5rem' }}>
          <button type="button" className="btn btn-secondary" onClick={onClose} disabled={isSaving}>
            Cancel
          </button>
          <button type="submit" className="btn btn-primary" disabled={isSaving}>
            {isSaving ? 'Saving...' : 'Save Changes'}
          </button>
        </div>
      </form>
    </OffCanvasPanel>
  );
}
