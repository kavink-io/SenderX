import React, { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { calculatePopoverPosition } from '../../utils/colorUtils';

const icons = {
  view: (
    <>
      <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12Z" />
      <circle cx="12" cy="12" r="3" />
    </>
  ),
  edit: (
    <>
      <path d="M12 20h9" />
      <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L8 18l-4 1 1-4Z" />
    </>
  ),
  delete: (
    <>
      <path d="M3 6h18" />
      <path d="M8 6V4h8v2" />
      <path d="m19 6-1 14H6L5 6" />
      <path d="M10 11v5m4-5v5" />
    </>
  ),
  copy: (
    <>
      <rect x="8" y="8" width="13" height="13" rx="2" />
      <path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3" />
    </>
  ),
  download: (
    <>
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" y1="15" x2="12" y2="3" />
    </>
  ),
  refresh: (
    <>
      <path d="M20 7v5h-5" />
      <path d="M4 17v-5h5" />
      <path d="M5.6 9a7 7 0 0 1 11.6-2L20 12" />
      <path d="M18.4 15a7 7 0 0 1-11.6 2L4 12" />
    </>
  ),
  users: (
    <>
      <path d="M16 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
      <circle cx="10" cy="7" r="4" />
      <path d="M20 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8" />
    </>
  ),
  mail: (
    <>
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <path d="m3 7 9 6 9-6" />
    </>
  ),
  check: <path d="m5 12 4 4L19 6" />,
  'user-round-x': (
    <>
      <circle cx="12" cy="8" r="5" />
      <path d="M20 21a8 8 0 0 0-16 0" />
      <path d="m19 8 4 4m0-4-4 4" />
    </>
  ),
  'user-check': (
    <>
      <path d="M16 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
      <circle cx="10" cy="7" r="4" />
      <path d="m16 11 2 2 4-4" />
    </>
  ),
  pause: (
    <>
      <path d="M7 4h3v16H7zM14 4h3v16h-3z" />
    </>
  ),
  power: (
    <>
      <path d="M12 2v10" />
      <path d="M18.4 6.6a9 9 0 1 1-12.77.04" />
    </>
  ),
  'power-off': (
    <>
      <path d="M18.36 6.64A9 9 0 0 1 20.77 15" />
      <path d="M6.16 6.16a9 9 0 1 0 12.68 12.68" />
      <path d="M12 2v4" />
      <path d="m2 2 20 20" />
    </>
  ),
  ellipsis: (
    <>
      <circle cx="12" cy="12" r="1" />
      <circle cx="19" cy="12" r="1" />
      <circle cx="5" cy="12" r="1" />
    </>
  ),
  close: (
    <>
      <path d="m18 6-12 12M6 6l12 12" />
    </>
  ),
};

export default function GridActionButton({
  icon,
  label,
  onClick,
  variant = '',
  disabled = false,
  ariaExpanded,
  ariaHaspopup,
  buttonRef,
}) {
  return (
    <button
      ref={buttonRef}
      type="button"
      className={`icon-btn icon-btn-sm${variant ? ` icon-btn-${variant}` : ''}`}
      onClick={onClick}
      title={label}
      aria-label={label}
      aria-expanded={ariaExpanded}
      aria-haspopup={ariaHaspopup}
      disabled={disabled}
    >
      <svg
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
        focusable="false"
      >
        {icons[icon]}
      </svg>
    </button>
  );
}

/**
 * Portal-rendered overflow menu for dense AG Grid action columns.
 */
export function GridMoreMenu({ items = [], label = 'More actions' }) {
  const [isOpen, setIsOpen] = useState(false);
  const [pos, setPos] = useState({ top: 0, left: 0, width: 196, openUp: false });
  const triggerRef = useRef(null);
  const menuRef = useRef(null);

  const visibleItems = items.filter((item) => item && !item.hidden);
  if (!visibleItems.length) return null;

  const updatePos = () => {
    if (!triggerRef.current) return;
    const rect = triggerRef.current.getBoundingClientRect();
    const menuRect = menuRef.current?.getBoundingClientRect();
    const isRtl = document.documentElement.getAttribute('dir') === 'rtl';
    setPos(
      calculatePopoverPosition({
        triggerRect: rect,
        popoverWidth: menuRect?.width || 196,
        popoverHeight: menuRect?.height || Math.min(240, visibleItems.length * 38 + 16),
        viewportWidth: window.innerWidth,
        viewportHeight: window.innerHeight,
        isRtl: !isRtl, // In LTR, prefer aligning menu right edge with trigger right edge
      })
    );
  };

  useLayoutEffect(() => {
    if (!isOpen) return;
    updatePos();
    const raf = window.requestAnimationFrame(updatePos);
    return () => window.cancelAnimationFrame(raf);
  }, [isOpen, visibleItems.length]);

  useEffect(() => {
    if (!isOpen) return undefined;
    const handleOutside = (event) => {
      if (triggerRef.current?.contains(event.target) || menuRef.current?.contains(event.target)) return;
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

  return (
    <>
      <GridActionButton
        buttonRef={triggerRef}
        icon="ellipsis"
        label={label}
        ariaExpanded={isOpen}
        ariaHaspopup="menu"
        onClick={() => setIsOpen((prev) => !prev)}
      />
      {isOpen && createPortal(
        <div
          ref={menuRef}
          role="menu"
          className={`lg-dropdown-menu grid-more-menu${pos.openUp ? ' is-up' : ''}`}
          style={{
            position: 'fixed',
            top: `${pos.top}px`,
            left: `${pos.left}px`,
            minWidth: '188px',
            width: `${pos.width}px`,
            zIndex: 3000,
          }}
          onMouseDown={(e) => e.stopPropagation()}
        >
          {visibleItems.map((item) => (
            <button
              key={item.key || item.label}
              type="button"
              role="menuitem"
              className={`lg-dropdown-item${item.variant === 'danger' ? ' is-danger' : ''}`}
              disabled={item.disabled}
              onClick={() => {
                setIsOpen(false);
                item.onClick?.();
              }}
            >
              {item.icon && icons[item.icon] && (
                <svg
                  width="15"
                  height="15"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  {icons[item.icon]}
                </svg>
              )}
              <span>{item.label}</span>
            </button>
          ))}
        </div>,
        document.body
      )}
    </>
  );
}
