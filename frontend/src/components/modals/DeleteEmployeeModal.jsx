import React, { useState } from 'react';
import Modal from '../common/Modal';
import ApiClient from '../../services/api';
import { useToast } from '../../context/ToastContext';

export default function DeleteEmployeeModal({ isOpen, onClose, employee, onDeleted }) {
  const [isDeleting, setIsDeleting] = useState(false);
  const { showToast } = useToast();

  if (!employee) return null;
  const userId = employee.user_id || employee._id || employee.id;

  const roleName = employee.roles && employee.roles.length > 0
    ? employee.roles.map((r) => r.name || r.role_id).join(', ')
    : (employee.is_org_admin ? 'ORG_ADMIN' : 'Employee (No Role)');

  const handleDelete = async () => {
    setIsDeleting(true);
    try {
      const res = await ApiClient.deleteUser(userId);
      if (res?.success) {
        showToast(`Employee "${employee.name || employee.email}" deleted successfully`, 'success');
        onDeleted();
        onClose();
      } else {
        showToast(res?.message || 'Delete failed', 'error');
      }
    } catch (err) {
      showToast(err?.message || 'Error deleting employee', 'error');
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Delete Employee"
      maxWidth="540px"
      id="modal-delete-employee"
    >
      <div style={{ color: 'var(--status-error)', display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '1rem' }}>
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/>
          <line x1="12" y1="9" x2="12" y2="13"/>
          <line x1="12" y1="17" x2="12.01" y2="17"/>
        </svg>
        <strong>This employee will lose access immediately.</strong>
      </div>

      <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', marginBottom: '1.25rem' }}>
        Please verify the employee details below before confirming removal.
      </p>

      {/* Rich Employee Details Confirmation Matrix */}
      <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--glass-border)', borderRadius: '6px', padding: '1rem', marginBottom: '1.5rem', display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '0.75rem', fontSize: '0.85rem' }}>
        <div>
          <span style={{ color: 'var(--text-secondary)' }}>Employee Name:</span>
          <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{employee.name || 'Not provided'}</div>
        </div>
        <div>
          <span style={{ color: 'var(--text-secondary)' }}>Employee ID:</span>
          <div style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-cyan)' }}>
            {employee.employee_code || 'Not provided'}
          </div>
        </div>
        <div>
          <span style={{ color: 'var(--text-secondary)' }}>Email:</span>
          <div style={{ color: 'var(--text-primary)' }}>{employee.email}</div>
        </div>
        <div>
          <span style={{ color: 'var(--text-secondary)' }}>Assigned Role:</span>
          <div style={{ fontWeight: 600, color: 'var(--accent-blue)' }}>{roleName}</div>
        </div>
        <div>
          <span style={{ color: 'var(--text-secondary)' }}>Department:</span>
          <div style={{ color: 'var(--text-primary)' }}>{employee.department || 'Not provided'}</div>
        </div>
        <div>
          <span style={{ color: 'var(--text-secondary)' }}>Phone Number:</span>
          <div style={{ color: 'var(--text-primary)' }}>{employee.phone_number || employee.phone || 'Not provided'}</div>
        </div>
      </div>

      <div className="modal-actions" style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
        <button type="button" className="btn btn-secondary" onClick={onClose} disabled={isDeleting}>
          Cancel
        </button>
        <button
          type="button"
          className="btn btn-danger"
          onClick={handleDelete}
          disabled={isDeleting}
        >
          {isDeleting ? 'Deleting...' : 'Delete Employee'}
        </button>
      </div>
    </Modal>
  );
}
