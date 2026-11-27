import test from 'node:test';
import assert from 'node:assert/strict';

import {
  getEmployeeRoleLabel,
  getEmployeeRolesList,
  partitionRoleBadges,
} from '../utils/employeeTable.js';

test('getEmployeeRolesList resolves admin and human-readable roles while hiding raw UUIDs', () => {
  const adminRoles = getEmployeeRolesList({ is_org_admin: true });
  assert.equal(adminRoles.length, 1);
  assert.equal(adminRoles[0].name, 'Organization Admin');

  const uuidOnly = getEmployeeRolesList({
    roles: [{ role_id: '550e8400-e29b-41d4-a716-446655440000', name: '550e8400-e29b-41d4-a716-446655440000' }],
  });
  assert.equal(uuidOnly[0].name, 'Unknown Role');
  assert.equal(uuidOnly[0].id, '550e8400-e29b-41d4-a716-446655440000');

  const multi = getEmployeeRolesList({
    roles: [
      { role_id: 'r1', name: 'Admin' },
      { role_id: 'r2', name: 'Member' },
      { role_id: 'r3', name: 'Auditor' },
      { role_id: 'r4', name: 'Developer' },
      { role_id: 'r5', name: 'Support' },
    ],
  });
  assert.equal(multi.length, 5);
  assert.equal(getEmployeeRoleLabel({ roles: multi }), 'Admin, Member, Auditor, Developer, Support');
});

test('partitionRoleBadges displays 1-2 roles cleanly and produces +N overflow for 3+ roles', () => {
  assert.deepEqual(partitionRoleBadges([]), { visible: [], overflow: [] });

  const one = partitionRoleBadges([{ key: '1', name: 'Auditor' }]);
  assert.equal(one.visible.length, 1);
  assert.equal(one.overflow.length, 0);

  const twoShort = partitionRoleBadges([
    { key: '1', name: 'Admin' },
    { key: '2', name: 'Member' },
  ]);
  assert.equal(twoShort.visible.length, 2);
  assert.equal(twoShort.overflow.length, 0);

  const fiveRoles = partitionRoleBadges([
    { key: '1', name: 'Admin' },
    { key: '2', name: 'Member' },
    { key: '3', name: 'Auditor' },
    { key: '4', name: 'Developer' },
    { key: '5', name: 'Support' },
  ]);
  assert.equal(fiveRoles.visible.length, 2);
  assert.equal(fiveRoles.overflow.length, 3);
  assert.deepEqual(
    fiveRoles.overflow.map((r) => r.name),
    ['Auditor', 'Developer', 'Support']
  );
});
