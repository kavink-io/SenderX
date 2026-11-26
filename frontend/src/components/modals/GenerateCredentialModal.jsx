import React, { useState } from 'react';
import Modal from '../common/Modal';
import ApiClient from '../../services/api';
import { useToast } from '../../context/ToastContext';
import { GlassSelect } from '../glass';

export default function GenerateCredentialModal({ isOpen, onClose, apps, onGenerated }) {
  const [applicationId, setApplicationId] = useState('');
  const [name, setName] = useState('');
  const [environment, setEnvironment] = useState('live');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { showToast } = useToast();

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!applicationId) {
      showToast('Please select a connected application', 'error');
      return;
    }

    setIsSubmitting(true);
    try {
      const res = await ApiClient.createCredential({
        application_id: applicationId,
        name: name.trim() || 'API Key',
        environment,
      });

      const rawSecret = res.data?.raw_key || res.data?.secret_key || res.data?.api_key || res.raw_key || res.api_key;
      if (res.success && rawSecret) {
        showToast('API Credential generated!', 'success');
        setName('');
        onGenerated(rawSecret, name.trim() || 'API Key');
        onClose();
      } else {
        showToast(res.message || 'Failed to generate key', 'error');
      }
    } catch (err) {
      showToast(err?.message || 'Error generating API credential', 'error');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Generate API Credential"
      maxWidth="500px"
      id="modal-generate-credential"
    >
      <form id="form-generate-credential" onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="cred-app-select">Application *</label>
          <GlassSelect
            id="cred-app-select"
            value={applicationId}
            onChange={(e) => setApplicationId(e.target.value)}
          >
            <option value="">Select Connected Application...</option>
            {apps.map((app) => (
              <option key={app.application_id || app._id} value={app.application_id || app._id}>
                {app.name} ({app.application_id})
              </option>
            ))}
          </GlassSelect>
        </div>

        <div className="form-group">
          <label htmlFor="cred-name">Key Identifier / Name</label>
          <input
            type="text"
            id="cred-name"
            className="form-control"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g., Primary Ingestion Worker"
          />
        </div>

        <div className="form-group" style={{ marginBottom: '1.5rem' }}>
          <label htmlFor="cred-env">Environment</label>
          <GlassSelect
            id="cred-env"
            value={environment}
            onChange={(e) => setEnvironment(e.target.value)}
          >
            <option value="live">Live / Production</option>
            <option value="test">Test / Sandbox</option>
          </GlassSelect>
        </div>

        <div className="modal-actions" style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
          <button type="button" className="btn btn-secondary" onClick={onClose} disabled={isSubmitting}>
            Cancel
          </button>
          <button type="submit" id="btn-submit-generate-cred" className="btn btn-primary" disabled={isSubmitting}>
            {isSubmitting ? 'Generating...' : 'Generate Key'}
          </button>
        </div>
      </form>
    </Modal>
  );
}
