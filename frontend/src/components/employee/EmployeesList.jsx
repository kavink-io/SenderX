import React, { useState, useEffect, useCallback, useMemo } from 'react';
import ApiClient from '../../services/api';
import DataGrid from '../tables/DataGrid';
import GridActionButton from '../tables/GridActionButton';
import CreateEmployeeModal from '../modals/CreateEmployeeModal';
import EditEmployeeModal from '../modals/EditEmployeeModal';
import EmployeeDetailsModal from '../modals/EmployeeDetailsModal';
import AssignRoleModal from '../modals/AssignRoleModal';
import DeleteEmployeeModal from '../modals/DeleteEmployeeModal';
import { useToast } from '../../context/ToastContext';
import { useAuth } from '../../context/AuthContext';
import { GlassSearch, GlassSelect } from '../glass';
import ProfessionalAvatar from '../common/ProfessionalAvatar';
import RoleBadgesCell from './RoleBadgesCell';
import { getEmployeeRoleLabel, getEmployeeStatus } from '../../utils/employeeTable';

export default function EmployeesList() {
  const [employees, setEmployees] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [isLoading, setIsLoading] = useState(true);

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [selectedEmp, setSelectedEmp] = useState(null);
  const [isDetailsOpen, setIsDetailsOpen] = useState(false);
  const [isAssignOpen, setIsAssignOpen] = useState(false);
  const [isDeleteOpen, setIsDeleteOpen] = useState(false);

  const { showToast } = useToast();
  const { account, isOrgAdmin, hasPermission, refreshProfile } = useAuth();
  const canManage = isOrgAdmin || hasPermission('organization:users:manage');

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
    const { isActive } = getEmployeeStatus(emp);

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

  const handleEmployeeUpdated = async (updatedEmployee) => {
    const employee = updatedEmployee?.data || updatedEmployee;
    const employeeId = employee?.user_id || employee?._id || employee?.id;
    const currentAccountId = account?.user_id || account?.id;

    if (employeeId && currentAccountId && String(employeeId) === String(currentAccountId)) {
      await refreshProfile();
    }
    await fetchEmployees();
  };

  const columnDefs = useMemo(() => [
    {
      headerName: 'Employee',
      field: 'name',
      minWidth: 190,
      maxWidth: 380,
      flex: 1.6,
      autoHeight: true,
      wrapText: true,
      valueGetter: ({ data }) => `${data.name || ''} ${data.email || ''}`.trim(),
      cellRenderer: ({ data: emp }) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <ProfessionalAvatar employee={emp} name={emp.name} size={34} />
          <div>
            <div className="employee-table-ellipsis" title={emp.name || emp.email} style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
              {emp.name || emp.email}
            </div>
            <div className="employee-table-ellipsis" title={emp.email} style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
              {emp.email}
            </div>
          </div>
        </div>
      ),
    },
    {
      headerName: 'Employee Code',
      field: 'employee_code',
      width: 118,
      minWidth: 110,
      maxWidth: 130,
      flex: 0,
      valueGetter: ({ data }) => data.employee_code || '—',
      cellRenderer: ({ value }) => (
        <span className="employee-table-ellipsis" title={value} style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85rem', color: 'var(--accent-cyan)' }}>
          {value}
        </span>
      ),
    },
    {
      headerName: 'Roles',
      field: 'roles',
      minWidth: 185,
      maxWidth: 260,
      flex: 1.2,
      valueGetter: ({ data: emp }) => getEmployeeRoleLabel(emp),
      cellRenderer: ({ data: emp }) => (
        <RoleBadgesCell
          employee={emp}
          onViewProfile={() => {
            setSelectedEmp(emp);
            setIsDetailsOpen(true);
          }}
          onManageRoles={
            canManage
              ? () => {
                  setSelectedEmp(emp);
                  setIsAssignOpen(true);
                }
              : undefined
          }
        />
      ),
    },
    {
      headerName: 'Status',
      field: 'status',
      width: 170,
      minWidth: 164,
      maxWidth: 178,
      flex: 0,
      valueGetter: ({ data: emp }) => getEmployeeStatus(emp).label,
      cellRenderer: ({ data: emp }) => {
        const { label, badgeClass } = getEmployeeStatus(emp);
        return <span className={`badge ${badgeClass} employee-status-badge`} title={label}>{label}</span>;
      },
    },
    {
      headerName: 'Department',
      field: 'department',
      minWidth: 110,
      maxWidth: 240,
      flex: 1,
      valueGetter: ({ data }) => data.department || 'Not provided',
      cellRenderer: ({ value }) => (
        <span className="employee-table-ellipsis" title={value} style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
          {value}
        </span>
      ),
    },
    {
      headerName: 'Actions',
      colId: 'actions',
      width: 240,
      minWidth: 230,
      maxWidth: 250,
      sortable: false,
      filter: false,
      resizable: false,
      suppressHeaderMenuButton: true,
      headerClass: 'ag-right-aligned-header',
      cellClass: 'ag-actions-cell',
      cellRenderer: ({ data: emp }) => {
        const { isActive, isPending } = getEmployeeStatus(emp);
        return (
          <div className="ag-icon-actions" role="group" aria-label="Employee actions">
            <GridActionButton
              icon="view"
              label="View employee profile"
              onClick={() => {
                setSelectedEmp(emp);
                setIsDetailsOpen(true);
              }}
            />
            {canManage && (
              <>
                <GridActionButton
                  icon="edit"
                  label="Edit employee"
                  onClick={() => {
                    setSelectedEmp(emp);
                    setIsEditOpen(true);
                  }}
                />
                <GridActionButton
                  icon="users"
                  label="Manage employee roles"
                  onClick={() => {
                    setSelectedEmp(emp);
                    setIsAssignOpen(true);
                  }}
                />
                {isPending && (
                  <GridActionButton icon="mail" label="Resend activation invite" onClick={() => handleResendOtp(emp)} />
                )}
                {!emp.is_org_admin && (
                  <>
                    <GridActionButton
                      icon={isActive ? 'user-round-x' : 'user-check'}
                      label={isActive ? 'Deactivate Employee' : 'Activate Employee'}
                      variant={isActive ? 'danger' : 'success'}
                      onClick={() => handleToggleActive(emp)}
                    />
                    <GridActionButton
                      icon="delete"
                      label="Delete employee"
                      variant="danger"
                      onClick={() => {
                        setSelectedEmp(emp);
                        setIsDeleteOpen(true);
                      }}
                    />
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
            <div style={{ flex: '1 1 240px', maxWidth: '320px' }}>
              <GlassSearch
                placeholder="Search by name, email, or employee code..."
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setPage(1);
                }}
                onClear={() => {
                  setSearch('');
                  setPage(1);
                }}
              />
            </div>
            <div style={{ minWidth: '165px' }}>
              <GlassSelect
                value={statusFilter}
                onChange={(e) => {
                  setStatusFilter(e.target.value);
                  setPage(1);
                }}
                aria-label="Filter employees by status"
              >
                <option value="ALL">All Statuses</option>
                <option value="ACTIVE">Active</option>
                <option value="PENDING">Pending Activation</option>
                <option value="INACTIVE">Deactivated</option>
              </GlassSelect>
            </div>
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

      <EditEmployeeModal
        isOpen={isEditOpen}
        onClose={() => setIsEditOpen(false)}
        employee={selectedEmp}
        onUpdated={handleEmployeeUpdated}
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
