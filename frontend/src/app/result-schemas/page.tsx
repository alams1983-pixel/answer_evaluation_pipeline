"use client";

import { useState, useEffect } from 'react';
import { useAuth } from '@/lib/auth';
import { apiGet, apiPost, apiPatch, apiDelete } from '@/lib/api';
import SchemaBuilder from '@/components/SchemaBuilder';
import { SchemaField, jsonSchemaToFields, fieldsToJsonSchema } from '@/lib/schema-builder';

interface ResultSchema {
  id: string;
  name: string;
  description: string | null;
  schema_definition: object;
  created_by: string | null;
  created_at: string;
}

type ViewMode = 'list' | 'create' | 'edit';

export default function ResultSchemasPage() {
  const { user, loading: authLoading } = useAuth();
  const [schemas, setSchemas] = useState<ResultSchema[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>('list');
  const [editingSchema, setEditingSchema] = useState<ResultSchema | null>(null);
  const [schemaName, setSchemaName] = useState('');
  const [schemaDescription, setSchemaDescription] = useState('');
  const [builderFields, setBuilderFields] = useState<SchemaField[]>([]);
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && user && ['admin', 'teacher'].includes(user.role!)) {
      loadSchemas();
    } else if (!authLoading && (!user || !['admin', 'teacher'].includes(user.role!))) {
      setLoading(false);
    }
  }, [user, authLoading]);

  const loadSchemas = async () => {
    try {
      setLoading(true);
      const data = await apiGet<ResultSchema[]>('/exams/result-schemas/');
      setSchemas(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load schemas');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateNew = () => {
    setEditingSchema(null);
    setSchemaName('');
    setSchemaDescription('');
    setBuilderFields([]);
    setViewMode('create');
    setError(null);
    setSuccess(null);
  };

  const handleEdit = (schema: ResultSchema) => {
    setEditingSchema(schema);
    setSchemaName(schema.name);
    setSchemaDescription(schema.description || '');
    setBuilderFields(jsonSchemaToFields(schema.schema_definition));
    setViewMode('edit');
    setError(null);
    setSuccess(null);
  };

  const handleDuplicate = async (schema: ResultSchema) => {
    try {
      await apiPost('/exams/result-schemas/', {
        name: `Copy of ${schema.name}`,
        description: schema.description || undefined,
        schema_definition: schema.schema_definition,
      });
      setSuccess('Schema duplicated successfully');
      loadSchemas();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to duplicate schema');
    }
  };

  const handleDelete = async (id: string, name: string) => {
    if (!confirm(`Delete "${name}"? This will unlink it from any exams using it.`)) return;
    try {
      await apiDelete(`/exams/result-schemas/${id}/`);
      setSuccess('Schema deleted successfully');
      loadSchemas();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete schema');
    }
  };

  const handleSave = async () => {
    if (!schemaName.trim()) {
      setError('Schema name is required');
      return;
    }
    if (builderFields.length === 0) {
      setError('Add at least one field');
      return;
    }

    setSaving(true);
    try {
      const schemaDefinition = fieldsToJsonSchema(builderFields);

      if (editingSchema) {
        await apiPatch(`/exams/result-schemas/${editingSchema.id}/`, {
          name: schemaName,
          description: schemaDescription || undefined,
          schema_definition: schemaDefinition,
        });
        setSuccess('Schema updated successfully');
      } else {
        await apiPost('/exams/result-schemas/', {
          name: schemaName,
          description: schemaDescription || undefined,
          schema_definition: schemaDefinition,
        });
        setSuccess('Schema created successfully');
      }

      setViewMode('list');
      loadSchemas();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save schema');
    } finally {
      setSaving(false);
    }
  };

  if (authLoading || loading) {
    return <div style={{ textAlign: 'center', padding: '2rem' }}>Loading...</div>;
  }

  if (!user || !['admin', 'teacher'].includes(user.role!)) {
    return <div>Access denied</div>;
  }

  return (
    <div>
      {viewMode === 'list' && (
        <>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
            <h1 className="text-xl">Result Schemas</h1>
            <button className="btn btn-primary" onClick={handleCreateNew}>
              + New Schema
            </button>
          </div>

          {error && (
            <div className="error-message" style={{ marginBottom: '1rem' }}>
              {error}
              <button onClick={() => setError(null)} style={{ float: 'right', background: 'none', border: 'none', color: 'inherit', cursor: 'pointer' }}>&times;</button>
            </div>
          )}

          {success && (
            <div style={{ marginBottom: '1rem', padding: '0.75rem 1rem', background: 'var(--success-bg)', border: '1px solid var(--success)', borderRadius: 'var(--radius-md)', color: 'var(--success-text)', fontSize: '0.875rem' }}>
              {success}
              <button onClick={() => setSuccess(null)} style={{ float: 'right', background: 'none', border: 'none', color: 'inherit', cursor: 'pointer' }}>&times;</button>
            </div>
          )}

          {schemas.length === 0 ? (
            <div className="panel" style={{ padding: '2rem', textAlign: 'center' }}>
              <p style={{ color: 'var(--text-muted)' }}>No result schemas yet. Create one to get started.</p>
            </div>
          ) : (
            <div className="table-container">
              <table className="table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Description</th>
                    <th>Created</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {schemas.map(s => (
                    <tr key={s.id}>
                      <td>
                        <span className="node node-purple">{s.name}</span>
                      </td>
                      <td style={{ color: 'var(--text-secondary)' }}>{s.description || '-'}</td>
                      <td style={{ color: 'var(--text-secondary)' }}>
                        {new Date(s.created_at).toLocaleDateString()}
                      </td>
                      <td style={{ display: 'flex', gap: '0.5rem' }}>
                        <button className="btn btn-secondary" onClick={() => handleEdit(s)}>
                          Edit
                        </button>
                        <button className="btn btn-secondary" onClick={() => handleDuplicate(s)}>
                          Duplicate
                        </button>
                        <button className="btn" style={{ color: 'var(--error)' }} onClick={() => handleDelete(s.id, s.name)}>
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {(viewMode === 'create' || viewMode === 'edit') && (
        <>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
            <div>
              <button className="btn btn-secondary" onClick={() => setViewMode('list')} style={{ marginBottom: '0.5rem' }}>
                &larr; Back to Schemas
              </button>
              <h1 className="text-xl">{viewMode === 'create' ? 'Create Result Schema' : 'Edit Result Schema'}</h1>
            </div>
          </div>

          {error && (
            <div className="error-message" style={{ marginBottom: '1rem' }}>
              {error}
              <button onClick={() => setError(null)} style={{ float: 'right', background: 'none', border: 'none', color: 'inherit', cursor: 'pointer' }}>&times;</button>
            </div>
          )}

          <div className="panel" style={{ padding: '1.5rem', marginBottom: '1.5rem' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <div>
                <label className="form-label">Schema Name</label>
                <input
                  type="text"
                  className="form-input"
                  value={schemaName}
                  onChange={(e) => setSchemaName(e.target.value)}
                  placeholder="e.g., Standard Written Paper"
                />
              </div>
              <div>
                <label className="form-label">Description (optional)</label>
                <input
                  type="text"
                  className="form-input"
                  value={schemaDescription}
                  onChange={(e) => setSchemaDescription(e.target.value)}
                  placeholder="Brief description..."
                />
              </div>
            </div>
          </div>

          <div className="panel" style={{ padding: '1.5rem', marginBottom: '1.5rem' }}>
            <SchemaBuilder
              initialFields={builderFields.length > 0 ? builderFields : undefined}
              onChange={(fields) => setBuilderFields(fields)}
            />
          </div>

          <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' }}>
            <button className="btn btn-secondary" onClick={() => setViewMode('list')}>
              Cancel
            </button>
            <button className="btn btn-primary" onClick={handleSave} disabled={saving || !schemaName.trim() || builderFields.length === 0}>
              {saving ? 'Saving...' : viewMode === 'create' ? 'Create Schema' : 'Update Schema'}
            </button>
          </div>
        </>
      )}
    </div>
  );
}
