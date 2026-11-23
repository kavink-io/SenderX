import React, { useState } from 'react';
import EmployeesList from '../../components/employee/EmployeesList';
import RolesList from '../../components/employee/RolesList';
import AuditLogsList from '../../components/employee/AuditLogsList';

export default function EmployeesAndRoles() {
  const [subTab, setSubTab] = useState('EMPLOYEES'); // 'EMPLOYEES', 'ROLES', 'AUDIT'

  return (
    <div className="tab-pane active" id="tab-org-users">
      {/* Sub-tab Navigation Pills */}
      <div style={{ display: 'flex', gap: '8px', marginBottom: '1.5rem', borderBottom: '1px solid var(--glass-border)', paddingBottom: '0.75rem' }}>
        <button
          type="button"
          className={`btn btn-sm ${subTab === 'EMPLOYEES' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setSubTab('EMPLOYEES')}
        >
          Employees
        </button>
        <button
          type="button"
          className={`btn btn-sm ${subTab === 'ROLES' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setSubTab('ROLES')}
        >
          Custom Roles
        </button>
        <button
          type="button"
          className={`btn btn-sm ${subTab === 'AUDIT' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setSubTab('AUDIT')}
        >
          Security Audit Logs
        </button>
      </div>

      {subTab === 'EMPLOYEES' && <EmployeesList />}
      {subTab === 'ROLES' && <RolesList />}
      {subTab === 'AUDIT' && <AuditLogsList />}
    </div>
  );
}
