import React, { useState, lazy, Suspense } from 'react';
import EmployeesList from '../../components/employee/EmployeesList';
import PageLoader from '../../components/common/PageLoader';
import { GlassTabs } from '../../components/glass';

const RolesList = lazy(() => import('../../components/employee/RolesList'));
const AuditLogsList = lazy(() => import('../../components/employee/AuditLogsList'));

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
      {subTab === 'ROLES' && (
        <Suspense fallback={<PageLoader compact label="Loading roles..." />}>
          <RolesList />
        </Suspense>
      )}
      {subTab === 'AUDIT' && (
        <Suspense fallback={<PageLoader compact label="Loading audit logs..." />}>
          <AuditLogsList />
        </Suspense>
      )}
    </div>
  );
}
