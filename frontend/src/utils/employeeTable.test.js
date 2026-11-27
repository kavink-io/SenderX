import assert from 'node:assert/strict';
import test from 'node:test';
import { getEmployeeRoleLabel, getEmployeeStatus } from './employeeTable.js';

test('employee roles display backend role names instead of IDs', () => {
  assert.equal(
    getEmployeeRoleLabel({ roles: [{ role_id: 'role-1', role_name: 'Developer' }] }),
    'Developer'
  );
  assert.equal(
    getEmployeeRoleLabel({ roles: [{ role_id: 'role-2', role_name: 'ORG_ADMIN' }] }),
    'Organization Admin'
  );
  assert.equal(
    getEmployeeRoleLabel({
      roles: [],
      role_assignments: [{ role_id: 'role-3', role_name: 'Manager' }],
    }),
    'Manager'
  );
});

test('unresolved role IDs use an explicit fallback without exposing IDs', () => {
  assert.equal(
    getEmployeeRoleLabel({ roles: [{ role_id: '67e3aa76-2135-4117-8d7f-f8a0fd891716' }] }),
    'Unknown Role'
  );
  assert.equal(getEmployeeRoleLabel({ role_ids: ['custom-role-id'] }), 'Unknown Role');
  assert.equal(getEmployeeRoleLabel({ roles: [] }), 'Unassigned');
});

test('employee statuses use readable labels and appropriate badge tones', () => {
  assert.deepEqual(getEmployeeStatus({ status: 'PENDING_ACTIVATION' }), {
    label: 'PENDING ACTIVATION',
    badgeClass: 'badge-warning',
    isActive: false,
    isPending: true,
  });
  assert.equal(getEmployeeStatus({ status: 'INVITED' }).badgeClass, 'badge-warning');
  assert.equal(getEmployeeStatus({ status: 'SUSPENDED' }).badgeClass, 'badge-danger');
  assert.equal(getEmployeeStatus({ is_active: false }).label, 'INACTIVE');
  assert.equal(getEmployeeStatus({ status: 'ACTIVE' }).isActive, true);
});
