import React, { useState, useEffect } from 'react';
import ApiClient from '../../services/api';
import MediaSelectorModal from '../modals/MediaSelectorModal';
import { useToast } from '../../context/ToastContext';
import { useAppScope } from '../../context/ScopeContext';
import { GlassCard, GlassTabs, GlassButton, GlassBadge, GlassSelect } from '../glass';

export default function MessageComposer({ onMessageSent }) {
  const [channel, setChannel] = useState('email');
  const [recipient, setRecipient] = useState('');
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [selectedTemplate, setSelectedTemplate] = useState('');
  const [templates, setTemplates] = useState([]);
  const [selectedMedia, setSelectedMedia] = useState(null);
  const [isMediaModalOpen, setIsMediaModalOpen] = useState(false);
  const [isSending, setIsSending] = useState(false);

  const { showToast } = useToast();
  const { activeAppId } = useAppScope();

  useEffect(() => {
    async function fetchTemplates() {
      if (channel !== 'email') return;
      try {
        const res = await ApiClient.listTemplates(1, 50, { status: 'PUBLISHED' });
        if (res?.success) {
          setTemplates(res.data?.items || res.items || []);
        }
      } catch (err) {
        console.warn('Could not load templates for composer:', err);
      }
    }
    fetchTemplates();
  }, [channel]);

  const handleSend = async (e) => {
    e.preventDefault();
    if (!recipient.trim()) {
      showToast('Recipient is required', 'error');
      return;
    }
    if (channel === 'email' && !subject.trim() && !selectedTemplate) {
      showToast('Email subject is required', 'error');
      return;
    }
    if (!body.trim() && !selectedTemplate) {
      showToast('Message body is required', 'error');
      return;
    }

    setIsSending(true);
    try {
      const payload = {
        channel,
        recipient: recipient.trim(),
        subject: channel === 'email' ? subject.trim() : undefined,
        body: body.trim() || undefined,
        template_id: selectedTemplate || undefined,
        application_id: activeAppId || undefined,
        attachments: selectedMedia ? [selectedMedia.media_id || selectedMedia.url] : undefined,
      };

      const res = await ApiClient.createMessage(payload);
      if (res?.success) {
        showToast('Message created and queued for delivery!', 'success');
        setRecipient('');
        setSubject('');
        setBody('');
        setSelectedTemplate('');
        setSelectedMedia(null);
        if (onMessageSent) onMessageSent();
      } else {
        showToast(res?.message || 'Failed to dispatch message', 'error');
      }
    } catch (err) {
      showToast(err?.message || 'Error dispatching message', 'error');
    } finally {
      setIsSending(false);
    }
  };

  return (
    <GlassCard style={{ marginBottom: '1.35rem' }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: '12px', marginBottom: '1.1rem' }}>
        <h3 style={{ fontSize: '1.05rem', margin: 0, color: 'var(--text-primary)' }}>
          Direct Message Composer
        </h3>
        <GlassTabs
          activeKey={channel}
          onChange={setChannel}
          tabs={[
            { key: 'email', label: 'Email' },
            { key: 'sms', label: 'SMS' },
            { key: 'whatsapp', label: 'WhatsApp' },
          ]}
        />
      </div>

      <form onSubmit={handleSend}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem', marginBottom: '1rem' }}>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label>Recipient Address / Phone *</label>
            <input
              type="text"
              className="form-control"
              value={recipient}
              onChange={(e) => setRecipient(e.target.value)}
              placeholder={channel === 'email' ? 'user@example.com' : '+1555019988'}
              required
            />
          </div>

          {channel === 'email' && (
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label>Published Template (Optional)</label>
              <GlassSelect
                value={selectedTemplate}
                onChange={(e) => setSelectedTemplate(e.target.value)}
                aria-label="Published Template"
              >
                <option value="">None (Custom HTML/Text)</option>
                {templates.map((t) => (
                  <option key={t.template_id || t._id} value={t.template_id || t._id}>
                    {t.name} (v{t.version || 1})
                  </option>
                ))}
              </GlassSelect>
            </div>
          )}
        </div>

        {channel === 'email' && !selectedTemplate && (
          <div className="form-group" style={{ marginBottom: '1rem' }}>
            <label>Email Subject *</label>
            <input
              type="text"
              className="form-control"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="Important Account Notification"
              required={!selectedTemplate}
            />
          </div>
        )}

        {!selectedTemplate && (
          <div className="form-group" style={{ marginBottom: '1rem' }}>
            <label>Message Content / Body *</label>
            <textarea
              className="form-control"
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder="Enter message body..."
              rows={4}
              required={!selectedTemplate}
            />
          </div>
        )}

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '1rem' }}>
          <div>
            {selectedMedia ? (
              <GlassBadge tone="info" style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                Attachment: {selectedMedia.filename || 'Selected'}
                <button
                  type="button"
                  onClick={() => setSelectedMedia(null)}
                  style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', padding: 0 }}
                >
                  &times;
                </button>
              </GlassBadge>
            ) : (
              <GlassButton
                variant="secondary"
                size="sm"
                onClick={() => setIsMediaModalOpen(true)}
              >
                + Attach Media
              </GlassButton>
            )}
          </div>

          <GlassButton
            type="submit"
            variant="primary"
            disabled={isSending}
          >
            {isSending ? 'Dispatching...' : 'Dispatch Message'}
          </GlassButton>
        </div>
      </form>

      <MediaSelectorModal
        isOpen={isMediaModalOpen}
        onClose={() => setIsMediaModalOpen(false)}
        onSelectMedia={(media) => setSelectedMedia(media)}
      />
    </GlassCard>
  );
}
