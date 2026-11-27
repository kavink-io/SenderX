import React from 'react';
import OffCanvasPanel from '../common/OffCanvasPanel';
import ProfessionalAvatar from '../common/ProfessionalAvatar';
import { getEmployeeAge } from '../../utils/professionalAvatar';

export default function EmployeeDetailsModal({ isOpen, onClose, employee }) {
  if (!employee) return null;

  const roles = employee.roles || [];
  const assignedApps = employee.assigned_applications || [];
  const permissions = employee.permissions || [];
  const age = getEmployeeAge(employee);

  return (
    <OffCanvasPanel
      isOpen={isOpen}
      onClose={onClose}
      title="Employee Profile & Permissions Matrix"
      size="large"
      id="panel-user-details"
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '14px', marginBottom: '1.5rem' }}>
        <ProfessionalAvatar employee={employee} name={employee.name} size={52} />
        <div>
          <strong style={{ display: 'block', color: 'var(--text-primary)' }}>{employee.name || employee.email}</strong>
          <span style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
            {employee.email}
          </span>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1.25rem', marginBottom: '1.5rem' }}>
        <div>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Full Name</span>
          <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{employee.name || 'Not provided'}</div>
        </div>
        <div>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Employee Code</span>
          <div style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-cyan)' }}>
            {employee.employee_code || 'Not assigned'}
          </div>
        </div>
        <div>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Email</span>
          <div style={{ color: 'var(--text-primary)' }}>{employee.email}</div>
        </div>
        <div>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Status</span>
          <div>
            <span className={`badge ${employee.is_active || employee.status === 'ACTIVE' ? 'badge-success' : 'badge-danger'}`}>
              {employee.status || (employee.is_active ? 'ACTIVE' : 'INACTIVE')}
            </span>
          </div>
        </div>
        <div>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Department</span>
          <div style={{ color: 'var(--text-primary)' }}>{employee.department || 'Not provided'}</div>
        </div>
        <div>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Phone</span>
          <div style={{ color: 'var(--text-primary)' }}>{employee.phone_number || employee.phone || 'Not provided'}</div>
        </div>
        <div>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Gender</span>
          <div style={{ color: 'var(--text-primary)' }}>{employee.gender || 'Not provided'}</div>
        </div>
        <div>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Age</span>
          <div style={{ color: 'var(--text-primary)' }}>{age === null ? 'Not provided' : age}</div>
        </div>
      </div>

      {/* Roles & Scopes */}
      <div style={{ borderTop: '1px solid var(--glass-border)', paddingTop: '1rem', marginBottom: '1.25rem' }}>
        <h4 style={{ fontSize: '0.95rem', marginBottom: '0.5rem', color: 'var(--text-primary)' }}>Assigned Roles</h4>
        {roles.length === 0 ? (
          <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
            {employee.is_org_admin ? 'Organization Administrator' : 'Standard Employee'}
          </p>
        ) : (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
            {roles.map((r, i) => (
              <span key={i} className="badge badge-primary">{r.name || r.role_id}</span>
            ))}
          </div>
        )}
      </div>

      <div style={{ marginBottom: '1.25rem' }}>
        <h4 style={{ fontSize: '0.95rem', marginBottom: '0.5rem', color: 'var(--text-primary)' }}>Application Scope</h4>
        {employee.is_org_admin ? (
          <span className="badge badge-success">Global (All Applications)</span>
        ) : assignedApps.length === 0 ? (
          <span className="badge badge-secondary">All Applications</span>
        ) : (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
            {assignedApps.map((a, i) => (
              <span key={i} className="badge badge-info">{a.name || a.application_id}</span>
            ))}
          </div>
        )}
      </div>

      {/* Permissions Matrix */}
      <div>
        <h4 style={{ fontSize: '0.95rem', marginBottom: '0.5rem', color: 'var(--text-primary)' }}>Effective Permissions</h4>
        {employee.is_org_admin ? (
          <p style={{ color: 'var(--status-success)', fontSize: '0.85rem' }}>
            ✓ Full Organization Administrator Access (All permissions granted)
          </p>
        ) : permissions.length === 0 ? (
          <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>No explicit permissions granted.</p>
        ) : (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', maxHeight: '160px', overflowY: 'auto' }}>
            {permissions.map((p, i) => (
              <span key={i} className="badge badge-scope">{p}</span>
            ))}
          </div>
        )}
      </div>

      <div className="modal-actions" style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '1.5rem' }}>
        <button type="button" className="btn btn-secondary" onClick={onClose}>
          Close
        </button>
      </div>
    </OffCanvasPanel>
  );
}
