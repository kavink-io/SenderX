import React, { useCallback, useEffect, useState, lazy, Suspense } from 'react';
import ApiClient from '../../services/api';
import { useToast } from '../../context/ToastContext';
import { useAuth } from '../../context/AuthContext';
import { GlassCard, GlassTabs, GlassButton, GlassSkeleton } from '../glass';

const WhatsAppProviderConfig = lazy(() => import('./WhatsAppProviderConfig'));

export default function ProviderConfigSection() {
  const [activeProvider, setActiveProvider] = useState('sendgrid');
  const [apiKey, setApiKey] = useState('');
  const [fromEmail, setFromEmail] = useState('');
  const [sesFromEmail, setSesFromEmail] = useState('');
  const [smtpFromEmail, setSmtpFromEmail] = useState('');
  const [awsAccessKey, setAwsAccessKey] = useState('');
  const [awsSecretKey, setAwsSecretKey] = useState('');
  const [awsRegion, setAwsRegion] = useState('');
  const [smtpHost, setSmtpHost] = useState('');
  const [smtpPort, setSmtpPort] = useState('');
  const [smtpUser, setSmtpUser] = useState('');
  const [smtpPassword, setSmtpPassword] = useState('');
  const [twilioSid, setTwilioSid] = useState('');
  const [twilioToken, setTwilioToken] = useState('');
  const [twilioFromNumber, setTwilioFromNumber] = useState('');
  const [teamsTenantId, setTeamsTenantId] = useState('');
  const [teamsClientId, setTeamsClientId] = useState('');
  const [teamsClientSecret, setTeamsClientSecret] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [isConnectingTeams, setIsConnectingTeams] = useState(false);
  const [providerStatuses, setProviderStatuses] = useState([]);

  const { showToast } = useToast();
  const { hasPermission } = useAuth();
  const canManageProviders = hasPermission('organization:providers:manage');

  const refreshProviderStatuses = useCallback(async () => {
    try {
      const response = await ApiClient.getOrganizationProviderConfigs();
      if (!response?.success) throw new Error(response?.message || 'Could not load provider status.');
      setProviderStatuses(Array.isArray(response.data) ? response.data : []);
    } catch (error) {
      console.error('Failed to load provider configuration status:', error);
      showToast('Could not load provider configuration status', 'error');
    }
  }, [showToast]);

  useEffect(() => {
    refreshProviderStatuses();
  }, [refreshProviderStatuses]);

  const handleSave = async (e) => {
    e.preventDefault();
    if (!canManageProviders) return;
    setIsSaving(true);

    let credentials = {};
    if (activeProvider === 'sendgrid') {
      credentials = { api_key: apiKey.trim(), from_email: fromEmail.trim() };
    } else if (activeProvider === 'ses') {
      credentials = {
        aws_access_key_id: awsAccessKey.trim(),
        aws_secret_access_key: awsSecretKey.trim(),
        aws_region: awsRegion.trim(),
        from_email: sesFromEmail.trim(),
      };
    } else if (activeProvider === 'smtp') {
      credentials = {
        smtp_host: smtpHost.trim(),
        smtp_port: parseInt(smtpPort, 10),
        smtp_user: smtpUser.trim(),
        smtp_password: smtpPassword,
        from_email: smtpFromEmail.trim(),
      };
    } else if (activeProvider === 'twilio') {
      credentials = { account_sid: twilioSid.trim(), auth_token: twilioToken.trim(), from_number: twilioFromNumber.trim() };
    } else if (activeProvider === 'teams') {
      credentials = {
        tenant_id: teamsTenantId.trim(),
        client_id: teamsClientId.trim(),
        client_secret: teamsClientSecret.trim(),
      };
    } else {
      setIsSaving(false);
      return;
    }

    try {
      const submittedCredentials = Object.fromEntries(
        Object.entries(credentials).filter(([, value]) => (
          value !== ''
          && value !== null
          && value !== undefined
          && !(typeof value === 'number' && Number.isNaN(value))
        ))
      );
      if (!Object.keys(submittedCredentials).length) {
        showToast('Enter at least one new or updated provider value.', 'error');
        return;
      }

      const res = await ApiClient.saveProviderConfig(activeProvider, submittedCredentials);
      if (res?.success) {
        showToast(`${activeProvider.toUpperCase()} provider configuration saved!`, 'success');
        setApiKey('');
        setAwsAccessKey('');
        setAwsSecretKey('');
        setSmtpUser('');
        setSmtpPassword('');
        setTwilioSid('');
        setTwilioToken('');
        setTwilioFromNumber('');
        setTeamsClientSecret('');
        await refreshProviderStatuses();
      } else {
        showToast(res?.message || 'Configuration save failed', 'error');
      }
    } catch (err) {
      showToast(err?.message || 'Error saving provider config', 'error');
    } finally {
      setIsSaving(false);
    }
  };

  const handleTeamsConnect = async () => {
    setIsConnectingTeams(true);
    try {
      const response = await ApiClient.getTeamsConnectUrl();
      if (!response?.success || !response.authorization_url) {
        throw new Error(response?.message || 'Could not start Microsoft Teams authorization.');
      }
      window.location.assign(response.authorization_url);
    } catch (error) {
      showToast(error?.message || 'Could not connect Microsoft Teams', 'error');
      setIsConnectingTeams(false);
    }
  };

  const activeStatus = providerStatuses.find((status) => status.provider === activeProvider);

  return (
    <GlassCard style={{ marginTop: '0.25rem' }}>
      <h4 style={{ fontSize: '1.05rem', marginBottom: '0.4rem', color: 'var(--text-primary)' }}>
        Channel Delivery Providers
      </h4>
      <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1.15rem' }}>
        Configure authenticated carrier APIs to route outbound notifications directly through your organization accounts.
      </p>
      <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
        Leave saved credential fields empty to keep their current values. New credentials are written only to SenderX’s encrypted backend store.
      </p>

      <div style={{ marginBottom: '1.25rem' }}>
        <GlassTabs
          activeKey={activeProvider}
          onChange={setActiveProvider}
          tabs={[
            { key: 'whatsapp', label: 'WhatsApp API' },
            { key: 'teams', label: 'Microsoft Teams' },
            { key: 'sendgrid', label: 'SendGrid Email' },
            { key: 'ses', label: 'Amazon SES' },
            { key: 'smtp', label: 'Custom SMTP' },
            { key: 'twilio', label: 'Twilio SMS' },
            { key: 'telegram', label: 'Telegram API' },
          ]}
        />
      </div>

      {activeProvider === 'whatsapp' ? (
        <Suspense fallback={<GlassSkeleton width="100%" height="180px" />}>
          <WhatsAppProviderConfig />
        </Suspense>
      ) : (
      <>
        <div className="saas-provider-status" role="status" style={{ display: 'flex', flexWrap: 'wrap', gap: '8px 14px', alignItems: 'center', marginBottom: '1rem', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
          <strong>{activeStatus?.configured ? 'Configuration saved' : 'Not configured'}</strong>
          <span>
            Last updated: {activeStatus?.updated_at && !Number.isNaN(new Date(activeStatus.updated_at).getTime())
              ? new Date(activeStatus.updated_at).toLocaleString()
              : 'Unavailable'}
          </span>
          <span>
            Saved credentials are encrypted by SenderX and are never returned to this screen.
          </span>
          <span>
            {activeProvider === 'teams'
              ? 'Complete Microsoft OAuth to authorize messaging; saved app credentials alone do not indicate a connected account.'
              : 'Saved configuration does not imply provider connectivity; live testing is unavailable for this provider.'}
          </span>
        </div>

        {activeProvider === 'telegram' ? (
          <div className="saas-empty-state">
            Telegram delivery currently uses the mock adapter only. Adding a bot token here would not enable live delivery.
          </div>
        ) : (
      <form onSubmit={handleSave}>
        <fieldset disabled={!canManageProviders || isSaving} style={{ border: 0, margin: 0, minWidth: 0, padding: 0 }}>
        {activeProvider === 'sendgrid' && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '1rem', marginBottom: '1rem' }}>
            <div className="form-group">
              <label>SendGrid API Key</label>
              <input
                type="password"
                className="form-control"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="SG.xxxxxxxxxxxx"
                required={!activeStatus?.configured}
              />
            </div>
            <div className="form-group">
              <label>Verified Sender Address</label>
              <input
                type="email"
                className="form-control"
                value={fromEmail}
                onChange={(e) => setFromEmail(e.target.value)}
                placeholder="notifications@tenant.com"
                required={!activeStatus?.configured}
              />
            </div>
          </div>
        )}

        {activeProvider === 'ses' && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem', marginBottom: '1rem' }}>
            <div className="form-group">
              <label>AWS Access Key ID</label>
              <input
                type="password"
                className="form-control"
                value={awsAccessKey}
                onChange={(e) => setAwsAccessKey(e.target.value)}
                placeholder="Enter access key ID"
                required={!activeStatus?.configured}
              />
            </div>
            <div className="form-group">
              <label>AWS Secret Access Key</label>
              <input
                type="password"
                className="form-control"
                value={awsSecretKey}
                onChange={(e) => setAwsSecretKey(e.target.value)}
                placeholder="Enter secret access key"
                required={!activeStatus?.configured}
              />
            </div>
            <div className="form-group">
              <label>SES Region</label>
              <input
                type="text"
                className="form-control"
                value={awsRegion}
                onChange={(e) => setAwsRegion(e.target.value)}
                placeholder="us-east-1"
              />
            </div>
            <div className="form-group">
              <label>Verified Sender Address</label>
              <input
                type="email"
                className="form-control"
                value={sesFromEmail}
                onChange={(e) => setSesFromEmail(e.target.value)}
                placeholder="notifications@tenant.com"
                required={!activeStatus?.configured}
              />
            </div>
          </div>
        )}

        {activeProvider === 'smtp' && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginBottom: '1rem' }}>
            <div className="form-group">
              <label>SMTP Host</label>
              <input
                type="text"
                className="form-control"
                value={smtpHost}
                onChange={(e) => setSmtpHost(e.target.value)}
                placeholder="smtp.mailgun.org"
                required={!activeStatus?.configured}
              />
            </div>
            <div className="form-group">
              <label>SMTP Port</label>
              <input
                type="text"
                className="form-control"
                value={smtpPort}
                onChange={(e) => setSmtpPort(e.target.value)}
                placeholder="587"
                inputMode="numeric"
              />
            </div>
            <div className="form-group">
              <label>Username</label>
              <input
                type="text"
                className="form-control"
                value={smtpUser}
                onChange={(e) => setSmtpUser(e.target.value)}
                placeholder="postmaster@tenant.com"
              />
            </div>
            <div className="form-group">
              <label>Password</label>
              <input
                type="password"
                className="form-control"
                value={smtpPassword}
                onChange={(e) => setSmtpPassword(e.target.value)}
                placeholder="••••••••"
              />
            </div>
            <div className="form-group">
              <label>Verified Sender Address</label>
              <input
                type="email"
                className="form-control"
                value={smtpFromEmail}
                onChange={(e) => setSmtpFromEmail(e.target.value)}
                placeholder="notifications@tenant.com"
                required={!activeStatus?.configured}
              />
            </div>
          </div>
        )}

        {activeProvider === 'twilio' && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem', marginBottom: '1rem' }}>
            <div className="form-group">
              <label>Twilio Account SID</label>
              <input
                type="password"
                className="form-control"
                value={twilioSid}
                onChange={(e) => setTwilioSid(e.target.value)}
                placeholder="ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
                required={!activeStatus?.configured}
              />
            </div>
            <div className="form-group">
              <label>Twilio Auth Token</label>
              <input
                type="password"
                className="form-control"
                value={twilioToken}
                onChange={(e) => setTwilioToken(e.target.value)}
                placeholder="••••••••"
                required={!activeStatus?.configured}
              />
            </div>
            <div className="form-group">
              <label>Origination Phone Number</label>
              <input
                type="text"
                className="form-control"
                value={twilioFromNumber}
                onChange={(e) => setTwilioFromNumber(e.target.value)}
                placeholder="+15551234567"
                required={!activeStatus?.configured}
              />
            </div>
          </div>
        )}

        {activeProvider === 'teams' && (
          <div>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
              Configure the Microsoft Entra application credentials, save them, then use the existing delegated OAuth flow to connect the organization.
            </p>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem', marginBottom: '1rem' }}>
              <div className="form-group">
                <label>Tenant ID</label>
                <input type="text" className="form-control" value={teamsTenantId} onChange={(e) => setTeamsTenantId(e.target.value)} required={!activeStatus?.configured} />
              </div>
              <div className="form-group">
                <label>Client ID</label>
                <input type="text" className="form-control" value={teamsClientId} onChange={(e) => setTeamsClientId(e.target.value)} required={!activeStatus?.configured} />
              </div>
              <div className="form-group">
                <label>Client Secret</label>
                <input type="password" className="form-control" value={teamsClientSecret} onChange={(e) => setTeamsClientSecret(e.target.value)} placeholder="Enter client secret" required={!activeStatus?.configured} />
              </div>
            </div>
          </div>
        )}
        </fieldset>

        {!canManageProviders && (
          <p className="saas-empty-state">You have read-only access to provider configuration.</p>
        )}

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem' }}>
        <GlassButton type="submit" variant="primary" disabled={isSaving || !canManageProviders}>
          {isSaving ? 'Saving Configuration...' : `Save ${activeProvider.toUpperCase()} Config`}
        </GlassButton>
        {activeProvider === 'teams' && (
          <GlassButton type="button" variant="secondary" disabled={isConnectingTeams || !canManageProviders || !activeStatus?.configured} onClick={handleTeamsConnect}>
            {isConnectingTeams ? 'Connecting...' : 'Connect Microsoft Teams'}
          </GlassButton>
        )}
        </div>
      </form>
        )}
      </>
      )}
    </GlassCard>
  );
}
