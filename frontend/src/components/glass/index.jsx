import React, { useState, useEffect, useRef, useMemo, lazy, Suspense } from 'react';
import { createPortal } from 'react-dom';
import Modal from '../common/Modal';

const LazyDataGrid = lazy(() => import('../tables/DataGrid'));

function GlassTable(props) {
  return (
    <Suspense fallback={<div className="lg-glass-skeleton" style={{ width: '100%', height: '220px', borderRadius: 'var(--lg-radius-md)' }} />}>
      <LazyDataGrid {...props} />
    </Suspense>
  );
}

/** Translucent Liquid Glass card container with subtle top specular rim highlight. */
export function GlassCard({
  children,
  className = '',
  variant = 'default', // 'default' | 'elevated' | 'inset'
  interactive = false,
  style,
  ...props
}) {
  const variantClass =
    variant === 'elevated'
      ? 'lg-glass-card lg-glass-elevated'
      : variant === 'inset'
      ? 'lg-glass-inset'
      : 'card lg-glass-card';

  return (
    <div
      className={`${variantClass} ${interactive ? 'is-interactive' : ''} ${className}`.trim()}
      style={style}
      {...props}
    >
      {children}
    </div>
  );
}

/** Liquid Glass button supporting primary, secondary, success, danger, and ghost variants. */
export function GlassButton({
  children,
  variant = 'secondary', // 'primary' | 'secondary' | 'success' | 'danger' | 'ghost'
  size = 'md', // 'sm' | 'md' | 'lg'
  className = '',
  type = 'button',
  ...props
}) {
  const variantMap = {
    primary: 'btn btn-primary',
    secondary: 'btn btn-secondary',
    success: 'btn btn-success',
    danger: 'btn btn-danger',
    ghost: 'btn btn-outline',
  };
  const sizeClass = size === 'sm' ? 'btn-sm' : '';
  return (
    <button
      type={type}
      className={`${variantMap[variant] || 'btn btn-secondary'} ${sizeClass} ${className}`.trim()}
      {...props}
    >
      {children}
    </button>
  );
}

/** Liquid Glass text input with optional label. */
export function GlassInput({ label, className = '', id, ...props }) {
  const inputEl = <input id={id} className={`form-control ${className}`.trim()} {...props} />;
  if (!label) return inputEl;
  return (
    <div className="form-group">
      <label htmlFor={id}>{label}</label>
      {inputEl}
    </div>
  );
}

function extractSelectOptions(children, optionsProp) {
  if (Array.isArray(optionsProp)) {
    return optionsProp.map((o) => ({
      value: String(o.value ?? ''),
      label: o.label ?? String(o.value ?? ''),
      disabled: Boolean(o.disabled),
    }));
  }
  const items = [];
  React.Children.forEach(children, (child) => {
    if (!child) return;
    if (Array.isArray(child)) {
      items.push(...extractSelectOptions(child));
    } else if (React.isValidElement(child) && child.type === 'option') {
      items.push({
        value: String(child.props.value ?? ''),
        label: child.props.children,
        disabled: Boolean(child.props.disabled),
      });
    } else if (React.isValidElement(child) && child.props?.children) {
      items.push(...extractSelectOptions(child.props.children));
    }
  });
  return items;
}

/**
 * Custom Apple Liquid Glass dropdown select with floating blurred portal menu.
 * Accepts `<option>` children or `options`, and emits `{ target: { value } }`.
 */
export function GlassSelect({
  label,
  children,
  options: optionsProp,
  value = '',
  onChange,
  className = '',
  id,
  name,
  disabled = false,
  compact = false,
  placeholder = 'Select...',
  style,
  'aria-label': ariaLabel,
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [menuPos, setMenuPos] = useState({ top: 0, left: 0, width: 180, openUp: false });
  const triggerRef = useRef(null);
  const menuRef = useRef(null);

  const items = useMemo(
    () => extractSelectOptions(children, optionsProp),
    [children, optionsProp]
  );

  const selectedItem = items.find((opt) => opt.value === String(value ?? '')) || items[0];

  const updatePosition = () => {
    if (!triggerRef.current) return;
    const rect = triggerRef.current.getBoundingClientRect();
    const viewportH = window.innerHeight;
    const spaceBelow = viewportH - rect.bottom - 12;
    const spaceAbove = rect.top - 12;
    const openUp = spaceBelow < 180 && spaceAbove > spaceBelow;
    const width = Math.max(rect.width, compact ? 170 : rect.width);
    const left = Math.min(rect.left, window.innerWidth - width - 12);
    setMenuPos({
      top: openUp ? rect.top - 6 : rect.bottom + 6,
      left: Math.max(12, left),
      width,
      maxHeight: Math.min(280, Math.max(120, openUp ? spaceAbove : spaceBelow)),
      openUp,
    });
  };

  useEffect(() => {
    if (!isOpen) return;
    updatePosition();

    const handleOutside = (e) => {
      if (
        triggerRef.current?.contains(e.target) ||
        menuRef.current?.contains(e.target)
      ) {
        return;
      }
      setIsOpen(false);
    };
    const handleEscape = (e) => {
      if (e.key === 'Escape') {
        setIsOpen(false);
        triggerRef.current?.focus();
      }
    };
    const handleReposition = (e) => {
      if (menuRef.current && e?.target && menuRef.current.contains(e.target)) return;
      updatePosition();
    };

    document.addEventListener('mousedown', handleOutside);
    document.addEventListener('keydown', handleEscape);
    window.addEventListener('resize', handleReposition);
    window.addEventListener('scroll', handleReposition, true);
    return () => {
      document.removeEventListener('mousedown', handleOutside);
      document.removeEventListener('keydown', handleEscape);
      window.removeEventListener('resize', handleReposition);
      window.removeEventListener('scroll', handleReposition, true);
    };
  }, [isOpen]);

  const handleSelect = (opt) => {
    if (opt.disabled) return;
    setIsOpen(false);
    if (onChange) {
      onChange({ target: { value: opt.value, id, name } });
    }
  };

  const selectEl = (
    <>
      <button
        ref={triggerRef}
        id={id}
        type="button"
        disabled={disabled}
        role="combobox"
        aria-expanded={isOpen}
        aria-label={ariaLabel || label || placeholder}
        className={`lg-select-trigger ${compact ? 'is-compact' : ''} ${isOpen ? 'is-open' : ''} ${className}`.trim()}
        style={style}
        onClick={() => {
          if (!disabled) setIsOpen((prev) => !prev);
        }}
      >
        <span className="lg-select-value">
          {selectedItem ? selectedItem.label : placeholder}
        </span>
        <svg
          className="lg-select-chevron"
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      {isOpen &&
        createPortal(
          <div
            ref={menuRef}
            role="listbox"
            className={`lg-select-menu ${menuPos.openUp ? 'is-up' : ''}`}
            style={{
              position: 'fixed',
              left: `${menuPos.left}px`,
              width: `${menuPos.width}px`,
              maxHeight: `${menuPos.maxHeight}px`,
              ...(menuPos.openUp
                ? { bottom: `${window.innerHeight - menuPos.top}px` }
                : { top: `${menuPos.top}px` }),
            }}
          >
            {items.map((opt) => {
              const isSelected = opt.value === String(value ?? '');
              return (
                <button
                  key={`${opt.value}-${String(opt.label)}`}
                  type="button"
                  role="option"
                  aria-selected={isSelected}
                  disabled={opt.disabled}
                  className={`lg-select-option ${isSelected ? 'is-selected' : ''}`}
                  onClick={() => handleSelect(opt)}
                >
                  <span className="lg-select-option-label">{opt.label}</span>
                  {isSelected && (
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                  )}
                </button>
              );
            })}
          </div>,
          document.body
        )}
    </>
  );

  if (!label) return selectEl;
  return (
    <div className="form-group">
      <label htmlFor={id}>{label}</label>
      {selectEl}
    </div>
  );
}

/** Liquid Glass search bar with leading search icon and optional shortcut hint / clear control. */
export function GlassSearch({
  value = '',
  onChange,
  onClear,
  placeholder = 'Search...',
  shortcutHint,
  inputRef,
  className = '',
  ...props
}) {
  return (
    <div className={`lg-search-box ${className}`.trim()}>
      <span className="lg-search-icon" aria-hidden="true">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="11" cy="11" r="8" />
          <line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
      </span>
      <input
        ref={inputRef}
        type="text"
        className="form-control lg-search-input"
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        {...props}
      />
      {value && onClear ? (
        <button
          type="button"
          className="lg-search-clear"
          onClick={onClear}
          aria-label="Clear search"
        >
          &times;
        </button>
      ) : (
        shortcutHint && <span className="lg-search-kbd">{shortcutHint}</span>
      )}
    </div>
  );
}

/** Segmented Liquid Glass tab switcher. */
export function GlassTabs({ tabs = [], activeKey, onChange, className = '', style }) {
  return (
    <div className={`lg-tabs ${className}`.trim()} role="tablist" style={style}>
      {tabs.map((tab) => {
        const isActive = activeKey === tab.key;
        return (
          <button
            key={tab.key}
            id={tab.id}
            type="button"
            role="tab"
            aria-selected={isActive}
            className={`lg-tab-btn ${isActive ? 'is-active' : ''}`}
            onClick={() => onChange(tab.key)}
          >
            {tab.icon}
            <span>{tab.label}</span>
          </button>
        );
      })}
    </div>
  );
}

/** Translucent glass pill badge. */
export function GlassBadge({ children, tone = 'info', className = '', ...props }) {
  const toneClass = {
    info: 'badge badge-info',
    primary: 'badge badge-primary',
    success: 'badge badge-success',
    warning: 'badge badge-warning',
    danger: 'badge badge-danger',
    neutral: 'badge badge-secondary',
    code: 'badge badge-code',
  }[tone] || 'badge badge-info';

  return (
    <span className={`${toneClass} lg-badge ${className}`.trim()} {...props}>
      {children}
    </span>
  );
}

/** Lightweight frosted tooltip wrapper. */
export function GlassTooltip({ text, children }) {
  if (!text) return children;
  return (
    <span className="lg-tooltip-wrap">
      {children}
      <span className="lg-tooltip-bubble" role="tooltip">
        {text}
      </span>
    </span>
  );
}

/** Accessible Liquid Glass dropdown popover with click-outside and Escape close handling. */
export function GlassDropdown({ isOpen, onClose, trigger, children, align = 'right', menuStyle }) {
  const containerRef = useRef(null);

  useEffect(() => {
    if (!isOpen) return;
    const handleOutside = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        onClose();
      }
    };
    const handleEscape = (e) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('mousedown', handleOutside);
    document.addEventListener('keydown', handleEscape);
    return () => {
      document.removeEventListener('mousedown', handleOutside);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [isOpen, onClose]);

  return (
    <div ref={containerRef} className="lg-dropdown">
      {trigger}
      {isOpen && (
        <div
          className="lg-dropdown-menu"
          style={{
            ...(align === 'left' ? { left: 0, right: 'auto', transformOrigin: 'top left' } : {}),
            ...menuStyle,
          }}
        >
          {children}
        </div>
      )}
    </div>
  );
}

/** Semantic shell wrappers for Sidebar and Navbar. */
export function GlassSidebar({ className = '', children, ...props }) {
  return (
    <aside className={`sidebar ${className}`.trim()} {...props}>
      {children}
    </aside>
  );
}

export function GlassNavbar({ className = '', children, ...props }) {
  return (
    <header className={`content-header top-nav ${className}`.trim()} {...props}>
      {children}
    </header>
  );
}

export function GlassToast({ message, type = 'info', onDismiss }) {
  return (
    <div className={`toast toast-${type}`} onClick={onDismiss} role="status">
      <span>{message}</span>
    </div>
  );
}

export function GlassSkeleton({ width = '100%', height = '18px', style }) {
  return <span className="lg-skeleton" style={{ width, height, ...style }} aria-hidden="true" />;
}

/** Smoothly animates numeric KPI values while respecting reduced-motion preferences. */
export function AnimatedNumber({ value, suffix = '', decimals = 0 }) {
  const target = Number(value);
  const isValid = Number.isFinite(target);
  const [display, setDisplay] = useState(isValid ? target : value);

  useEffect(() => {
    if (!isValid) {
      setDisplay(value);
      return;
    }
    const reduced =
      typeof window !== 'undefined' &&
      window.matchMedia &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduced) {
      setDisplay(target);
      return;
    }

    let rafId = 0;
    const duration = 420;
    const start = performance.now();
    const initial = 0;

    const tick = (now) => {
      const progress = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplay(initial + (target - initial) * eased);
      if (progress < 1) {
        rafId = requestAnimationFrame(tick);
      }
    };

    rafId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafId);
  }, [target, isValid, value]);

  if (!isValid) return <>{value}{suffix}</>;
  const formatted = decimals > 0 ? display.toFixed(decimals) : Math.round(display).toLocaleString();
  return <>{formatted}{suffix}</>;
}

export { Modal as GlassModal, GlassTable };
