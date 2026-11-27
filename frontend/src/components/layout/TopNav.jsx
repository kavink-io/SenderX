import React, { useEffect, useMemo, useState, lazy, Suspense } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useTheme } from '../../context/ThemeContext';
import ThemeToggle from '../common/ThemeToggle';
import OffCanvasPanel from '../common/OffCanvasPanel';
import ProfessionalAvatar from '../common/ProfessionalAvatar';
import PageLoader from '../common/PageLoader';
import ApiClient from '../../services/api';
import { getNavigationLabel, PLATFORM_NAVIGATION, ORG_NAVIGATION, getPageMeta } from '../../utils/navigation';
import { GlassNavbar, GlassDropdown } from '../glass';

const OrgSettings = lazy(() => import('../../pages/settings/OrgSettings'));
const AppearanceSettings = lazy(() => import('../settings/AppearanceSettings'));

function ChevronIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="m9 18 6-6-6-6" />
    </svg>
  );
}

export default function TopNav({ isSidebarOpen = true, onToggleSidebar, onOpenProfile }) {
  const location = useLocation();
  const { account, isPlatformAdmin, isOrgAdmin, dashboardContext, logout, hasPermission } = useAuth();
  const { preferences, updatePreferences } = useTheme();
  const [isNotifsOpen, setIsNotifsOpen] = useState(false);
  const [notificationItems, setNotificationItems] = useState([]);
  const [readNotificationIds, setReadNotificationIds] = useState([]);
  const [notificationFilter, setNotificationFilter] = useState('all');
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [settingsTab, setSettingsTab] = useState('IDENTITY');

  useEffect(() => {
    let active = true;
    async function fetchRecentMessages() {
      if (isPlatformAdmin || !hasPermission('organization:messages:read')) {
        setNotificationItems([]);
        return;
      }
      try {
        const response = await ApiClient.listMessages(1, 10);
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
  }, [hasPermission, isPlatformAdmin]);

  const orgName = isPlatformAdmin ? 'Platform' : (dashboardContext?.organization?.name || 'Organization');
  const displayName = account?.name || account?.email || 'User';
  const avatarEmployee = account || dashboardContext || {};
  const roleLabel = isPlatformAdmin
    ? 'Platform Admin'
    : isOrgAdmin
      ? 'Organization Admin'
      : (account?.roles?.[0]?.name || account?.roles?.[0]?.role_id || 'Employee');

  const navItems = useMemo(() => {
    const source = isPlatformAdmin ? PLATFORM_NAVIGATION : ORG_NAVIGATION;
    return source
      .filter((item) => isPlatformAdmin || !item.requiredPermission || hasPermission(item.requiredPermission))
      .map((item) => ({
        ...item,
        name: getNavigationLabel(item),
      }));
  }, [hasPermission, isPlatformAdmin]);
  const canManageOrgSettings = !isPlatformAdmin && hasPermission('organization:configuration:manage');
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
  const openSettings = (tab = 'IDENTITY') => {
    setSettingsTab(tab);
    setIsSettingsOpen(true);
  };

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
        {navItems.map((item) => (
          <NavLink key={item.id} to={item.path} title={item.name}>
            {item.name}
          </NavLink>
        ))}
      </nav>

      <div className="saas-header-actions">
        <ThemeToggle />

        <button
          type="button"
          className="icon-btn saas-settings-button"
          title="Settings"
          aria-label="Settings"
          onClick={() => openSettings(canManageOrgSettings ? 'IDENTITY' : 'APPEARANCE')}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
            <circle cx="12" cy="12" r="3" />
          </svg>
        </button>

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
              <ProfessionalAvatar
                employee={avatarEmployee}
                name={displayName}
                size={34}
                className="saas-avatar"
              />
              <span className="saas-profile-name">
                <strong>{displayName}</strong>
                <small>{roleLabel}</small>
              </span>
            </button>
          }
        >
          <button type="button" className="saas-profile-card" onClick={() => { setIsProfileOpen(false); onOpenProfile(); }}>
            <ProfessionalAvatar
              employee={avatarEmployee}
              name={displayName}
              size={48}
              className="saas-avatar saas-avatar-large"
            />
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
          <button type="button" className="lg-dropdown-item" onClick={() => { setIsProfileOpen(false); openSettings('APPEARANCE'); }}>
            <span className="saas-menu-glyph" aria-hidden="true">⚙</span>
            <span>Appearance &amp; Layout</span>
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
      <OffCanvasPanel
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        title={canManageOrgSettings ? 'Settings' : 'Appearance & Layout'}
        description={canManageOrgSettings
          ? 'Organization configuration and workspace appearance.'
          : 'Personalize your SenderX workspace.'}
        size="large"
        id="settings-offcanvas"
      >
        {isSettingsOpen && (
          <Suspense fallback={<PageLoader compact label="Loading settings..." />}>
            {canManageOrgSettings ? (
              <OrgSettings initialTab={settingsTab} inPanel />
            ) : (
              <AppearanceSettings />
            )}
          </Suspense>
        )}
      </OffCanvasPanel>
    </GlassNavbar>
  );
}
