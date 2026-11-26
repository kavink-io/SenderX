import React, { useState, useEffect, useCallback, useMemo } from 'react';
import ApiClient from '../../services/api';
import DataGrid from '../../components/tables/DataGrid';
import TemplateStudioModal from '../../components/templates/TemplateStudioModal';
import TemplatePreviewModal from '../../components/modals/TemplatePreviewModal';
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

  const handleDelete = useCallback(async (t) => {
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
  }, [fetchTemplates, showToast]);

  const hasDraft = templates.some((t) => t.status === 'DRAFT');

  const columnDefs = useMemo(() => [
    {
      headerName: 'Template Name',
      field: 'name',
      minWidth: 200,
      flex: 1.4,
      autoHeight: true,
      wrapText: true,
      cellRenderer: ({ data: t }) => (
        <div style={{ minWidth: 0 }}>
          <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{t.name}</div>
          {t.description && (
            <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {t.description}
            </div>
          )}
        </div>
      ),
    },
    {
      headerName: 'Subject',
      field: 'subject',
      minWidth: 180,
      flex: 1.2,
      valueGetter: ({ data }) => data.subject || 'No subject',
      cellStyle: { fontSize: '0.85rem', color: 'var(--text-secondary)' },
    },
    {
      headerName: 'Status',
      field: 'status',
      minWidth: 120,
      maxWidth: 145,
      cellRenderer: ({ data: t }) => {
        const isPublished = t.status === 'PUBLISHED' || t.status === 'ACTIVE';
        const isDraft = t.status === 'DRAFT';
        return (
          <span className={`badge ${isPublished ? 'badge-success' : isDraft ? 'badge-warning' : 'badge-secondary'}`}>
            {t.status}
          </span>
        );
      },
    },
    {
      headerName: 'Updated',
      field: 'updated_at',
      minWidth: 120,
      maxWidth: 150,
      valueFormatter: ({ value }) => (value ? new Date(value).toLocaleDateString() : 'N/A'),
      cellStyle: { fontSize: '0.85rem', color: 'var(--text-secondary)' },
    },
    {
      headerName: 'Actions',
      colId: 'actions',
      width: hasDraft ? 210 : 176,
      minWidth: 176,
      maxWidth: 215,
      flex: 0,
      sortable: false,
      filter: false,
      resizable: false,
      suppressHeaderMenuButton: true,
      headerClass: 'ag-right-aligned-header',
      cellClass: 'ag-actions-cell',
      cellRenderer: ({ data: t }) => {
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
        );
      },
    },
  ], [handleDelete, hasDraft]);

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
        <DataGrid
          rowData={templates}
          columnDefs={columnDefs}
          loading={isLoading}
          emptyMessage='No templates found. Click "+ New Template" to launch Template Studio.'
          getRowId={({ data }) => String(data.template_id || data._id || data.id)}
        />

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
    </div>
  );
}
