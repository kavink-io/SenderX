import React, { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useAppScope } from '../../context/ScopeContext';
import ThemeToggle from '../common/ThemeToggle';
import ApiClient from '../../services/api';

export default function TopNav({ onToggleSidebar, onOpenProfile }) {
  const location = useLocation();
  const { account, isPlatformAdmin, isOrgAdmin, dashboardContext, logout } = useAuth();
  const { activeAppId, setAppScope, assignedApps, setAssignedApps } = useAppScope();
  const [showNotifs, setShowNotifs] = useState(false);

  useEffect(() => {
    async function fetchApps() {
      if (isPlatformAdmin) return;
      try {
        const res = await ApiClient.listApplications(1, 100, 'active');
        if (res?.success && Array.isArray(res.data?.items)) {
          setAssignedApps(res.data.items);
        } else if (Array.isArray(dashboardContext?.assigned_applications)) {
          setAssignedApps(dashboardContext.assigned_applications);
        }
      } catch (e) {
        console.warn('Could not load applications for scope selector:', e);
      }
    }
    fetchApps();
  }, [isPlatformAdmin, dashboardContext, setAssignedApps]);

  // Determine page title from path
  const path = location.pathname;
  let pageTitle = 'Dashboard';
  let pageSubtitle = 'Multi-tenant messaging platform';

  const routeMeta = {
    '/platform/organizations': { title: 'Platform Organizations', sub: 'Platform-wide organization management' },
    '/platform/change-requests': { title: 'Organization Change Requests', sub: 'Review, approve, or reject tenant name and slug rebranding requests' },
    '/platform/analytics': { title: 'Platform Analytics', sub: 'Cross-organization telemetry and system throughput' },
    '/platform/monitoring': { title: 'System Health', sub: 'Real-time health status of infrastructure services' },
    '/org/overview': { title: 'Overview', sub: 'Organization performance, application telemetry, and delivery metrics' },
    '/org/applications': { title: 'Connected Applications', sub: 'Register and manage external web applications, e-commerce stores, and microservices' },
    '/org/credentials': { title: 'API Credentials', sub: 'Cryptographically hashed API keys for external payload ingestion' },
    '/org/messages': { title: 'Messages', sub: 'Direct message management & outbox delivery logs' },
    '/org/templates': { title: 'Email Templates', sub: 'Multi-tenant sandboxed email templates' },
    '/org/json-requests': { title: 'Received JSON Requests', sub: 'Immutable audit log of inbound JSON payloads and routing states' },
    '/org/dlq': { title: 'Dead Letter Queue', sub: 'Unrouted or delivery-failed messages requiring inspection or manual retry' },
    '/org/analytics': { title: 'Analytics', sub: 'Comprehensive volume, delivery performance, and failure trends' },
    '/org/users': { title: 'Employees & Roles', sub: 'Manage organization members, assignments, and custom role permissions' },
    '/org/settings': { title: 'Settings', sub: 'Organization profile, environment policies, and security architecture parameters' },
  };

  if (routeMeta[path]) {
    pageTitle = routeMeta[path].title;
    pageSubtitle = routeMeta[path].sub;
  }

  const displayName = account?.name || account?.email || 'User';
  let roleLabel = 'EMPLOYEE';
  if (isPlatformAdmin) {
    roleLabel = 'SUPER_ADMIN';
  } else if (isOrgAdmin) {
    roleLabel = 'ORG_ADMIN';
  } else if (account?.roles && account.roles.length > 0) {
    roleLabel = account.roles[0].name || account.roles[0].role_id;
  }

  const orgName = isPlatformAdmin ? 'Platform' : (dashboardContext?.organization?.name || 'Organization');

  return (
    <header className="content-header top-nav">
      <div className="top-nav-left">
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <button
            id="btn-sidebar-toggle"
            className="icon-btn sidebar-toggle-btn"
            onClick={onToggleSidebar}
            title="Toggle navigation sidebar"
            aria-label="Toggle navigation sidebar"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="3" y1="12" x2="21" y2="12"></line>
              <line x1="3" y1="6" x2="21" y2="6"></line>
              <line x1="3" y1="18" x2="21" y2="18"></line>
            </svg>
          </button>
          <div className="breadcrumb-nav" id="breadcrumb-container">
            <span>SenderX</span>
            <span className="separator">/</span>
            <span id="breadcrumb-org-name">{orgName}</span>
            <span className="separator">/</span>
            <span className="current" id="breadcrumb-current-tab">{pageTitle}</span>
          </div>
        </div>
        <div className="page-title-row">
          <h2 id="page-title">{pageTitle}</h2>
        </div>
        <p className="subtitle" id="page-subtitle" style={{ margin: 0 }}>
          {pageSubtitle}
        </p>
      </div>

      <div className="top-nav-right">
        {/* Application Scope Selector */}
        {!isPlatformAdmin && (
          <div className="app-scope-selector-box" id="header-scope-box">
            <label htmlFor="header-scope-select" className="scope-label" title="Filter resources by Connected Application">
              Scope:
            </label>
            <select
              id="header-scope-select"
              className="scope-select"
              value={activeAppId || ''}
              onChange={(e) => setAppScope(e.target.value || null)}
            >
              {isOrgAdmin && <option value="">Global (All Applications)</option>}
              {assignedApps.map((app) => (
                <option key={app.application_id || app._id} value={app.application_id || app._id}>
                  {app.name || app.application_id}
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Environment Indicator */}
        <div
          id="header-env-indicator"
          className="env-indicator env-live"
          title="Current deployment environment"
        >
          <span className="env-dot"></span>
          <span>{isPlatformAdmin ? 'Platform Console' : 'Live'}</span>
        </div>

        {/* Theme Toggle */}
        <ThemeToggle />

        {/* Notification Bell */}
        <div style={{ position: 'relative' }}>
          <button
            id="btn-notifications"
            className="icon-btn"
            onClick={() => setShowNotifs((prev) => !prev)}
            title="Notifications"
            aria-label="View notifications"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"></path>
              <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"></path>
            </svg>
          </button>
          {showNotifs && (
            <div id="notification-menu" className="notification-menu open">
              <div className="notification-header">
                <span className="notif-title">Notifications</span>
                <span className="badge badge-success">Live</span>
              </div>
              <div className="notification-list">
                <div className="notif-item">
                  <div className="notif-text">System is running normally. All services operational.</div>
                  <div className="notif-time">Just now</div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* User Profile Pill */}
        <div
          id="user-profile-pill"
          className="user-profile-pill"
          onClick={onOpenProfile}
          title="Click to view and edit profile"
          role="button"
          tabIndex={0}
        >
          <div className="avatar-circle" id="user-avatar-initial">
            {(displayName.charAt(0) || 'U').toUpperCase()}
          </div>
          <div className="user-details-box">
            <span className="user-email" id="header-user-email">{account?.email}</span>
            <div className="user-tags">
              <span className="user-role badge-primary" id="header-user-role">{roleLabel}</span>
              {account?.employee_code && (
                <span className="badge badge-code" id="header-user-emp-code">
                  {account.employee_code}
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Logout Button in Header */}
        <button
          id="btn-header-logout"
          className="icon-btn logout-header-btn"
          onClick={logout}
          title="Sign Out"
          aria-label="Sign out"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
            <polyline points="16 17 21 12 16 7"/>
            <line x1="21" y1="12" x2="9" y2="12"/>
          </svg>
        </button>
      </div>
    </header>
  );
}
