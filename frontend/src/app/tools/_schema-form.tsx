'use client';

// Generic JSON-Schema → form renderer for the Tools page.
// Takes a Pydantic-generated JSON schema and renders one input per property.
// No per-tool knowledge — a new plugin's action form is generated from here.

const BRAND = '#18E299';

// ── Schema normalization ─────────────────────────────────────────────────────

export type FieldKind = 'string' | 'integer' | 'number' | 'boolean' | 'enum' | 'string_array' | 'json';

export interface ResolvedField {
  name: string;
  label: string;
  description?: string;
  kind: FieldKind;
  enumValues?: string[];
  nullable: boolean;
  required: boolean;
  default: unknown;
}

interface RawProp {
  type?: string;
  title?: string;
  description?: string;
  default?: unknown;
  enum?: string[];
  anyOf?: RawProp[];
  items?: RawProp;
}

interface JsonSchema {
  properties?: Record<string, RawProp>;
  required?: string[];
}

function humanize(name: string): string {
  return name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

/** Collapse `anyOf: [T, null]` to T, flag nullable, and classify the field kind. */
export function resolveField(name: string, prop: RawProp, requiredSet: Set<string>): ResolvedField {
  let effective: RawProp = prop;
  let nullable = false;

  if (prop.anyOf && prop.anyOf.length > 0) {
    const nonNull = prop.anyOf.filter(b => b.type !== 'null');
    nullable = nonNull.length !== prop.anyOf.length;
    effective = nonNull[0] ?? {};
  }

  const enumValues = effective.enum ?? prop.enum;
  let kind: FieldKind;
  if (enumValues) kind = 'enum';
  else if (effective.type === 'integer') kind = 'integer';
  else if (effective.type === 'number') kind = 'number';
  else if (effective.type === 'boolean') kind = 'boolean';
  else if (effective.type === 'array' && effective.items?.type === 'string') kind = 'string_array';
  else if (effective.type === 'string') kind = 'string';
  else kind = 'json';

  return {
    name,
    label: prop.title ?? humanize(name),
    description: prop.description,
    kind,
    enumValues,
    nullable,
    required: requiredSet.has(name),
    default: prop.default,
  };
}

export function resolveFields(schema: JsonSchema): ResolvedField[] {
  const props = schema.properties ?? {};
  const requiredSet = new Set(schema.required ?? []);
  return Object.entries(props).map(([name, prop]) => resolveField(name, prop, requiredSet));
}

/** Build the initial form-value map from each field's default. */
export function initialValues(fields: ResolvedField[]): Record<string, unknown> {
  const v: Record<string, unknown> = {};
  for (const f of fields) {
    switch (f.kind) {
      case 'boolean': v[f.name] = f.default ?? false; break;
      case 'string_array': v[f.name] = Array.isArray(f.default) ? f.default : []; break;
      case 'integer': case 'number': v[f.name] = f.default != null ? String(f.default) : ''; break;
      case 'json': v[f.name] = f.default !== undefined ? JSON.stringify(f.default) : ''; break;
      default: v[f.name] = f.default != null ? String(f.default) : '';
    }
  }
  return v;
}

/** True when every required field has a usable value. */
export function isComplete(fields: ResolvedField[], values: Record<string, unknown>): boolean {
  return fields.every(f => {
    if (!f.required) return true;
    const val = values[f.name];
    if (f.kind === 'boolean') return true;
    if (f.kind === 'string_array') return Array.isArray(val) && val.length > 0;
    return val != null && String(val).trim() !== '';
  });
}

/**
 * Convert form values into the JSON payload sent to the action. Optional fields
 * left empty are omitted so the action's own Pydantic defaults apply. Throws on
 * malformed JSON in a json-kind field (caller surfaces the message).
 */
export function buildPayload(fields: ResolvedField[], values: Record<string, unknown>): Record<string, unknown> {
  const payload: Record<string, unknown> = {};
  for (const f of fields) {
    const val = values[f.name];
    switch (f.kind) {
      case 'boolean':
        payload[f.name] = !!val;
        break;
      case 'integer': case 'number': {
        const s = String(val ?? '').trim();
        if (s !== '') payload[f.name] = Number(s);
        break;
      }
      case 'string_array':
        if (Array.isArray(val) && val.length > 0) payload[f.name] = val;
        break;
      case 'json': {
        const s = String(val ?? '').trim();
        if (s !== '') {
          try { payload[f.name] = JSON.parse(s); }
          catch { throw new Error(`Field "${f.label}" is not valid JSON.`); }
        }
        break;
      }
      default: {
        const s = String(val ?? '').trim();
        if (s !== '') payload[f.name] = s;
      }
    }
  }
  return payload;
}

// ── Field widgets ────────────────────────────────────────────────────────────

const inputStyle: React.CSSProperties = {
  width: '100%', boxSizing: 'border-box', padding: '8px 11px',
  border: '1px solid var(--border-md)', borderRadius: 8,
  fontFamily: 'var(--sans)', fontSize: 13, color: 'var(--fg1)',
  background: 'var(--bg)', outline: 'none',
};

function Toggle({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <button type="button" onClick={() => onChange(!checked)} style={{
      width: 34, height: 20, borderRadius: 9999, border: 'none',
      background: checked ? BRAND : 'var(--gray200)', position: 'relative',
      cursor: 'pointer', padding: 0, transition: 'background 0.15s', flexShrink: 0,
    }}>
      <span style={{
        position: 'absolute', top: 2, left: checked ? 16 : 2,
        width: 16, height: 16, borderRadius: '50%', background: '#fff',
        boxShadow: '0 1px 2px rgba(0,0,0,0.2)', transition: 'left 0.15s',
      }} />
    </button>
  );
}

function FieldRow({ field, value, onChange }: {
  field: ResolvedField; value: unknown; onChange: (v: unknown) => void;
}) {
  const labelEl = (
    <label style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 5, fontFamily: 'var(--sans)', fontSize: 12, fontWeight: 500, color: 'var(--fg2)' }}>
      {field.label}
      {field.required && <span style={{ color: '#D45656', fontSize: 11 }}>*</span>}
      <span style={{ fontFamily: 'var(--mono)', fontSize: 9.5, color: 'var(--fg4)', fontWeight: 400, letterSpacing: '0.3px' }}>
        {field.kind === 'string_array' ? 'list' : field.kind}{field.nullable ? ' · optional' : ''}
      </span>
    </label>
  );

  let control: React.ReactNode;
  switch (field.kind) {
    case 'boolean':
      control = (
        <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
          <Toggle checked={!!value} onChange={onChange} />
          <span style={{ fontFamily: 'var(--sans)', fontSize: 12.5, color: 'var(--fg3)' }}>{value ? 'on' : 'off'}</span>
        </div>
      );
      break;
    case 'enum':
      control = (
        <select value={String(value ?? '')} onChange={e => onChange(e.target.value)} style={{ ...inputStyle, fontFamily: 'var(--mono)', fontSize: 12.5, cursor: 'pointer' }}>
          {field.nullable && <option value="">— unset —</option>}
          {field.enumValues!.map(opt => <option key={opt} value={opt}>{opt}</option>)}
        </select>
      );
      break;
    case 'string_array': {
      const arr = Array.isArray(value) ? value as string[] : [];
      control = (
        <textarea
          value={arr.join('\n')}
          onChange={e => onChange(e.target.value.split('\n').map(s => s.trim()).filter(Boolean))}
          placeholder="One item per line"
          rows={3}
          style={{ ...inputStyle, fontFamily: 'var(--mono)', fontSize: 12, resize: 'vertical' }}
        />
      );
      break;
    }
    case 'integer': case 'number':
      control = (
        <input type="number" value={String(value ?? '')} onChange={e => onChange(e.target.value)}
          step={field.kind === 'integer' ? 1 : 'any'}
          style={{ ...inputStyle, fontFamily: 'var(--mono)', width: 160 }} />
      );
      break;
    case 'json':
      control = (
        <textarea value={String(value ?? '')} onChange={e => onChange(e.target.value)}
          placeholder='{ }' rows={3}
          style={{ ...inputStyle, fontFamily: 'var(--mono)', fontSize: 12, resize: 'vertical' }} />
      );
      break;
    default:
      control = (
        <input type="text" value={String(value ?? '')} onChange={e => onChange(e.target.value)}
          style={inputStyle} />
      );
  }

  return (
    <div>
      {labelEl}
      {control}
      {field.description && (
        <p style={{ margin: '5px 0 0', fontFamily: 'var(--sans)', fontSize: 11, color: 'var(--fg4)', lineHeight: 1.5 }}>
          {field.description.length > 220 ? field.description.slice(0, 220).trimEnd() + '…' : field.description}
        </p>
      )}
    </div>
  );
}

// ── Form ─────────────────────────────────────────────────────────────────────

export function SchemaForm({ fields, values, onChange }: {
  fields: ResolvedField[];
  values: Record<string, unknown>;
  onChange: (name: string, v: unknown) => void;
}) {
  if (fields.length === 0) {
    return <p style={{ fontFamily: 'var(--sans)', fontSize: 13, color: 'var(--fg4)' }}>This action takes no inputs — just run it.</p>;
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {fields.map(f => (
        <FieldRow key={f.name} field={f} value={values[f.name]} onChange={v => onChange(f.name, v)} />
      ))}
    </div>
  );
}
