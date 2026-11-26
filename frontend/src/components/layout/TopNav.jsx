import React, { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useAppScope } from '../../context/ScopeContext';
import ThemeToggle from '../common/ThemeToggle';
import ApiClient from '../../services/api';
import { getPageMeta } from '../../utils/navigation';

export default function TopNav({ isSidebarOpen = true, onToggleSidebar, onOpenProfile }) {
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
  const { title: pageTitle, sub: pageSubtitle } = getPageMeta(location.pathname);

  return (
    <header className="content-header top-nav">
      <div className="top-nav-left">
        <div className="page-title-row">
          {!isSidebarOpen && (
            <button
              id="btn-sidebar-reopen"
              className="icon-btn sidebar-toggle-btn"
              onClick={onToggleSidebar}
              title="Open navigation sidebar"
              aria-label="Open navigation sidebar"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="3" y1="12" x2="21" y2="12"></line>
                <line x1="3" y1="6" x2="21" y2="6"></line>
                <line x1="3" y1="18" x2="21" y2="18"></line>
              </svg>
            </button>
          )}
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
          <span className="user-email" id="header-user-email">
            {account?.email || 'User'}
          </span>
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
