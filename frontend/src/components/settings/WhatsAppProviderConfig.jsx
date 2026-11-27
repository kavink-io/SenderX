import React, { useCallback, useEffect, useState } from 'react';
import ApiClient from '../../services/api';
import { useToast } from '../../context/ToastContext';
import { useAuth } from '../../context/AuthContext';
import OffCanvasPanel from '../common/OffCanvasPanel';
import GridActionButton from '../tables/GridActionButton';
import { GlassButton, GlassSkeleton } from '../glass';

const EMPTY_FORM = {
  name: '',
  waba_id: '',
  phone_number_id: '',
  display_phone_number: '',
  access_token: '',
};

function formatDate(value) {
  if (!value) return 'Not verified';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Not verified' : date.toLocaleString();
}

export default function WhatsAppProviderConfig() {
  const { showToast } = useToast();
  const { hasPermission } = useAuth();
  const canManage = hasPermission('organization:providers:manage');
  const [integrations, setIntegrations] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [panelMode, setPanelMode] = useState(null);
  const [selectedIntegration, setSelectedIntegration] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [isSaving, setIsSaving] = useState(false);
  const [busyIntegrationId, setBusyIntegrationId] = useState(null);

  const loadIntegrations = useCallback(async () => {
    setLoadError('');
    try {
      const response = await ApiClient.listWhatsAppIntegrations();
      if (!response?.success || !Array.isArray(response.data)) {
        throw new Error(response?.message || 'Could not load WhatsApp integrations.');
      }
      setIntegrations(response.data);
    } catch (error) {
      console.error('Failed to load WhatsApp integrations:', error);
      setLoadError('WhatsApp integrations could not be loaded.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadIntegrations();
  }, [loadIntegrations]);

  const openConnectPanel = () => {
    setSelectedIntegration(null);
    setForm(EMPTY_FORM);
    setPanelMode('connect');
  };

  const openEditPanel = (integration) => {
    setSelectedIntegration(integration);
    setForm({
      ...EMPTY_FORM,
      name: integration.name || '',
      display_phone_number: integration.display_phone_number || '',
    });
    setPanelMode('edit');
  };

  const openRotatePanel = (integration) => {
    setSelectedIntegration(integration);
    setForm({ ...EMPTY_FORM, access_token: '' });
    setPanelMode('rotate');
  };

  const closePanel = () => {
    setPanelMode(null);
    setSelectedIntegration(null);
    setForm(EMPTY_FORM);
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!canManage || !panelMode) return;
    setIsSaving(true);
    try {
      let response;
      if (panelMode === 'connect') {
        response = await ApiClient.connectWhatsAppIntegration({
          ...form,
          name: form.name.trim() || undefined,
          display_phone_number: form.display_phone_number.trim() || undefined,
          waba_id: form.waba_id.trim(),
          phone_number_id: form.phone_number_id.trim(),
          access_token: form.access_token.trim(),
        });
      } else if (panelMode === 'edit') {
        response = await ApiClient.updateWhatsAppIntegration(selectedIntegration.integration_id, {
          name: form.name.trim(),
          display_phone_number: form.display_phone_number.trim() || undefined,
        });
      } else {
        response = await ApiClient.rotateWhatsAppIntegration(
          selectedIntegration.integration_id,
          { access_token: form.access_token.trim() }
        );
      }

      if (!response?.success) throw new Error(response?.message || 'WhatsApp configuration update failed.');
      showToast(
        panelMode === 'connect'
          ? 'WhatsApp integration verified and connected'
          : panelMode === 'rotate'
            ? 'WhatsApp access token rotated and verified'
            : 'WhatsApp integration updated',
        'success'
      );
      closePanel();
      await loadIntegrations();
    } catch (error) {
      showToast(error?.message || 'Could not update WhatsApp configuration', 'error');
    } finally {
      setIsSaving(false);
    }
  };

  const handleVerify = async (integration) => {
    setBusyIntegrationId(integration.integration_id);
    try {
      const response = await ApiClient.verifyWhatsAppIntegration(integration.integration_id);
      if (!response?.success) throw new Error(response?.message || 'WhatsApp credential verification failed.');
      showToast('WhatsApp credentials verified', 'success');
      await loadIntegrations();
    } catch (error) {
      showToast(error?.message || 'Could not verify WhatsApp credentials', 'error');
    } finally {
      setBusyIntegrationId(null);
    }
  };

  const handleDisconnect = async (integration) => {
    if (!window.confirm(`Disconnect WhatsApp integration "${integration.name || integration.display_phone_number || integration.integration_id}"?`)) {
      return;
    }
    setBusyIntegrationId(integration.integration_id);
    try {
      const response = await ApiClient.disconnectWhatsAppIntegration(integration.integration_id);
      if (!response?.success) throw new Error(response?.message || 'WhatsApp disconnect failed.');
      showToast('WhatsApp integration disconnected', 'success');
      await loadIntegrations();
    } catch (error) {
      showToast(error?.message || 'Could not disconnect WhatsApp integration', 'error');
    } finally {
      setBusyIntegrationId(null);
    }
  };

  return (
    <div>
      <div className="saas-section-heading saas-activity-heading">
        <div>
          <h5 style={{ margin: 0, color: 'var(--text-primary)' }}>WhatsApp Cloud API</h5>
          <p>Connect and verify organization-owned WhatsApp Business phone numbers. Credentials stay in the dedicated encrypted integration store.</p>
        </div>
        {canManage && <GlassButton type="button" variant="primary" onClick={openConnectPanel}>Add WhatsApp account</GlassButton>}
      </div>

      {!canManage && <p className="saas-empty-state">You have read-only access to WhatsApp configuration.</p>}
      {loadError && (
        <div className="saas-empty-state" role="alert">
          <p>{loadError}</p>
          <button type="button" className="btn btn-secondary" onClick={loadIntegrations}>Retry</button>
        </div>
      )}
      {isLoading ? <GlassSkeleton width="100%" height="120px" /> : (
        !loadError && (integrations.length ? (
          <div className="saas-health-list">
            {integrations.map((integration) => (
              <div className="lg-glass-inset" key={integration.integration_id} style={{ marginBottom: '10px', padding: '14px' }}>
                <div className="saas-section-heading saas-activity-heading">
                  <div>
                    <strong style={{ color: 'var(--text-primary)' }}>{integration.name || integration.display_phone_number || 'WhatsApp account'}</strong>
                    <p style={{ margin: '4px 0 0' }}>
                      {integration.display_phone_number || 'Phone number unavailable'} · {integration.status || 'UNKNOWN'}
                    </p>
                  </div>
                  {canManage && (
                    <div className="grid-action-group">
                      <GridActionButton icon="check" label="Verify WhatsApp credentials" disabled={busyIntegrationId === integration.integration_id} onClick={() => handleVerify(integration)} />
                      <GridActionButton icon="edit" label="Edit WhatsApp details" disabled={busyIntegrationId === integration.integration_id} onClick={() => openEditPanel(integration)} />
                      <GridActionButton icon="refresh" label="Rotate WhatsApp access token" disabled={busyIntegrationId === integration.integration_id} onClick={() => openRotatePanel(integration)} />
                      <GridActionButton icon="delete" label="Disconnect WhatsApp integration" variant="danger" disabled={busyIntegrationId === integration.integration_id} onClick={() => handleDisconnect(integration)} />
                    </div>
                  )}
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px 18px', marginTop: '12px', color: 'var(--text-secondary)', fontSize: '0.8rem' }}>
                  <span>Phone ID: {integration.phone_number_id || '—'}</span>
                  <span>Token: {integration.has_access_token ? 'Stored securely' : 'Missing'}</span>
                  <span>Last verified: {formatDate(integration.last_verified_at)}</span>
                  <span>Last updated: {formatDate(integration.updated_at)}</span>
                </div>
              </div>
            ))}
          </div>
        ) : !loadError && <div className="saas-empty-state">No WhatsApp accounts are connected to this organization.</div>)
      )}

      {panelMode && (
        <OffCanvasPanel
          isOpen
          onClose={closePanel}
          title={panelMode === 'connect' ? 'Connect WhatsApp Business Account' : panelMode === 'rotate' ? 'Rotate WhatsApp Access Token' : 'Edit WhatsApp Integration'}
          description="Credentials are sent directly to SenderX and are never saved in browser storage."
          size="medium"
          closeOnBackdrop
          closeOnEscape
        >
          <form onSubmit={handleSubmit}>
            {panelMode === 'connect' && (
              <>
                <div className="form-group">
                  <label htmlFor="whatsapp-name">Configuration Name</label>
                  <input id="whatsapp-name" className="form-control" value={form.name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} placeholder="Main WhatsApp account" />
                </div>
                <div className="form-group">
                  <label htmlFor="whatsapp-waba-id">WhatsApp Business Account ID</label>
                  <input id="whatsapp-waba-id" className="form-control" value={form.waba_id} onChange={(event) => setForm((current) => ({ ...current, waba_id: event.target.value }))} required />
                </div>
                <div className="form-group">
                  <label htmlFor="whatsapp-phone-id">Phone Number ID</label>
                  <input id="whatsapp-phone-id" className="form-control" value={form.phone_number_id} onChange={(event) => setForm((current) => ({ ...current, phone_number_id: event.target.value }))} required />
                </div>
                <div className="form-group">
                  <label htmlFor="whatsapp-display-phone">Display Phone Number (optional)</label>
                  <input id="whatsapp-display-phone" className="form-control" value={form.display_phone_number} onChange={(event) => setForm((current) => ({ ...current, display_phone_number: event.target.value }))} placeholder="+15551234567" />
                </div>
              </>
            )}
            {(panelMode === 'connect' || panelMode === 'rotate') && (
              <div className="form-group">
                <label htmlFor="whatsapp-access-token">{panelMode === 'rotate' ? 'New Access Token' : 'Access Token'}</label>
                <input id="whatsapp-access-token" type="password" className="form-control" autoComplete="new-password" value={form.access_token} onChange={(event) => setForm((current) => ({ ...current, access_token: event.target.value }))} required />
              </div>
            )}
            {panelMode === 'edit' && (
              <div className="form-group">
                <label htmlFor="whatsapp-edit-name">Configuration Name</label>
                <input id="whatsapp-edit-name" className="form-control" value={form.name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} />
              </div>
            )}
            {panelMode === 'edit' && (
              <div className="form-group">
                <label htmlFor="whatsapp-edit-phone">Display Phone Number</label>
                <input id="whatsapp-edit-phone" className="form-control" value={form.display_phone_number} onChange={(event) => setForm((current) => ({ ...current, display_phone_number: event.target.value }))} />
              </div>
            )}
            <div className="modal-actions">
              <button type="button" className="btn btn-secondary" onClick={closePanel} disabled={isSaving}>Cancel</button>
              <button type="submit" className="btn btn-primary" disabled={isSaving}>
                {isSaving ? 'Saving...' : panelMode === 'connect' ? 'Verify and Connect' : panelMode === 'rotate' ? 'Rotate Token' : 'Save Changes'}
              </button>
            </div>
          </form>
        </OffCanvasPanel>
      )}
    </div>
  );
}
