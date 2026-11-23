import React, { useState, useEffect } from 'react';
import Modal from '../common/Modal';
import ApiClient from '../../services/api';
import { useToast } from '../../context/ToastContext';

export default function MediaSelectorModal({ isOpen, onClose, onSelectMedia }) {
  const [mediaList, setMediaList] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const { showToast } = useToast();

  const fetchMedia = async () => {
    setIsLoading(true);
    try {
      const res = await ApiClient.listMedia(1, 50);
      if (res?.success) {
        setMediaList(res.data?.items || []);
      }
    } catch (err) {
      console.warn('Could not load media library:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchMedia();
    }
  }, [isOpen]);

  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    setIsUploading(true);
    try {
      const res = await ApiClient.uploadMedia(formData);
      if (res?.success) {
        showToast('Media uploaded successfully!', 'success');
        fetchMedia();
      } else {
        showToast(res?.message || 'Upload failed', 'error');
      }
    } catch (err) {
      showToast(err?.message || 'Error uploading file', 'error');
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Select from Media Library"
      maxWidth="650px"
      id="modal-media-selector"
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
        <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
          Select an asset to attach or upload a new file.
        </span>
        <label className="btn btn-secondary btn-sm" style={{ cursor: 'pointer', margin: 0 }}>
          {isUploading ? 'Uploading...' : '+ Upload Asset'}
          <input
            type="file"
            onChange={handleUpload}
            disabled={isUploading}
            style={{ display: 'none' }}
          />
        </label>
      </div>

      <div style={{ maxHeight: '360px', overflowY: 'auto' }}>
        {isLoading ? (
          <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
            Loading media library...
          </div>
        ) : mediaList.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
            No media assets found in library.
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: '10px' }}>
            {mediaList.map((item) => (
              <div
                key={item.media_id || item._id}
                onClick={() => {
                  onSelectMedia(item);
                  onClose();
                }}
                style={{
                  background: 'var(--bg-surface)',
                  border: '1px solid var(--glass-border)',
                  borderRadius: '6px',
                  padding: '0.75rem',
                  cursor: 'pointer',
                  transition: 'border-color 0.2s',
                }}
              >
                <div style={{ fontWeight: 600, fontSize: '0.85rem', color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {item.filename || item.name || 'Attachment'}
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
                  {item.mime_type || 'application/octet-stream'}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="modal-actions" style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '1.25rem' }}>
        <button type="button" className="btn btn-secondary" onClick={onClose}>
          Cancel
        </button>
      </div>
    </Modal>
  );
}
