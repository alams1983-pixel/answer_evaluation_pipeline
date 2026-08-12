interface SchemaProperty {
  type: string;
  description?: string;
  properties?: Record<string, SchemaProperty>;
  items?: SchemaProperty;
  required?: string[];
  minimum?: number;
  maximum?: number;
  minLength?: number;
  maxLength?: number;
  enum?: string[];
}

interface SchemaFormRendererProps {
  schema: SchemaProperty;
  value: Record<string, unknown>;
  onChange: (value: Record<string, unknown>) => void;
  readOnly?: boolean;
  indentLevel?: number;
}

export default function SchemaFormRenderer({
  schema,
  value,
  onChange,
  readOnly = false,
  indentLevel = 0,
}: SchemaFormRendererProps) {
  if (schema.type === 'object' && schema.properties) {
    const requiredKeys = new Set(schema.required || []);
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        {Object.entries(schema.properties).map(([key, prop]) => {
          const childValue = (value as Record<string, unknown>)?.[key];
          const isRequired = requiredKeys.has(key);
          return (
            <div key={key} style={{ paddingLeft: indentLevel > 0 ? '1rem' : 0 }}>
              <label className="label" style={{ marginBottom: '0.25rem' }}>
                {formatLabel(key)}
                {isRequired && <span style={{ color: 'var(--red)' }}> *</span>}
                {prop.description && (
                  <span style={{ fontWeight: 400, color: 'var(--muted)', fontSize: '0.75rem', marginLeft: '0.5rem' }}>
                    — {prop.description}
                  </span>
                )}
              </label>
              <SchemaFormRenderer
                schema={prop}
                value={childValue as Record<string, unknown>}
                onChange={(newVal) => {
                  onChange({ ...value, [key]: newVal });
                }}
                readOnly={readOnly}
                indentLevel={indentLevel + 1}
              />
            </div>
          );
        })}
      </div>
    );
  }

  if (schema.type === 'array' && schema.items) {
    const arr = Array.isArray(value) ? value : [];
    if (schema.items.type === 'object' && schema.items.properties) {
      const itemRequired = new Set(schema.items.required || []);
      return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.85rem', color: 'var(--muted)' }}>{arr.length} item(s)</span>
            {!readOnly && (
              <button
                className="btn btn-secondary"
                style={{ padding: '0.2rem 0.6rem', fontSize: '0.75rem' }}
                onClick={() => {
                  const newItem: Record<string, unknown> = {};
                  for (const [k, p] of Object.entries(schema.items.properties!)) {
                    if (p.type === 'number' || p.type === 'integer') newItem[k] = 0;
                    else if (p.type === 'array') newItem[k] = [];
                    else newItem[k] = '';
                  }
                  onChange([...arr, newItem] as unknown as Record<string, unknown>);
                }}
              >
                + Add Item
              </button>
            )}
          </div>
          {arr.map((item, idx) => (
            <div
              key={idx}
              className="panel"
              style={{ padding: '0.75rem', position: 'relative' }}
            >
              {!readOnly && (
                <button
                  onClick={() => {
                    const newArr = [...arr];
                    newArr.splice(idx, 1);
                    onChange(newArr as unknown as Record<string, unknown>);
                  }}
                  style={{
                    position: 'absolute',
                    top: '0.5rem',
                    right: '0.5rem',
                    background: 'none',
                    border: '1px solid var(--red)',
                    color: 'var(--red)',
                    borderRadius: '3px',
                    padding: '0.1rem 0.4rem',
                    fontSize: '0.7rem',
                    cursor: 'pointer',
                  }}
                >
                  Remove
                </button>
              )}
              <div style={{ fontSize: '0.8rem', color: 'var(--accent)', marginBottom: '0.5rem', fontWeight: 600 }}>
                Item {idx + 1}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {Object.entries(schema.items.properties).map(([key, prop]) => {
                  const childValue = (item as Record<string, unknown>)?.[key];
                  const isReq = itemRequired.has(key);
                  return (
                    <div key={key} style={{ paddingLeft: indentLevel > 0 ? '0.5rem' : 0 }}>
                      <label className="label" style={{ marginBottom: '0.25rem' }}>
                        {formatLabel(key)}
                        {isReq && <span style={{ color: 'var(--red)' }}> *</span>}
                      </label>
                      <SchemaFormRenderer
                        schema={prop}
                        value={childValue as Record<string, unknown>}
                        onChange={(newVal) => {
                          const newArr = [...arr];
                          newArr[idx] = { ...(newArr[idx] as Record<string, unknown>), [key]: newVal };
                          onChange(newArr as unknown as Record<string, unknown>);
                        }}
                        readOnly={readOnly}
                        indentLevel={indentLevel + 1}
                      />
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
          {arr.length === 0 && (
            <p style={{ color: 'var(--muted)', textAlign: 'center', fontSize: '0.85rem' }}>No items yet.</p>
          )}
        </div>
      );
    }
    const itemType = schema.items.type;
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
        {arr.map((item, idx) => (
          <input
            key={idx}
            className="input-field"
            type={itemType === 'number' || itemType === 'integer' ? 'number' : 'text'}
            value={String(item ?? '')}
            readOnly={readOnly}
            onChange={(e) => {
              const newVal = itemType === 'number' || itemType === 'integer'
                ? parseFloat(e.target.value) || 0
                : e.target.value;
              const newArr = [...arr];
              newArr[idx] = newVal;
              onChange(newArr as unknown as Record<string, unknown>);
            }}
            style={{ padding: '0.4rem 0.6rem', fontSize: '0.85rem' }}
          />
        ))}
        {!readOnly && (
          <button
            className="btn btn-secondary"
            style={{ padding: '0.2rem 0.6rem', fontSize: '0.75rem', alignSelf: 'flex-start' }}
            onClick={() => {
              const defaultVal = itemType === 'number' || itemType === 'integer' ? 0 : '';
              onChange([...arr, defaultVal] as unknown as Record<string, unknown>);
            }}
          >
            + Add
          </button>
        )}
      </div>
    );
  }

  if (schema.enum && schema.enum.length > 0) {
    return (
      <select
        className="input-field"
        value={String(value ?? '')}
        disabled={readOnly}
        onChange={(e) => onChange(e.target.value as unknown as Record<string, unknown>)}
      >
        <option value="">Select...</option>
        {schema.enum.map((opt) => (
          <option key={opt} value={opt}>{opt}</option>
        ))}
      </select>
    );
  }

  if (schema.type === 'number' || schema.type === 'integer') {
    return (
      <input
        className="input-field"
        type="number"
        value={value as number ?? 0}
        readOnly={readOnly}
        onChange={(e) => {
          const val = schema.type === 'integer'
            ? parseInt(e.target.value) || 0
            : parseFloat(e.target.value) || 0;
          onChange(val as unknown as Record<string, unknown>);
        }}
        min={schema.minimum}
        max={schema.maximum}
        style={{ padding: '0.4rem 0.6rem', fontSize: '0.85rem' }}
      />
    );
  }

  if (schema.type === 'boolean') {
    return (
      <input
        type="checkbox"
        checked={Boolean(value)}
        disabled={readOnly}
        onChange={(e) => onChange(e.target.checked as unknown as Record<string, unknown>)}
        style={{ width: '18px', height: '18px', cursor: readOnly ? 'default' : 'pointer' }}
      />
    );
  }

  return (
    <textarea
      className="input-field"
      value={String(value ?? '')}
      readOnly={readOnly}
      onChange={(e) => onChange(e.target.value as unknown as Record<string, unknown>)}
      rows={2}
      style={{ padding: '0.4rem 0.6rem', fontSize: '0.85rem', resize: 'vertical' }}
    />
  );
}

function formatLabel(key: string): string {
  return key
    .replace(/_/g, ' ')
    .replace(/([A-Z])/g, ' $1')
    .replace(/^./, (s) => s.toUpperCase())
    .trim();
}
