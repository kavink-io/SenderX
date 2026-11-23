import React, { useState } from 'react';
import Modal from '../common/Modal';
import ApiClient from '../../services/api';
import { useToast } from '../../context/ToastContext';

export default function RegisterAppModal({ isOpen, onClose, onRegistered }) {
  const [name, setName] = useState('');
  const [environment, setEnvironment] = useState('live');
  const [description, setDescription] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { showToast } = useToast();

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!name.trim()) {
      showToast('Application name is required', 'error');
      return;
    }

    setIsSubmitting(true);
    try {
      const res = await ApiClient.registerApplication({
        name: name.trim(),
        environment,
        description: description.trim(),
      });

      if (res.success) {
        showToast('Application registered successfully!', 'success');
        setName('');
        setEnvironment('live');
        setDescription('');
        onRegistered();
        onClose();
      } else {
        showToast(res.message || 'Registration failed', 'error');
      }
    } catch (err) {
      showToast(err?.message || 'Error registering application', 'error');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Register Connected Application"
      maxWidth="540px"
      id="modal-register-app"
    >
      <form id="form-register-app" onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="reg-app-name">Application Name *</label>
          <input
            type="text"
            id="reg-app-name"
            className="form-control"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g., E-Commerce Checkout Service"
            required
            autoFocus
          />
        </div>

        <div className="form-group">
          <label htmlFor="reg-app-env">Environment</label>
          <select
            id="reg-app-env"
            className="form-control"
            value={environment}
            onChange={(e) => setEnvironment(e.target.value)}
          >
            <option value="live">Production / Live</option>
            <option value="staging">Staging</option>
            <option value="development">Development</option>
            <option value="sandbox">Sandbox</option>
          </select>
        </div>

        <div className="form-group" style={{ marginBottom: '1.5rem' }}>
          <label htmlFor="reg-app-desc">Description</label>
          <textarea
            id="reg-app-desc"
            className="form-control"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Dispatches transactional purchase receipts and delivery alerts..."
            rows={2}
          />
        </div>

        <div className="modal-actions" style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
          <button type="button" className="btn btn-secondary" onClick={onClose} disabled={isSubmitting}>
            Cancel
          </button>
          <button type="submit" id="btn-submit-register-app" className="btn btn-primary" disabled={isSubmitting}>
            {isSubmitting ? 'Registering...' : 'Register Application'}
          </button>
        </div>
      </form>
    </Modal>
  );
}
