import React from 'react';
import { NavLink } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { PLATFORM_NAVIGATION, ORG_NAVIGATION } from '../../utils/navigation';

export default function Sidebar({ isOpen, onClose, onToggle, onOpenProfile }) {
  const { account, isPlatformAdmin, isOrgAdmin, allowedTabs, hasPermission, dashboardContext } = useAuth();

  const handleNavClick = () => {
    if (window.innerWidth <= 1024) {
      onClose();
    }
  };

  const navItems = isPlatformAdmin
    ? PLATFORM_NAVIGATION
    : ORG_NAVIGATION.filter((item) => {
        if (!isOrgAdmin && allowedTabs.size > 0 && !allowedTabs.has(item.tabId)) {
          return false;
        }
        if (item.requiredPermission && !hasPermission(item.requiredPermission)) {
          return false;
        }
        return true;
      });

  const displayName = account?.name || account?.email || 'User';
  let roleLabel = 'EMPLOYEE';
  if (isPlatformAdmin) {
    roleLabel = 'PLATFORM_ADMIN';
  } else if (isOrgAdmin) {
    roleLabel = 'ORG_ADMIN';
  } else if (account?.roles && account.roles.length > 0) {
    roleLabel = account.roles[0].name || account.roles[0].role_id;
  }

  return (
    <aside className={`sidebar ${isOpen ? 'sidebar-open mobile-open' : 'sidebar-closed'}`}>
      <div className="sidebar-header">
        <div className="sidebar-brand">
          <div className="brand-logo sm">SX</div>
          <span className="brand-title">SenderX</span>
        </div>
        <button
          id="btn-sidebar-toggle"
          className="icon-btn sidebar-toggle-btn"
          onClick={onToggle || onClose}
          title="Toggle navigation sidebar"
          aria-label="Toggle navigation sidebar"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="3" y1="12" x2="21" y2="12"></line>
            <line x1="3" y1="6" x2="21" y2="6"></line>
            <line x1="3" y1="18" x2="21" y2="18"></line>
          </svg>
        </button>
      </div>

      <nav className="sidebar-nav">
        <div className="nav-section">
          <div id="nav-org-items">
            {navItems.map((item) => (
              <NavLink
                key={item.id}
                to={item.path}
                className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
                onClick={handleNavClick}
              >
                <span className="nav-icon">{item.icon}</span>
                <span>{item.name}</span>
              </NavLink>
            ))}
          </div>
        </div>
      </nav>

      {/* Tenant info & user footer */}
      <div className="sidebar-footer">
        {!isPlatformAdmin && dashboardContext?.organization && (
          <div className="tenant-badge-container" style={{ padding: '0 0.5rem 0.75rem' }}>
            <span className="tenant-badge" title={dashboardContext.organization.name}>
              {dashboardContext.organization.name || 'Organization'}
            </span>
          </div>
        )}
        <div
          className="user-profile-summary"
          onClick={onOpenProfile}
          style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}
          title="View profile"
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0 }}>
            <div className="avatar-circle">
              {(displayName.charAt(0) || 'U').toUpperCase()}
            </div>
            <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              <div id="current-account-name" style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                {displayName}
              </div>
              <div id="current-account-type" style={{ fontSize: '0.75rem', color: 'var(--text-primary)' }}>
                {roleLabel}
              </div>
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}
