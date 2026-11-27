const PLATFORM_PREFIXES = ['/platform/'];
const ORG_PREFIXES = ['/org/'];
const SHARED_AUTHENTICATED_PATHS = ['/appearance'];

export function getDefaultDashboardPath(account) {
  return account?.account_type === 'PLATFORM_ADMIN'
    ? '/platform/organizations'
    : '/org/overview';
}

export function getSafeRedirectPath(target, account) {
  const fallback = getDefaultDashboardPath(account);
  if (!target) return fallback;

  const raw = typeof target === 'string'
    ? target
    : `${target.pathname || ''}${target.search || ''}${target.hash || ''}`;

  const trimmed = raw.trim();
  if (
    !trimmed.startsWith('/') ||
    trimmed.startsWith('//') ||
    trimmed.includes('\\') ||
    /[\u0000-\u001f]/.test(trimmed)
  ) {
    return fallback;
  }

  let parsed;
  try {
    parsed = new URL(trimmed, 'https://senderx.local');
  } catch {
    return fallback;
  }

  if (parsed.origin !== 'https://senderx.local') {
    return fallback;
  }

  const pathname = parsed.pathname;
  if (
    pathname === '/' ||
    pathname === '/dashboard' ||
    pathname === '/login' ||
    pathname === '/access-denied'
  ) {
    return fallback;
  }

  const isShared = SHARED_AUTHENTICATED_PATHS.includes(pathname);
  const isPlatform = account?.account_type === 'PLATFORM_ADMIN';
  const allowedPrefixes = isPlatform ? PLATFORM_PREFIXES : ORG_PREFIXES;
  const matchesRoleRoute = allowedPrefixes.some((prefix) => pathname.startsWith(prefix));

  if (!isShared && !matchesRoleRoute) {
    return fallback;
  }

  return `${pathname}${parsed.search}${parsed.hash}`;
}
