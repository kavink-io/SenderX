import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import AuthLoadingScreen from '../components/common/AuthLoadingScreen';

export default function ProtectedRoute({
  children,
  requiredPermission,
  tabId,
  platformOnly = false,
  orgOnly = false,
}) {
  const { isAuthenticated, isLoading, isPlatformAdmin, hasPermission, allowedTabs, isOrgAdmin } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return <AuthLoadingScreen message="Verifying session and workspace..." />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (platformOnly && !isPlatformAdmin) {
    return <Navigate to="/access-denied" replace />;
  }

  if (orgOnly && isPlatformAdmin) {
    return <Navigate to="/access-denied" replace />;
  }

  if (tabId && !isPlatformAdmin && !isOrgAdmin && allowedTabs.size > 0 && !allowedTabs.has(tabId)) {
    return <Navigate to="/access-denied" replace />;
  }

  if (requiredPermission && !hasPermission(requiredPermission)) {
    return <Navigate to="/access-denied" replace />;
  }

  return children;
}
