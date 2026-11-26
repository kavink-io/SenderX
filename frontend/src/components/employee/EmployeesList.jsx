import React, { useState, useEffect, useCallback, useMemo } from 'react';
import ApiClient from '../../services/api';
import DataGrid from '../tables/DataGrid';
import CreateEmployeeModal from '../modals/CreateEmployeeModal';
import EmployeeDetailsModal from '../modals/EmployeeDetailsModal';
import AssignRoleModal from '../modals/AssignRoleModal';
import DeleteEmployeeModal from '../modals/DeleteEmployeeModal';
import { useToast } from '../../context/ToastContext';
import { useAuth } from '../../context/AuthContext';

export default function EmployeesList() {
  const [employees, setEmployees] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [isLoading, setIsLoading] = useState(true);

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [selectedEmp, setSelectedEmp] = useState(null);
  const [isDetailsOpen, setIsDetailsOpen] = useState(false);
  const [isAssignOpen, setIsAssignOpen] = useState(false);
  const [isDeleteOpen, setIsDeleteOpen] = useState(false);

  const { showToast } = useToast();
  const { isOrgAdmin, hasPermission } = useAuth();
  const canManage = isOrgAdmin || hasPermission('organization:users:read');

  const fetchEmployees = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await ApiClient.listUsers(page, 20, {
        search: search.trim() || undefined,
        status: statusFilter !== 'ALL' ? statusFilter : undefined,
      });

      if (res?.success) {
        setEmployees(res.data?.items || res.data || []);
        setTotalCount(res.data?.total || 0);
      }
    } catch (err) {
      console.error('Failed to load employees:', err);
      showToast('Could not load employees list', 'error');
    } finally {
      setIsLoading(false);
    }
  }, [page, search, statusFilter, showToast]);

  useEffect(() => {
    fetchEmployees();
  }, [fetchEmployees]);

  const handleToggleActive = async (emp) => {
    const uid = emp.user_id || emp._id || emp.id;
    const isActive = emp.is_active || emp.status === 'ACTIVE';

    try {
      const res = isActive
        ? await ApiClient.deactivateUser(uid)
        : await ApiClient.activateUser(uid);

      if (res?.success) {
        showToast(`Employee ${isActive ? 'deactivated' : 'activated'}`, 'success');
        fetchEmployees();
      } else {
        showToast(res?.message || 'Status update failed', 'error');
      }
    } catch (err) {
      showToast(err?.message || 'Error updating status', 'error');
    }
  };

  const handleResendOtp = useCallback(async (emp) => {
    const uid = emp.user_id || emp._id || emp.id;
    try {
      const res = await ApiClient.resendActivationOtp(uid);
      if (res?.success) {
        showToast('Activation invite re-sent to employee!', 'success');
      } else {
        showToast(res?.message || 'Failed to resend invite', 'error');
      }
    } catch (err) {
      showToast(err?.message || 'Error resending activation code', 'error');
    }
  }, [showToast]);

  const columnDefs = useMemo(() => [
    {
      headerName: 'Employee',
      field: 'name',
      minWidth: 200,
      flex: 1.4,
      autoHeight: true,
      wrapText: true,
      valueGetter: ({ data }) => `${data.name || ''} ${data.email || ''}`.trim(),
      cellRenderer: ({ data: emp }) => (
        <div>
          <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{emp.name || emp.email}</div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{emp.email}</div>
        </div>
      ),
    },
    {
      headerName: 'Employee Code',
      field: 'employee_code',
      minWidth: 130,
      valueGetter: ({ data }) => data.employee_code || '—',
      cellRenderer: ({ value }) => (
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85rem', color: 'var(--accent-cyan)' }}>
          {value}
        </span>
      ),
    },
    {
      headerName: 'Role',
      field: 'roles',
      minWidth: 140,
      valueGetter: ({ data: emp }) =>
        emp.is_org_admin
          ? 'ORG_ADMIN'
          : emp.roles && emp.roles.length > 0
          ? emp.roles.map((r) => r.name || r.role_id).join(', ')
          : 'Standard Member',
      cellRenderer: ({ data: emp, value }) => (
        <span className={`badge ${emp.is_org_admin ? 'badge-primary' : 'badge-info'}`}>{value}</span>
      ),
    },
    {
      headerName: 'Status',
      field: 'status',
      minWidth: 120,
      maxWidth: 155,
      valueGetter: ({ data: emp }) => emp.status || (emp.is_active ? 'ACTIVE' : 'INACTIVE'),
      cellRenderer: ({ data: emp, value }) => {
        const isActive = emp.is_active || emp.status === 'ACTIVE';
        const isPending = emp.status === 'PENDING' || emp.status === 'PENDING_ACTIVATION';
        return (
          <span className={`badge ${isActive ? 'badge-success' : isPending ? 'badge-warning' : 'badge-danger'}`}>
            {value}
          </span>
        );
      },
    },
    {
      headerName: 'Department',
      field: 'department',
      minWidth: 130,
      valueGetter: ({ data }) => data.department || 'Not provided',
      cellStyle: { fontSize: '0.85rem', color: 'var(--text-secondary)' },
    },
    {
      headerName: 'Actions',
      colId: 'actions',
      minWidth: 280,
      maxWidth: 340,
      sortable: false,
      filter: false,
      resizable: false,
      suppressHeaderMenuButton: true,
      headerClass: 'ag-right-aligned-header',
      cellClass: 'ag-actions-cell',
      cellRenderer: ({ data: emp }) => {
        const isActive = emp.is_active || emp.status === 'ACTIVE';
        const isPending = emp.status === 'PENDING' || emp.status === 'PENDING_ACTIVATION';
        return (
          <div style={{ display: 'inline-flex', gap: '6px' }}>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => {
                setSelectedEmp(emp);
                setIsDetailsOpen(true);
              }}
            >
              Profile
            </button>
            {canManage && (
              <>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => {
                    setSelectedEmp(emp);
                    setIsAssignOpen(true);
                  }}
                >
                  Roles
                </button>
                {isPending && (
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    onClick={() => handleResendOtp(emp)}
                    title="Resend activation invite email"
                  >
                    Resend
                  </button>
                )}
                {!emp.is_org_admin && (
                  <>
                    <button
                      type="button"
                      className={`btn btn-sm ${isActive ? 'btn-secondary' : 'btn-success'}`}
                      onClick={() => handleToggleActive(emp)}
                    >
                      {isActive ? 'Deactivate' : 'Activate'}
                    </button>
                    <button
                      type="button"
                      className="btn btn-danger btn-sm"
                      onClick={() => {
                        setSelectedEmp(emp);
                        setIsDeleteOpen(true);
                      }}
                    >
                      Delete
                    </button>
                  </>
                )}
              </>
            )}
          </div>
        );
      },
    },
  ], [canManage, handleResendOtp]);

  return (
    <div id="view-org-employees">
      {/* Filtering & Action Bar */}
      <div className="card" style={{ marginBottom: '1.5rem', padding: '1rem 1.25rem' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1rem', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center', flex: 1, minWidth: '260px' }}>
            <input
              type="text"
              className="form-control"
              placeholder="Search by name, email, or employee code..."
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              style={{ maxWidth: '320px' }}
            />
            <select
              className="form-control"
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setPage(1);
              }}
              style={{ maxWidth: '140px' }}
            >
              <option value="ALL">All Statuses</option>
              <option value="ACTIVE">Active</option>
              <option value="PENDING">Pending Activation</option>
              <option value="INACTIVE">Deactivated</option>
            </select>
          </div>

          {canManage && (
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => setIsCreateOpen(true)}
              id="btn-open-create-user"
            >
              + Add Employee
            </button>
          )}
        </div>
      </div>

      {/* Employees Table */}
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <DataGrid
          rowData={employees}
          columnDefs={columnDefs}
          loading={isLoading}
          emptyMessage="No employees found matching filters."
          getRowId={({ data }) => String(data.user_id || data._id || data.id)}
        />

        {totalCount > 20 && (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '1rem', borderTop: '1px solid var(--glass-border)' }}>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              Showing {employees.length} of {totalCount}
            </span>
            <div style={{ display: 'flex', gap: '6px' }}>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                Previous
              </button>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                disabled={page * 20 >= totalCount}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>

      <CreateEmployeeModal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        onCreated={fetchEmployees}
      />

      <EmployeeDetailsModal
        isOpen={isDetailsOpen}
        onClose={() => setIsDetailsOpen(false)}
        employee={selectedEmp}
      />

      <AssignRoleModal
        isOpen={isAssignOpen}
        onClose={() => setIsAssignOpen(false)}
        employee={selectedEmp}
        onAssigned={fetchEmployees}
      />

      <DeleteEmployeeModal
        isOpen={isDeleteOpen}
        onClose={() => setIsDeleteOpen(false)}
        employee={selectedEmp}
        onDeleted={fetchEmployees}
      />
    </div>
  );
}
