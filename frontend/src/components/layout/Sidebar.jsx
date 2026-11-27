import React from 'react';
import { NavLink } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { getNavigationLabel, PLATFORM_NAVIGATION, ORG_NAVIGATION } from '../../utils/navigation';
import { GlassSidebar } from '../glass';

export default function Sidebar({ isOpen, onClose, onToggle }) {
  const { isPlatformAdmin, isOrgAdmin, allowedTabs, hasPermission } = useAuth();

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

  const sections = isPlatformAdmin
    ? [
        { title: 'Manage', ids: ['platform-organizations'] },
        { title: 'Insights', ids: ['platform-analytics'] },
        { title: 'Platform', ids: ['platform-monitoring', 'platform-change-requests'] },
      ]
    : [
        { title: 'Manage', ids: ['menu-overview', 'menu-messages', 'menu-templates'] },
        { title: 'Insights', ids: ['menu-analytics'] },
        { title: 'Manage Accounts', ids: ['menu-applications', 'menu-credentials', 'menu-users'] },
        { title: 'Channel Configurations', ids: ['menu-channel-configurations'] },
        { title: 'Tools', ids: ['menu-json-requests', 'menu-dlq'] },
      ];

  return (
    <GlassSidebar className={isOpen ? 'sidebar-open mobile-open' : 'sidebar-closed'}>
      <div className="sidebar-header">
        <div className="sidebar-brand">
          <svg className="saas-brand-mark" width="27" height="27" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M21.2 3.2 3.6 10.1c-1.1.4-1.1 2 0 2.4l6.3 2.1 2.1 6.3c.4 1.1 2 1.1 2.4 0l6.9-17.6c.4-1-.9-2.3-2.1-2.1Z" fill="currentColor" />
            <path d="m9.9 14.6 6.5-6.5" stroke="white" strokeWidth="1.7" strokeLinecap="round" />
          </svg>
          <span className="brand-title">SenderX</span>
        </div>
        <button
          id="btn-sidebar-toggle"
          className="icon-btn sidebar-toggle-btn"
          onClick={onToggle || onClose}
          title="Toggle navigation sidebar"
          aria-label="Toggle navigation sidebar"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <rect x="3" y="4" width="18" height="16" rx="2" />
            <path d="M9 4v16" />
          </svg>
        </button>
      </div>

      <nav className="sidebar-nav">
        {sections.map((section) => {
          const items = section.ids
            .map((id) => navItems.find((item) => item.id === id))
            .filter(Boolean);
          if (!items.length) return null;
          return (
            <div className="nav-section" key={section.title}>
              <div className="nav-category">{section.title}</div>
              {items.map((item) => (
              <NavLink
                key={item.id}
                to={item.path}
                className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
                onClick={handleNavClick}
                title={getNavigationLabel(item)}
              >
                <span className="nav-icon">{item.icon}</span>
                <span>{getNavigationLabel(item)}</span>
              </NavLink>
              ))}
            </div>
          );
        })}
      </nav>
    </GlassSidebar>
  );
}
