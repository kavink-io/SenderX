import React, { useState, useEffect, useCallback } from 'react';
import ApiClient from '../../services/api';
import TemplateStudioModal from '../../components/templates/TemplateStudioModal';
import TemplatePreviewModal from '../../components/modals/TemplatePreviewModal';
import TemplateVersionsModal from '../../components/modals/TemplateVersionsModal';
import { useToast } from '../../context/ToastContext';
import { useAuth } from '../../context/AuthContext';

export default function TemplatesPage() {
  const [templates, setTemplates] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [search, setSearch] = useState('');
  const [isLoading, setIsLoading] = useState(true);

  const [isStudioOpen, setIsStudioOpen] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState(null);
  const [previewTemplate, setPreviewTemplate] = useState(null);
  const [versionsTemplate, setVersionsTemplate] = useState(null);

  const { showToast } = useToast();
  const { hasPermission } = useAuth();
  const canManage = hasPermission('organization:templates:read');

  const fetchTemplates = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await ApiClient.listTemplates(page, 20, {
        status: statusFilter !== 'ALL' ? statusFilter : undefined,
        search: search.trim() || undefined,
      });

      if (res?.success) {
        setTemplates(res.data?.items || []);
        setTotalCount(res.data?.total || 0);
      }
    } catch (err) {
      console.error('Failed to load templates:', err);
      showToast('Could not load email templates', 'error');
    } finally {
      setIsLoading(false);
    }
  }, [page, statusFilter, search, showToast]);

  useEffect(() => {
    fetchTemplates();
  }, [fetchTemplates]);

  const handlePublish = async (t) => {
    const tid = t.template_id || t._id || t.id;
    try {
      const res = await ApiClient.publishTemplate(tid);
      if (res?.success) {
        showToast('Template published successfully!', 'success');
        fetchTemplates();
      } else {
        showToast(res?.message || 'Publishing failed', 'error');
      }
    } catch (err) {
      showToast(err?.message || 'Error publishing template', 'error');
    }
  };

  const handleArchive = async (t) => {
    const tid = t.template_id || t._id || t.id;
    try {
      const res = await ApiClient.archiveTemplate(tid);
      if (res?.success) {
        showToast('Template archived', 'info');
        fetchTemplates();
      } else {
        showToast(res?.message || 'Archive failed', 'error');
      }
    } catch (err) {
      showToast(err?.message || 'Error archiving template', 'error');
    }
  };

  const handleDuplicate = async (t) => {
    const tid = t.template_id || t._id || t.id;
    try {
      const res = await ApiClient.duplicateTemplate(tid);
      if (res?.success) {
        showToast('Template duplicated as draft!', 'success');
        fetchTemplates();
      } else {
        showToast(res?.message || 'Duplication failed', 'error');
      }
    } catch (err) {
      showToast(err?.message || 'Error duplicating template', 'error');
    }
  };

  const handleDelete = async (t) => {
    const tid = t.template_id || t._id || t.id;
    if (!window.confirm(`Delete template "${t.name}"?`)) return;

    try {
      const res = await ApiClient.deleteTemplate(tid);
      if (res?.success) {
        showToast('Template deleted', 'info');
        fetchTemplates();
      } else {
        showToast(res?.message || 'Deletion failed', 'error');
      }
    } catch (err) {
      showToast(err?.message || 'Error deleting template', 'error');
    }
  };

  return (
    <div className="tab-pane active" id="tab-org-templates">
      {/* Action and Filter Header */}
      <div className="card" style={{ marginBottom: '1.5rem', padding: '1rem 1.25rem' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1rem', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center', flex: 1, minWidth: '260px' }}>
            <input
              type="text"
              className="form-control"
              placeholder="Search templates by name..."
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              style={{ maxWidth: '280px' }}
            />
            <select
              className="form-control"
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setPage(1);
              }}
              style={{ maxWidth: '140px' }}
            >
              <option value="ALL">All Statuses</option>
              <option value="DRAFT">Draft</option>
              <option value="PUBLISHED">Published</option>
              <option value="ARCHIVED">Archived</option>
            </select>
          </div>

          <button
            type="button"
            className="btn btn-primary"
            onClick={() => {
              setEditingTemplate(null);
              setIsStudioOpen(true);
            }}
            id="btn-open-template-studio"
          >
            + New Template
          </button>
        </div>
      </div>

      {/* Templates Table */}
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div className="table-responsive-wrapper">
          <table className="data-table" style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                <th>Template Name</th>
                <th>Subject</th>
                <th>Status</th>
                <th>Version</th>
                <th>Updated</th>
                <th style={{ textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={6} style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                    Loading templates...
                  </td>
                </tr>
              ) : templates.length === 0 ? (
                <tr>
                  <td colSpan={6} style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                    No templates found. Click "+ New Template" to launch Template Studio.
                  </td>
                </tr>
              ) : (
                templates.map((t) => {
                  const tid = t.template_id || t._id || t.id;
                  const isPublished = t.status === 'PUBLISHED';
                  const isDraft = t.status === 'DRAFT';

                  return (
                    <tr key={tid}>
                      <td>
                        <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{t.name}</div>
                        {t.description && (
                          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', maxWidth: '260px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                            {t.description}
                          </div>
                        )}
                      </td>
                      <td style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', maxWidth: '220px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {t.subject || 'No subject'}
                      </td>
                      <td>
                        <span className={`badge ${isPublished ? 'badge-success' : isDraft ? 'badge-warning' : 'badge-secondary'}`}>
                          {t.status}
                        </span>
                      </td>
                      <td>
                        <span className="badge badge-code">v{t.version || 1}</span>
                      </td>
                      <td style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                        {t.updated_at ? new Date(t.updated_at).toLocaleDateString() : 'N/A'}
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <div style={{ display: 'inline-flex', gap: '6px' }}>
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            onClick={() => {
                              setEditingTemplate(t);
                              setIsStudioOpen(true);
                            }}
                          >
                            Edit
                          </button>
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            onClick={() => setPreviewTemplate(t)}
                          >
                            Preview
                          </button>
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            onClick={() => setVersionsTemplate(t)}
                          >
                            Versions
                          </button>
                          {isDraft && (
                            <button
                              type="button"
                              className="btn btn-success btn-sm"
                              onClick={() => handlePublish(t)}
                            >
                              Publish
                            </button>
                          )}
                          {isPublished && (
                            <button
                              type="button"
                              className="btn btn-secondary btn-sm"
                              onClick={() => handleArchive(t)}
                            >
                              Archive
                            </button>
                          )}
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            onClick={() => handleDuplicate(t)}
                            title="Duplicate as draft"
                          >
                            Copy
                          </button>
                          <button
                            type="button"
                            className="btn btn-danger btn-sm"
                            onClick={() => handleDelete(t)}
                          >
                            Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      <TemplateStudioModal
        isOpen={isStudioOpen}
        onClose={() => {
          setIsStudioOpen(false);
          setEditingTemplate(null);
        }}
        template={editingTemplate}
        onSaved={fetchTemplates}
      />

      <TemplatePreviewModal
        isOpen={Boolean(previewTemplate)}
        onClose={() => setPreviewTemplate(null)}
        template={previewTemplate}
      />

      <TemplateVersionsModal
        isOpen={Boolean(versionsTemplate)}
        onClose={() => setVersionsTemplate(null)}
        template={versionsTemplate}
      />
    </div>
  );
}
