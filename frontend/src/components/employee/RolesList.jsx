import React, { useState, useEffect, useCallback, useMemo } from 'react';
import ApiClient from '../../services/api';
import DataGrid from '../tables/DataGrid';
import GridActionButton from '../tables/GridActionButton';
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

  const handleDeleteRole = useCallback(async (role) => {
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
  }, [fetchRoles, showToast]);

  const columnDefs = useMemo(() => [
    {
      headerName: 'Role Name',
      field: 'name',
      minWidth: 160,
      maxWidth: 260,
      flex: 1,
      cellRenderer: ({ value }) => (
        <span className="employee-table-ellipsis" title={value} style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
          {value}
        </span>
      ),
    },
    {
      headerName: 'Description',
      field: 'description',
      minWidth: 220,
      flex: 1.6,
      valueGetter: ({ data }) => data.description || 'Custom organization role',
      cellRenderer: ({ value }) => (
        <span className="employee-table-ellipsis" title={value} style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
          {value}
        </span>
      ),
    },
    {
      headerName: 'Permissions Count',
      field: 'permissions',
      width: 160,
      minWidth: 155,
      maxWidth: 170,
      flex: 0,
      valueGetter: ({ data }) => (data.permissions || []).length,
      cellRenderer: ({ value }) => <span className="badge badge-scope">{value} permissions</span>,
    },
    {
      headerName: 'Actions',
      colId: 'actions',
      width: 138,
      minWidth: 130,
      maxWidth: 150,
      sortable: false,
      filter: false,
      resizable: false,
      suppressHeaderMenuButton: true,
      headerClass: 'ag-right-aligned-header',
      cellClass: 'ag-actions-cell',
      cellRenderer: ({ data: r }) => (
        <div className="ag-icon-actions" role="group" aria-label="Role actions">
          <GridActionButton
            icon="view"
            label="View role details"
            onClick={() => {
              setSelectedRole(r);
              setIsDetailsOpen(true);
            }}
          />
          {isOrgAdmin && (
            <>
              <GridActionButton
                icon="edit"
                label="Edit role"
                onClick={() => {
                  setSelectedRole(r);
                  setIsCreateOpen(true);
                }}
              />
              <GridActionButton icon="delete" label="Delete role" variant="danger" onClick={() => handleDeleteRole(r)} />
            </>
          )}
        </div>
      ),
    },
  ], [isOrgAdmin, handleDeleteRole]);

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
        <DataGrid
          rowData={roles}
          columnDefs={columnDefs}
          loading={isLoading}
          emptyMessage='No custom roles defined. Click "+ Create Role" to establish an RBAC policy.'
          getRowId={({ data }) => String(data.role_id || data._id || data.id)}
          pagination={roles.length > 20}
        />
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
