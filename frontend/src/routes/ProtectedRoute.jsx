import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import AccessDenied from '../pages/common/AccessDenied';

export default function ProtectedRoute({
  children,
  platformOnly = false,
  orgOnly = false,
  requiredPermission = null,
  tabId = null
}) {
  const { isAuthenticated, isPlatformAdmin, isOrgAdmin, hasPermission, allowedTabs, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '60vh' }}>
        <div className="spinner"></div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (platformOnly && !isPlatformAdmin) {
    return <Navigate to="/org/overview" replace />;
  }

  if (orgOnly && isPlatformAdmin) {
    return <Navigate to="/platform/organizations" replace />;
  }

  if (requiredPermission && !hasPermission(requiredPermission)) {
    return <AccessDenied message={`You lack the required permission (${requiredPermission}) to access this view.`} />;
  }

  if (tabId && !isPlatformAdmin && !isOrgAdmin) {
    if (allowedTabs.size > 0 && !allowedTabs.has(tabId)) {
      return <AccessDenied message={`Your assigned roles do not grant access to this module.`} />;
    }
  }

  return children;
}
