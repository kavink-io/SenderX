const UUID_PATTERN = /^[{]?[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}[}]?$/i;

function readableRoleName(role) {
  if (typeof role === 'string') {
    const name = role.trim();
    return name && !UUID_PATTERN.test(name) ? name : null;
  }

  if (!role || typeof role !== 'object') return null;

  const roleId = typeof role.role_id === 'string' ? role.role_id.trim() : '';
  const candidate = [role.role_name, role.name].find((value) => typeof value === 'string' && value.trim());
  if (!candidate) return null;

  const name = candidate.trim();
  if (name === roleId || UUID_PATTERN.test(name)) return null;
  return name.toUpperCase() === 'ORG_ADMIN' ? 'Organization Admin' : name;
}

/**
 * Resolve normalized, human-readable role entries for an employee without exposing raw UUIDs.
 */
export function getEmployeeRolesList(employee = {}) {
  if (employee.is_org_admin) {
    return [{ key: 'org-admin', id: 'ORG_ADMIN', name: 'Organization Admin', isAdmin: true }];
  }

  const assignments = [employee.roles, employee.role_assignments]
    .find((roles) => Array.isArray(roles) && roles.length) || [];

  const resolved = [];
  const seenNames = new Set();

  for (let i = 0; i < assignments.length; i += 1) {
    const role = assignments[i];
    const roleId = typeof role === 'string'
      ? role.trim()
      : (role && typeof role === 'object' ? (role.role_id || role.id || null) : null);

    let name = readableRoleName(role);
    if (!name && roleId) {
      name = 'Unknown Role';
    }
    if (!name) continue;

    const dedupeKey = name === 'Unknown Role' ? `unknown-${roleId || i}` : name.toLowerCase();
    if (seenNames.has(dedupeKey)) continue;
    seenNames.add(dedupeKey);

    resolved.push({
      key: String(roleId || `${name}-${i}`),
      id: roleId,
      name,
      isAdmin: false,
    });
  }

  if (resolved.length > 0) return resolved;

  const roleIds = Array.isArray(employee.role_ids) ? employee.role_ids.filter(Boolean) : [];
  if (roleIds.length > 0) {
    return roleIds.map((rid, idx) => ({
      key: String(rid || idx),
      id: rid,
      name: 'Unknown Role',
      isAdmin: false,
    }));
  }

  return [];
}

/**
 * Split roles into visible badges (1-2 depending on length) and overflow items for `+N`.
 */
export function partitionRoleBadges(roles = []) {
  if (!Array.isArray(roles) || roles.length === 0) {
    return { visible: [], overflow: [] };
  }
  if (roles.length === 1) {
    return { visible: roles, overflow: [] };
  }
  if (roles.length === 2) {
    const combinedLen = roles[0].name.length + roles[1].name.length;
    return combinedLen <= 26
      ? { visible: roles, overflow: [] }
      : { visible: [roles[0]], overflow: [roles[1]] };
  }
  const firstTwoLen = roles[0].name.length + roles[1].name.length;
  const visibleCount = firstTwoLen <= 24 ? 2 : 1;
  return {
    visible: roles.slice(0, visibleCount),
    overflow: roles.slice(visibleCount),
  };
}

export function getEmployeeRoleLabel(employee = {}) {
  const list = getEmployeeRolesList(employee);
  return list.length ? list.map((r) => r.name).join(', ') : 'Unassigned';
}

export function getEmployeeStatus(employee = {}) {
  const rawStatus = typeof employee.status === 'string' ? employee.status.trim() : '';
  const status = (rawStatus || (employee.is_active === true ? 'ACTIVE' : 'INACTIVE'))
    .toUpperCase()
    .replace(/[_-]+/g, ' ');
  const label = status === 'PENDING' ? 'PENDING ACTIVATION' : status;
  const isActive = status === 'ACTIVE';
  const isPending = ['PENDING', 'PENDING ACTIVATION', 'INVITED'].includes(status);

  let badgeClass = 'badge-secondary';
  if (isActive) badgeClass = 'badge-success';
  else if (isPending) badgeClass = 'badge-warning';
  else if (status === 'SUSPENDED') badgeClass = 'badge-danger';

  return { label, badgeClass, isActive, isPending };
}
