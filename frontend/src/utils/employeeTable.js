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

export function getEmployeeRoleLabel(employee = {}) {
  if (employee.is_org_admin) return 'Organization Admin';

  const assignments = [employee.roles, employee.role_assignments]
    .find((roles) => Array.isArray(roles) && roles.length) || [];
  const roleNames = assignments
    .map((role) => readableRoleName(role) || (
      typeof role === 'string'
        ? (role.trim() ? 'Unknown Role' : null)
        : role && typeof role === 'object' && (role.role_id || role.id)
          ? 'Unknown Role'
          : null
    ))
    .filter(Boolean);

  if (roleNames.length) return [...new Set(roleNames)].join(', ');

  const roleIds = Array.isArray(employee.role_ids) ? employee.role_ids : [];
  return roleIds.length ? 'Unknown Role' : 'Unassigned';
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
