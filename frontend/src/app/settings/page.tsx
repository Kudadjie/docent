'use client';

import { useState, useEffect } from 'react';
import { Settings, Trash2, Pencil, Check, X, FolderOpen, BookOpen } from 'lucide-react';
import Sidebar from '@/components/Sidebar';
import Toast, { type ToastData } from '@/components/Toast';

interface ReadingConfig {
  database_dir: string | null;
  queue_collection: string;
}

interface ConfigData {
  reading: ReadingConfig;
}

const READING_FIELDS: {
  key: keyof ReadingConfig;
  label: string;
  description: string;
  placeholder: string;
}[] = [
  {
    key: 'database_dir',
    label: 'Database directory',
    description: 'Local folder where your PDFs are stored. Docent counts PDFs here and uses this path for paper scanning.',
    placeholder: '~/Documents/Papers',
  },
  {
    key: 'queue_collection',
    label: 'Mendeley collection',
    description: 'Name of the Mendeley collection to sync from. Must exactly match the collection name in the Mendeley desktop app.',
    placeholder: 'Docent-Queue',
  },
];

function ConfigRow({
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
                  background: 'var(--bg)', color: 'var(--fg1)',
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

export default function SettingsPage() {
  const [dark, setDark] = useState(false);
  const [config, setConfig] = useState<ConfigData | null>(null);
  const [toast, setToast] = useState<ToastData | null>(null);
  const [confirmClear, setConfirmClear] = useState(false);
  const [clearing, setClearing] = useState(false);

  useEffect(() => {
    setDark(localStorage.getItem('docent:dark') === 'true');
  }, []);

  useEffect(() => {
    fetch('/api/config')
      .then(r => r.json())
      .then((d: ConfigData) => setConfig(d))
      .catch(() => {});
  }, []);

  async function handleSaveReading(key: keyof ReadingConfig, value: string) {
    try {
      const res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ section: 'reading', key, value }),
      });
      const body = await res.json() as { ok: boolean; reading?: ReadingConfig; error?: string };
      if (!res.ok || !body.ok) {
        const clean = (body.error ?? 'Unknown error').replace(/\x1b\[[0-9;]*m/g, '').trim();
        setToast({ type: 'error', message: `Could not save: ${clean.slice(0, 120)}` });
      } else {
        if (body.reading) setConfig(c => c ? { ...c, reading: body.reading! } : c);
        setToast({ type: 'success', message: `Saved reading.${key}.` });
      }
    } catch {
      setToast({ type: 'error', message: 'Network error.' });
    }
  }

  async function handleClearQueue() {
    setClearing(true);
    try {
      const res = await fetch('/api/actions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'queue-clear' }),
      });
      const body = await res.json().catch(() => ({})) as Record<string, string>;
      if (!res.ok) {
        const clean = (body.error ?? body.stderr ?? 'Unknown error').replace(/\x1b\[[0-9;]*m/g, '').trim();
        setToast({ type: 'error', message: `Clear failed: ${clean.slice(0, 120)}` });
      } else {
        setToast({ type: 'success', message: 'Reading queue cleared.' });
      }
    } catch {
      setToast({ type: 'error', message: 'Network error.' });
    } finally {
      setClearing(false);
      setConfirmClear(false);
    }
  }

  const rc = config?.reading;

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden', background: 'var(--bg)' }}>
      <Sidebar active="settings" queueCount={0} dark={dark} />

      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, overflow: 'auto' }}>
        {/* Header */}
        <div style={{
          padding: '28px 32px 24px',
          borderBottom: '1px solid var(--border)',
          flexShrink: 0,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
            <Settings size={16} strokeWidth={1.5} color="#0fa76e" />
            <h1 style={{
              fontFamily: 'var(--sans)', fontSize: 18, fontWeight: 600,
              letterSpacing: '-0.3px', color: 'var(--fg1)', margin: 0,
            }}>
              Settings
            </h1>
          </div>
          <p style={{ fontFamily: 'var(--sans)', fontSize: 13, color: 'var(--fg3)', margin: 0 }}>
            Manage your Docent preferences and data.
          </p>
        </div>

        {/* Content */}
        <div style={{ padding: '32px', maxWidth: 640 }}>

          {/* Reading config */}
          <section style={{ marginBottom: 48 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <BookOpen size={14} strokeWidth={1.5} color="#0fa76e" />
              <h2 style={{
                fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 600,
                color: 'var(--fg2)', letterSpacing: '0.2px', margin: 0,
              }}>
                Reading
              </h2>
            </div>
            <p style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg4)', marginBottom: 16 }}>
              Controls how Docent syncs your reading queue with Mendeley and your local paper database.
            </p>

            <div style={{ borderTop: '1px solid var(--border)' }}>
              {READING_FIELDS.map(f => (
                <ConfigRow
                  key={f.key}
                  label={f.label}
                  description={f.description}
                  value={rc ? (rc[f.key] as string | null) : null}
                  placeholder={f.placeholder}
                  onSave={v => handleSaveReading(f.key, v)}
                />
              ))}
            </div>
          </section>

          {/* Danger zone */}
          <section>
            <h2 style={{
              fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 600,
              color: 'var(--fg4)', letterSpacing: '0.5px', textTransform: 'uppercase',
              margin: '0 0 16px',
            }}>
              Danger Zone
            </h2>

            <div style={{
              border: '1px solid rgba(212,86,86,0.3)',
              borderRadius: 10,
              padding: '20px 24px',
              background: 'rgba(212,86,86,0.03)',
            }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 24 }}>
                <div>
                  <div style={{
                    fontFamily: 'var(--sans)', fontSize: 14, fontWeight: 500,
                    color: 'var(--fg1)', marginBottom: 4,
                  }}>
                    Clear reading queue
                  </div>
                  <div style={{ fontFamily: 'var(--sans)', fontSize: 12, color: 'var(--fg3)', lineHeight: 1.5 }}>
                    Removes all entries from the local queue. Your Mendeley library is not affected —
                    you can restore the queue by running{' '}
                    <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--fg2)' }}>
                      Sync Mendeley
                    </span>{' '}
                    on the Reading page.
                  </div>
                </div>

                {confirmClear ? (
                  <div style={{ display: 'flex', gap: 8, flexShrink: 0, alignItems: 'center' }}>
                    <button
                      onClick={handleClearQueue}
                      disabled={clearing}
                      style={{
                        padding: '6px 14px', borderRadius: 7, border: 'none',
                        background: '#D45656', color: '#fff',
                        fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 600,
                        cursor: clearing ? 'default' : 'pointer',
                        opacity: clearing ? 0.6 : 1, whiteSpace: 'nowrap',
                      }}
                    >
                      {clearing ? 'Clearing…' : 'Yes, clear'}
                    </button>
                    <button
                      onClick={() => setConfirmClear(false)}
                      style={{
                        padding: '6px 12px', borderRadius: 7,
                        border: '1px solid var(--border-md)',
                        background: 'transparent', color: 'var(--fg3)',
                        fontFamily: 'var(--sans)', fontSize: 13, cursor: 'pointer',
                      }}
                    >
                      Cancel
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => setConfirmClear(true)}
                    style={{
                      display: 'inline-flex', alignItems: 'center', gap: 6,
                      padding: '6px 14px', borderRadius: 7,
                      border: '1px solid rgba(212,86,86,0.4)',
                      background: 'transparent', color: '#D45656',
                      fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 500,
                      cursor: 'pointer', flexShrink: 0,
                    }}
                  >
                    <Trash2 size={14} strokeWidth={1.5} />
                    Clear queue
                  </button>
                )}
              </div>
            </div>
          </section>
        </div>
      </main>

      {toast && <Toast toast={toast} onDismiss={() => setToast(null)} />}
    </div>
  );
}
