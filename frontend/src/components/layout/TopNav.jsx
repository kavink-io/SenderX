import React, { useState, useEffect, useMemo, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useAppScope } from '../../context/ScopeContext';
import ThemeToggle from '../common/ThemeToggle';
import ApiClient from '../../services/api';
import { getPageMeta, PLATFORM_NAVIGATION, ORG_NAVIGATION } from '../../utils/navigation';
import { GlassNavbar, GlassSearch, GlassDropdown, GlassSelect } from '../glass';

export default function TopNav({ isSidebarOpen = true, onToggleSidebar, onOpenProfile }) {
  const location = useLocation();
  const navigate = useNavigate();
  const { account, isPlatformAdmin, isOrgAdmin, allowedTabs, hasPermission, dashboardContext, logout } = useAuth();
  const { activeAppId, setAppScope, assignedApps, setAssignedApps } = useAppScope();

  const [showNotifs, setShowNotifs] = useState(false);
  const [hasUnreadNotifs, setHasUnreadNotifs] = useState(true);
  const [showProfileMenu, setShowProfileMenu] = useState(false);
  const [globalQuery, setGlobalQuery] = useState('');
  const [showSearchMenu, setShowSearchMenu] = useState(false);
  const searchInputRef = useRef(null);

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

  useEffect(() => {
    const handleShortcut = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        searchInputRef.current?.focus();
        setShowSearchMenu(true);
      }
    };
    window.addEventListener('keydown', handleShortcut);
    return () => window.removeEventListener('keydown', handleShortcut);
  }, []);

  const searchableItems = useMemo(() => {
    const base = isPlatformAdmin
      ? PLATFORM_NAVIGATION
      : ORG_NAVIGATION.filter((item) => {
          if (!isOrgAdmin && allowedTabs.size > 0 && !allowedTabs.has(item.tabId)) return false;
          if (item.requiredPermission && !hasPermission(item.requiredPermission)) return false;
          return true;
        });

    const q = globalQuery.trim().toLowerCase();
    if (!q) return base;
    return base.filter(
      (item) => item.name.toLowerCase().includes(q) || item.path.toLowerCase().includes(q)
    );
  }, [isPlatformAdmin, isOrgAdmin, allowedTabs, hasPermission, globalQuery]);

  const { title: pageTitle, sub: pageSubtitle } = getPageMeta(location.pathname);

  const handleNavigateSearch = (path) => {
    navigate(path);
    setGlobalQuery('');
    setShowSearchMenu(false);
  };

  return (
    <GlassNavbar>
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
        {/* Global Quick-Jump Search */}
        <div className="lg-global-search-wrap">
          <GlassDropdown
            isOpen={showSearchMenu && searchableItems.length > 0}
            onClose={() => setShowSearchMenu(false)}
            align="left"
            menuStyle={{ width: '260px' }}
            trigger={
              <GlassSearch
                inputRef={searchInputRef}
                id="global-nav-search"
                value={globalQuery}
                onFocus={() => setShowSearchMenu(true)}
                onChange={(e) => {
                  setGlobalQuery(e.target.value);
                  setShowSearchMenu(true);
                }}
                onClear={() => setGlobalQuery('')}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && searchableItems.length > 0) {
                    e.preventDefault();
                    handleNavigateSearch(searchableItems[0].path);
                  }
                }}
                placeholder="Jump to page..."
                shortcutHint="Ctrl K"
                aria-label="Jump to page"
              />
            }
          >
            <div style={{ padding: '4px 8px 6px', fontSize: '0.68rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-muted)' }}>
              Quick Navigation
            </div>
            {searchableItems.map((item) => (
              <button
                key={item.id}
                type="button"
                className="lg-dropdown-item"
                onClick={() => handleNavigateSearch(item.path)}
              >
                <span className="nav-icon" style={{ display: 'inline-flex' }}>{item.icon}</span>
                <span>{item.name}</span>
              </button>
            ))}
          </GlassDropdown>
        </div>

        {/* Application Scope Selector */}
        {!isPlatformAdmin && (
          <div className="app-scope-selector-box" id="header-scope-box">
            <label htmlFor="header-scope-select" className="scope-label" title="Filter resources by Connected Application">
              Scope:
            </label>
            <GlassSelect
              id="header-scope-select"
              compact
              value={activeAppId || ''}
              onChange={(e) => setAppScope(e.target.value || null)}
              aria-label="Filter resources by Connected Application"
            >
              {isOrgAdmin && <option value="">Global (All Applications)</option>}
              {assignedApps.map((app) => (
                <option key={app.application_id || app._id} value={app.application_id || app._id}>
                  {app.name || app.application_id}
                </option>
              ))}
            </GlassSelect>
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

        {/* Notification Bell Dropdown */}
        <GlassDropdown
          isOpen={showNotifs}
          onClose={() => setShowNotifs(false)}
          menuStyle={{ width: '300px', padding: '12px' }}
          trigger={
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
              {hasUnreadNotifs && <span className="notification-badge-dot" />}
            </button>
          }
        >
          <div className="notification-header">
            <span className="notif-title">Notifications</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {hasUnreadNotifs && (
                <button
                  type="button"
                  onClick={() => setHasUnreadNotifs(false)}
                  style={{ background: 'none', border: 'none', color: 'var(--accent-blue)', fontSize: '0.72rem', fontWeight: 600, cursor: 'pointer' }}
                >
                  Mark read
                </button>
              )}
              <span className="badge badge-success">Live</span>
            </div>
          </div>
          <div className="notification-list">
            <div className="notification-item">
              <div className="notif-text">System is running normally. All services operational.</div>
              <div className="notif-time">Just now</div>
            </div>
          </div>
        </GlassDropdown>

        {/* User Profile Pill & Dropdown */}
        <GlassDropdown
          isOpen={showProfileMenu}
          onClose={() => setShowProfileMenu(false)}
          menuStyle={{ minWidth: '215px' }}
          trigger={
            <div
              id="user-profile-pill"
              className="user-profile-pill"
              onClick={() => setShowProfileMenu((prev) => !prev)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  setShowProfileMenu((prev) => !prev);
                }
              }}
              title="Account menu"
              role="button"
              tabIndex={0}
              aria-expanded={showProfileMenu}
            >
              <span className="user-email" id="header-user-email">
                {account?.email || 'User'}
              </span>
            </div>
          }
        >
          <button
            type="button"
            className="lg-dropdown-item"
            onClick={() => {
              setShowProfileMenu(false);
              onOpenProfile();
            }}
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
              <circle cx="12" cy="7" r="4" />
            </svg>
            <span>Profile &amp; Security</span>
          </button>
          <div className="lg-dropdown-divider" />
          <button
            type="button"
            className="lg-dropdown-item is-danger"
            onClick={() => {
              setShowProfileMenu(false);
              logout();
            }}
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
              <polyline points="16 17 21 12 16 7" />
              <line x1="21" y1="12" x2="9" y2="12" />
            </svg>
            <span>Sign Out</span>
          </button>
        </GlassDropdown>

        {/* Quick Logout Button in Header */}
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
    </GlassNavbar>
  );
}
