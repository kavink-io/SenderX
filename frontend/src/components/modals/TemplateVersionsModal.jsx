import React, { useState, useEffect } from 'react';
import Modal from '../common/Modal';
import ApiClient from '../../services/api';
import { useToast } from '../../context/ToastContext';

export default function TemplateVersionsModal({ isOpen, onClose, template }) {
  const [versions, setVersions] = useState([]);
  const [selectedVersion, setSelectedVersion] = useState(null);
  const [versionDetail, setVersionDetail] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  const { showToast } = useToast();

  useEffect(() => {
    if (!isOpen || !template) return;
    const tid = template.template_id || template._id || template.id;
    setIsLoading(true);
    setSelectedVersion(null);
    setVersionDetail(null);

    ApiClient.getTemplateVersions(tid)
      .then((res) => {
        if (res?.success) {
          setVersions(res.data?.versions || res.data?.items || res.data || []);
        }
      })
      .catch((err) => console.warn('Could not load versions:', err))
      .finally(() => setIsLoading(false));
  }, [isOpen, template]);

  if (!template) return null;
  const tid = template.template_id || template._id || template.id;

  const handleInspectVersion = async (vNum) => {
    setSelectedVersion(vNum);
    try {
      const res = await ApiClient.getTemplateVersion(tid, vNum);
      if (res?.success && res.data) {
        setVersionDetail(res.data);
      }
    } catch (err) {
      showToast('Error loading version details', 'error');
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`Version History: ${template.name}`}
      maxWidth="750px"
      id="modal-template-versions"
    >
      <div style={{ display: 'grid', gridTemplateColumns: '240px 1fr', gap: '1.25rem', minHeight: '340px' }}>
        {/* Version List Sidebar */}
        <div style={{ borderRight: '1px solid var(--glass-border)', paddingRight: '1rem' }}>
          <h4 style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '0.75rem' }}>
            Available Versions
          </h4>
          {isLoading ? (
            <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>Loading versions...</div>
          ) : versions.length === 0 ? (
            <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>No historical versions.</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {versions.map((v, i) => {
                const vNum = typeof v === 'number' ? v : v.version || i + 1;
                const isSelected = selectedVersion === vNum;

                return (
                  <button
                    key={i}
                    type="button"
                    className={`btn btn-sm ${isSelected ? 'btn-primary' : 'btn-secondary'}`}
                    style={{ textAlign: 'left', display: 'flex', justifyContent: 'space-between' }}
                    onClick={() => handleInspectVersion(vNum)}
                  >
                    <span>Version {vNum}</span>
                    {v.created_at && (
                      <span style={{ fontSize: '0.75rem', opacity: 0.7 }}>
                        {new Date(v.created_at).toLocaleDateString()}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Version Detail View */}
        <div>
          {versionDetail ? (
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                  Version {versionDetail.version} Snapshot
                </span>
                <span className="badge badge-info">{versionDetail.status || 'Archived'}</span>
              </div>
              <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                Subject: <strong>{versionDetail.subject || 'No subject'}</strong>
              </div>
              <div style={{ background: 'var(--bg-main)', border: '1px solid var(--glass-border)', borderRadius: '6px', padding: '0.75rem', maxHeight: '240px', overflowY: 'auto' }}>
                <pre style={{ margin: 0, fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--text-primary)', whiteSpace: 'pre-wrap' }}>
                  {versionDetail.html_body || versionDetail.html_content || versionDetail.html || '<!-- Empty content -->'}
                </pre>
              </div>
            </div>
          ) : (
            <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem', textAlign: 'center', paddingTop: '4rem' }}>
              Select a version from the left panel to inspect its historical markup snapshot.
            </div>
          )}
        </div>
      </div>

      <div className="modal-actions" style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '1.25rem' }}>
        <button type="button" className="btn btn-secondary" onClick={onClose}>
          Close
        </button>
      </div>
    </Modal>
  );
}
