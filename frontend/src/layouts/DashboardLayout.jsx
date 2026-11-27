import React, { useState, useEffect } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import Sidebar from '../components/layout/Sidebar';
import TopNav from '../components/layout/TopNav';
import MobileBackdrop from '../components/layout/MobileBackdrop';
import UserProfileModal from '../components/modals/UserProfileModal';
import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/ThemeContext';

export default function DashboardLayout() {
  const location = useLocation();
  const { isPlatformAdmin } = useAuth();
  const { preferences, updatePreferences } = useTheme();
  const [isDesktop, setIsDesktop] = useState(() => {
    return typeof window !== 'undefined' ? window.innerWidth > 1024 : true;
  });
  const [isSidebarOpen, setIsSidebarOpen] = useState(() =>
    preferences.sidebarMode !== 'collapsed' && preferences.navigationLayout !== 'horizontal'
  );
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

  useEffect(() => {
    if (preferences.navigationLayout === 'horizontal') {
      setIsSidebarOpen(false);
    } else if (!preferences.sidebarCollapsible) {
      setIsSidebarOpen(true);
    } else if (preferences.sidebarMode === 'expanded') {
      setIsSidebarOpen(true);
    } else if (preferences.sidebarMode === 'collapsed') {
      setIsSidebarOpen(false);
    }
  }, [preferences.navigationLayout, preferences.sidebarMode]);

  const handleToggleSidebar = () => {
    if (isDesktop) {
      if (!preferences.sidebarCollapsible) return;
      const nextOpen = !isSidebarOpen;
      setIsSidebarOpen(nextOpen);
      updatePreferences({ sidebarMode: nextOpen ? 'expanded' : 'collapsed' });
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
          <div key={location.pathname} className="lg-page-transition">
            <Outlet />
          </div>
        </main>
      </div>

      <UserProfileModal
        isOpen={isProfileModalOpen}
        onClose={() => setIsProfileModalOpen(false)}
      />
    </div>
  );
}
