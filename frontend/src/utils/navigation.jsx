import React from 'react';

export const PLATFORM_NAVIGATION = [
  {
    id: 'platform-organizations',
    name: 'Organizations',
    path: '/platform/organizations',
    tabId: 'tab-platform-overview',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M6 22V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18Z"/>
        <path d="M6 12H4a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h2"/>
        <path d="M18 9h2a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-2"/>
        <path d="M10 6h4"/>
        <path d="M10 10h4"/>
        <path d="M10 14h4"/>
        <path d="M10 18h4"/>
      </svg>
    )
  },
  {
    id: 'platform-analytics',
    name: 'Platform Analytics',
    path: '/platform/analytics',
    tabId: 'tab-platform-analytics',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
      </svg>
    )
  },
  {
    id: 'platform-monitoring',
    name: 'System Health',
    path: '/platform/monitoring',
    tabId: 'tab-platform-monitoring',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"/>
      </svg>
    )
  },
  {
    id: 'platform-change-requests',
    name: 'Change Requests',
    path: '/platform/change-requests',
    tabId: 'tab-platform-change-requests',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
        <polyline points="14 2 14 8 20 8"/>
        <line x1="16" y1="13" x2="8" y2="13"/>
        <line x1="16" y1="17" x2="8" y2="17"/>
        <polyline points="10 9 9 9 8 9"/>
      </svg>
    )
  }
];

export const ORG_NAVIGATION = [
  {
    id: 'menu-overview',
    name: 'Overview',
    path: '/org/overview',
    tabId: 'tab-org-overview',
    requiredPermission: null,
    allowedActions: ['view_dashboard'],
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect width="7" height="9" x="3" y="3" rx="1"/>
        <rect width="7" height="5" x="14" y="3" rx="1"/>
        <rect width="7" height="9" x="14" y="12" rx="1"/>
        <rect width="7" height="5" x="3" y="16" rx="1"/>
      </svg>
    )
  },
  {
    id: 'menu-applications',
    name: 'Connected Applications',
    path: '/org/applications',
    tabId: 'tab-org-applications',
    requiredPermission: 'organization:configuration:manage',
    allowedActions: ['register_app', 'activate_app', 'deactivate_app'],
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect width="14" height="20" x="5" y="2" rx="2" ry="2"/>
        <path d="M12 18h.01"/>
      </svg>
    )
  },
  {
    id: 'menu-credentials',
    name: 'API Credentials',
    path: '/org/credentials',
    tabId: 'tab-org-credentials',
    requiredPermission: 'organization:configuration:manage',
    allowedActions: ['create_key', 'rotate_key', 'revoke_key'],
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="7.5" cy="15.5" r="5.5"/>
        <path d="m21 2-9.6 9.6"/>
        <path d="m15.5 7.5 3 3L22 7l-3-3"/>
      </svg>
    )
  },
  {
    id: 'menu-channel-configurations',
    name: 'Channel Configurations',
    path: '/org/channels',
    tabId: 'tab-org-channels',
    requiredPermission: 'organization:providers:read',
    allowedActions: ['view_provider_configs', 'manage_provider_configs'],
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 2v4" />
        <path d="M12 18v4" />
        <path d="m4.93 4.93 2.83 2.83" />
        <path d="m16.24 16.24 2.83 2.83" />
        <path d="M2 12h4" />
        <path d="M18 12h4" />
        <path d="m4.93 19.07 2.83-2.83" />
        <path d="m16.24 7.76 2.83-2.83" />
        <circle cx="12" cy="12" r="4" />
      </svg>
    )
  },
  {
    id: 'menu-messages',
    name: 'Messages',
    path: '/org/messages',
    tabId: 'tab-org-messages',
    requiredPermission: 'organization:messages:read',
    allowedActions: ['view_messages', 'send_message', 'queue_message'],
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="m22 2-7 20-4-9-9-4Z"/>
        <path d="M22 2 11 13"/>
      </svg>
    )
  },
  {
    id: 'menu-templates',
    name: 'Email Templates',
    path: '/org/templates',
    tabId: 'tab-org-templates',
    requiredPermission: 'organization:templates:read',
    allowedActions: ['view_templates', 'create_template', 'publish_template'],
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
        <polyline points="14 2 14 8 20 8"/>
        <line x1="16" y1="13" x2="8" y2="13"/>
        <line x1="16" y1="17" x2="8" y2="17"/>
        <polyline points="10 9 9 9 8 9"/>
      </svg>
    )
  },
  {
    id: 'menu-json-requests',
    name: 'JSON Requests',
    path: '/org/json-requests',
    tabId: 'tab-org-json-requests',
    requiredPermission: 'organization:payloads:read',
    allowedActions: ['view_payload', 'edit_payload', 'validate_payload', 'retry_payload'],
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <polyline points="16 18 22 12 16 6"/>
        <polyline points="8 6 2 12 8 18"/>
      </svg>
    )
  },
  {
    id: 'menu-dlq',
    name: 'Dead Letter Queue',
    path: '/org/dlq',
    tabId: 'tab-org-dlq',
    requiredPermission: 'organization:dead_letters:read',
    allowedActions: ['view_dlq', 'retry_dlq', 'delete_dlq'],
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <polygon points="7.86 2 16.14 2 22 7.86 22 16.14 16.14 22 7.86 22 2 16.14 2 7.86 7.86 2"/>
        <line x1="12" y1="8" x2="12" y2="12"/>
        <line x1="12" y1="16" x2="12.01" y2="16"/>
      </svg>
    )
  },
  {
    id: 'menu-analytics',
    name: 'Analytics',
    path: '/org/analytics',
    tabId: 'tab-org-analytics',
    requiredPermission: 'organization:analytics:read',
    allowedActions: ['view_analytics', 'export_reports'],
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M3 3v18h18"/>
        <path d="m19 9-5 5-4-4-3 3"/>
      </svg>
    )
  },
  {
    id: 'menu-users',
    name: 'Employees & Roles',
    path: '/org/users',
    tabId: 'tab-org-users',
    requiredPermission: 'organization:users:read',
    allowedActions: ['view_users', 'create_user', 'edit_user', 'manage_roles'],
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/>
        <circle cx="9" cy="7" r="4"/>
        <path d="M22 21v-2a4 4 0 0 0-3-3.87"/>
        <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
      </svg>
    )
  },
  {
    id: 'menu-settings',
    name: 'Settings',
    path: '/org/settings',
    tabId: 'tab-org-settings',
    requiredPermission: 'organization:configuration:manage',
    allowedActions: ['manage_settings', 'view_security_architecture'],
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/>
        <circle cx="12" cy="12" r="3"/>
      </svg>
    )
  }
];

export function getNavigationLabel(item) {
  if (item.id === 'menu-overview') return 'Dashboard';
  if (item.id === 'menu-credentials') return 'API Keys';
  if (item.id === 'menu-users') return 'Users & Roles';
  if (item.name === 'Email Templates') return 'Templates';
  return item.name;
}

export const ROUTE_META = {
  '/platform/organizations': { title: 'Platform Organizations', sub: 'Platform-wide organization management' },
  '/platform/change-requests': { title: 'Organization Change Requests', sub: 'Review, approve, or reject tenant name and slug rebranding requests' },
  '/platform/analytics': { title: 'Platform Analytics', sub: 'Cross-organization telemetry and system throughput' },
  '/platform/monitoring': { title: 'System Health', sub: 'Real-time health status of infrastructure services' },
  '/org/overview': { title: 'Overview', sub: 'Organization performance, application telemetry, and delivery metrics' },
  '/org/applications': { title: 'Connected Applications', sub: 'Register and manage external web applications, e-commerce stores, and microservices' },
  '/org/credentials': { title: 'API Credentials', sub: 'Cryptographically hashed API keys for external payload ingestion' },
  '/org/channels': { title: 'Channel Configurations', sub: 'Configure SenderX outbound messaging providers for this organization' },
  '/org/messages': { title: 'Messages', sub: 'Direct message management & outbox delivery logs' },
  '/org/templates': { title: 'Email Templates', sub: 'Multi-tenant sandboxed email templates' },
  '/org/json-requests': { title: 'Received JSON Requests', sub: 'Immutable audit log of inbound JSON payloads and routing states' },
  '/org/dlq': { title: 'Dead Letter Queue', sub: 'Unrouted or delivery-failed messages requiring inspection or manual retry' },
  '/org/analytics': { title: 'Analytics', sub: 'Comprehensive volume, delivery performance, and failure trends' },
  '/org/users': { title: 'Employees & Roles', sub: 'Manage organization members, assignments, and custom role permissions' },
  '/org/settings': { title: 'Settings', sub: 'Organization profile, environment policies, and security architecture parameters' },
  '/appearance': { title: 'Appearance & Layout', sub: 'Personalize your SenderX workspace' },
};

/** Resolve header/breadcrumb title and subtitle metadata for a route path. */
export function getPageMeta(pathname) {
  return ROUTE_META[pathname] || {
    title: 'Dashboard',
    sub: 'Multi-tenant messaging platform',
  };
}
