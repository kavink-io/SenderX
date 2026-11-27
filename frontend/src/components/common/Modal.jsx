import React, { useEffect, useRef } from 'react';
import OffCanvasPanel from './OffCanvasPanel';
import { lockBodyScroll, unlockBodyScroll } from './overlayScrollLock';

export default function Modal({
  isOpen,
  onClose,
  title,
  children,
  footer,
  maxWidth = '600px',
  id = '',
  variant = 'panel',
  size,
  description,
}) {
  if (variant !== 'dialog') {
    const widthValue = String(maxWidth);
    const numericWidth = Number.parseInt(widthValue, 10);
    const panelSize = size || (
      widthValue.includes('1200') || numericWidth >= 960 ? 'xl'
        : numericWidth >= 650 ? 'large'
          : numericWidth >= 500 ? 'medium'
            : 'small'
    );

    return (
      <OffCanvasPanel
        isOpen={isOpen}
        onClose={onClose}
        title={title}
        description={description}
        size={panelSize}
        id={id}
      >
        {children}
        {footer && <div className="modal-footer">{footer}</div>}
      </OffCanvasPanel>
    );
  }

  return (
    <CompactModal
      isOpen={isOpen}
      onClose={onClose}
      title={title}
      children={children}
      footer={footer}
      maxWidth={maxWidth}
      id={id}
    />
  );
}

function CompactModal({ isOpen, onClose, title, children, footer, maxWidth, id }) {
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!isOpen) return;

    const scrollToken = {};
    lockBodyScroll(scrollToken);
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        onCloseRef.current();
      }
    };

    document.addEventListener('keydown', handleKeyDown);

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      unlockBodyScroll(scrollToken);
    };
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div
      id={id}
      className="modal active"
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          onClose();
        }
      }}
      role="dialog"
      aria-modal="true"
    >
      <div className="modal-card modal-content" style={{ maxWidth }}>
        {title && (
          <div className="modal-header">
            <h3>{title}</h3>
            <button
              type="button"
              className="btn-close modal-close"
              onClick={onClose}
              aria-label="Close modal"
            >
              &times;
            </button>
          </div>
        )}
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-footer">{footer}</div>}
      </div>
    </div>
  );
}
