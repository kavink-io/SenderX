import React, { createContext, useContext, useState, useCallback } from 'react';
import ApiClient from '../services/api';

const ScopeContext = createContext();

export function ScopeProvider({ children }) {
  const [activeAppId, setActiveAppId] = useState(() => ApiClient.getActiveApplicationId());
  const [assignedApps, setAssignedApps] = useState([]);

  const setAppScope = useCallback((appId) => {
    ApiClient.setActiveApplicationId(appId);
    setActiveAppId(appId || null);
  }, []);

  return (
    <ScopeContext.Provider
      value={{
        activeAppId,
        setAppScope,
        assignedApps,
        setAssignedApps,
      }}
    >
      {children}
    </ScopeContext.Provider>
  );
}

export function useAppScope() {
  const context = useContext(ScopeContext);
  if (!context) {
    throw new Error('useAppScope must be used within a ScopeProvider');
  }
  return context;
}
