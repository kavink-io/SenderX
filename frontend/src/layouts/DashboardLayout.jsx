import React, { useState, useEffect } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import Sidebar from '../components/layout/Sidebar';
import TopNav from '../components/layout/TopNav';
import MobileBackdrop from '../components/layout/MobileBackdrop';
import UserProfileModal from '../components/modals/UserProfileModal';
import { useAuth } from '../context/AuthContext';
import { getPageMeta } from '../utils/navigation';

export default function DashboardLayout() {
  const location = useLocation();
  const { isPlatformAdmin, dashboardContext } = useAuth();
  const { title: pageTitle } = getPageMeta(location.pathname);
  const orgName = isPlatformAdmin ? 'Platform' : (dashboardContext?.organization?.name || 'Organization');
  const [isDesktop, setIsDesktop] = useState(() => {
    return typeof window !== 'undefined' ? window.innerWidth > 1024 : true;
  });
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [isMobileDrawerOpen, setIsMobileDrawerOpen] = useState(false);
  const [isProfileModalOpen, setIsProfileModalOpen] = useState(false);

  useEffect(() => {
    const handleResize = () => {
      const desktop = window.innerWidth > 1024;
      setIsDesktop(desktop);
      if (desktop) {
        setIsMobileDrawerOpen(false);
      }
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const handleToggleSidebar = () => {
    if (isDesktop) {
      setIsSidebarOpen((prev) => !prev);
    } else {
      setIsMobileDrawerOpen((prev) => !prev);
    }
  };

  const handleCloseMobileDrawer = () => {
    setIsMobileDrawerOpen(false);
  };

  return (
    <div className="app-container" id="app-shell">
      <Sidebar
        isOpen={isDesktop ? isSidebarOpen : isMobileDrawerOpen}
        onClose={handleCloseMobileDrawer}
        onToggle={handleToggleSidebar}
        onOpenProfile={() => setIsProfileModalOpen(true)}
      />
      {!isDesktop && (
        <MobileBackdrop
          isOpen={isMobileDrawerOpen}
          onClose={handleCloseMobileDrawer}
        />
      )}
      <div className={`main-content-wrapper ${isSidebarOpen ? 'sidebar-open' : 'sidebar-collapsed'}`}>
        <TopNav
          isSidebarOpen={isDesktop ? isSidebarOpen : isMobileDrawerOpen}
          onToggleSidebar={handleToggleSidebar}
          onOpenProfile={() => setIsProfileModalOpen(true)}
        />
        <main className="page-container">
          <nav className="breadcrumb-nav page-body-breadcrumb" id="breadcrumb-container" aria-label="Breadcrumb">
            <span>SenderX</span>
            <span className="separator">/</span>
            <span id="breadcrumb-org-name">{orgName}</span>
            <span className="separator">/</span>
            <span className="current" id="breadcrumb-current-tab">{pageTitle}</span>
          </nav>
          <Outlet />
        </main>
      </div>

      <UserProfileModal
        isOpen={isProfileModalOpen}
        onClose={() => setIsProfileModalOpen(false)}
      />
    </div>
  );
}
