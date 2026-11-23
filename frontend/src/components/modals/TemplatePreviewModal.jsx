import React, { useState } from 'react';
import Modal from '../common/Modal';
import ApiClient from '../../services/api';
import { useToast } from '../../context/ToastContext';

export default function TemplatePreviewModal({ isOpen, onClose, template }) {
  const [sampleData, setSampleData] = useState('{\n  "name": "Jane Doe",\n  "company": "SenderX",\n  "activation_link": "https://senderx.io/verify"\n}');
  const [renderedHtml, setRenderedHtml] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { showToast } = useToast();

  if (!template) return null;
  const tid = template.template_id || template._id || template.id;

  const handleRender = async () => {
    let parsed = {};
    try {
      parsed = JSON.parse(sampleData);
    } catch (e) {
      showToast('Invalid sample JSON format', 'error');
      return;
    }

    setIsLoading(true);
    try {
      const res = await ApiClient.previewTemplate(tid, parsed);
      if (res?.success && res.data?.rendered_html) {
        setRenderedHtml(res.data.rendered_html);
      } else {
        showToast(res?.message || 'Rendering failed', 'error');
      }
    } catch (err) {
      showToast(err?.message || 'Error rendering preview', 'error');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`Live Template Preview: ${template.name}`}
      maxWidth="900px"
      id="modal-template-preview"
    >
      <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: '1.25rem', height: '480px' }}>
        {/* Sample Data Sidebar */}
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <label style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.35rem' }}>
            Sample Context (JSON)
          </label>
          <textarea
            className="form-control"
            value={sampleData}
            onChange={(e) => setSampleData(e.target.value)}
            rows={14}
            style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem', flex: 1, resize: 'none' }}
          />
          <button
            type="button"
            className="btn btn-primary btn-sm"
            onClick={handleRender}
            disabled={isLoading}
            style={{ marginTop: '0.75rem' }}
          >
            {isLoading ? 'Rendering...' : 'Render Preview'}
          </button>
        </div>

        {/* Sandboxed iframe preview */}
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <label style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.35rem' }}>
            Sandboxed Email Output
          </label>
          <div style={{ flex: 1, border: '1px solid var(--glass-border)', borderRadius: '6px', overflow: 'hidden', background: '#ffffff' }}>
            <iframe
              title="Template Preview"
              srcDoc={renderedHtml || template.html_content || '<p style="padding: 2rem; color: #666; font-family: sans-serif;">Click "Render Preview" to compile Jinja variables safely.</p>'}
              sandbox=""
              style={{ width: '100%', height: '100%', border: 'none' }}
            />
          </div>
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
