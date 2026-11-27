import React, { useEffect, useMemo, useRef, useState } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useAppScope } from '../../context/ScopeContext';
import { useTheme } from '../../context/ThemeContext';
import ThemeToggle from '../common/ThemeToggle';
import ApiClient from '../../services/api';
import { getNavigationLabel, PLATFORM_NAVIGATION, ORG_NAVIGATION, getPageMeta } from '../../utils/navigation';
import { GlassNavbar, GlassDropdown, GlassSelect } from '../glass';

function SearchIcon() {
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-4-4" />
    </svg>
  );
}

function ChevronIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="m9 18 6-6-6-6" />
    </svg>
  );
}

export default function TopNav({ isSidebarOpen = true, onToggleSidebar, onOpenProfile }) {
  const location = useLocation();
  const navigate = useNavigate();
  const searchRef = useRef(null);
  const { account, isPlatformAdmin, isOrgAdmin, dashboardContext, logout, hasPermission } = useAuth();
  const { activeAppId, setAppScope, assignedApps, setAssignedApps } = useAppScope();
  const { preferences, updatePreferences } = useTheme();
  const [query, setQuery] = useState('');
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [isNotifsOpen, setIsNotifsOpen] = useState(false);
  const [notificationItems, setNotificationItems] = useState([]);
  const [readNotificationIds, setReadNotificationIds] = useState([]);
  const [notificationFilter, setNotificationFilter] = useState('all');
  const [isProfileOpen, setIsProfileOpen] = useState(false);

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
      } catch (error) {
        console.warn('Could not load applications for scope selector:', error);
      }
    }
    fetchApps();
  }, [isPlatformAdmin, dashboardContext, setAssignedApps]);

  useEffect(() => {
    let active = true;
    async function fetchRecentMessages() {
      if (isPlatformAdmin || !hasPermission('organization:messages:read')) {
        setNotificationItems([]);
        return;
      }
      try {
        const response = await ApiClient.listMessages(1, 10, { application_id: activeAppId || undefined });
        if (!active) return;
        if (response?.success) {
          const data = response.data;
          const items = Array.isArray(data) ? data : (data?.items || response.items || []);
          setNotificationItems(items);
        } else {
          setNotificationItems([]);
          console.warn('Could not load recent message notifications:', response?.message || 'Request was unsuccessful');
        }
      } catch (error) {
        if (active) {
          setNotificationItems([]);
          console.warn('Could not load recent message notifications:', error);
        }
      }
    }
    fetchRecentMessages();
    return () => { active = false; };
  }, [activeAppId, hasPermission, isPlatformAdmin]);

  useEffect(() => {
    const handleShortcut = (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        searchRef.current?.focus();
        setIsSearchOpen(true);
      }
    };
    window.addEventListener('keydown', handleShortcut);
    return () => window.removeEventListener('keydown', handleShortcut);
  }, []);

  const pageTitle = getPageMeta(location.pathname).title;
  const orgName = isPlatformAdmin ? 'Platform' : (dashboardContext?.organization?.name || 'Organization');
  const displayName = account?.name || account?.email || 'User';
  const roleLabel = isPlatformAdmin
    ? 'Platform Admin'
    : isOrgAdmin
      ? 'Organization Admin'
      : (account?.roles?.[0]?.name || account?.roles?.[0]?.role_id || 'Employee');
  const initials = displayName.split(/\s+/).map((part) => part[0]).join('').slice(0, 2).toUpperCase();

  const searchItems = useMemo(() => {
    const source = isPlatformAdmin ? PLATFORM_NAVIGATION : ORG_NAVIGATION;
    return source
      .filter((item) => isPlatformAdmin || !item.requiredPermission || hasPermission(item.requiredPermission))
      .map((item) => ({
        ...item,
        name: getNavigationLabel(item),
        group: item.name.includes('Message') || item.name.includes('Template') || item.name === 'Overview'
          ? 'Workspace'
          : item.name.includes('Analytic')
            ? 'Insights'
            : 'Management',
      }))
      .concat([{ id: 'appearance-settings', name: 'Appearance & Layout', path: '/appearance', group: 'Preferences' }]);
  }, [hasPermission, isPlatformAdmin]);
  const matchingItems = searchItems.filter((item) => item.name.toLowerCase().includes(query.trim().toLowerCase()));
  const groupedItems = matchingItems.reduce((groups, item) => {
    groups[item.group] = [...(groups[item.group] || []), item];
    return groups;
  }, {});
  const visibleNotifications = notificationFilter === 'unread'
    ? notificationItems.filter((item) => !readNotificationIds.includes(item.message_id || item._id))
    : notificationItems;
  const notificationGroups = visibleNotifications.reduce((groups, item) => {
    const rawDate = item.created_at || item.updated_at;
    const date = rawDate ? new Date(rawDate) : null;
    const label = !date || Number.isNaN(date.getTime())
      ? 'Recent'
      : date.toDateString() === new Date().toDateString() ? 'Today' : 'Earlier';
    groups[label] = [...(groups[label] || []), item];
    return groups;
  }, {});

  const { title: breadcrumbTitle } = getPageMeta(location.pathname);
  const toggleDirection = () => updatePreferences({ direction: preferences.direction === 'rtl' ? 'ltr' : 'rtl' });

  return (
    <GlassNavbar className="saas-header">
      <div className="saas-header-left">
        {!isSidebarOpen && (
          <button
            id="btn-sidebar-reopen"
            className="icon-btn sidebar-toggle-btn saas-sidebar-reopen"
            onClick={onToggleSidebar}
            title="Open navigation sidebar"
            aria-label="Open navigation sidebar"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <rect x="3" y="4" width="18" height="16" rx="2" />
              <path d="M9 4v16" />
            </svg>
          </button>
        )}
        <nav className="saas-breadcrumb" aria-label="Breadcrumb">
          <span>SenderX</span>
          <ChevronIcon />
          <span>{orgName}</span>
          <ChevronIcon />
          <span className="current">{breadcrumbTitle}</span>
        </nav>
      </div>

      <nav className="saas-horizontal-nav" aria-label="Primary navigation">
        {searchItems.filter((item) => item.id !== 'appearance-settings').map((item) => (
          <NavLink key={item.id} to={item.path} title={item.name}>
            {item.name}
          </NavLink>
        ))}
      </nav>

      <div className="saas-header-actions">
        <GlassDropdown
          isOpen={isSearchOpen}
          onClose={() => setIsSearchOpen(false)}
          menuStyle={{ width: 360, maxWidth: 'min(360px, calc(100vw - 24px))', padding: 8 }}
          trigger={
            <label className="saas-search">
              <SearchIcon />
              <input
                ref={searchRef}
                value={query}
                onChange={(event) => { setQuery(event.target.value); setIsSearchOpen(true); }}
                onFocus={() => setIsSearchOpen(true)}
                placeholder="Search here"
                aria-label="Search navigation"
              />
              <span className="saas-search-shortcut"><kbd>Ctrl</kbd><kbd>+</kbd><kbd>K</kbd></span>
            </label>
          }
        >
          {!isPlatformAdmin && (
            <div className="saas-search-scope-mobile">
              <span>Application scope</span>
              <GlassSelect
                id="mobile-header-scope-select"
                compact
                value={activeAppId || ''}
                onChange={(event) => setAppScope(event.target.value || null)}
                aria-label="Filter resources by connected application"
              >
                {isOrgAdmin && <option value="">All Applications</option>}
                {assignedApps.map((app) => (
                  <option key={app.application_id || app._id} value={app.application_id || app._id}>
                    {app.name || app.application_id}
                  </option>
                ))}
              </GlassSelect>
            </div>
          )}
          <div className="saas-search-results">
            {Object.entries(groupedItems).length ? Object.entries(groupedItems).map(([group, items]) => (
              <section key={group} className="saas-search-group">
                <div className="saas-search-group-title">{group}</div>
                {items.map((item) => (
                  <button
                    type="button"
                    key={item.id}
                    className="saas-search-result"
                    onClick={() => {
                      setIsSearchOpen(false);
                      setQuery('');
                      navigate(item.path);
                    }}
                  >
                    {item.icon ? <span className="nav-icon">{item.icon}</span> : <span className="search-result-dot" />}
                    <span>{item.name}</span>
                  </button>
                ))}
              </section>
            )) : <div className="saas-search-empty">No matching pages</div>}
          </div>
        </GlassDropdown>

        <ThemeToggle />

        <GlassDropdown
          isOpen={isNotifsOpen}
          onClose={() => setIsNotifsOpen(false)}
          menuStyle={{ width: 320, maxWidth: 'min(320px, calc(100vw - 24px))', padding: 0 }}
          trigger={
            <button
              id="btn-notifications"
              className="icon-btn"
              onClick={() => setIsNotifsOpen((open) => !open)}
              title="Notifications"
              aria-label="View notifications"
              aria-expanded={isNotifsOpen}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" />
                <path d="M10 21h4" />
              </svg>
            </button>
          }
        >
          <div className="saas-popover-heading">
            <strong>Notifications</strong>
            <button
              type="button"
              onClick={() => setReadNotificationIds(notificationItems.map((item) => item.message_id || item._id))}
              disabled={!notificationItems.length}
            >
              Mark all as read
            </button>
          </div>
          <div className="saas-notification-filters">
            {['all', 'unread'].map((filter) => (
              <button type="button" key={filter} className={notificationFilter === filter ? 'active' : ''} onClick={() => setNotificationFilter(filter)}>
                {filter === 'all' ? 'All' : 'Unread'}
              </button>
            ))}
          </div>
          {Object.keys(notificationGroups).length ? (
            <div className="saas-notification-list">
              {Object.entries(notificationGroups).map(([group, items]) => (
                <section key={group}>
                  <h4>{group}</h4>
                  {items.map((item) => {
                    const id = item.message_id || item._id;
                    const isRead = readNotificationIds.includes(id);
                    return (
                      <button type="button" className={`saas-notification-row ${isRead ? 'is-read' : ''}`} key={id} onClick={() => setReadNotificationIds((current) => current.includes(id) ? current : [...current, id])}>
                        <span className="saas-notification-icon" aria-hidden="true">↗</span>
                        <span>
                          <strong>{item.status || 'Message'} · {item.channel || 'Delivery'}</strong>
                          <small>{item.recipient || item.to || 'Message activity'}</small>
                          {(item.updated_at || item.created_at) && (
                            <time>{new Date(item.updated_at || item.created_at).toLocaleString()}</time>
                          )}
                        </span>
                      </button>
                    );
                  })}
                </section>
              ))}
            </div>
          ) : (
            <div className="saas-notification-empty">
              <span className="saas-notification-icon" aria-hidden="true">✓</span>
              <strong>{notificationFilter === 'unread' ? 'No unread messages' : 'No recent messages'}</strong>
              <span>Message activity will appear here when available.</span>
            </div>
          )}
          <div className="saas-popover-footer">
            <button type="button" onClick={() => { setNotificationItems([]); setReadNotificationIds([]); }} disabled={!notificationItems.length}>Clear all</button>
          </div>
        </GlassDropdown>

        <GlassDropdown
          isOpen={isProfileOpen}
          onClose={() => setIsProfileOpen(false)}
          menuStyle={{ width: 232, padding: 8 }}
          trigger={
            <button
              id="user-profile-pill"
              type="button"
              className="saas-profile-trigger"
              onClick={() => setIsProfileOpen((open) => !open)}
              aria-expanded={isProfileOpen}
              aria-label="Account menu"
            >
              <span className="saas-avatar">{initials}</span>
              <span className="saas-profile-name">
                <strong>{displayName}</strong>
                <small>{roleLabel}</small>
              </span>
            </button>
          }
        >
          <button type="button" className="saas-profile-card" onClick={() => { setIsProfileOpen(false); onOpenProfile(); }}>
            <span className="saas-avatar saas-avatar-large">{initials}</span>
            <strong>{displayName}</strong>
            <small>{roleLabel}</small>
          </button>
          <div className="lg-dropdown-divider" />
          <button type="button" className="lg-dropdown-item saas-rtl-setting" onClick={toggleDirection}>
            <span className="saas-menu-glyph" aria-hidden="true">¶</span>
            <span>RTL</span>
            <span className={`saas-switch ${preferences.direction === 'rtl' ? 'is-on' : ''}`} aria-hidden="true"><i /></span>
          </button>
          <div className="lg-dropdown-item saas-language-setting" aria-label="Language: English">
            <span className="saas-menu-glyph" aria-hidden="true">文</span>
            <span>Language</span>
            <span className="saas-menu-value">Eng&nbsp; ›</span>
          </div>
          <button type="button" className="lg-dropdown-item" onClick={() => { setIsProfileOpen(false); navigate('/appearance'); }}>
            <span className="saas-menu-glyph" aria-hidden="true">⚙</span>
            <span>Settings</span>
          </button>
          <div className="lg-dropdown-divider" />
          <button
            type="button"
            className="saas-logout-button"
            onClick={() => { setIsProfileOpen(false); logout(); }}
          >
            Logout
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
              <path d="m16 17 5-5-5-5M21 12H9" />
            </svg>
          </button>
        </GlassDropdown>
      </div>
    </GlassNavbar>
  );
}
