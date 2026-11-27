import React, { lazy, Suspense } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import ProtectedRoute from './ProtectedRoute';
import AuthLoadingScreen from '../components/common/AuthLoadingScreen';
import { getDefaultDashboardPath } from '../utils/authRedirect';

const DashboardLayout = lazy(() => import('../layouts/DashboardLayout'));

// Auth & Common
const AuthPage = lazy(() => import('../pages/auth/AuthPage'));
const AccessDenied = lazy(() => import('../pages/common/AccessDenied'));

// Super Admin
const PlatformOrganizations = lazy(() => import('../pages/super-admin/PlatformOrganizations'));
const PlatformChangeRequests = lazy(() => import('../pages/super-admin/PlatformChangeRequests'));
const PlatformAnalytics = lazy(() => import('../pages/super-admin/PlatformAnalytics'));
const SystemHealth = lazy(() => import('../pages/super-admin/SystemHealth'));

// Org & Employee
const OrgOverview = lazy(() => import('../pages/organization/OrgOverview'));
const ConnectedApplications = lazy(() => import('../pages/organization/ConnectedApplications'));
const ApiCredentials = lazy(() => import('../pages/organization/ApiCredentials'));
const ChannelConfigurations = lazy(() => import('../pages/organization/ChannelConfigurations'));
const MessagesPage = lazy(() => import('../pages/messages/MessagesPage'));
const TemplatesPage = lazy(() => import('../pages/templates/TemplatesPage'));
const JsonRequests = lazy(() => import('../pages/organization/JsonRequests'));
const DlqPage = lazy(() => import('../pages/dlq/DlqPage'));
const OrgAnalytics = lazy(() => import('../pages/organization/OrgAnalytics'));
const EmployeesAndRoles = lazy(() => import('../pages/employee/EmployeesAndRoles'));
const OrgSettings = lazy(() => import('../pages/settings/OrgSettings'));
const AppearancePage = lazy(() => import('../pages/settings/AppearancePage'));

function RootRedirect() {
  const { isAuthenticated, account, isLoading } = useAuth();

  if (isLoading) {
    return <AuthLoadingScreen message="Loading workspace..." />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <Navigate to={getDefaultDashboardPath(account)} replace />;
}

export default function AppRoutes() {
  return (
    <Suspense fallback={<AuthLoadingScreen message="Loading workspace..." />}>
      <Routes>
      {/* Public Auth Routes */}
      <Route path="/login" element={<AuthPage />} />
      <Route path="/access-denied" element={<AccessDenied />} />

      {/* Root & Dashboard redirect */}
      <Route path="/" element={<RootRedirect />} />
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <RootRedirect />
          </ProtectedRoute>
        }
      />

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
          path="channels"
          element={
            <ProtectedRoute tabId="tab-org-channels" requiredPermission="organization:providers:read">
              <ChannelConfigurations />
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
      <Route
        path="*"
        element={
          <ProtectedRoute>
            <RootRedirect />
          </ProtectedRoute>
        }
      />
      </Routes>
    </Suspense>
  );
}
