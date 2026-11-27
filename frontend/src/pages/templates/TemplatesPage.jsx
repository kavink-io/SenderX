import React, { useState, useEffect, useCallback, useMemo, lazy, Suspense } from 'react';
import ApiClient from '../../services/api';
import DataGrid from '../../components/tables/DataGrid';
import GridActionButton from '../../components/tables/GridActionButton';
import { useToast } from '../../context/ToastContext';
import { useAuth } from '../../context/AuthContext';
import { GlassSearch, GlassSelect } from '../../components/glass';

const TemplateStudioModal = lazy(() => import('../../components/templates/TemplateStudioModal'));
const TemplatePreviewModal = lazy(() => import('../../components/modals/TemplatePreviewModal'));

export default function TemplatesPage() {
  const [templates, setTemplates] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [search, setSearch] = useState('');
  const [isLoading, setIsLoading] = useState(true);

  const [isStudioOpen, setIsStudioOpen] = useState(false);
  const [studioMounted, setStudioMounted] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState(null);
  const [previewTemplate, setPreviewTemplate] = useState(null);
  const [previewMounted, setPreviewMounted] = useState(false);

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
    setStudioMounted(true);
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
      width: hasDraft ? 180 : 144,
      minWidth: 144,
      maxWidth: 180,
      flex: 0,
      sortable: false,
      filter: false,
      resizable: false,
      suppressHeaderMenuButton: true,
      headerClass: 'ag-right-aligned-header',
      cellClass: 'ag-actions-cell',
      cellRenderer: ({ data: t }) => {
        const isDraft = t.status === 'DRAFT';

        return (
          <div className="ag-icon-actions" role="group" aria-label="Template actions">
            <GridActionButton icon="edit" label="Edit template" onClick={() => handleEditOpen(t)} />
            <GridActionButton icon="view" label="Preview template" onClick={() => { setPreviewMounted(true); setPreviewTemplate(t); }} />
            {isDraft && <GridActionButton icon="check" label="Publish template" variant="success" onClick={() => handlePublish(t)} />}
            <GridActionButton icon="copy" label="Duplicate template as draft" onClick={() => handleDuplicate(t)} />
            <GridActionButton icon="delete" label="Delete template" variant="danger" onClick={() => handleDelete(t)} />
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
            <div style={{ flex: '1 1 240px', maxWidth: '300px' }}>
              <GlassSearch
                placeholder="Search templates by name..."
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setPage(1);
                }}
                onClear={() => {
                  setSearch('');
                  setPage(1);
                }}
              />
            </div>
            <div style={{ minWidth: '145px' }}>
              <GlassSelect
                value={statusFilter}
                onChange={(e) => {
                  setStatusFilter(e.target.value);
                  setPage(1);
                }}
                aria-label="Filter templates by status"
              >
                <option value="ALL">All Statuses</option>
                <option value="DRAFT">Draft</option>
                <option value="PUBLISHED">Published</option>
              </GlassSelect>
            </div>
          </div>

          <button
            type="button"
            className="btn btn-primary"
            onClick={() => {
              setEditingTemplate(null);
              setStudioMounted(true);
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

      {(isStudioOpen || studioMounted) && (
        <Suspense fallback={null}>
          <TemplateStudioModal
            isOpen={isStudioOpen}
            onClose={() => {
              setIsStudioOpen(false);
              setEditingTemplate(null);
            }}
            template={editingTemplate}
            onSaved={fetchTemplates}
          />
        </Suspense>
      )}

      {(Boolean(previewTemplate) || previewMounted) && (
        <Suspense fallback={null}>
          <TemplatePreviewModal
            isOpen={Boolean(previewTemplate)}
            onClose={() => setPreviewTemplate(null)}
            template={previewTemplate}
          />
        </Suspense>
      )}
    </div>
  );
}
