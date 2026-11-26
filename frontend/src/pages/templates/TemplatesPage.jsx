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
        const items = res.data?.items || res.items || (Array.isArray(res.data) ? res.data : []);
        const total = res.data?.total ?? res.pagination?.total ?? items.length;
        setTemplates(items);
        setTotalCount(total);
      } else {
        showToast(res?.message || 'Could not load email templates', 'error');
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

  const handleEditOpen = async (t) => {
    const tid = t.template_id || t._id || t.id;
    setEditingTemplate(t);
    setIsStudioOpen(true);
    try {
      const res = await ApiClient.getTemplate(tid);
      if (res?.success && res.data) {
        setEditingTemplate(res.data);
      }
    } catch {
      // Fallback to list row data already loaded
    }
  };

  const handlePublish = async (t) => {
    const tid = t.template_id || t._id || t.id;
    try {
      const res = await ApiClient.publishTemplate(tid, 'PUBLISHED');
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
                  const isPublished = t.status === 'PUBLISHED' || t.status === 'ACTIVE';
                  const isDraft = t.status === 'DRAFT';

                  const rowActions = [
                    {
                      key: 'edit',
                      title: 'Edit',
                      ariaLabel: 'Edit template',
                      className: 'icon-btn icon-btn-sm',
                      onClick: () => handleEditOpen(t),
                      icon: (
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                          <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
                        </svg>
                      ),
                    },
                    {
                      key: 'preview',
                      title: 'Preview',
                      ariaLabel: 'Preview template',
                      className: 'icon-btn icon-btn-sm',
                      onClick: () => setPreviewTemplate(t),
                      icon: (
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                          <circle cx="12" cy="12" r="3" />
                        </svg>
                      ),
                    },
                    {
                      key: 'versions',
                      title: 'Versions',
                      ariaLabel: 'View template versions',
                      className: 'icon-btn icon-btn-sm',
                      onClick: () => setVersionsTemplate(t),
                      icon: (
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
                          <path d="M3 3v5h5" />
                          <path d="M12 7v5l4 2" />
                        </svg>
                      ),
                    },
                    ...(isDraft
                      ? [
                          {
                            key: 'publish',
                            title: 'Publish',
                            ariaLabel: 'Publish template',
                            className: 'icon-btn icon-btn-sm icon-btn-success',
                            onClick: () => handlePublish(t),
                            icon: (
                              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                                <polyline points="22 4 12 14.01 9 11.01" />
                              </svg>
                            ),
                          },
                        ]
                      : []),
                    ...(isPublished
                      ? [
                          {
                            key: 'archive',
                            title: 'Archive',
                            ariaLabel: 'Archive template',
                            className: 'icon-btn icon-btn-sm',
                            onClick: () => handleArchive(t),
                            icon: (
                              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <polyline points="21 8 21 21 3 21 3 8" />
                                <rect x="1" y="3" width="22" height="5" />
                                <line x1="10" y1="12" x2="14" y2="12" />
                              </svg>
                            ),
                          },
                        ]
                      : []),
                    {
                      key: 'copy',
                      title: 'Duplicate as draft',
                      ariaLabel: 'Duplicate template as draft',
                      className: 'icon-btn icon-btn-sm',
                      onClick: () => handleDuplicate(t),
                      icon: (
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                          <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                        </svg>
                      ),
                    },
                    {
                      key: 'delete',
                      title: 'Delete',
                      ariaLabel: 'Delete template',
                      className: 'icon-btn icon-btn-sm icon-btn-danger',
                      onClick: () => handleDelete(t),
                      icon: (
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <polyline points="3 6 5 6 21 6" />
                          <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                          <line x1="10" y1="11" x2="10" y2="17" />
                          <line x1="14" y1="11" x2="14" y2="17" />
                        </svg>
                      ),
                    },
                  ];

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
                          {rowActions.map((action) => (
                            <button
                              key={action.key}
                              type="button"
                              className={action.className}
                              onClick={action.onClick}
                              title={action.title}
                              aria-label={action.ariaLabel}
                            >
                              {action.icon}
                            </button>
                          ))}
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {totalCount > 20 && (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '1rem', borderTop: '1px solid var(--glass-border)' }}>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              Showing {templates.length} of {totalCount}
            </span>
            <div style={{ display: 'flex', gap: '6px' }}>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                Previous
              </button>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                disabled={page * 20 >= totalCount}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </button>
            </div>
          </div>
        )}
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
