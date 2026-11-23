import React, { useState, useEffect } from 'react';
import Modal from '../common/Modal';
import ApiClient from '../../services/api';
import { useToast } from '../../context/ToastContext';

export default function TemplateStudioModal({ isOpen, onClose, template, onSaved }) {
  const [activeTab, setActiveTab] = useState('HTML'); // 'HTML' or 'CSS'
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [subject, setSubject] = useState('');
  const [category, setCategory] = useState('marketing');
  const [htmlContent, setHtmlContent] = useState('');
  const [cssContent, setCssContent] = useState('');
  const [previewHtml, setPreviewHtml] = useState('');
  const [validationResult, setValidationResult] = useState(null);
  const [customVarName, setCustomVarName] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [isValidating, setIsValidating] = useState(false);

  const { showToast } = useToast();

  const DEFAULT_VARIABLES = [
    { label: 'User Name', tag: '{{ name }}' },
    { label: 'Company', tag: '{{ company }}' },
    { label: 'Email', tag: '{{ email }}' },
    { label: 'Activation Link', tag: '{{ activation_link }}' },
    { label: 'Unsubscribe', tag: '{{ unsubscribe_link }}' },
    { label: 'Current Year', tag: '{{ current_year }}' },
  ];

  const [availableVars, setAvailableVars] = useState(DEFAULT_VARIABLES);

  useEffect(() => {
    if (template) {
      setName(template.name || '');
      setDescription(template.description || '');
      setSubject(template.subject || '');
      setCategory(template.category || 'marketing');
      setHtmlContent(template.html_content || template.html || '');
      setCssContent(template.css_content || template.css || '');
      setPreviewHtml(template.html_content || template.html || '');
    } else {
      setName('');
      setDescription('');
      setSubject('');
      setCategory('marketing');
      setHtmlContent('');
      setCssContent('');
      setPreviewHtml('');
    }
    setValidationResult(null);
  }, [template, isOpen]);

  // Update live preview when HTML or CSS changes
  useEffect(() => {
    const combined = cssContent
      ? `<style>${cssContent}</style>\n${htmlContent}`
      : htmlContent;
    setPreviewHtml(combined);
  }, [htmlContent, cssContent]);

  const handleInsertVariable = (tag) => {
    setHtmlContent((prev) => prev + tag);
    showToast(`Inserted ${tag}`, 'info');
  };

  const handleAddCustomVar = (e) => {
    e.preventDefault();
    if (!customVarName.trim()) return;
    const tag = `{{ ${customVarName.trim().replace(/[^a-zA-Z0-9_]/g, '_')} }}`;
    setAvailableVars((prev) => [...prev, { label: customVarName.trim(), tag }]);
    setCustomVarName('');
    showToast(`Added variable ${tag}`, 'success');
  };

  const handleLoadStarter = async () => {
    try {
      const res = await ApiClient.getStarterLayout();
      if (res?.success && res.data) {
        setHtmlContent(res.data.html || res.data.html_content || '');
        setCssContent(res.data.css || res.data.css_content || '');
        if (res.data.subject) setSubject(res.data.subject);
        showToast('Starter layout applied!', 'success');
      } else {
        // Fallback starter layout
        setHtmlContent(`<div class="email-container">
  <h1>Welcome to {{ company }}!</h1>
  <p>Hi {{ name }},</p>
  <p>Thank you for creating an account with us. Please confirm your email address below:</p>
  <a href="{{ activation_link }}" class="button">Activate My Account</a>
  <p>If you have any questions, reply directly to this email.</p>
</div>`);
        setCssContent(`.email-container {
  font-family: Arial, sans-serif;
  max-width: 600px;
  margin: 0 auto;
  padding: 24px;
  background: #ffffff;
  color: #333333;
}
.button {
  display: inline-block;
  padding: 12px 24px;
  background-color: #2563eb;
  color: #ffffff !important;
  text-decoration: none;
  border-radius: 6px;
  margin: 16px 0;
}`);
        showToast('Starter layout applied!', 'success');
      }
    } catch (e) {
      showToast('Could not fetch starter layout', 'warning');
    }
  };

  const handleValidate = async () => {
    setIsValidating(true);
    try {
      const res = await ApiClient.validateTemplate({
        name: name.trim() || 'Draft Template',
        subject: subject.trim() || 'Subject',
        html_content: htmlContent,
        css_content: cssContent,
      });

      if (res?.success) {
        setValidationResult({ valid: true, message: 'Template syntax and CSS properties are safe & valid.' });
        showToast('Template is safe and valid!', 'success');
      } else {
        setValidationResult({ valid: false, message: res?.message || 'Validation failed.' });
        showToast(res?.message || 'Template has validation errors', 'error');
      }
    } catch (err) {
      setValidationResult({ valid: false, message: err?.message || 'Error executing validation' });
      showToast(err?.message || 'Validation failed', 'error');
    } finally {
      setIsValidating(false);
    }
  };

  const handleSave = async (publish = false) => {
    if (!name.trim()) {
      showToast('Template name is required (2-80 characters)', 'error');
      return;
    }
    if (!subject.trim()) {
      showToast('Email subject is required', 'error');
      return;
    }
    if (!htmlContent.trim()) {
      showToast('HTML content is required', 'error');
      return;
    }

    setIsSaving(true);
    try {
      const payload = {
        name: name.trim(),
        description: description.trim(),
        subject: subject.trim(),
        category,
        html_content: htmlContent,
        css_content: cssContent,
        status: publish ? 'PUBLISHED' : 'DRAFT',
      };

      const tid = template?.template_id || template?._id || template?.id;
      const res = tid
        ? await ApiClient.updateTemplate(tid, payload)
        : await ApiClient.createTemplate(payload);

      if (res?.success) {
        showToast(`Template ${publish ? 'published' : 'saved as draft'} successfully!`, 'success');
        onSaved();
        onClose();
      } else {
        showToast(res?.message || 'Failed to save template', 'error');
      }
    } catch (err) {
      showToast(err?.message || 'Error saving template', 'error');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={template ? `Edit Template: ${template.name}` : 'Email Template Studio'}
      maxWidth="min(1200px, 94vw)"
      id="modal-template-editor"
    >
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginBottom: '1rem' }}>
        <div className="form-group">
          <label>Template Name *</label>
          <input
            type="text"
            className="form-control"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g., Enterprise Order Confirmation"
            required
          />
        </div>

        <div className="form-group">
          <label>Email Subject *</label>
          <input
            type="text"
            className="form-control"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            placeholder="Your order has shipped! (supports {{ name }})"
            required
          />
        </div>

        <div className="form-group">
          <label>Category</label>
          <select
            className="form-control"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
          >
            <option value="transactional">Transactional</option>
            <option value="marketing">Marketing</option>
            <option value="system">System / Alert</option>
          </select>
        </div>
      </div>

      {/* Editor & Preview Split View */}
      <div
        className="studio-split-view"
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))',
          gap: '1rem',
          minHeight: '360px',
          maxHeight: '52vh',
          marginBottom: '1rem',
        }}
      >
        {/* Left Side: Code Editor with Tabs & Variables */}
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
            <div style={{ display: 'flex', gap: '6px' }}>
              <button
                type="button"
                id="btn-tab-html"
                className={`btn btn-sm ${activeTab === 'HTML' ? 'btn-primary' : 'btn-secondary'}`}
                onClick={() => setActiveTab('HTML')}
              >
                HTML Source
              </button>
              <button
                type="button"
                id="btn-tab-css"
                className={`btn btn-sm ${activeTab === 'CSS' ? 'btn-primary' : 'btn-secondary'}`}
                onClick={() => setActiveTab('CSS')}
              >
                CSS Stylesheet
              </button>
            </div>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={handleLoadStarter}
              title="Replace with clean, responsive starter layout"
            >
              Start from starter layout
            </button>
          </div>

          <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
            {activeTab === 'HTML' ? (
              <textarea
                className="form-control"
                value={htmlContent}
                onChange={(e) => setHtmlContent(e.target.value)}
                placeholder="<div class='email-wrapper'><h1>Hello {{ name }}</h1></div>"
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: '0.8rem',
                  flex: 1,
                  resize: 'none',
                  background: 'var(--bg-main)',
                }}
              />
            ) : (
              <textarea
                className="form-control"
                value={cssContent}
                onChange={(e) => setCssContent(e.target.value)}
                placeholder=".email-wrapper { font-family: sans-serif; max-width: 600px; }"
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: '0.8rem',
                  flex: 1,
                  resize: 'none',
                  background: 'var(--bg-main)',
                }}
              />
            )}
          </div>

          {/* Dynamic Variables Pill Bar */}
          <div style={{ marginTop: '0.5rem', background: 'var(--bg-surface)', padding: '0.5rem', borderRadius: '6px' }}>
            <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '4px' }}>
              Insert Variables:
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', maxHeight: '60px', overflowY: 'auto' }}>
              {availableVars.map((v, i) => (
                <button
                  key={i}
                  type="button"
                  className="badge badge-scope"
                  style={{ cursor: 'pointer', border: 'none', padding: '3px 8px' }}
                  onClick={() => handleInsertVariable(v.tag)}
                  title={`Click to append ${v.tag}`}
                >
                  {v.label} ({v.tag})
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Right Side: Live Sandboxed Iframe Preview */}
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
            <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)' }}>
              Live Sandboxed Preview
            </span>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={handleValidate}
              disabled={isValidating}
            >
              {isValidating ? 'Validating...' : 'Validate Markup'}
            </button>
          </div>

          <div style={{ flex: 1, border: '1px solid var(--glass-border)', borderRadius: '6px', overflow: 'hidden', background: '#ffffff' }}>
            <iframe
              title="Studio Preview"
              srcDoc={previewHtml || '<p style="padding: 2rem; color: #888; font-family: sans-serif;">Start typing HTML to see live rendering...</p>'}
              sandbox=""
              style={{ width: '100%', height: '100%', border: 'none' }}
            />
          </div>

          {validationResult && (
            <div
              style={{
                marginTop: '0.5rem',
                padding: '0.5rem 0.75rem',
                borderRadius: '6px',
                fontSize: '0.8rem',
                background: validationResult.valid ? 'rgba(53, 214, 160, 0.1)' : 'rgba(255, 100, 124, 0.1)',
                border: `1px solid ${validationResult.valid ? 'var(--status-success)' : 'var(--status-error)'}`,
                color: validationResult.valid ? 'var(--status-success)' : 'var(--status-error)',
              }}
            >
              {validationResult.valid ? '✓ ' : '✕ '} {validationResult.message}
            </div>
          )}
        </div>
      </div>

      {/* Footer Actions */}
      <div className="modal-actions" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <button type="button" className="btn btn-secondary" onClick={onClose} disabled={isSaving}>
          Cancel
        </button>

        <div style={{ display: 'flex', gap: '10px' }}>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => handleSave(false)}
            disabled={isSaving}
          >
            {isSaving ? 'Saving...' : 'Save Draft'}
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => handleSave(true)}
            disabled={isSaving}
          >
            {isSaving ? 'Publishing...' : 'Save & Publish'}
          </button>
        </div>
      </div>
    </Modal>
  );
}
