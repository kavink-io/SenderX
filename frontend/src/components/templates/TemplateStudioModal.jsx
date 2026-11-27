import React, { useState, useEffect, useCallback } from 'react';
import Modal from '../common/Modal';
import ApiClient from '../../services/api';
import { useToast } from '../../context/ToastContext';
import { GlassTabs, GlassButton, GlassSelect } from '../glass';

const DEFAULT_VARIABLES = [
  { label: 'User Name', name: 'name', type: 'text', tag: '{{ name }}' },
  { label: 'Company', name: 'company', type: 'text', tag: '{{ company }}' },
  { label: 'Email', name: 'email', type: 'text', tag: '{{ email }}' },
  { label: 'Activation Link', name: 'activation_link', type: 'url', tag: '{{ activation_link }}' },
  { label: 'Unsubscribe', name: 'unsubscribe_link', type: 'url', tag: '{{ unsubscribe_link }}' },
  { label: 'Current Year', name: 'current_year', type: 'text', tag: '{{ current_year }}' },
];

const BUILTIN_VAR_META = DEFAULT_VARIABLES.reduce((acc, item) => {
  acc[item.name] = { name: item.name, type: item.type, required: true };
  return acc;
}, {});

function extractTemplateVarNames(...texts) {
  const found = new Set();
  const pattern = /\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)(?:\s*\|[^}]+)?\s*\}\}/g;
  for (const text of texts) {
    if (!text) continue;
    pattern.lastIndex = 0;
    let match;
    while ((match = pattern.exec(text)) !== null) {
      found.add(match[1]);
    }
  }
  return Array.from(found);
}

function buildDeclaredVariables(subjectText, htmlText, cssText, existingVars = []) {
  const varMap = new Map();

  for (const v of existingVars || []) {
    if (v && typeof v === 'object' && v.name) {
      varMap.set(v.name, { ...v });
    }
  }

  const detectedNames = extractTemplateVarNames(subjectText, htmlText, cssText);
  for (const varName of detectedNames) {
    if (!varMap.has(varName)) {
      const preset = BUILTIN_VAR_META[varName];
      varMap.set(varName, {
        name: varName,
        type: preset?.type || (varName.endsWith('_url') || varName.endsWith('_link') ? 'url' : 'text'),
        required: preset?.required ?? false,
      });
    }
  }

  return Array.from(varMap.values());
}

export default function TemplateStudioModal({ isOpen, onClose, template, onSaved }) {
  const [activeTab, setActiveTab] = useState('HTML'); // 'HTML' or 'CSS'
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [subject, setSubject] = useState('');
  const [category, setCategory] = useState('marketing');
  const [htmlContent, setHtmlContent] = useState('');
  const [cssContent, setCssContent] = useState('');
  const [declaredVars, setDeclaredVars] = useState([]);
  const [previewHtml, setPreviewHtml] = useState('');
  const [validationResult, setValidationResult] = useState(null);
  const [saveError, setSaveError] = useState('');
  const [savingAction, setSavingAction] = useState(null); // null | 'draft' | 'publish'
  const [isValidating, setIsValidating] = useState(false);
  const [previewMode, setPreviewMode] = useState('desktop'); // 'desktop' | 'mobile'

  const { showToast } = useToast();
  const [availableVars, setAvailableVars] = useState(DEFAULT_VARIABLES);

  const hydrateFromTemplate = useCallback((tmpl) => {
    if (tmpl) {
      setName(tmpl.name || '');
      setDescription(tmpl.description || '');
      setSubject(tmpl.subject || '');
      setCategory(tmpl.category || 'marketing');
      setHtmlContent(tmpl.html_body || tmpl.html_content || tmpl.html || '');
      setCssContent(tmpl.css || tmpl.css_content || '');

      const savedVars = Array.isArray(tmpl.variables) ? tmpl.variables : [];
      setDeclaredVars(savedVars);

      // Merge any custom saved variables into pill bar
      const known = new Set(DEFAULT_VARIABLES.map((v) => v.name));
      const extras = savedVars
        .filter((v) => v?.name && !known.has(v.name))
        .map((v) => ({
          label: v.name,
          name: v.name,
          type: v.type || 'text',
          tag: `{{ ${v.name} }}`,
        }));
      setAvailableVars([...DEFAULT_VARIABLES, ...extras]);
    } else {
      setName('');
      setDescription('');
      setSubject('');
      setCategory('marketing');
      setHtmlContent('');
      setCssContent('');
      setDeclaredVars([]);
      setAvailableVars(DEFAULT_VARIABLES);
    }
    setActiveTab('HTML');
    setValidationResult(null);
    setSaveError('');
    setSavingAction(null);
  }, []);

  useEffect(() => {
    if (isOpen) {
      hydrateFromTemplate(template);
    }
  }, [template, isOpen, hydrateFromTemplate]);

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

  const handleLoadStarter = async () => {
    setSaveError('');
    try {
      const res = await ApiClient.getStarterLayout();
      if (res?.success && res.data) {
        setHtmlContent(res.data.html || res.data.html_body || res.data.html_content || '');
        setCssContent(res.data.css || res.data.css_content || '');
        if (res.data.subject) setSubject(res.data.subject);
        if (Array.isArray(res.data.variables)) {
          setDeclaredVars((prev) => {
            const byName = new Map(prev.map((v) => [v.name, v]));
            for (const sv of res.data.variables) {
              if (sv?.name) byName.set(sv.name, sv);
            }
            return Array.from(byName.values());
          });
        }
        showToast('Starter layout applied!', 'success');
      } else {
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
    setSaveError('');
    try {
      const variablesPayload = buildDeclaredVariables(subject, htmlContent, cssContent, declaredVars);
      const res = await ApiClient.validateTemplate({
        name: name.trim() || 'Draft Template',
        subject: subject.trim() || 'Subject',
        html_body: htmlContent,
        css: cssContent,
        variables: variablesPayload,
      });

      if (res?.success && res.data) {
        const isValid = Boolean(res.data.valid ?? res.data.isValid);
        const errors = Array.isArray(res.data.errors) ? res.data.errors : [];
        const warnings = Array.isArray(res.data.warnings) ? res.data.warnings : [];

        if (isValid) {
          const warnNote = warnings.length > 0 ? ` (${warnings.length} compatibility warning${warnings.length > 1 ? 's' : ''})` : '';
          setValidationResult({
            valid: true,
            message: `Template syntax and CSS properties are safe & valid.${warnNote}`,
          });
          showToast('Template is safe and valid!', 'success');
        } else {
          const errMsg = errors.length > 0 ? errors.join('; ') : 'Validation failed.';
          setValidationResult({ valid: false, message: errMsg });
          showToast(errMsg, 'error');
        }
      } else {
        const msg = res?.message || 'Validation failed.';
        setValidationResult({ valid: false, message: msg });
        showToast(msg, 'error');
      }
    } catch (err) {
      const msg = err?.message || 'Error executing validation';
      setValidationResult({ valid: false, message: msg });
      showToast(msg, 'error');
    } finally {
      setIsValidating(false);
    }
  };

  const handleSave = async (publish = false) => {
    setSaveError('');
    const trimmedName = name.trim();
    const trimmedSubject = subject.trim();
    const trimmedHtml = htmlContent.trim();

    if (!trimmedName || trimmedName.length < 2 || trimmedName.length > 80) {
      const msg = 'Template name is required (2-80 characters)';
      setSaveError(msg);
      showToast(msg, 'error');
      return;
    }
    if (!trimmedSubject) {
      const msg = 'Email subject is required';
      setSaveError(msg);
      showToast(msg, 'error');
      return;
    }
    if (!trimmedHtml) {
      const msg = 'HTML content is required';
      setSaveError(msg);
      showToast(msg, 'error');
      return;
    }

    setSavingAction(publish ? 'publish' : 'draft');
    try {
      const variablesPayload = buildDeclaredVariables(trimmedSubject, htmlContent, cssContent, declaredVars);

      const payload = {
        name: trimmedName,
        description: description.trim(),
        subject: trimmedSubject,
        category: category || 'marketing',
        channel: 'email',
        html_body: htmlContent,
        css: cssContent,
        variables: variablesPayload,
        status: publish ? 'PUBLISHED' : 'DRAFT',
      };

      const tid = template?.template_id || template?._id || template?.id;
      const res = tid
        ? await ApiClient.updateTemplate(tid, payload)
        : await ApiClient.createTemplate(payload);

      if (res?.success) {
        showToast(
          publish ? 'Template saved & published successfully!' : 'Template saved as draft successfully!',
          'success'
        );
        if (onSaved) await onSaved(res.data);
        onClose();
      } else {
        const errMsg = res?.message || 'Failed to save template';
        setSaveError(errMsg);
        showToast(errMsg, 'error');
      }
    } catch (err) {
      const errMsg = err?.message || 'Error saving template';
      setSaveError(errMsg);
      showToast(errMsg, 'error');
    } finally {
      setSavingAction(null);
    }
  };

  const isSaving = savingAction !== null;
  const standardCategories = ['transactional', 'marketing', 'system', 'general'];
  const hasCustomCategory = category && !standardCategories.includes(category);

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={
        template
          ? `Edit Template: ${template.name}${template.status ? ` (${template.status})` : ''}`
          : 'Email Template Studio'
      }
      maxWidth="min(1200px, 94vw)"
      size="xl"
      id="modal-template-editor"
    >
      {saveError && (
        <div
          role="alert"
          style={{
            marginBottom: '1rem',
            padding: '0.65rem 0.9rem',
            borderRadius: '6px',
            fontSize: '0.85rem',
            background: 'rgba(255, 100, 124, 0.1)',
            border: '1px solid var(--status-error)',
            color: 'var(--status-error)',
          }}
        >
          {saveError}
        </div>
      )}

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
          <GlassSelect
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            aria-label="Template category"
          >
            <option value="transactional">Transactional</option>
            <option value="marketing">Marketing</option>
            <option value="system">System / Alert</option>
            <option value="general">General</option>
            {hasCustomCategory && <option value={category}>{category}</option>}
          </GlassSelect>
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
        {/* Left Side: Code Editor with Glass Toolbar & Floating Variables */}
        <div style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <div className="lg-studio-toolbar">
            <GlassTabs
              activeKey={activeTab}
              onChange={setActiveTab}
              tabs={[
                { key: 'HTML', id: 'btn-tab-html', label: 'HTML Source' },
                { key: 'CSS', id: 'btn-tab-css', label: 'CSS Stylesheet' },
              ]}
            />
            <GlassButton
              variant="secondary"
              size="sm"
              onClick={handleLoadStarter}
              title="Replace with clean, responsive starter layout"
            >
              Start from starter layout
            </GlassButton>
          </div>

          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: '210px' }}>
            {activeTab === 'HTML' ? (
              <textarea
                className="form-control lg-studio-editor"
                value={htmlContent}
                onChange={(e) => setHtmlContent(e.target.value)}
                placeholder="<div class='email-wrapper'><h1>Hello {{ name }}</h1></div>"
                style={{ flex: 1, resize: 'none' }}
              />
            ) : (
              <textarea
                className="form-control lg-studio-editor"
                value={cssContent}
                onChange={(e) => setCssContent(e.target.value)}
                placeholder=".email-wrapper { font-family: sans-serif; max-width: 600px; }"
                style={{ flex: 1, resize: 'none' }}
              />
            )}
          </div>

          {/* Floating Dynamic Variables Pill Bar */}
          <div className="lg-glass-inset" style={{ marginTop: '0.65rem', padding: '0.6rem 0.75rem' }}>
            <div style={{ fontSize: '0.73rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '6px' }}>
              Insert Variables:
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', maxHeight: '64px', overflowY: 'auto' }}>
              {availableVars.map((v, i) => (
                <button
                  key={i}
                  type="button"
                  className="badge badge-scope"
                  style={{ cursor: 'pointer', padding: '4px 9px' }}
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
        <div style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <div className="lg-studio-toolbar">
            <span style={{ fontSize: '0.84rem', fontWeight: 600, color: 'var(--text-primary)' }}>
              Live Sandboxed Preview
            </span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <GlassTabs
                activeKey={previewMode}
                onChange={setPreviewMode}
                tabs={[
                  { key: 'desktop', label: 'Desktop' },
                  { key: 'mobile', label: 'Mobile' },
                ]}
              />
              <GlassButton
                variant="secondary"
                size="sm"
                onClick={handleValidate}
                disabled={isValidating || isSaving}
              >
                {isValidating ? 'Validating...' : 'Validate Markup'}
              </GlassButton>
            </div>
          </div>

          <div className="lg-studio-preview-shell">
            <iframe
              title="Studio Preview"
              className="lg-studio-preview-frame"
              srcDoc={previewHtml || '<p style="padding: 2rem; color: #888; font-family: sans-serif;">Start typing HTML to see live rendering...</p>'}
              sandbox=""
              style={{ maxWidth: previewMode === 'mobile' ? '375px' : '100%' }}
            />
          </div>

          {validationResult && (
            <div
              className="lg-glass-inset"
              style={{
                marginTop: '0.6rem',
                padding: '0.6rem 0.85rem',
                fontSize: '0.8rem',
                background: validationResult.valid ? 'rgba(53, 214, 160, 0.12)' : 'rgba(255, 100, 124, 0.12)',
                borderColor: validationResult.valid ? 'rgba(53, 214, 160, 0.35)' : 'rgba(255, 100, 124, 0.35)',
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
            id="btn-save-draft"
            className="btn btn-secondary"
            onClick={() => handleSave(false)}
            disabled={isSaving}
          >
            {savingAction === 'draft' ? 'Saving...' : 'Save Draft'}
          </button>
          <button
            type="button"
            id="btn-save-publish"
            className="btn btn-primary"
            onClick={() => handleSave(true)}
            disabled={isSaving}
          >
            {savingAction === 'publish' ? 'Publishing...' : 'Save & Publish'}
          </button>
        </div>
      </div>
    </Modal>
  );
}
