'use client';

import { useState } from 'react';
import { Check, X, Key, EyeOff } from 'lucide-react';

export default function SecretKeyRow({
  label,
  description,
  masked,
  placeholder,
  onSave,
}: {
  label: string;
  description: string;
  masked: string | null;
  placeholder: string;
  onSave: (v: string) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    await onSave(draft.trim());
    setSaving(false);
    setEditing(false);
    setDraft('');
  }

  function cancel() {
    setEditing(false);
    setDraft('');
  }

  const isSet = !!masked;

  return (
    <div style={{
      padding: '14px 0',
      borderBottom: '1px solid var(--border)',
      display: 'grid',
      gridTemplateColumns: '1fr auto',
      gap: '8px 24px',
      alignItems: 'start',
    }}>
      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 2 }}>
          <span style={{ fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 500, color: 'var(--fg1)' }}>
            {label}
          </span>
          {isSet && (
            <span style={{
              display: 'inline-flex', alignItems: 'center', gap: 3,
              fontFamily: 'var(--mono)', fontSize: 9, fontWeight: 500,
              padding: '1px 6px', borderRadius: 9999,
              background: 'rgba(24,226,153,0.15)', color: '#0fa76e',
              textTransform: 'uppercase', letterSpacing: '0.3px',
            }}>
              set
            </span>
          )}
        </div>
        <div style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg4)', lineHeight: 1.5 }}>
          {description}
        </div>
        <div style={{ marginTop: 6 }}>
          {editing ? (
            <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              <input
                autoFocus
                type="password"
                value={draft}
                onChange={e => setDraft(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') save(); if (e.key === 'Escape') cancel(); }}
                placeholder={isSet ? 'Enter new key to replace…' : placeholder}
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
                disabled={saving || !draft.trim()}
                aria-label="Save"
                style={{
                  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                  width: 28, height: 28, borderRadius: 6, border: 'none',
                  background: 'rgba(24,226,153,0.15)', color: '#0fa76e',
                  cursor: saving || !draft.trim() ? 'default' : 'pointer',
                  opacity: saving || !draft.trim() ? 0.5 : 1,
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
              display: 'inline-flex', alignItems: 'center', gap: 5,
              fontFamily: 'var(--mono)', fontSize: 12,
              color: isSet ? 'var(--fg2)' : 'var(--fg4)',
              fontStyle: isSet ? 'normal' : 'italic',
            }}>
              {isSet ? (
                <>
                  <EyeOff size={11} strokeWidth={1.5} style={{ color: 'var(--fg4)' }} />
                  {masked}
                </>
              ) : 'not set'}
            </span>
          )}
        </div>
      </div>

      {!editing && (
        <button
          onClick={() => setEditing(true)}
          aria-label={`${isSet ? 'Replace' : 'Set'} ${label} key`}
          style={{
            display: 'inline-flex', alignItems: 'center', gap: 5,
            padding: '5px 10px', borderRadius: 6,
            border: '1px solid var(--border-md)',
            background: 'transparent', color: 'var(--fg3)',
            fontFamily: 'var(--sans)', fontSize: 12,
            cursor: 'pointer', whiteSpace: 'nowrap', marginTop: 2,
          }}
        >
          <Key size={11} strokeWidth={1.5} />
          {isSet ? 'Replace' : 'Set key'}
        </button>
      )}
    </div>
  );
}
