import React, { useState } from 'react';
import ApiClient from '../../services/api';
import { useToast } from '../../context/ToastContext';
import { GlassCard, GlassTabs, GlassButton } from '../glass';

export default function ProviderConfigSection() {
  const [activeProvider, setActiveProvider] = useState('sendgrid');
  const [apiKey, setApiKey] = useState('');
  const [fromEmail, setFromEmail] = useState('');
  const [awsAccessKey, setAwsAccessKey] = useState('');
  const [awsSecretKey, setAwsSecretKey] = useState('');
  const [awsRegion, setAwsRegion] = useState('us-east-1');
  const [smtpHost, setSmtpHost] = useState('');
  const [smtpPort, setSmtpPort] = useState('587');
  const [smtpUser, setSmtpUser] = useState('');
  const [smtpPassword, setSmtpPassword] = useState('');
  const [twilioSid, setTwilioSid] = useState('');
  const [twilioToken, setTwilioToken] = useState('');
  const [twilioFromNumber, setTwilioFromNumber] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  const { showToast } = useToast();

  const handleSave = async (e) => {
    e.preventDefault();
    setIsSaving(true);

    let credentials = {};
    if (activeProvider === 'sendgrid') {
      credentials = { api_key: apiKey.trim(), from_email: fromEmail.trim() };
    } else if (activeProvider === 'ses') {
      credentials = { access_key_id: awsAccessKey.trim(), secret_access_key: awsSecretKey.trim(), region: awsRegion };
    } else if (activeProvider === 'smtp') {
      credentials = { host: smtpHost.trim(), port: parseInt(smtpPort, 10), username: smtpUser.trim(), password: smtpPassword };
    } else if (activeProvider === 'twilio') {
      credentials = { account_sid: twilioSid.trim(), auth_token: twilioToken.trim(), from_number: twilioFromNumber.trim() };
    }

    try {
      const res = await ApiClient.saveProviderConfig(activeProvider, credentials);
      if (res?.success) {
        showToast(`${activeProvider.toUpperCase()} provider configuration saved!`, 'success');
      } else {
        showToast(res?.message || 'Configuration save failed', 'error');
      }
    } catch (err) {
      showToast(err?.message || 'Error saving provider config', 'error');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <GlassCard style={{ marginTop: '0.25rem' }}>
      <h4 style={{ fontSize: '1.05rem', marginBottom: '0.4rem', color: 'var(--text-primary)' }}>
        Channel Delivery Providers
      </h4>
      <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1.15rem' }}>
        Configure authenticated carrier APIs to route outbound notifications directly through your organization accounts.
      </p>

      {/* Provider Selector Tabs */}
      <div style={{ marginBottom: '1.25rem' }}>
        <GlassTabs
          activeKey={activeProvider}
          onChange={setActiveProvider}
          tabs={[
            { key: 'sendgrid', label: 'SendGrid Email' },
            { key: 'ses', label: 'Amazon SES' },
            { key: 'smtp', label: 'Custom SMTP' },
            { key: 'twilio', label: 'Twilio SMS' },
          ]}
        />
      </div>

      <form onSubmit={handleSave}>
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
              />
            </div>
          </div>
        )}

        {activeProvider === 'ses' && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem', marginBottom: '1rem' }}>
            <div className="form-group">
              <label>AWS Access Key ID</label>
              <input
                type="text"
                className="form-control"
                value={awsAccessKey}
                onChange={(e) => setAwsAccessKey(e.target.value)}
                placeholder="AKIAIOSFODNN7EXAMPLE"
              />
            </div>
            <div className="form-group">
              <label>AWS Secret Access Key</label>
              <input
                type="password"
                className="form-control"
                value={awsSecretKey}
                onChange={(e) => setAwsSecretKey(e.target.value)}
                placeholder="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
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
          </div>
        )}

        {activeProvider === 'twilio' && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem', marginBottom: '1rem' }}>
            <div className="form-group">
              <label>Twilio Account SID</label>
              <input
                type="text"
                className="form-control"
                value={twilioSid}
                onChange={(e) => setTwilioSid(e.target.value)}
                placeholder="ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
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
              />
            </div>
          </div>
        )}

        <GlassButton type="submit" variant="primary" disabled={isSaving}>
          {isSaving ? 'Saving Configuration...' : `Save ${activeProvider.toUpperCase()} Config`}
        </GlassButton>
      </form>
    </GlassCard>
  );
}
