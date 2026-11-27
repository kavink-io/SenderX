import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import ProtectedRoute from './ProtectedRoute';
import DashboardLayout from '../layouts/DashboardLayout';

// Auth & Common
import AuthPage from '../pages/auth/AuthPage';
import AccessDenied from '../pages/common/AccessDenied';

// Super Admin
import PlatformOrganizations from '../pages/super-admin/PlatformOrganizations';
import PlatformChangeRequests from '../pages/super-admin/PlatformChangeRequests';
import PlatformAnalytics from '../pages/super-admin/PlatformAnalytics';
import SystemHealth from '../pages/super-admin/SystemHealth';

// Org & Employee
import OrgOverview from '../pages/organization/OrgOverview';
import ConnectedApplications from '../pages/organization/ConnectedApplications';
import ApiCredentials from '../pages/organization/ApiCredentials';
import MessagesPage from '../pages/messages/MessagesPage';
import TemplatesPage from '../pages/templates/TemplatesPage';
import JsonRequests from '../pages/organization/JsonRequests';
import DlqPage from '../pages/dlq/DlqPage';
import OrgAnalytics from '../pages/organization/OrgAnalytics';
import EmployeesAndRoles from '../pages/employee/EmployeesAndRoles';
import OrgSettings from '../pages/settings/OrgSettings';
import AppearancePage from '../pages/settings/AppearancePage';

function RootRedirect() {
  const { isAuthenticated, isPlatformAdmin, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh' }}>
        <div className="spinner"></div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return isPlatformAdmin ? (
    <Navigate to="/platform/organizations" replace />
  ) : (
    <Navigate to="/org/overview" replace />
  );
}

export default function AppRoutes() {
  return (
    <Routes>
      {/* Public Auth Routes */}
      <Route path="/login" element={<AuthPage />} />
      <Route path="/access-denied" element={<AccessDenied />} />

      {/* Root redirect */}
      <Route path="/" element={<RootRedirect />} />

      <Route
        path="/appearance"
        element={
          <ProtectedRoute>
            <DashboardLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<AppearancePage />} />
      </Route>

      {/* Platform Admin Routes */}
      <Route
        path="/platform"
        element={
          <ProtectedRoute platformOnly>
            <DashboardLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Navigate to="organizations" replace />} />
        <Route path="organizations" element={<PlatformOrganizations />} />
        <Route path="change-requests" element={<PlatformChangeRequests />} />
        <Route path="analytics" element={<PlatformAnalytics />} />
        <Route path="monitoring" element={<SystemHealth />} />
      </Route>

      {/* Organization Admin & Employee Routes */}
      <Route
        path="/org"
        element={
          <ProtectedRoute orgOnly>
            <DashboardLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Navigate to="overview" replace />} />
        <Route
          path="overview"
          element={
            <ProtectedRoute tabId="tab-org-overview">
              <OrgOverview />
            </ProtectedRoute>
          }
        />
        <Route
          path="applications"
          element={
            <ProtectedRoute tabId="tab-org-applications" requiredPermission="organization:configuration:manage">
              <ConnectedApplications />
            </ProtectedRoute>
          }
        />
        <Route
          path="credentials"
          element={
            <ProtectedRoute tabId="tab-org-credentials" requiredPermission="organization:configuration:manage">
              <ApiCredentials />
            </ProtectedRoute>
          }
        />
        <Route
          path="messages"
          element={
            <ProtectedRoute tabId="tab-org-messages" requiredPermission="organization:messages:read">
              <MessagesPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="templates"
          element={
            <ProtectedRoute tabId="tab-org-templates" requiredPermission="organization:templates:read">
              <TemplatesPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="json-requests"
          element={
            <ProtectedRoute tabId="tab-org-json-requests" requiredPermission="organization:payloads:read">
              <JsonRequests />
            </ProtectedRoute>
          }
        />
        <Route
          path="dlq"
          element={
            <ProtectedRoute tabId="tab-org-dlq" requiredPermission="organization:dead_letters:read">
              <DlqPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="analytics"
          element={
            <ProtectedRoute tabId="tab-org-analytics" requiredPermission="organization:analytics:read">
              <OrgAnalytics />
            </ProtectedRoute>
          }
        />
        <Route
          path="users"
          element={
            <ProtectedRoute tabId="tab-org-users" requiredPermission="organization:users:read">
              <EmployeesAndRoles />
            </ProtectedRoute>
          }
        />
        <Route
          path="settings"
          element={
            <ProtectedRoute tabId="tab-org-settings" requiredPermission="organization:configuration:manage">
              <OrgSettings />
            </ProtectedRoute>
          }
        />
      </Route>

      {/* Catch-all fallback */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
