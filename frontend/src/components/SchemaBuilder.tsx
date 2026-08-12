"use client";

import { useState, useCallback, useEffect } from 'react';
import {
  SchemaField,
  SchemaFieldType,
  fieldsToJsonSchema,
  jsonSchemaToFields,
  createEmptyField,
  SAMPLE_SCHEMA_DEFINITION,
} from '@/lib/schema-builder';

interface SchemaBuilderProps {
  initialFields?: SchemaField[];
  onChange?: (fields: SchemaField[]) => void;
  showPreview?: boolean;
}

export default function SchemaBuilder({ initialFields, onChange, showPreview = true }: SchemaBuilderProps) {
  const [fields, setFields] = useState<SchemaField[]>(initialFields || [createEmptyField()]);
  const [jsonPreview, setJsonPreview] = useState('');
  const [showImportModal, setShowImportModal] = useState(false);
  const [importText, setImportText] = useState('');
  const [importError, setImportError] = useState('');
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (initialFields) {
      setFields(initialFields);
    }
  }, [initialFields]);

  useEffect(() => {
    const schema = fieldsToJsonSchema(fields);
    setJsonPreview(JSON.stringify(schema, null, 2));
    onChange?.(fields);
  }, [fields, onChange]);

  const updateField = useCallback((index: number, updates: Partial<SchemaField>, parentFields: SchemaField[] | null = null) => {
    setFields(prev => {
      const targetFields = parentFields || prev;
      const newFields = [...targetFields];
      newFields[index] = { ...newFields[index], ...updates };
      return parentFields ? [...prev] : newFields;
    });
  }, []);

  const updateFieldDeep = useCallback((fieldId: string, updates: Partial<SchemaField>) => {
    setFields(prev => {
      const updateInArray = (arr: SchemaField[]): SchemaField[] => {
        return arr.map(field => {
          if (field.id === fieldId) {
            return { ...field, ...updates };
          }
          if (field.children.length > 0) {
            return { ...field, children: updateInArray(field.children) };
          }
          return field;
        });
      };
      return updateInArray(prev);
    });
  }, []);

  const addChildField = useCallback((parentIndex: number) => {
    setFields(prev => {
      const newFields = [...prev];
      const parent = { ...newFields[parentIndex] };
      parent.children = [...parent.children, createEmptyField()];
      newFields[parentIndex] = parent;
      return newFields;
    });
  }, []);

  const addArrayItemDefinition = useCallback((parentIndex: number) => {
    setFields(prev => {
      const newFields = [...prev];
      const parent = { ...newFields[parentIndex] };
      parent.arrayItemType = 'object';
      parent.children = [...parent.children, createEmptyField()];
      newFields[parentIndex] = parent;
      return newFields;
    });
  }, []);

  const removeField = useCallback((index: number) => {
    setFields(prev => prev.filter((_, i) => i !== index));
  }, []);

  const removeChildField = useCallback((parentIndex: number, childIndex: number) => {
    setFields(prev => {
      const newFields = [...prev];
      const parent = { ...newFields[parentIndex] };
      parent.children = parent.children.filter((_, i) => i !== childIndex);
      newFields[parentIndex] = parent;
      return newFields;
    });
  }, []);

  const moveField = useCallback((index: number, direction: 'up' | 'down') => {
    setFields(prev => {
      const newFields = [...prev];
      const targetIndex = direction === 'up' ? index - 1 : index + 1;
      if (targetIndex < 0 || targetIndex >= newFields.length) return prev;
      [newFields[index], newFields[targetIndex]] = [newFields[targetIndex], newFields[index]];
      return newFields;
    });
  }, []);

  const moveChildField = useCallback((parentIndex: number, childIndex: number, direction: 'up' | 'down') => {
    setFields(prev => {
      const newFields = [...prev];
      const parent = { ...newFields[parentIndex] };
      const targetIndex = direction === 'up' ? childIndex - 1 : childIndex + 1;
      if (targetIndex < 0 || targetIndex >= parent.children.length) return prev;
      parent.children = [...parent.children];
      [parent.children[childIndex], parent.children[targetIndex]] = [parent.children[targetIndex], parent.children[childIndex]];
      newFields[parentIndex] = parent;
      return newFields;
    });
  }, []);

  const loadSample = useCallback(() => {
    const sampleFields = jsonSchemaToFields(SAMPLE_SCHEMA_DEFINITION);
    setFields(sampleFields);
  }, []);

  const handleImport = useCallback(() => {
    try {
      const parsed = JSON.parse(importText);
      const importedFields = jsonSchemaToFields(parsed);
      if (importedFields.length === 0) {
        setImportError('No fields found. Ensure the JSON has "type": "object" and "properties".');
        return;
      }
      setFields(importedFields);
      setShowImportModal(false);
      setImportText('');
      setImportError('');
    } catch (err) {
      setImportError('Invalid JSON: ' + (err instanceof Error ? err.message : 'Unknown error'));
    }
  }, [importText]);

  const handleExport = useCallback(() => {
    navigator.clipboard.writeText(jsonPreview);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [jsonPreview]);

  return (
    <div className="schema-builder" style={{ display: 'flex', gap: '1.5rem' }}>
      <div className="schema-builder-form" style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
          <button className="btn btn-secondary" onClick={loadSample} style={{ padding: '0.4rem 0.8rem', fontSize: '0.8rem' }}>
            Load Sample
          </button>
          <button className="btn btn-secondary" onClick={() => setShowImportModal(true)} style={{ padding: '0.4rem 0.8rem', fontSize: '0.8rem' }}>
            Import JSON
          </button>
          <button className="btn btn-secondary" onClick={handleExport} style={{ padding: '0.4rem 0.8rem', fontSize: '0.8rem' }}>
            {copied ? 'Copied!' : 'Copy JSON'}
          </button>
          <button className="btn btn-primary" onClick={() => setFields([...fields, createEmptyField()])} style={{ padding: '0.4rem 0.8rem', fontSize: '0.8rem' }}>
            + Add Field
          </button>
        </div>

        <div className="fields-container">
          {fields.map((field, index) => (
            <FieldRow
              key={field.id}
              field={field}
              index={index}
              totalFields={fields.length}
              onUpdate={(updates) => updateField(index, updates)}
              onAddChild={() => addChildField(index)}
              onAddArrayItem={() => addArrayItemDefinition(index)}
              onRemove={() => removeField(index)}
              onMove={(dir) => moveField(index, dir)}
              onUpdateChild={(childIndex, updates) => {
                setFields(prev => {
                  const newFields = [...prev];
                  const parent = { ...newFields[index] };
                  parent.children = [...parent.children];
                  parent.children[childIndex] = { ...parent.children[childIndex], ...updates };
                  newFields[index] = parent;
                  return newFields;
                });
              }}
              onRemoveChild={(childIndex) => removeChildField(index, childIndex)}
              onMoveChild={(childIndex, dir) => moveChildField(index, childIndex, dir)}
            />
          ))}
        </div>
      </div>

      {showPreview && (
        <div className="schema-builder-preview" style={{ width: '320px', flexShrink: 0 }}>
          <h4 style={{ marginBottom: '0.5rem', color: 'var(--muted)' }}>JSON Preview</h4>
          <pre style={{
            background: 'var(--surface2)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius)',
            padding: '1rem',
            fontSize: '0.75rem',
            overflow: 'auto',
            maxHeight: '70vh',
            fontFamily: 'monospace',
            color: 'var(--text)',
          }}>
            {jsonPreview}
          </pre>
        </div>
      )}

      {showImportModal && (
        <div className="modal-overlay" onClick={() => { setShowImportModal(false); setImportError(''); }}>
          <div className="modal-content" style={{ maxWidth: '500px' }} onClick={(e) => e.stopPropagation()}>
            <h3 style={{ marginBottom: '1rem' }}>Import JSON Schema</h3>
            <textarea
              className="input-field"
              value={importText}
              onChange={(e) => { setImportText(e.target.value); setImportError(''); }}
              rows={10}
              style={{ fontFamily: 'monospace', fontSize: '0.8rem', marginBottom: '0.5rem' }}
              placeholder='{"type": "object", "properties": {...}}'
            />
            {importError && <p style={{ color: 'var(--red)', fontSize: '0.85rem', marginBottom: '0.5rem' }}>{importError}</p>}
            <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
              <button className="btn btn-secondary" onClick={() => { setShowImportModal(false); setImportError(''); }}>Cancel</button>
              <button className="btn btn-primary" onClick={handleImport}>Import</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

interface FieldRowProps {
  field: SchemaField;
  index: number;
  totalFields: number;
  onUpdate: (updates: Partial<SchemaField>) => void;
  onAddChild: () => void;
  onAddArrayItem: () => void;
  onRemove: () => void;
  onMove: (dir: 'up' | 'down') => void;
  onUpdateChild: (childIndex: number, updates: Partial<SchemaField>) => void;
  onRemoveChild: (childIndex: number) => void;
  onMoveChild: (childIndex: number, dir: 'up' | 'down') => void;
}

function FieldRow({ field, index, totalFields, onUpdate, onAddChild, onAddArrayItem, onRemove, onMove, onUpdateChild, onRemoveChild, onMoveChild }: FieldRowProps) {
  const [expanded, setExpanded] = useState(true);

  const handleTypeChange = (newType: SchemaFieldType) => {
    const updates: Partial<SchemaField> = { type: newType };
    if (newType !== 'object' && newType !== 'array') {
      updates.children = [];
      updates.arrayItemType = undefined;
    }
    if (newType !== 'array') {
      updates.arrayItemType = undefined;
    }
    onUpdate(updates);
  };

  return (
    <div className="field-row" style={{
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--radius)',
      padding: '0.75rem',
      marginBottom: '0.5rem',
    }}>
      <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'flex-start', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', gap: '0.25rem', alignItems: 'center' }}>
          <button
            className="btn"
            onClick={() => onMove('up')}
            disabled={index === 0}
            style={{ padding: '0.2rem 0.4rem', fontSize: '0.7rem', color: 'var(--muted)' }}
          >
            ↑
          </button>
          <button
            className="btn"
            onClick={() => onMove('down')}
            disabled={index === totalFields - 1}
            style={{ padding: '0.2rem 0.4rem', fontSize: '0.7rem', color: 'var(--muted)' }}
          >
            ↓
          </button>
        </div>

        <input
          type="text"
          className="input-field"
          value={field.key}
          onChange={(e) => onUpdate({ key: e.target.value })}
          placeholder="Field name"
          style={{ width: '140px', padding: '0.4rem', fontSize: '0.85rem' }}
        />

        <select
          className="input-field"
          value={field.type}
          onChange={(e) => handleTypeChange(e.target.value as SchemaFieldType)}
          style={{ width: '100px', padding: '0.4rem', fontSize: '0.85rem' }}
        >
          <option value="string">string</option>
          <option value="number">number</option>
          <option value="integer">integer</option>
          <option value="boolean">boolean</option>
          <option value="array">array</option>
          <option value="object">object</option>
        </select>

        <label style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.85rem', color: 'var(--muted)' }}>
          <input
            type="checkbox"
            checked={field.required}
            onChange={(e) => onUpdate({ required: e.target.checked })}
          />
          Required
        </label>

        <input
          type="text"
          className="input-field"
          value={field.description || ''}
          onChange={(e) => onUpdate({ description: e.target.value || undefined })}
          placeholder="Description"
          style={{ flex: 1, minWidth: '120px', padding: '0.4rem', fontSize: '0.85rem' }}
        />

        <div style={{ display: 'flex', gap: '0.25rem' }}>
          {field.type === 'object' && (
            <button className="btn btn-secondary" onClick={onAddChild} style={{ padding: '0.3rem 0.6rem', fontSize: '0.75rem' }}>
              + Child
            </button>
          )}
          {field.type === 'array' && !field.arrayItemType && (
            <button className="btn btn-secondary" onClick={onAddArrayItem} style={{ padding: '0.3rem 0.6rem', fontSize: '0.75rem' }}>
              Define Items
            </button>
          )}
          <button className="btn" onClick={onRemove} style={{ padding: '0.3rem 0.6rem', fontSize: '0.75rem', color: 'var(--red)' }}>
            ✕
          </button>
        </div>
      </div>

      {(field.type === 'string' || field.type === 'number' || field.type === 'integer') && (
        <ConstraintFields field={field} onUpdate={onUpdate} />
      )}

      {field.type === 'array' && field.arrayItemType === 'object' && (
        <div style={{ marginTop: '0.5rem', marginLeft: '1.5rem', paddingLeft: '0.75rem', borderLeft: '2px solid var(--accent)' }}>
          <div style={{ fontSize: '0.8rem', color: 'var(--accent)', marginBottom: '0.5rem' }}>
            Array Items (object)
          </div>
          {field.children.map((child, childIndex) => (
            <div key={child.id} style={{ marginBottom: '0.5rem' }}>
              <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                <button
                  className="btn"
                  onClick={() => onMoveChild(childIndex, 'up')}
                  disabled={childIndex === 0}
                  style={{ padding: '0.15rem 0.3rem', fontSize: '0.65rem', color: 'var(--muted)' }}
                >
                  ↑
                </button>
                <button
                  className="btn"
                  onClick={() => onMoveChild(childIndex, 'down')}
                  disabled={childIndex === field.children.length - 1}
                  style={{ padding: '0.15rem 0.3rem', fontSize: '0.65rem', color: 'var(--muted)' }}
                >
                  ↓
                </button>
                <input
                  type="text"
                  className="input-field"
                  value={child.key}
                  onChange={(e) => onUpdateChild(childIndex, { key: e.target.value })}
                  placeholder="Field name"
                  style={{ width: '120px', padding: '0.3rem', fontSize: '0.8rem' }}
                />
                <select
                  className="input-field"
                  value={child.type}
                  onChange={(e) => onUpdateChild(childIndex, { type: e.target.value as SchemaFieldType })}
                  style={{ width: '90px', padding: '0.3rem', fontSize: '0.8rem' }}
                >
                  <option value="string">string</option>
                  <option value="number">number</option>
                  <option value="integer">integer</option>
                  <option value="boolean">boolean</option>
                  <option value="array">array</option>
                  <option value="object">object</option>
                </select>
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.2rem', fontSize: '0.8rem', color: 'var(--muted)' }}>
                  <input
                    type="checkbox"
                    checked={child.required}
                    onChange={(e) => onUpdateChild(childIndex, { required: e.target.checked })}
                  />
                  Req
                </label>
                <input
                  type="text"
                  className="input-field"
                  value={child.description || ''}
                  onChange={(e) => onUpdateChild(childIndex, { description: e.target.value || undefined })}
                  placeholder="Description"
                  style={{ flex: 1, minWidth: '100px', padding: '0.3rem', fontSize: '0.8rem' }}
                />
                <button
                  className="btn"
                  onClick={() => onRemoveChild(childIndex)}
                  style={{ padding: '0.2rem 0.5rem', fontSize: '0.7rem', color: 'var(--red)' }}
                >
                  ✕
                </button>
              </div>
              {(child.type === 'string' || child.type === 'number' || child.type === 'integer') && (
                <ConstraintFields field={child} onUpdate={(updates) => onUpdateChild(childIndex, updates)} />
              )}
              {child.type === 'object' && child.children.length > 0 && (
                <div style={{ marginTop: '0.3rem', marginLeft: '1rem', paddingLeft: '0.5rem', borderLeft: '1px solid var(--border)' }}>
                  {child.children.map((grandchild, gcIndex) => (
                    <div key={grandchild.id} style={{ display: 'flex', gap: '0.3rem', alignItems: 'center', marginBottom: '0.3rem' }}>
                      <input
                        type="text"
                        className="input-field"
                        value={grandchild.key}
                        onChange={(e) => onUpdateChild(childIndex, {
                          children: child.children.map((c, i) => i === gcIndex ? { ...c, key: e.target.value } : c)
                        })}
                        placeholder="Field name"
                        style={{ width: '100px', padding: '0.25rem', fontSize: '0.75rem' }}
                      />
                      <select
                        className="input-field"
                        value={grandchild.type}
                        onChange={(e) => onUpdateChild(childIndex, {
                          children: child.children.map((c, i) => i === gcIndex ? { ...c, type: e.target.value as SchemaFieldType } : c)
                        })}
                        style={{ width: '80px', padding: '0.25rem', fontSize: '0.75rem' }}
                      >
                        <option value="string">string</option>
                        <option value="number">number</option>
                        <option value="integer">integer</option>
                        <option value="boolean">boolean</option>
                      </select>
                      <label style={{ display: 'flex', alignItems: 'center', gap: '0.2rem', fontSize: '0.75rem', color: 'var(--muted)' }}>
                        <input
                          type="checkbox"
                          checked={grandchild.required}
                          onChange={(e) => onUpdateChild(childIndex, {
                            children: child.children.map((c, i) => i === gcIndex ? { ...c, required: e.target.checked } : c)
                          })}
                        />
                        Req
                      </label>
                      <button
                        className="btn"
                        onClick={() => onUpdateChild(childIndex, {
                          children: child.children.filter((_, i) => i !== gcIndex)
                        })}
                        style={{ padding: '0.15rem 0.4rem', fontSize: '0.65rem', color: 'var(--red)' }}
                      >
                        ✕
                      </button>
                    </div>
                  ))}
                </div>
              )}
              {child.type === 'object' && (
                <button
                  className="btn btn-secondary"
                  onClick={() => onUpdateChild(childIndex, { children: [...child.children, { id: `field_${Date.now()}`, key: '', type: 'string', required: false, description: '', constraints: {}, children: [] }] })}
                  style={{ padding: '0.2rem 0.5rem', fontSize: '0.7rem', marginTop: '0.3rem' }}
                >
                  + Add Field
                </button>
              )}
            </div>
          ))}
          <button
            className="btn btn-secondary"
            onClick={() => onUpdate({ children: [...field.children, { id: `field_${Date.now()}`, key: '', type: 'string', required: false, description: '', constraints: {}, children: [] }] })}
            style={{ padding: '0.3rem 0.6rem', fontSize: '0.75rem' }}
          >
            + Add Item Field
          </button>
        </div>
      )}

      {field.type === 'object' && field.children.length > 0 && (
        <div style={{ marginTop: '0.5rem', marginLeft: '1.5rem', paddingLeft: '0.75rem', borderLeft: '2px solid var(--accent)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--accent)' }}>
              Child Fields
            </span>
            <button
              className="btn"
              onClick={() => setExpanded(!expanded)}
              style={{ padding: '0.2rem 0.4rem', fontSize: '0.7rem', color: 'var(--muted)' }}
            >
              {expanded ? 'Collapse' : 'Expand'}
            </button>
          </div>
          {expanded && field.children.map((child, childIndex) => (
            <div key={child.id} style={{ marginBottom: '0.5rem' }}>
              <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                <button
                  className="btn"
                  onClick={() => onMoveChild(childIndex, 'up')}
                  disabled={childIndex === 0}
                  style={{ padding: '0.15rem 0.3rem', fontSize: '0.65rem', color: 'var(--muted)' }}
                >
                  ↑
                </button>
                <button
                  className="btn"
                  onClick={() => onMoveChild(childIndex, 'down')}
                  disabled={childIndex === field.children.length - 1}
                  style={{ padding: '0.15rem 0.3rem', fontSize: '0.65rem', color: 'var(--muted)' }}
                >
                  ↓
                </button>
                <input
                  type="text"
                  className="input-field"
                  value={child.key}
                  onChange={(e) => onUpdateChild(childIndex, { key: e.target.value })}
                  placeholder="Field name"
                  style={{ width: '120px', padding: '0.3rem', fontSize: '0.8rem' }}
                />
                <select
                  className="input-field"
                  value={child.type}
                  onChange={(e) => onUpdateChild(childIndex, { type: e.target.value as SchemaFieldType })}
                  style={{ width: '90px', padding: '0.3rem', fontSize: '0.8rem' }}
                >
                  <option value="string">string</option>
                  <option value="number">number</option>
                  <option value="integer">integer</option>
                  <option value="boolean">boolean</option>
                  <option value="array">array</option>
                  <option value="object">object</option>
                </select>
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.2rem', fontSize: '0.8rem', color: 'var(--muted)' }}>
                  <input
                    type="checkbox"
                    checked={child.required}
                    onChange={(e) => onUpdateChild(childIndex, { required: e.target.checked })}
                  />
                  Req
                </label>
                <input
                  type="text"
                  className="input-field"
                  value={child.description || ''}
                  onChange={(e) => onUpdateChild(childIndex, { description: e.target.value || undefined })}
                  placeholder="Description"
                  style={{ flex: 1, minWidth: '100px', padding: '0.3rem', fontSize: '0.8rem' }}
                />
                <button
                  className="btn"
                  onClick={() => onRemoveChild(childIndex)}
                  style={{ padding: '0.2rem 0.5rem', fontSize: '0.7rem', color: 'var(--red)' }}
                >
                  ✕
                </button>
              </div>
              {(child.type === 'string' || child.type === 'number' || child.type === 'integer') && (
                <ConstraintFields field={child} onUpdate={(updates) => onUpdateChild(childIndex, updates)} />
              )}
              {child.type === 'object' && (
                <div style={{ marginTop: '0.3rem', marginLeft: '1rem', paddingLeft: '0.5rem', borderLeft: '1px solid var(--border)' }}>
                  {child.children.map((grandchild, gcIndex) => (
                    <div key={grandchild.id} style={{ display: 'flex', gap: '0.3rem', alignItems: 'center', marginBottom: '0.3rem' }}>
                      <input
                        type="text"
                        className="input-field"
                        value={grandchild.key}
                        onChange={(e) => {
                          const newChildren = [...child.children];
                          newChildren[gcIndex] = { ...newChildren[gcIndex], key: e.target.value };
                          onUpdateChild(childIndex, { children: newChildren });
                        }}
                        placeholder="Field name"
                        style={{ width: '100px', padding: '0.25rem', fontSize: '0.75rem' }}
                      />
                      <select
                        className="input-field"
                        value={grandchild.type}
                        onChange={(e) => {
                          const newChildren = [...child.children];
                          newChildren[gcIndex] = { ...newChildren[gcIndex], type: e.target.value as SchemaFieldType };
                          onUpdateChild(childIndex, { children: newChildren });
                        }}
                        style={{ width: '80px', padding: '0.25rem', fontSize: '0.75rem' }}
                      >
                        <option value="string">string</option>
                        <option value="number">number</option>
                        <option value="integer">integer</option>
                        <option value="boolean">boolean</option>
                      </select>
                      <label style={{ display: 'flex', alignItems: 'center', gap: '0.2rem', fontSize: '0.75rem', color: 'var(--muted)' }}>
                        <input
                          type="checkbox"
                          checked={grandchild.required}
                          onChange={(e) => {
                            const newChildren = [...child.children];
                            newChildren[gcIndex] = { ...newChildren[gcIndex], required: e.target.checked };
                            onUpdateChild(childIndex, { children: newChildren });
                          }}
                        />
                        Req
                      </label>
                      <button
                        className="btn"
                        onClick={() => {
                          const newChildren = child.children.filter((_, i) => i !== gcIndex);
                          onUpdateChild(childIndex, { children: newChildren });
                        }}
                        style={{ padding: '0.15rem 0.4rem', fontSize: '0.65rem', color: 'var(--red)' }}
                      >
                        ✕
                      </button>
                    </div>
                  ))}
                  <button
                    className="btn btn-secondary"
                    onClick={() => onUpdateChild(childIndex, { children: [...child.children, { id: `field_${Date.now()}`, key: '', type: 'string', required: false, description: '', constraints: {}, children: [] }] })}
                    style={{ padding: '0.2rem 0.5rem', fontSize: '0.7rem', marginTop: '0.3rem' }}
                  >
                    + Add Field
                  </button>
                </div>
              )}
              {child.type === 'array' && child.arrayItemType === 'object' && (
                <div style={{ marginTop: '0.3rem', marginLeft: '1rem', paddingLeft: '0.5rem', borderLeft: '1px solid var(--border)' }}>
                  <span style={{ fontSize: '0.7rem', color: 'var(--muted)' }}>Array items: {child.children.length} fields defined</span>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

interface ConstraintFieldsProps {
  field: SchemaField;
  onUpdate: (updates: Partial<SchemaField>) => void;
}

function ConstraintFields({ field, onUpdate }: ConstraintFieldsProps) {
  const constraints = field.constraints || {};

  if (field.type === 'string') {
    return (
      <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem', marginLeft: '1.5rem', fontSize: '0.8rem' }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', color: 'var(--muted)' }}>
          Min:
          <input
            type="number"
            className="input-field"
            value={constraints.minLength ?? ''}
            onChange={(e) => onUpdate({ constraints: { ...constraints, minLength: e.target.value ? parseInt(e.target.value) : undefined } })}
            style={{ width: '60px', padding: '0.2rem', fontSize: '0.8rem' }}
            min={0}
          />
        </label>
        <label style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', color: 'var(--muted)' }}>
          Max:
          <input
            type="number"
            className="input-field"
            value={constraints.maxLength ?? ''}
            onChange={(e) => onUpdate({ constraints: { ...constraints, maxLength: e.target.value ? parseInt(e.target.value) : undefined } })}
            style={{ width: '60px', padding: '0.2rem', fontSize: '0.8rem' }}
            min={0}
          />
        </label>
      </div>
    );
  }

  if (field.type === 'number' || field.type === 'integer') {
    return (
      <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem', marginLeft: '1.5rem', fontSize: '0.8rem' }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', color: 'var(--muted)' }}>
          Min:
          <input
            type="number"
            className="input-field"
            value={constraints.minimum ?? ''}
            onChange={(e) => onUpdate({ constraints: { ...constraints, minimum: e.target.value ? parseFloat(e.target.value) : undefined } })}
            style={{ width: '60px', padding: '0.2rem', fontSize: '0.8rem' }}
          />
        </label>
        <label style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', color: 'var(--muted)' }}>
          Max:
          <input
            type="number"
            className="input-field"
            value={constraints.maximum ?? ''}
            onChange={(e) => onUpdate({ constraints: { ...constraints, maximum: e.target.value ? parseFloat(e.target.value) : undefined } })}
            style={{ width: '60px', padding: '0.2rem', fontSize: '0.8rem' }}
          />
        </label>
      </div>
    );
  }

  return null;
}
