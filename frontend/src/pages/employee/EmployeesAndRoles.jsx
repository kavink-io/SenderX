import React, { useState } from 'react';
import EmployeesList from '../../components/employee/EmployeesList';
import RolesList from '../../components/employee/RolesList';
import AuditLogsList from '../../components/employee/AuditLogsList';
import { GlassTabs } from '../../components/glass';

export default function EmployeesAndRoles() {
  const [subTab, setSubTab] = useState('EMPLOYEES'); // 'EMPLOYEES', 'ROLES', 'AUDIT'

  return (
    <div className="tab-pane active" id="tab-org-users">
      {/* Sub-tab Navigation Pills */}
      <div style={{ marginBottom: '1.35rem' }}>
        <GlassTabs
          activeKey={subTab}
          onChange={setSubTab}
          tabs={[
            { key: 'EMPLOYEES', label: 'Employees' },
            { key: 'ROLES', label: 'Custom Roles' },
            { key: 'AUDIT', label: 'Security Audit Logs' },
          ]}
        />
      </div>

      {subTab === 'EMPLOYEES' && <EmployeesList />}
      {subTab === 'ROLES' && <RolesList />}
      {subTab === 'AUDIT' && <AuditLogsList />}
    </div>
  );
}
