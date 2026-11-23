import React, { useState, useEffect } from 'react';
import Modal from '../common/Modal';
import ApiClient from '../../services/api';
import { useToast } from '../../context/ToastContext';

export default function CreateOrgModal({ isOpen, onClose, onCreated }) {
  const [name, setName] = useState('');
  const [slug, setSlug] = useState('');
  const [description, setDescription] = useState('');
  const [adminEmail, setAdminEmail] = useState('');
  const [adminName, setAdminName] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { showToast } = useToast();

  const handleNameChange = (val) => {
    setName(val);
    const generated = val.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
    setSlug(generated);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!name.trim() || !slug.trim()) {
      showToast('Organization name and slug are required', 'error');
      return;
    }

    setIsSubmitting(true);
    try {
      const payload = {
        name: name.trim(),
        slug: slug.trim(),
        description: description.trim(),
        admin_user: adminEmail.trim() ? {
          email: adminEmail.trim().toLowerCase(),
          name: adminName.trim() || undefined,
        } : undefined,
      };

      const res = await ApiClient.createOrganization(payload);
      if (res.success) {
        showToast('Organization created successfully!', 'success');
        setName('');
        setSlug('');
        setDescription('');
        setAdminEmail('');
        setAdminName('');
        onCreated();
        onClose();
      } else {
        showToast(res.message || 'Failed to create organization', 'error');
      }
    } catch (err) {
      showToast(err?.message || 'Error creating organization', 'error');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Create Organization"
      maxWidth="600px"
      id="modal-create-org"
    >
      <form id="form-create-org" onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="create-org-name">Organization Name *</label>
          <input
            type="text"
            id="create-org-name"
            className="form-control"
            value={name}
            onChange={(e) => handleNameChange(e.target.value)}
            placeholder="Acme Global Inc"
            required
          />
        </div>

        <div className="form-group">
          <label htmlFor="create-org-slug">Slug Identifier *</label>
          <input
            type="text"
            id="create-org-slug"
            className="form-control"
            value={slug}
            onChange={(e) => setSlug(e.target.value.toLowerCase())}
            placeholder="acme-global"
            required
          />
        </div>

        <div className="form-group">
          <label htmlFor="create-org-desc">Description</label>
          <textarea
            id="create-org-desc"
            className="form-control"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Primary tenant for enterprise communications..."
            rows={2}
          />
        </div>

        <div style={{ borderTop: '1px solid var(--glass-border)', margin: '1.25rem 0 1rem', paddingTop: '1rem' }}>
          <h4 style={{ fontSize: '0.95rem', marginBottom: '0.75rem', color: 'var(--text-primary)' }}>Initial Administrator (Optional)</h4>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
            <div className="form-group">
              <label htmlFor="create-org-admin-email">Admin Email</label>
              <input
                type="email"
                id="create-org-admin-email"
                className="form-control"
                value={adminEmail}
                onChange={(e) => setAdminEmail(e.target.value)}
                placeholder="admin@tenant.com"
              />
            </div>
            <div className="form-group">
              <label htmlFor="create-org-admin-name">Admin Name</label>
              <input
                type="text"
                id="create-org-admin-name"
                className="form-control"
                value={adminName}
                onChange={(e) => setAdminName(e.target.value)}
                placeholder="Jane Doe"
              />
            </div>
          </div>
        </div>

        <div className="modal-actions" style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
            {isSubmitting ? 'Creating...' : 'Create Organization'}
          </button>
        </div>
      </form>
    </Modal>
  );
}
