import React, { useCallback, useEffect, useId, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { lockBodyScroll, unlockBodyScroll } from './overlayScrollLock';

const TRANSITION_MS = 220;
const openPanels = [];

const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled]):not([type="hidden"])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',');

function getFocusableElements(panel) {
  return Array.from(panel.querySelectorAll(FOCUSABLE_SELECTOR))
    .filter((element) => element.getAttribute('aria-hidden') !== 'true');
}

function acquirePanel(token) {
  lockBodyScroll(token);
  openPanels.push(token);
}

function releasePanel(token) {
  const index = openPanels.indexOf(token);
  if (index !== -1) openPanels.splice(index, 1);
  unlockBodyScroll(token);
}

export default function OffCanvasPanel({
  isOpen,
  onClose,
  title,
  description,
  children,
  size = 'medium',
  position = 'right',
  id,
  closeOnBackdrop = true,
  closeOnEscape = true,
  className = '',
}) {
  const panelRef = useRef(null);
  const onCloseRef = useRef(onClose);
  const dirtyRef = useRef(false);
  const openerRef = useRef(null);
  const tokenRef = useRef({});
  const generatedId = useId();
  const [isRendered, setIsRendered] = useState(isOpen);
  const [isClosing, setIsClosing] = useState(false);
  const [depth, setDepth] = useState(0);

  onCloseRef.current = onClose;

  const requestClose = useCallback(() => {
    if (dirtyRef.current && !window.confirm('Discard your unsaved changes?')) {
      return;
    }
    onCloseRef.current?.();
  }, []);

  useEffect(() => {
    if (isOpen) {
      dirtyRef.current = false;
      setIsRendered(true);
      setIsClosing(false);
      return undefined;
    }
    dirtyRef.current = false;
    if (!isRendered) return undefined;

    setIsClosing(true);
    const transitionDuration = window.matchMedia('(prefers-reduced-motion: reduce)').matches
      ? 0
      : TRANSITION_MS;
    const timer = window.setTimeout(() => {
      setIsRendered(false);
      setIsClosing(false);
    }, transitionDuration);
    return () => window.clearTimeout(timer);
  }, [isOpen, isRendered]);

  useEffect(() => {
    if (!isRendered) return undefined;

    const token = tokenRef.current;
    openerRef.current = document.activeElement;
    acquirePanel(token);
    setDepth(openPanels.length - 1);

    const focusFrame = window.requestAnimationFrame(() => {
      const focusable = panelRef.current && getFocusableElements(panelRef.current);
      (focusable?.[0] || panelRef.current)?.focus();
    });

    const handleKeyDown = (event) => {
      if (openPanels[openPanels.length - 1] !== token) return;

      if (event.key === 'Escape' && closeOnEscape) {
        event.preventDefault();
        requestClose();
        return;
      }

      if (event.key !== 'Tab' || !panelRef.current) return;
      const focusable = getFocusableElements(panelRef.current);
      if (!focusable.length) {
        event.preventDefault();
        panelRef.current.focus();
        return;
      }

      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && (document.activeElement === first || !panelRef.current.contains(document.activeElement))) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && (document.activeElement === last || !panelRef.current.contains(document.activeElement))) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => {
      window.cancelAnimationFrame(focusFrame);
      document.removeEventListener('keydown', handleKeyDown);
      releasePanel(token);
      if (openerRef.current?.isConnected) openerRef.current.focus();
    };
  }, [isRendered, closeOnEscape, requestClose]);

  if (!isRendered) return null;

  const panelId = id || `offcanvas-${generatedId}`;
  const titleId = `${panelId}-title`;
  const descriptionId = description ? `${panelId}-description` : undefined;
  const handleDirtyInput = (event) => {
    if (panelRef.current?.contains(event.target) && event.target.closest('form')) {
      dirtyRef.current = true;
    }
  };
  const handleCloseAction = (event) => {
    if (!panelRef.current?.contains(event.target)) return;
    const button = event.target.closest('button');
    const label = button?.getAttribute('aria-label') || button?.textContent || '';
    if (button && /^(cancel|close|dismiss)$/i.test(label.trim())) {
      event.preventDefault();
      event.stopPropagation();
      requestClose();
    }
  };

  return createPortal(
    <div
      className={`offcanvas-backdrop ${isClosing ? 'is-closing' : 'is-open'}`}
      style={{ zIndex: 1600 + depth * 2 }}
      onMouseDown={(event) => {
        if (
          closeOnBackdrop &&
          event.target === event.currentTarget &&
          openPanels[openPanels.length - 1] === tokenRef.current
        ) {
          requestClose();
        }
      }}
      aria-hidden={isClosing || !isOpen}
    >
      <section
        ref={panelRef}
        id={panelId}
        className={`offcanvas-panel offcanvas-panel-${size} ${position === 'left' ? 'offcanvas-panel-left' : 'offcanvas-panel-right'} ${className}`.trim()}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
        tabIndex={-1}
        onInputCapture={handleDirtyInput}
        onChangeCapture={handleDirtyInput}
        onClickCapture={handleCloseAction}
      >
        <header className="offcanvas-header">
          <div className="offcanvas-heading">
            {title && <h2 id={titleId}>{title}</h2>}
            {description && <p id={descriptionId}>{description}</p>}
          </div>
          <button
            type="button"
            className="btn-close offcanvas-close"
            aria-label="Close panel"
            onClick={requestClose}
          >
            <span aria-hidden="true">&times;</span>
          </button>
        </header>
        <div className="offcanvas-body">{children}</div>
      </section>
    </div>,
    document.body
  );
}
