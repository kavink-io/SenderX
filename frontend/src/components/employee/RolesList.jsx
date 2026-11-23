import React, { useState, useEffect, useCallback } from 'react';
import ApiClient from '../../services/api';
import CreateRoleModal from '../modals/CreateRoleModal';
import RoleDetailsModal from '../modals/RoleDetailsModal';
import { useToast } from '../../context/ToastContext';
import { useAuth } from '../../context/AuthContext';

export default function RolesList() {
  const [roles, setRoles] = useState([]);
  const [isLoading, setIsLoading] = useState(true);

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [selectedRole, setSelectedRole] = useState(null);
  const [isDetailsOpen, setIsDetailsOpen] = useState(false);

  const { showToast } = useToast();
  const { isOrgAdmin } = useAuth();

  const fetchRoles = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await ApiClient.listRoles();
      if (res?.success) {
        setRoles(res.data?.items || res.data || []);
      }
    } catch (err) {
      console.error('Failed to load roles:', err);
      showToast('Could not load custom roles', 'error');
    } finally {
      setIsLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    fetchRoles();
  }, [fetchRoles]);

  const handleDeleteRole = async (role) => {
    const rid = role.role_id || role._id || role.id;
    if (!window.confirm(`Delete custom role "${role.name}"?`)) return;

    try {
      const res = await ApiClient.deleteRole(rid);
      if (res?.success) {
        showToast('Role deleted', 'info');
        fetchRoles();
      } else {
        showToast(res?.message || 'Delete failed', 'error');
      }
    } catch (err) {
      showToast(err?.message || 'Error deleting role', 'error');
    }
  };

  return (
    <div id="view-org-roles">
      <div className="card" style={{ marginBottom: '1.5rem', padding: '1rem 1.25rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h3 style={{ fontSize: '1.05rem', margin: '0 0 0.25rem', color: 'var(--text-primary)' }}>
            Organization Custom Roles & Permissions
          </h3>
          <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            Configure tailored RBAC roles with granular scopes across messaging, templates, and applications.
          </p>
        </div>

        {isOrgAdmin && (
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => {
              setSelectedRole(null);
              setIsCreateOpen(true);
            }}
            id="btn-open-create-role"
          >
            + Create Role
          </button>
        )}
      </div>

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div className="table-responsive-wrapper">
          <table className="data-table" style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                <th>Role Name</th>
                <th>Description</th>
                <th>Permissions Count</th>
                <th style={{ textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={4} style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                    Loading custom roles...
                  </td>
                </tr>
              ) : roles.length === 0 ? (
                <tr>
                  <td colSpan={4} style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                    No custom roles defined. Click "+ Create Role" to establish an RBAC policy.
                  </td>
                </tr>
              ) : (
                roles.map((r) => {
                  const rid = r.role_id || r._id || r.id;
                  const permCount = (r.permissions || []).length;

                  return (
                    <tr key={rid}>
                      <td style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                        {r.name}
                      </td>
                      <td style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                        {r.description || 'Custom organization role'}
                      </td>
                      <td>
                        <span className="badge badge-scope">{permCount} permissions</span>
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <div style={{ display: 'inline-flex', gap: '6px' }}>
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            onClick={() => {
                              setSelectedRole(r);
                              setIsDetailsOpen(true);
                            }}
                          >
                            Details
                          </button>
                          {isOrgAdmin && (
                            <>
                              <button
                                type="button"
                                className="btn btn-secondary btn-sm"
                                onClick={() => {
                                  setSelectedRole(r);
                                  setIsCreateOpen(true);
                                }}
                              >
                                Edit
                              </button>
                              <button
                                type="button"
                                className="btn btn-danger btn-sm"
                                onClick={() => handleDeleteRole(r)}
                              >
                                Delete
                              </button>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      <CreateRoleModal
        isOpen={isCreateOpen}
        onClose={() => {
          setIsCreateOpen(false);
          setSelectedRole(null);
        }}
        role={selectedRole}
        onSaved={fetchRoles}
      />

      <RoleDetailsModal
        isOpen={isDetailsOpen}
        onClose={() => setIsDetailsOpen(false)}
        role={selectedRole}
      />
    </div>
  );
}
