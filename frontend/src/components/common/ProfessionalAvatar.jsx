import React, { useEffect, useMemo, useState } from 'react';
import { getProfessionalAvatar, getUploadedAvatar } from '../../utils/professionalAvatar';

function getInitials(name) {
  return String(name || '')
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join('')
    .toUpperCase() || 'U';
}

export default function ProfessionalAvatar({ employee, name, size = 36, className = '' }) {
  const displayName = name || employee?.name || employee?.email || 'User';
  const uploadedAvatar = useMemo(() => getUploadedAvatar(employee), [employee]);
  const generatedAvatar = useMemo(() => getProfessionalAvatar(employee), [employee]);
  const [failedSource, setFailedSource] = useState(null);

  useEffect(() => {
    setFailedSource(null);
  }, [uploadedAvatar, generatedAvatar]);

  const src = uploadedAvatar && failedSource !== uploadedAvatar
    ? uploadedAvatar
    : failedSource !== generatedAvatar ? generatedAvatar : null;

  return (
    <span
      className={`professional-avatar ${className}`.trim()}
      style={{ width: size, height: size }}
      role="img"
      aria-label={`Profile avatar for ${displayName}`}
    >
      {src ? (
        <img src={src} alt="" onError={() => setFailedSource(src)} />
      ) : (
        <span aria-hidden="true">{getInitials(displayName)}</span>
      )}
    </span>
  );
}
