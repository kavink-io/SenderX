import React from 'react';

export default function MobileBackdrop({ isOpen, onClose }) {
  if (!isOpen) return null;

  return (
    <div
      id="mobile-backdrop"
      className="mobile-backdrop active"
      onClick={onClose}
      aria-hidden="true"
    />
  );
}
