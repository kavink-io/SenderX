import React, { useState, useEffect } from 'react';
import OffCanvasPanel from '../common/OffCanvasPanel';
import ApiClient from '../../services/api';
import { useToast } from '../../context/ToastContext';
import { GlassSelect } from '../glass';
import GenderSelect from '../employee/GenderSelect';

export default function CreateEmployeeModal({ isOpen, onClose, onCreated }) {
  const [email, setEmail] = useState('');
  const [name, setName] = useState('');
  const [employeeCode, setEmployeeCode] = useState('');
  const [department, setDepartment] = useState('');
  const [phone, setPhone] = useState('');
  const [gender, setGender] = useState('');
  const [roleId, setRoleId] = useState('');
  const [roles, setRoles] = useState([]);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { showToast } = useToast();

  useEffect(() => {
    if (!isOpen) return;
    setEmail('');
    setName('');
    setEmployeeCode('');
    setDepartment('');
    setPhone('');
    setGender('');
    setRoleId('');

    // Fetch next employee code and roles
    Promise.all([
      ApiClient.getNextEmployeeCode().catch(() => null),
      ApiClient.listRoles().catch(() => null),
    ]).then(([codeRes, rolesRes]) => {
      if (codeRes?.success && (codeRes.data?.next_code || codeRes.data?.employee_code)) {
        setEmployeeCode(codeRes.data?.next_code || codeRes.data?.employee_code);
      } else {
        setEmployeeCode('EMP001');
      }
      if (rolesRes?.success) {
        setRoles(rolesRes.data?.items || rolesRes.data || []);
      }
    });
  }, [isOpen]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email.trim() || !name.trim() || !employeeCode.trim()) {
      showToast('Name, work email, and employee code are required', 'error');
      return;
    }

    setIsSubmitting(true);
    try {
      const payload = {
        email: email.trim().toLowerCase(),
        name: name.trim(),
        employee_code: employeeCode.trim(),
        department: department.trim() || undefined,
        phone: phone.trim() || undefined,
        gender: gender || undefined,
        role_id: roleId || undefined,
      };

      const res = await ApiClient.createUser(payload);
      if (res?.success) {
        showToast('Employee created and activation invite sent!', 'success');
        onCreated();
        onClose();
      } else {
        showToast(res?.message || 'Failed to create employee', 'error');
      }
    } catch (err) {
      showToast(err?.message || 'Error creating employee', 'error');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <OffCanvasPanel
      isOpen={isOpen}
      onClose={onClose}
      title="Create Organization Employee"
      size="large"
      id="panel-create-user"
    >
      <form id="form-create-user" onSubmit={handleSubmit}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem', marginBottom: '1rem' }}>
          <div className="form-group">
            <label htmlFor="create-user-email">Work Email *</label>
            <input
              type="email"
              id="create-user-email"
              className="form-control"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="employee@tenant.com"
              required
              autoFocus
            />
          </div>

          <div className="form-group">
            <label htmlFor="create-user-name">Full Name *</label>
            <input
              type="text"
              id="create-user-name"
              className="form-control"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Alex Smith"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="create-user-emp-code">Employee Code *</label>
            <input
              type="text"
              id="create-user-emp-code"
              className="form-control"
              value={employeeCode}
              onChange={(e) => setEmployeeCode(e.target.value)}
              placeholder="EMP001"
              style={{ fontFamily: 'var(--font-mono)' }}
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="create-user-dept">Department</label>
            <input
              type="text"
              id="create-user-dept"
              className="form-control"
              value={department}
              onChange={(e) => setDepartment(e.target.value)}
              placeholder="Engineering / Operations"
            />
          </div>

          <div className="form-group">
            <label htmlFor="create-user-phone">Phone Number</label>
            <input
              type="text"
              id="create-user-phone"
              className="form-control"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="+1 555-0144"
            />
          </div>

          <GenderSelect
            id="create-user-gender"
            value={gender}
            onChange={(e) => setGender(e.target.value)}
          />

          <div className="form-group">
            <label htmlFor="create-user-role">Assigned Role</label>
            <GlassSelect
              id="create-user-role"
              value={roleId}
              onChange={(e) => setRoleId(e.target.value)}
            >
              <option value="">Standard Member (No Custom Role)</option>
              {roles.map((r) => (
                <option key={r.role_id || r._id} value={r.role_id || r._id}>
                  {r.name}
                </option>
              ))}
            </GlassSelect>
          </div>
        </div>

        <div className="modal-actions" style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
          <button type="button" className="btn btn-secondary" onClick={onClose} disabled={isSubmitting}>
            Cancel
          </button>
          <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
            {isSubmitting ? 'Creating...' : 'Create Employee'}
          </button>
        </div>
      </form>
    </OffCanvasPanel>
  );
}
