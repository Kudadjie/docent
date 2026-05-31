'use client';

import { useState } from 'react';
import { Check, X, Pencil } from 'lucide-react';

export default function ConfigRow({
  label,
  description,
  value,
  placeholder,
  onSave,
}: {
  label: string;
  description: string;
  value: string | null;
  placeholder: string;
  onSave: (v: string) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');
  const [saving, setSaving] = useState(false);

  function startEdit() {
    setDraft(value ?? '');
    setEditing(true);
  }

  async function save() {
    setSaving(true);
    await onSave(draft.trim());
    setSaving(false);
    setEditing(false);
  }

  function cancel() {
    setEditing(false);
    setDraft('');
  }

  return (
    <div style={{
      padding: '16px 0',
      borderBottom: '1px solid var(--border)',
      display: 'grid',
      gridTemplateColumns: '1fr auto',
      gap: '12px 24px',
      alignItems: 'start',
    }}>
      <div>
        <div style={{ fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 500, color: 'var(--fg1)', marginBottom: 3 }}>
          {label}
        </div>
        <div style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg4)', lineHeight: 1.5 }}>
          {description}
        </div>
        <div style={{ marginTop: 8 }}>
          {editing ? (
            <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              <input
                autoFocus
                value={draft}
                onChange={e => setDraft(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') save(); if (e.key === 'Escape') cancel(); }}
                placeholder={placeholder}
                style={{
                  fontFamily: 'var(--mono)', fontSize: 12,
                  padding: '5px 10px', borderRadius: 6,
                  border: '1px solid #18E299',
                  background: 'var(--bg-card)', color: 'var(--fg1)',
                  outline: 'none', width: 320,
                }}
              />
              <button
                onClick={save}
                disabled={saving}
                aria-label="Save"
                style={{
                  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                  width: 28, height: 28, borderRadius: 6, border: 'none',
                  background: 'rgba(24,226,153,0.15)', color: '#0fa76e',
                  cursor: saving ? 'default' : 'pointer', opacity: saving ? 0.6 : 1,
                }}
              >
                <Check size={14} strokeWidth={2} />
              </button>
              <button
                onClick={cancel}
                aria-label="Cancel"
                style={{
                  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                  width: 28, height: 28, borderRadius: 6, border: 'none',
                  background: 'var(--gray100)', color: 'var(--fg3)',
                  cursor: 'pointer',
                }}
              >
                <X size={14} strokeWidth={2} />
              </button>
            </div>
          ) : (
            <span style={{
              fontFamily: 'var(--mono)', fontSize: 12,
              color: value ? 'var(--fg2)' : 'var(--fg4)',
              fontStyle: value ? 'normal' : 'italic',
            }}>
              {value ?? 'not set'}
            </span>
          )}
        </div>
      </div>

      {!editing && (
        <button
          onClick={startEdit}
          aria-label={`Edit ${label}`}
          style={{
            display: 'inline-flex', alignItems: 'center', gap: 5,
            padding: '5px 10px', borderRadius: 6,
            border: '1px solid var(--border-md)',
            background: 'transparent', color: 'var(--fg3)',
            fontFamily: 'var(--sans)', fontSize: 12,
            cursor: 'pointer', whiteSpace: 'nowrap', marginTop: 2,
          }}
        >
          <Pencil size={12} strokeWidth={1.5} />
          Edit
        </button>
      )}
    </div>
  );
}
