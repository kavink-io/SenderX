import React, { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { getEmployeeRolesList, partitionRoleBadges } from '../../utils/employeeTable';
import { calculatePopoverPosition } from '../../utils/colorUtils';

export default function RoleBadgesCell({ employee, onManageRoles, onViewProfile }) {
  const roles = getEmployeeRolesList(employee);
  const { visible, overflow } = partitionRoleBadges(roles);

  const [isOpen, setIsOpen] = useState(false);
  const [pos, setPos] = useState({ top: 0, left: 0, width: 240, openUp: false });
  const triggerRef = useRef(null);
  const popoverRef = useRef(null);

  const updatePos = () => {
    if (!triggerRef.current) return;
    const rect = triggerRef.current.getBoundingClientRect();
    const popRect = popoverRef.current?.getBoundingClientRect();
    const isRtl = document.documentElement.getAttribute('dir') === 'rtl';
    setPos(
      calculatePopoverPosition({
        triggerRect: rect,
        popoverWidth: popRect?.width || 248,
        popoverHeight: popRect?.height || 220,
        viewportWidth: window.innerWidth,
        viewportHeight: window.innerHeight,
        isRtl,
      })
    );
  };

  useLayoutEffect(() => {
    if (!isOpen) return;
    updatePos();
    const raf = window.requestAnimationFrame(updatePos);
    return () => window.cancelAnimationFrame(raf);
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return undefined;
    const handleOutside = (event) => {
      if (triggerRef.current?.contains(event.target) || popoverRef.current?.contains(event.target)) return;
      setIsOpen(false);
    };
    const handleEscape = (event) => {
      if (event.key === 'Escape') {
        event.stopPropagation();
        setIsOpen(false);
        triggerRef.current?.focus();
      }
    };
    const handleReposition = () => updatePos();

    document.addEventListener('mousedown', handleOutside, true);
    document.addEventListener('keydown', handleEscape, true);
    window.addEventListener('resize', handleReposition);
    window.addEventListener('scroll', handleReposition, true);
    return () => {
      document.removeEventListener('mousedown', handleOutside, true);
      document.removeEventListener('keydown', handleEscape, true);
      window.removeEventListener('resize', handleReposition);
      window.removeEventListener('scroll', handleReposition, true);
    };
  }, [isOpen]);

  if (roles.length === 0) {
    return (
      <span className="badge badge-secondary employee-role-badge" title="Unassigned">
        Unassigned
      </span>
    );
  }

  const remainingNames = overflow.map((r) => r.name).join(', ');

  return (
    <div className="role-badges-wrap">
      {visible.map((role) => (
        <span
          key={role.key}
          className={`badge ${role.isAdmin ? 'badge-primary' : 'badge-info'} employee-role-badge`}
          title={role.name}
        >
          {role.name}
        </span>
      ))}

      {overflow.length > 0 && (
        <button
          ref={triggerRef}
          type="button"
          className="badge role-overflow-badge"
          title={remainingNames}
          aria-label={`Show ${overflow.length} more roles: ${remainingNames}`}
          aria-expanded={isOpen}
          aria-haspopup="dialog"
          onClick={(e) => {
            e.stopPropagation();
            setIsOpen((prev) => !prev);
          }}
        >
          +{overflow.length}
        </button>
      )}

      {isOpen && createPortal(
        <div
          ref={popoverRef}
          role="dialog"
          aria-label={`Assigned roles for ${employee?.name || employee?.email || 'employee'}`}
          className={`role-overflow-popover${pos.openUp ? ' is-up' : ''}`}
          style={{
            position: 'fixed',
            top: `${pos.top}px`,
            left: `${pos.left}px`,
            width: `${pos.width}px`,
            zIndex: 3000,
          }}
          onMouseDown={(e) => e.stopPropagation()}
        >
          <div className="role-overflow-popover-header">
            <span>Assigned Roles ({roles.length})</span>
          </div>
          <div className="role-overflow-popover-list">
            {roles.map((role) => (
              <span
                key={role.key}
                className={`badge ${role.isAdmin ? 'badge-primary' : 'badge-info'}`}
                title={role.name}
              >
                {role.name}
              </span>
            ))}
          </div>
          {(onManageRoles || onViewProfile) && (
            <div className="role-overflow-popover-actions">
              {onViewProfile && (
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => {
                    setIsOpen(false);
                    onViewProfile();
                  }}
                >
                  Profile
                </button>
              )}
              {onManageRoles && (
                <button
                  type="button"
                  className="btn btn-primary btn-sm"
                  onClick={() => {
                    setIsOpen(false);
                    onManageRoles();
                  }}
                >
                  Manage Roles
                </button>
              )}
            </div>
          )}
        </div>,
        document.body
      )}
    </div>
  );
}
